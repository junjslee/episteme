"""Service A — payment-processing API.

Uses corp-validator-lib for payload validation, with a custom validator
override that handles payment-specific edge cases (negative amounts,
fractional cents, etc.).
"""
from corp_validator_lib import Registry
from services.service_a.validators.custom_validator import customValidator


def setup_validation():
    """Register the custom validator with the library's registry."""
    Registry.register(customValidator)


def handle_payment_request(payload: dict) -> dict:
    """Validate the incoming payment payload and process it."""
    setup_validation()
    validator = Registry.get_validator_for("payment")
    if not validator.validate(payload):
        return {"error": "invalid_payload", "code": "VAL_001"}
    return process_payment(payload)


def process_payment(payload: dict) -> dict:
    # Stub — real impl charges the customer.
    return {"ok": True, "charge_id": "ch_xxx"}
