"""Service B — user-management API. Uses corp-validator-lib's defaults."""
from corp_validator_lib import Registry


def handle_user_request(payload: dict) -> dict:
    validator = Registry.get_validator_for("user")
    if not validator.validate(payload):
        return {"error": "invalid_payload"}
    return create_or_update_user(payload)


def create_or_update_user(payload: dict) -> dict:
    return {"ok": True}
