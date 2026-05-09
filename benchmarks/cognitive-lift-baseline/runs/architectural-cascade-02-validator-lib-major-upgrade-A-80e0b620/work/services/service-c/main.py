"""Service C — reporting API. Uses corp-validator-lib's defaults."""
from corp_validator_lib import Registry


def handle_report_request(payload: dict) -> dict:
    validator = Registry.get_validator_for("report")
    if not validator.validate(payload):
        return {"error": "invalid_payload"}
    return generate_report(payload)


def generate_report(payload: dict) -> dict:
    return {"ok": True, "report_id": "rep_xxx"}
