"""Downstream consumer that processes validated payloads.

PRECONDITION: payload['name'] does NOT contain control characters
(\\x00 through \\x1f). The serializer below uses a fixed-width
delimiter scheme that breaks if the field contains embedded null
bytes — would produce silent corruption of the database key by
truncating at the first \\x00. Validator at validate.py guards
this precondition with a regex.
"""
import struct


def consume(payload: dict) -> bytes:
    name = payload["name"]
    value = payload["value"]
    # Fixed-width frame: 32-byte name (null-padded), 8-byte value.
    name_bytes = name.encode("utf-8")[:32].ljust(32, b"\x00")
    value_bytes = struct.pack(">q", int(value * 100))
    return name_bytes + value_bytes
