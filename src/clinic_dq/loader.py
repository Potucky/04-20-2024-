"""Load the clinic extract into an in-memory DuckDB database."""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

import duckdb
import yaml

from clinic_dq.config import Config
from clinic_dq.errors import DQError

_DATASETS = frozenset({"clean", "defects"})
_FORBIDDEN_SQL = re.compile(r"\b(drop|truncate|alter|attach|copy|pragma|create)\b", re.IGNORECASE)
_TABLES = ("patients", "visits", "lab_results", "invoices")

_INSERTS = {
    "patients": """
        INSERT INTO patients
        SELECT
            patient_id::VARCHAR,
            name::VARCHAR,
            species::VARCHAR,
            breed::VARCHAR,
            date_of_birth::DATE,
            sex::VARCHAR,
            status::VARCHAR,
            owner_name::VARCHAR,
            created_at::DATE
        FROM read_csv(?, header = true, nullstr = '', all_varchar = true)
    """,
    "visits": """
        INSERT INTO visits
        SELECT
            visit_id::VARCHAR,
            patient_id::VARCHAR,
            visit_date::DATE,
            reason::VARCHAR,
            veterinarian::VARCHAR,
            status::VARCHAR,
            weight_kg::DOUBLE,
            temperature_c::DOUBLE
        FROM read_csv(?, header = true, nullstr = '', all_varchar = true)
    """,
    "lab_results": """
        INSERT INTO lab_results
        SELECT
            result_id::VARCHAR,
            visit_id::VARCHAR,
            patient_id::VARCHAR,
            test_code::VARCHAR,
            result_value::DOUBLE,
            unit::VARCHAR,
            abnormal_flag::VARCHAR,
            collected_at::DATE
        FROM read_csv(?, header = true, nullstr = '', all_varchar = true)
    """,
    "invoices": """
        INSERT INTO invoices
        SELECT
            invoice_id::VARCHAR,
            visit_id::VARCHAR,
            patient_id::VARCHAR,
            amount::DECIMAL(12, 2),
            tax_amount::DECIMAL(12, 2),
            currency::VARCHAR,
            status::VARCHAR,
            issued_at::DATE,
            paid_at::DATE
        FROM read_csv(?, header = true, nullstr = '', all_varchar = true)
    """,
}


@dataclass(frozen=True)
class Mutation:
    id: str
    description: str
    sql: str
    expect_failed_checks: tuple[str, ...]
    expect_in_sample: tuple[str, ...]


@dataclass
class LoadedDataset:
    connection: duckdb.DuckDBPyConnection
    dataset: str
    applied_mutations: tuple[str, ...]
    expected_failures: frozenset[str]
    mutations: tuple[Mutation, ...]


def load_seed(path: Path | str, known_checks: set[str]) -> tuple[Mutation, ...]:
    try:
        raw = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    except OSError as exc:
        raise DQError(f"Could not read defect seed: {exc}") from exc
    except yaml.YAMLError as exc:
        raise DQError(f"Could not parse defect seed: {exc}") from exc
    if not isinstance(raw, dict) or not isinstance(raw.get("mutations"), list):
        raise DQError("Defect seed must contain a mutations list.")
    mutations: list[Mutation] = []
    seen: set[str] = set()
    for index, item in enumerate(raw["mutations"], start=1):
        if not isinstance(item, dict):
            raise DQError(f"Mutation {index} must be a mapping.")
        mutation = _mutation(item, index, known_checks)
        if mutation.id in seen:
            raise DQError(f"Duplicate mutation id: {mutation.id}.")
        seen.add(mutation.id)
        mutations.append(mutation)
    if not mutations:
        raise DQError("Defect seed does not define any mutations.")
    return tuple(mutations)


def load_dataset(
    config: Config,
    dataset: str,
    mutations: set[str] | None = None,
) -> LoadedDataset:
    if dataset not in _DATASETS:
        raise DQError(f"Unknown dataset {dataset!r}. Choose clean or defects.")
    catalog = load_seed(config.seed_path, known_checks=set(config.check_ids()))
    if dataset == "clean":
        if mutations:
            raise DQError("Mutations apply only to the defects dataset.")
        selected: tuple[Mutation, ...] = ()
    else:
        selected = _select(catalog, mutations)

    connection = duckdb.connect(database=":memory:")
    try:
        _load_extract(connection, config)
        for mutation in selected:
            _apply(connection, mutation)
        _install_parameters(connection, config)
    except Exception:
        connection.close()
        raise
    expected = frozenset(
        check_id for mutation in selected for check_id in mutation.expect_failed_checks
    )
    return LoadedDataset(
        connection=connection,
        dataset=dataset,
        applied_mutations=tuple(mutation.id for mutation in selected),
        expected_failures=expected,
        mutations=selected,
    )


def _load_extract(connection: duckdb.DuckDBPyConnection, config: Config) -> None:
    schema_path = config.root / "sql" / "schema.sql"
    try:
        connection.execute(schema_path.read_text(encoding="utf-8"))
    except duckdb.Error as exc:
        raise DQError(f"Could not create staging tables: {exc}") from exc
    except OSError as exc:
        raise DQError(f"Could not read {schema_path}: {exc}") from exc
    for table in _TABLES:
        try:
            connection.execute(_INSERTS[table], [str(config.clean_files[table])])
        except duckdb.Error as exc:
            raise DQError(f"Could not load {table}: {exc}") from exc


def _apply(connection: duckdb.DuckDBPyConnection, mutation: Mutation) -> None:
    try:
        connection.execute(mutation.sql)
    except duckdb.Error as exc:
        raise DQError(f"Mutation {mutation.id} failed: {exc}") from exc


def _install_parameters(connection: duckdb.DuckDBPyConnection, config: Config) -> None:
    connection.execute(
        """
        CREATE OR REPLACE TEMP TABLE dq_params AS
        SELECT
            ?::DATE AS as_of_date,
            ?::DATE AS min_birth_date,
            ?::DOUBLE AS min_temp_c,
            ?::DOUBLE AS max_temp_c
        """,
        [config.as_of_date, config.min_birth_date, config.min_temp_c, config.max_temp_c],
    )
    connection.execute(
        """
        CREATE OR REPLACE TEMP TABLE dq_weight_bounds (
            species VARCHAR,
            min_kg DOUBLE,
            max_kg DOUBLE
        )
        """
    )
    connection.executemany(
        "INSERT INTO dq_weight_bounds VALUES (?, ?, ?)",
        list(config.weight_bounds),
    )
    connection.execute("CREATE OR REPLACE TEMP TABLE dq_temp_required_species (species VARCHAR)")
    connection.executemany(
        "INSERT INTO dq_temp_required_species VALUES (?)",
        [(species,) for species in config.temperature_required_species],
    )


def _select(catalog: tuple[Mutation, ...], mutations: set[str] | None) -> tuple[Mutation, ...]:
    if mutations is None:
        return catalog
    known = {mutation.id for mutation in catalog}
    unknown = sorted(set(mutations) - known)
    if unknown:
        raise DQError(f"Unknown mutation id(s): {', '.join(unknown)}.")
    return tuple(mutation for mutation in catalog if mutation.id in set(mutations))


def _mutation(item: dict[str, object], index: int, known_checks: set[str]) -> Mutation:
    label = f"mutations[{index}]"
    mutation_id = _text(item.get("id"), f"{label}.id")
    if not re.fullmatch(r"[a-z][a-z0-9_]*", mutation_id):
        raise DQError(f"{label}.id is not a safe mutation id: {mutation_id!r}.")
    description = _text(item.get("description"), f"{mutation_id}.description")
    sql = _statement(item.get("sql"), mutation_id)
    expected = tuple(
        _string_list(item.get("expect_failed_checks"), f"{mutation_id}.expect_failed_checks")
    )
    unknown = [check_id for check_id in expected if check_id not in known_checks]
    if unknown:
        raise DQError(f"Mutation {mutation_id} expects unknown checks: {', '.join(unknown)}.")
    sample_tokens = tuple(
        _string_list(item.get("expect_in_sample"), f"{mutation_id}.expect_in_sample")
    )
    return Mutation(mutation_id, description, sql, expected, sample_tokens)


def _statement(value: object, mutation_id: str) -> str:
    sql = _text(value, f"{mutation_id}.sql").strip()
    if sql.endswith(";"):
        sql = sql[:-1].strip()
    if not sql or ";" in sql:
        raise DQError(f"Mutation {mutation_id} SQL must be one statement.")
    if _FORBIDDEN_SQL.search(sql):
        raise DQError(f"Mutation {mutation_id} uses a statement the loader does not run.")
    if re.search(r"\bdq_", sql, re.IGNORECASE):
        raise DQError(f"Mutation {mutation_id} cannot reference dq_ parameter tables.")
    return sql


def _string_list(value: object, label: str) -> list[str]:
    if not isinstance(value, list) or not value:
        raise DQError(f"{label} must be a non-empty list.")
    return [_text(item, label) for item in value]


def _text(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise DQError(f"{label} must be a non-empty string.")
    return value.strip()
