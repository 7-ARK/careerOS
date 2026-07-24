"""Small, conservative redaction helpers for autonomous-run evidence."""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

REDACTED = "[REDACTED]"

_ASSIGNMENT = re.compile(
    r"(?P<name>\b[A-Za-z_][A-Za-z0-9_]*(?:API_KEY|TOKEN|SECRET|PASSWORD|CREDENTIALS?|"
    r"DATABASE_URL|DB_URL|CONNECTION_STRING)\b)"
    r"(?P<separator>\s*[=:]\s*)"
    r"(?P<value>\"[^\"]*\"|'[^']*'|[^\s,;]+)",
    re.IGNORECASE,
)
_URL_SECRET = re.compile(
    r"(?P<name>[?&](?:api[_-]?key|access[_-]?token|auth(?:orization)?|secret|password)\s*=\s*)"
    r"(?P<value>[^&#\s]+)",
    re.IGNORECASE,
)
_BEARER = re.compile(r"(?i)(\bBearer\s+)[A-Za-z0-9._~+/=-]+")
_TOKEN = re.compile(r"(?i)\b(?:sk|rk|ghp|github_pat|xox[baprs])-[A-Za-z0-9_-]{8,}\b")
_MASKED_TOKEN = re.compile(r"(?i)\b(?:sk|rk|ghp|github_pat|xox[baprs])-[^\s,;'\"}]+")
_SENSITIVE_KEY = re.compile(
    r"(?i)(?:api[_-]?key|access[_-]?token|auth(?:orization)?|secret|password|"
    r"credential|database[_-]?url)"
)


def redact_text(value: str, *, replacement: str = REDACTED) -> str:
    """Redact common secret-bearing assignments, URLs, headers, and token shapes."""

    if not value:
        return value

    def replace_assignment(match: re.Match[str]) -> str:
        return f"{match.group('name')}{match.group('separator')}{replacement}"

    value = _ASSIGNMENT.sub(replace_assignment, value)
    value = _URL_SECRET.sub(lambda match: f"{match.group('name')}{replacement}", value)
    value = _BEARER.sub(lambda match: f"{match.group(1)}{replacement}", value)
    value = _MASKED_TOKEN.sub(replacement, value)
    return _TOKEN.sub(replacement, value)


def redact_mapping(value: Mapping[str, Any]) -> dict[str, Any]:
    """Return a recursively redacted copy of a mapping suitable for artifacts."""

    return {
        str(key): REDACTED if _SENSITIVE_KEY.search(str(key)) else _redact_value(item)
        for key, item in value.items()
    }


def _redact_value(value: Any) -> Any:
    if isinstance(value, str):
        return redact_text(value)
    if isinstance(value, Mapping):
        return redact_mapping(value)
    if isinstance(value, list):
        return [_redact_value(item) for item in value]
    if isinstance(value, tuple):
        return tuple(_redact_value(item) for item in value)
    return value


def redact_command(arguments: list[str] | tuple[str, ...]) -> tuple[str, ...]:
    """Redact values embedded in command arguments before logging them."""

    return tuple(redact_text(argument) for argument in arguments)


__all__ = ["REDACTED", "redact_command", "redact_mapping", "redact_text"]
