"""Turn catalog rules into SQL and collect failing rows."""

from __future__ import annotations

import duckdb

from clinic_dq.catalog import category_for
from clinic_dq.config import (
    AcceptedRule,
    Config,
    DomainRule,
    ForeignKeyRule,
    RangeRule,
    RequiredRule,
    RowCountRule,
    UniqueRule,
)
from clinic_dq.errors import DQError
from clinic_dq.models import CheckResult, FailedRow


def run_checks(connection: duckdb.DuckDBPyConnection, config: Config) -> list[CheckResult]:
    results: list[CheckResult] = []
    for rule in config.row_counts:
        results.append(_row_count(connection, rule))
    for rule in config.required:
        results.append(_query_check(connection, config, _required_spec(rule)))
    for rule in config.uniqueness:
        results.append(_query_check(connection, config, _unique_spec(rule)))
    for rule in config.foreign_keys:
        results.append(_query_check(connection, config, _foreign_key_spec(rule)))
    for rule in config.accepted:
        results.append(_query_check(connection, config, _accepted_spec(rule)))
    for rule in config.ranges:
        results.append(_query_check(connection, config, _range_spec(rule)))
    for rule in config.domain:
        results.append(_query_check(connection, config, _domain_spec(rule)))
    return results


def _row_count(connection: duckdb.DuckDBPyConnection, rule: RowCountRule) -> CheckResult:
    table = _ident(rule.table)
    count = connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()
    observed = int(count[0]) if count else 0
    passed = observed >= rule.min_rows
    sample = () if passed else (FailedRow(rule.table, f"rows={observed}"),)
    return CheckResult(
        check_id=rule.id,
        category=category_for(rule.id),
        severity=rule.severity,
        table=rule.table,
        description=rule.description,
        passed=passed,
        observed=str(observed),
        expected=f">= {rule.min_rows}",
        failed_count=0 if passed else rule.min_rows - observed,
        sample=sample,
    )


def _query_check(
    connection: duckdb.DuckDBPyConnection,
    config: Config,
    spec: _QuerySpec,
) -> CheckResult:
    try:
        count_row = connection.execute(f"SELECT COUNT(*) FROM ({spec.sql}) AS failures").fetchone()
        sample_rows = connection.execute(
            f"""
            SELECT entity_key, detail
            FROM ({spec.sql}) AS failures
            ORDER BY entity_key, detail
            LIMIT {config.sample_limit}
            """
        ).fetchall()
    except duckdb.Error as exc:
        raise DQError(f"Check {spec.check_id} failed to execute: {exc}") from exc
    failed_count = int(count_row[0]) if count_row else 0
    sample = tuple(_failed_row(row) for row in sample_rows)
    return CheckResult(
        check_id=spec.check_id,
        category=category_for(spec.check_id),
        severity=spec.severity,
        table=spec.table,
        description=spec.description,
        passed=failed_count == 0,
        observed=f"{failed_count} failing",
        expected="0 failing",
        failed_count=failed_count,
        sample=sample,
    )


class _QuerySpec:
    def __init__(
        self, check_id: str, severity: str, table: str, description: str, sql: str
    ) -> None:
        self.check_id = check_id
        self.severity = severity
        self.table = table
        self.description = description
        self.sql = sql


def _required_spec(rule: RequiredRule) -> _QuerySpec:
    table = _ident(rule.table)
    key = _ident(rule.key)
    parts = []
    for column in rule.columns:
        col = _ident(column)
        parts.append(
            f"""
            SELECT COALESCE(CAST({key} AS VARCHAR), '(null)') AS entity_key,
                   '{col}' AS detail
            FROM {table}
            WHERE {col} IS NULL
            """.strip()
        )
    return _QuerySpec(
        rule.id, rule.severity, rule.table, rule.description, "\nUNION ALL\n".join(parts)
    )


def _unique_spec(rule: UniqueRule) -> _QuerySpec:
    table = _ident(rule.table)
    columns = [_ident(column) for column in rule.columns]
    entity_key = " || '|' || ".join(
        f"COALESCE(CAST({column} AS VARCHAR), '(null)')" for column in columns
    )
    sql = f"""
        SELECT {entity_key} AS entity_key,
               'count=' || CAST(COUNT(*) AS VARCHAR) AS detail
        FROM {table}
        GROUP BY {", ".join(columns)}
        HAVING COUNT(*) > 1
    """
    return _QuerySpec(rule.id, rule.severity, rule.table, rule.description, sql)


def _foreign_key_spec(rule: ForeignKeyRule) -> _QuerySpec:
    child_key = _ident(rule.child_key)
    child_column = _ident(rule.child_column)
    parent_column = _ident(rule.parent_column)
    sql = f"""
        SELECT COALESCE(CAST(child.{child_key} AS VARCHAR), '(null)') AS entity_key,
               COALESCE(CAST(child.{child_column} AS VARCHAR), '(null)') AS detail
        FROM {_ident(rule.child_table)} AS child
        LEFT JOIN {_ident(rule.parent_table)} AS parent
          ON child.{child_column} = parent.{parent_column}
        WHERE child.{child_column} IS NOT NULL
          AND parent.{parent_column} IS NULL
    """
    return _QuerySpec(rule.id, rule.severity, rule.child_table, rule.description, sql)


def _accepted_spec(rule: AcceptedRule) -> _QuerySpec:
    column = _ident(rule.column)
    key = _ident(rule.key)
    allowed = ", ".join(_string_literal(value) for value in rule.values)
    sql = f"""
        SELECT COALESCE(CAST({key} AS VARCHAR), '(null)') AS entity_key,
               COALESCE(CAST({column} AS VARCHAR), '(null)') AS detail
        FROM {_ident(rule.table)}
        WHERE {column} IS NOT NULL
          AND {column} NOT IN ({allowed})
    """
    return _QuerySpec(rule.id, rule.severity, rule.table, rule.description, sql)


def _range_spec(rule: RangeRule) -> _QuerySpec:
    column = _ident(rule.column)
    predicates: list[str] = []
    if rule.min_value is not None:
        predicates.append(f"{column} < {_number_literal(rule.min_value)}")
    if rule.max_value is not None:
        predicates.append(f"{column} > {_number_literal(rule.max_value)}")
    sql = f"""
        SELECT COALESCE(CAST({_ident(rule.key)} AS VARCHAR), '(null)') AS entity_key,
               CAST({column} AS VARCHAR) AS detail
        FROM {_ident(rule.table)}
        WHERE {column} IS NOT NULL
          AND ({" OR ".join(predicates)})
    """
    return _QuerySpec(rule.id, rule.severity, rule.table, rule.description, sql)


def _domain_spec(rule: DomainRule) -> _QuerySpec:
    sql = rule.sql_path.read_text(encoding="utf-8").strip()
    if sql.endswith(";"):
        sql = sql[:-1].strip()
    if not sql or ";" in sql:
        raise DQError(f"Check {rule.id} SQL must be one non-empty statement.")
    return _QuerySpec(rule.id, rule.severity, rule.table, rule.description, sql)


def _failed_row(row: tuple[object, object]) -> FailedRow:
    entity_key, detail = row
    return FailedRow(_cell(entity_key), _cell(detail))


def _cell(value: object) -> str:
    if value is None:
        return "(null)"
    return str(value)


def _ident(name: str) -> str:
    if not name.isidentifier() or not name.islower():
        raise DQError(f"Unsafe SQL identifier: {name!r}")
    return name


def _string_literal(value: str) -> str:
    if "'" in value or "\n" in value:
        raise DQError(f"Unsafe SQL string literal: {value!r}")
    return f"'{value}'"


def _number_literal(value: float) -> str:
    if value.is_integer():
        return str(int(value))
    return repr(value)
