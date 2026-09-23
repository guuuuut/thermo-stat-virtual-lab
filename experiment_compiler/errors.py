"""Structured errors returned by the ExperimentSpec compiler."""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass
from typing import Any, Mapping


def json_safe(value: Any) -> Any:
    if isinstance(value, float) and not math.isfinite(value):
        return str(value)
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, list):
        return [json_safe(item) for item in value]
    if isinstance(value, dict):
        return {str(key): json_safe(item) for key, item in value.items()}
    return repr(value)


@dataclass(frozen=True)
class ValidationIssue:
    code: str
    path: str
    message: str
    value: Any
    expected: str
    hint: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class SpecValidationError(ValueError):
    """One or more ExperimentSpec validation failures."""

    def __init__(self, issues: list[ValidationIssue]):
        self.issues = tuple(issues)
        super().__init__(f"ExperimentSpec validation failed with {len(issues)} issue(s)")

    def to_dict(self) -> dict[str, Any]:
        return {
            "error": {
                "code": "SPEC_VALIDATION_FAILED",
                "message": str(self),
                "issue_count": len(self.issues),
                "issues": [issue.to_dict() for issue in self.issues],
            }
        }


class TemplateCompileError(RuntimeError):
    """A validated spec could not be rendered into a safe script."""

    def __init__(
        self,
        code: str,
        message: str,
        details: Mapping[str, Any] | None = None,
    ):
        self.code = code
        self.details = dict(details or {})
        super().__init__(message)

    def to_dict(self) -> dict[str, Any]:
        return {
            "error": {
                "code": self.code,
                "message": str(self),
                "details": self.details,
            }
        }
