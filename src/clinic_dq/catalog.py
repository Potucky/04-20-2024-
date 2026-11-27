"""Check id prefixes and the order used in reports."""

from __future__ import annotations

from clinic_dq.errors import DQError

CATEGORY_BY_PREFIX: dict[str, str] = {
    "row_count": "row_count",
    "not_null": "not_null",
    "uniqueness": "uniqueness",
    "fk": "referential",
    "accepted": "accepted_values",
    "range": "range",
    "date": "date_logic",
    "consistency": "consistency",
}

CATEGORY_ORDER: tuple[str, ...] = (
    "row_count",
    "not_null",
    "uniqueness",
    "referential",
    "accepted_values",
    "range",
    "date_logic",
    "consistency",
)


def category_for(check_id: str) -> str:
    prefix = check_id.split(".", 1)[0]
    try:
        return CATEGORY_BY_PREFIX[prefix]
    except KeyError as exc:
        known = ", ".join(sorted(CATEGORY_BY_PREFIX))
        raise DQError(
            f"Check id {check_id!r} uses an unknown prefix. Known prefixes: {known}."
        ) from exc
