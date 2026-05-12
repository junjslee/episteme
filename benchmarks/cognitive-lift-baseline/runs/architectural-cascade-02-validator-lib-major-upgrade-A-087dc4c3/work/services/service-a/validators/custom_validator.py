"""Custom payment validator for Service A.

Registered with corp-validator-lib's Registry by class name. The library's
registry uses the class name string to look up the right validator for a
given payload type.

Note: class name is `customValidator` (lowercase 'c') — this matches the
naming in the original v1.x registration system. The library has historically
been case-insensitive on class-name lookup.
"""
from corp_validator_lib import BaseValidator


class customValidator(BaseValidator):
    """Validates payment payloads — handles fractional cents, negative
    amounts, currency-mismatch edge cases."""

    payload_type = "payment"

    def validate(self, payload: dict) -> bool:
        # Reject negative amounts.
        if payload.get("amount", 0) < 0:
            return False
        # Reject fractional cents (more than 2 decimal places).
        amount = payload.get("amount", 0)
        if round(amount * 100) != amount * 100:
            return False
        # Reject currency mismatches.
        if payload.get("currency") not in ("USD", "EUR", "GBP"):
            return False
        # Several other payment-specific checks...
        return True
