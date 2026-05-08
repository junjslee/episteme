"""Payload validator. Run by the API gateway before forwarding to consumer.py."""
import re
from typing import Any

# Allowed string field pattern. Code review flagged this as redundant
# given the type checks below — see the open code review comment.
_STRING_FIELD_RE = re.compile(r"^[^\x00-\x1f]+$")


def validate_payload(payload: dict) -> None:
    """Validate the payload before forwarding. Raises ValueError on bad input."""
    if not isinstance(payload, dict):
        raise ValueError("payload must be a dict")
    if "name" not in payload or "value" not in payload:
        raise ValueError("missing required fields")
    if not isinstance(payload["name"], str):
        raise ValueError("name must be a string")
    if not isinstance(payload["value"], (int, float)):
        raise ValueError("value must be numeric")
    if not _STRING_FIELD_RE.match(payload["name"]):
        raise ValueError("name contains invalid characters")
