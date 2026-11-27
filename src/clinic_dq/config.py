"""Load the YAML catalog and reject a config that cannot be executed safely."""

from __future__ import annotations

import math
import os
import re
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path

import yaml

from clinic_dq.catalog import category_for
from clinic_dq.errors import DQError

_IDENT = re.compile(r"^[a-z_][a-z0-9_]*$")
_CHECK_ID = re.compile(r"^[a-z][a-z0-9_]*(\.[a-z][a-z0-9_]*){1,5}$")
_TABLES = frozenset({"patients", "visits", "lab_results", "invoices"})
_SEVERITIES = frozenset({"error", "warning"})
_SPECIES_CHECK = "accepted.patients.species"


@dataclass(frozen=True)
class RowCountRule:
    id: str
    description: str
    severity: str
    table: str
    min_rows: int


@dataclass(frozen=True)
class RequiredRule:
    id: str
    description: str
    severity: str
    table: str
    key: str
    columns: tuple[str, ...]


@dataclass(frozen=True)
class UniqueRule:
    id: str
    description: str
    severity: str
    table: str
    columns: tuple[str, ...]


@dataclass(frozen=True)
class ForeignKeyRule:
    id: str
    description: str
    severity: str
    child_table: str
    child_key: str
    child_column: str
    parent_table: str
    parent_column: str


@dataclass(frozen=True)
class AcceptedRule:
    id: str
    description: str
    severity: str
    table: str
    key: str
    column: str
    values: tuple[str, ...]


@dataclass(frozen=True)
class RangeRule:
    id: str
    description: str
    severity: str
    table: str
    key: str
    column: str
    min_value: float | None
    max_value: float | None


@dataclass(frozen=True)
class DomainRule:
    id: str
    description: str
    severity: str
    table: str
    sql_path: Path


@dataclass(frozen=True)
class Config:
    root: Path
    config_path: Path
    as_of_date: date
    min_birth_date: date
    min_temp_c: float
    max_temp_c: float
    sample_limit: int
    weight_bounds: tuple[tuple[str, float, float], ...]
    temperature_required_species: tuple[str, ...]
    clean_files: dict[str, Path]
    seed_path: Path
    row_counts: tuple[RowCountRule, ...]
    required: tuple[RequiredRule, ...]
    uniqueness: tuple[UniqueRule, ...]
    foreign_keys: tuple[ForeignKeyRule, ...]
    accepted: tuple[AcceptedRule, ...]
    ranges: tuple[RangeRule, ...]
    domain: tuple[DomainRule, ...]

    def check_ids(self) -> tuple[str, ...]:
        groups = (
            self.row_counts,
            self.required,
            self.uniqueness,
            self.foreign_keys,
            self.accepted,
            self.ranges,
            self.domain,
        )
        return tuple(rule.id for group in groups for rule in group)


def load_config(
    path: str | Path | None = None,
    environ: Mapping[str, str] | None = None,
) -> Config:
    env = os.environ if environ is None else environ
    if path is None:
        configured = env.get("DQ_CONFIG")
        path = Path(configured) if configured else Path.cwd() / "config" / "checks.yaml"
    config_path = Path(path).resolve()
    if config_path.name != "checks.yaml" or config_path.parent.name != "config":
        raise DQError("Config path must be <project>/config/checks.yaml.")
    root = config_path.parent.parent
    try:
        raw = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise DQError(f"Could not read config {config_path}: {exc}") from exc
    except yaml.YAMLError as exc:
        raise DQError(f"Could not parse config {config_path}: {exc}") from exc
    document = _mapping(raw, "config")

    as_of_date = _as_date(document.get("as_of_date"), "as_of_date")
    if "DQ_AS_OF_DATE" in env and str(env.get("DQ_AS_OF_DATE", "")).strip():
        as_of_date = _as_date(env["DQ_AS_OF_DATE"], "DQ_AS_OF_DATE")
    min_birth_date = _as_date(document.get("min_birth_date"), "min_birth_date")
    if min_birth_date > as_of_date:
        raise DQError("min_birth_date is after as_of_date.")

    temperature = _mapping(document.get("temperature_c"), "temperature_c")
    min_temp_c = _as_number(temperature.get("min"), "temperature_c.min")
    max_temp_c = _as_number(temperature.get("max"), "temperature_c.max")
    if min_temp_c >= max_temp_c:
        raise DQError("temperature_c.min must be lower than temperature_c.max.")
    temp_species = tuple(
        _as_token(item, "temperature_c.required_for_species")
        for item in _as_list(
            temperature.get("required_for_species"),
            "temperature_c.required_for_species",
        )
    )
    if len(temp_species) != len(set(temp_species)):
        raise DQError("temperature_c.required_for_species contains a duplicate.")
    weight_bounds = _weight_bounds(document.get("weight_kg_by_species"))
    sample_limit = _as_int(document.get("sample_limit"), "sample_limit")
    if not 1 <= sample_limit <= 100:
        raise DQError("sample_limit must be between 1 and 100.")

    datasets = _mapping(document.get("datasets"), "datasets")
    clean_files = _clean_files(root, datasets.get("clean"))
    seed_path = _seed_path(root, datasets.get("defects"))
    checks = _mapping(document.get("checks"), "checks")

    config = Config(
        root=root,
        config_path=config_path,
        as_of_date=as_of_date,
        min_birth_date=min_birth_date,
        min_temp_c=min_temp_c,
        max_temp_c=max_temp_c,
        sample_limit=sample_limit,
        weight_bounds=weight_bounds,
        temperature_required_species=temp_species,
        clean_files=clean_files,
        seed_path=seed_path,
        row_counts=_row_counts(checks.get("row_counts")),
        required=_required(checks.get("required_columns")),
        uniqueness=_uniqueness(checks.get("uniqueness")),
        foreign_keys=_foreign_keys(checks.get("foreign_keys")),
        accepted=_accepted(checks.get("accepted_values")),
        ranges=_ranges(checks.get("ranges")),
        domain=_domain(root, checks.get("domain")),
    )
    _reject_duplicate_ids(config.check_ids())
    _validate_species_coverage(config)
    schema = root / "sql" / "schema.sql"
    if not schema.is_file():
        raise DQError(f"Schema file does not exist: {schema}")
    return config


def validate_species_coverage(
    accepted_species: set[str],
    weight_species: set[str],
    temperature_species: set[str],
) -> None:
    extra_bounds = weight_species - accepted_species
    if extra_bounds:
        names = ", ".join(sorted(extra_bounds))
        raise DQError(f"Weight bounds include species outside the accepted list: {names}.")
    missing_bounds = accepted_species - weight_species
    if missing_bounds:
        names = ", ".join(sorted(missing_bounds))
        raise DQError(f"Accepted species missing weight bounds: {names}.")
    extra_temperature = temperature_species - accepted_species
    if extra_temperature:
        names = ", ".join(sorted(extra_temperature))
        raise DQError(f"Temperature is required for species outside the accepted list: {names}.")


def _validate_species_coverage(config: Config) -> None:
    species_rule = next((rule for rule in config.accepted if rule.id == _SPECIES_CHECK), None)
    if species_rule is None:
        raise DQError(f"Catalog is missing {_SPECIES_CHECK}.")
    validate_species_coverage(
        set(species_rule.values),
        {species for species, _, _ in config.weight_bounds},
        set(config.temperature_required_species),
    )


def _weight_bounds(raw: object) -> tuple[tuple[str, float, float], ...]:
    mapping = _mapping(raw, "weight_kg_by_species")
    bounds: list[tuple[str, float, float]] = []
    for species, window in mapping.items():
        species_name = _as_token(species, "weight_kg_by_species species")
        window_map = _mapping(window, f"weight_kg_by_species.{species_name}")
        low = _as_number(window_map.get("min"), f"weight_kg_by_species.{species_name}.min")
        high = _as_number(window_map.get("max"), f"weight_kg_by_species.{species_name}.max")
        if low >= high:
            raise DQError(f"Weight bounds for {species_name} have min >= max.")
        bounds.append((species_name, low, high))
    if not bounds:
        raise DQError("weight_kg_by_species must not be empty.")
    return tuple(bounds)


def _clean_files(root: Path, raw: object) -> dict[str, Path]:
    mapping = _mapping(raw, "datasets.clean")
    if set(mapping) != _TABLES:
        raise DQError("datasets.clean must name patients, visits, lab_results, and invoices.")
    return {
        table: _resolve_under(root, mapping[table], f"datasets.clean.{table}", root / "data")
        for table in ("patients", "visits", "lab_results", "invoices")
    }


def _seed_path(root: Path, raw: object) -> Path:
    mapping = _mapping(raw, "datasets.defects")
    if mapping.get("base") != "clean":
        raise DQError("datasets.defects.base must be 'clean'.")
    return _resolve_under(root, mapping.get("seed"), "datasets.defects.seed", root / "data")


def _row_counts(raw: object) -> tuple[RowCountRule, ...]:
    rules: list[RowCountRule] = []
    for index, item in enumerate(_as_list(raw, "checks.row_counts"), start=1):
        body = _mapping(item, f"checks.row_counts[{index}]")
        check_id, description, severity = _common(body, f"checks.row_counts[{index}]")
        table = _table(body.get("table"), f"{check_id}.table")
        min_rows = _as_int(body.get("min_rows"), f"{check_id}.min_rows")
        if min_rows < 1:
            raise DQError(f"{check_id}.min_rows must be at least 1.")
        rules.append(RowCountRule(check_id, description, severity, table, min_rows))
    return tuple(rules)


def _required(raw: object) -> tuple[RequiredRule, ...]:
    rules: list[RequiredRule] = []
    for index, item in enumerate(_as_list(raw, "checks.required_columns"), start=1):
        body = _mapping(item, f"checks.required_columns[{index}]")
        check_id, description, severity = _common(body, f"checks.required_columns[{index}]")
        table = _table(body.get("table"), f"{check_id}.table")
        key = _as_ident(body.get("key"), f"{check_id}.key")
        columns = _idents(body.get("columns"), f"{check_id}.columns")
        rules.append(RequiredRule(check_id, description, severity, table, key, columns))
    return tuple(rules)


def _uniqueness(raw: object) -> tuple[UniqueRule, ...]:
    rules: list[UniqueRule] = []
    for index, item in enumerate(_as_list(raw, "checks.uniqueness"), start=1):
        body = _mapping(item, f"checks.uniqueness[{index}]")
        check_id, description, severity = _common(body, f"checks.uniqueness[{index}]")
        table = _table(body.get("table"), f"{check_id}.table")
        columns = _idents(body.get("columns"), f"{check_id}.columns")
        rules.append(UniqueRule(check_id, description, severity, table, columns))
    return tuple(rules)


def _foreign_keys(raw: object) -> tuple[ForeignKeyRule, ...]:
    rules: list[ForeignKeyRule] = []
    for index, item in enumerate(_as_list(raw, "checks.foreign_keys"), start=1):
        body = _mapping(item, f"checks.foreign_keys[{index}]")
        check_id, description, severity = _common(body, f"checks.foreign_keys[{index}]")
        rules.append(
            ForeignKeyRule(
                id=check_id,
                description=description,
                severity=severity,
                child_table=_table(body.get("child_table"), f"{check_id}.child_table"),
                child_key=_as_ident(body.get("child_key"), f"{check_id}.child_key"),
                child_column=_as_ident(body.get("child_column"), f"{check_id}.child_column"),
                parent_table=_table(body.get("parent_table"), f"{check_id}.parent_table"),
                parent_column=_as_ident(body.get("parent_column"), f"{check_id}.parent_column"),
            )
        )
    return tuple(rules)


def _accepted(raw: object) -> tuple[AcceptedRule, ...]:
    rules: list[AcceptedRule] = []
    for index, item in enumerate(_as_list(raw, "checks.accepted_values"), start=1):
        body = _mapping(item, f"checks.accepted_values[{index}]")
        check_id, description, severity = _common(body, f"checks.accepted_values[{index}]")
        values = tuple(
            _as_token(value, f"{check_id}.values")
            for value in _as_list(body.get("values"), f"{check_id}.values")
        )
        if not values:
            raise DQError(f"{check_id}.values must not be empty.")
        rules.append(
            AcceptedRule(
                id=check_id,
                description=description,
                severity=severity,
                table=_table(body.get("table"), f"{check_id}.table"),
                key=_as_ident(body.get("key"), f"{check_id}.key"),
                column=_as_ident(body.get("column"), f"{check_id}.column"),
                values=values,
            )
        )
    return tuple(rules)


def _ranges(raw: object) -> tuple[RangeRule, ...]:
    rules: list[RangeRule] = []
    for index, item in enumerate(_as_list(raw, "checks.ranges"), start=1):
        body = _mapping(item, f"checks.ranges[{index}]")
        check_id, description, severity = _common(body, f"checks.ranges[{index}]")
        min_raw = body.get("min")
        max_raw = body.get("max")
        if min_raw is None and max_raw is None:
            raise DQError(f"{check_id} needs min, max, or both.")
        min_value = None if min_raw is None else _as_number(min_raw, f"{check_id}.min")
        max_value = None if max_raw is None else _as_number(max_raw, f"{check_id}.max")
        if min_value is not None and max_value is not None and min_value > max_value:
            raise DQError(f"{check_id} min is greater than max.")
        rules.append(
            RangeRule(
                id=check_id,
                description=description,
                severity=severity,
                table=_table(body.get("table"), f"{check_id}.table"),
                key=_as_ident(body.get("key"), f"{check_id}.key"),
                column=_as_ident(body.get("column"), f"{check_id}.column"),
                min_value=min_value,
                max_value=max_value,
            )
        )
    return tuple(rules)


def _domain(root: Path, raw: object) -> tuple[DomainRule, ...]:
    rules: list[DomainRule] = []
    for index, item in enumerate(_as_list(raw, "checks.domain"), start=1):
        body = _mapping(item, f"checks.domain[{index}]")
        check_id, description, severity = _common(body, f"checks.domain[{index}]")
        sql_path = _resolve_under(
            root, body.get("file"), f"{check_id}.file", root / "sql" / "domain"
        )
        rules.append(
            DomainRule(
                id=check_id,
                description=description,
                severity=severity,
                table=_table(body.get("table"), f"{check_id}.table"),
                sql_path=sql_path,
            )
        )
    return tuple(rules)


def _common(body: dict[str, object], label: str) -> tuple[str, str, str]:
    check_id = _as_check_id(body.get("id"), f"{label}.id")
    description = _as_str(body.get("description"), f"{check_id}.description")
    severity = body.get("severity", "error")
    if not isinstance(severity, str) or severity not in _SEVERITIES:
        raise DQError(f"{check_id} severity must be error or warning.")
    category_for(check_id)
    return check_id, description, severity


def _reject_duplicate_ids(check_ids: tuple[str, ...]) -> None:
    seen: set[str] = set()
    for check_id in check_ids:
        if check_id in seen:
            raise DQError(f"Duplicate check id: {check_id}.")
        seen.add(check_id)
    if not seen:
        raise DQError("Catalog does not define any checks.")


def _resolve_under(root: Path, raw: object, label: str, parent: Path) -> Path:
    if not isinstance(raw, str) or not raw.strip():
        raise DQError(f"{label} must be a relative path.")
    candidate = Path(raw)
    if candidate.is_absolute():
        raise DQError(f"{label} must be a relative path.")
    path = (root / candidate).resolve()
    if not path.is_relative_to(parent.resolve()):
        raise DQError(f"{label} must stay under {parent.relative_to(root)}.")
    if not path.is_file():
        raise DQError(f"{label} does not exist: {candidate.as_posix()}.")
    return path


def _mapping(value: object, label: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise DQError(f"{label} must be a mapping.")
    return value


def _as_list(value: object, label: str) -> list[object]:
    if not isinstance(value, list) or not value:
        raise DQError(f"{label} must be a non-empty list.")
    return value


def _as_str(value: object, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise DQError(f"{label} must be a non-empty string.")
    return value.strip()


def _as_ident(value: object, label: str) -> str:
    text = _as_str(value, label)
    if not _IDENT.fullmatch(text):
        raise DQError(f"{label} is not a safe identifier: {text!r}.")
    return text


def _idents(value: object, label: str) -> tuple[str, ...]:
    names = tuple(_as_ident(item, label) for item in _as_list(value, label))
    if len(names) != len(set(names)):
        raise DQError(f"{label} contains a duplicate identifier.")
    return names


def _as_token(value: object, label: str) -> str:
    text = _as_str(value, label)
    if "'" in text or "\n" in text or "\r" in text:
        raise DQError(f"{label} contains a character that cannot be inlined into SQL.")
    return text


def _as_check_id(value: object, label: str) -> str:
    text = _as_str(value, label)
    if not _CHECK_ID.fullmatch(text):
        raise DQError(f"{label} is not a dotted check id: {text!r}.")
    return text


def _table(value: object, label: str) -> str:
    name = _as_ident(value, label)
    if name not in _TABLES:
        raise DQError(f"{label} must be one of: {', '.join(sorted(_TABLES))}.")
    return name


def _as_int(value: object, label: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise DQError(f"{label} must be an integer.")
    return value


def _as_number(value: object, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, int | float):
        raise DQError(f"{label} must be a number.")
    number = float(value)
    if not math.isfinite(number):
        raise DQError(f"{label} must be a finite number.")
    return number


def _as_date(value: object, label: str) -> date:
    if isinstance(value, datetime):
        raise DQError(f"{label} must be an ISO date (YYYY-MM-DD).")
    if isinstance(value, date):
        return value
    text = _as_str(value, label)
    try:
        parsed = date.fromisoformat(text)
    except ValueError as exc:
        raise DQError(f"{label} must be an ISO date (YYYY-MM-DD).") from exc
    return parsed
