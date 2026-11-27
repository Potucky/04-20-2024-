"""Result records shared by the engine, the report, and the CLI."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FailedRow:
    entity_key: str
    detail: str


@dataclass(frozen=True)
class CheckResult:
    check_id: str
    category: str
    severity: str
    table: str
    description: str
    passed: bool
    observed: str
    expected: str
    failed_count: int
    sample: tuple[FailedRow, ...]


@dataclass(frozen=True)
class RunReport:
    dataset: str
    as_of_date: str
    generated_at: str
    applied_mutations: tuple[str, ...]
    note: str
    results: tuple[CheckResult, ...]

    @property
    def total(self) -> int:
        return len(self.results)

    @property
    def failed_results(self) -> tuple[CheckResult, ...]:
        return tuple(result for result in self.results if not result.passed)

    @property
    def passed_count(self) -> int:
        return self.total - len(self.failed_results)

    @property
    def error_count(self) -> int:
        return sum(1 for result in self.failed_results if result.severity == "error")

    @property
    def warning_count(self) -> int:
        return sum(1 for result in self.failed_results if result.severity == "warning")


def has_blocking_failure(results: tuple[CheckResult, ...] | list[CheckResult]) -> bool:
    return any(not result.passed and result.severity == "error" for result in results)
