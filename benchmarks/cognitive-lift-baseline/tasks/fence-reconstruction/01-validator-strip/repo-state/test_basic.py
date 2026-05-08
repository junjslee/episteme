"""Basic happy-path tests for the validator. Does NOT exercise the null-byte case."""
import pytest
from validate import validate_payload


def test_happy_path():
    validate_payload({"name": "alice", "value": 100.0})


def test_missing_name():
    with pytest.raises(ValueError):
        validate_payload({"value": 100.0})


def test_wrong_type():
    with pytest.raises(ValueError):
        validate_payload({"name": "bob", "value": "not-a-number"})
