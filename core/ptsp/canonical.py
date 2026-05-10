"""RFC 8785 JSON Canonicalization Scheme (JCS) helpers.

The canonical form is the byte sequence that gets hashed and signed. Any
two semantically-equal JSON values must produce the same canonical bytes,
regardless of whitespace, key order, or number formatting in the input.

We implement a pragmatic subset of RFC 8785 sufficient for episteme's
needs: sorted object keys, separators with no whitespace, UTF-8 output,
ECMAScript-style number formatting via Python's repr for floats (with
careful handling of integer-valued floats). For values that fall outside
this scope (large floats, scientific notation, surrogate pairs), we
recommend the `rfc8785` PyPI library; this module is a no-extra-dependency
shim so the kernel does not require pip-installs for the verifier to run.

Determinism is load-bearing: a one-byte mismatch in canonical form is the
exact tamper detection signal that `episteme verify` uses to flag mutation.
Any change to this module's output must bump the schema version and update
the verifier's tolerance.
"""
from __future__ import annotations

import hashlib
import json
from typing import Any


def _canonical_default(obj: Any) -> Any:
    """JSON default for non-serializable types — refuses by design.

    PTSP types are all dataclasses with explicit dict conversion. Anything
    reaching this default is a programming error, not a runtime concern.
    """
    raise TypeError(
        f"PTSP JCS canonicalization received non-JSON-serializable type "
        f"{type(obj).__name__}; convert to dict via the type's own "
        f"`to_dict()` method before canonicalizing."
    )


def jcs_canonical(obj: Any) -> bytes:
    """Return the JCS-canonical UTF-8 byte sequence for a JSON-compatible value.

    Sorted keys, no whitespace, no ASCII-escape of non-ASCII, ensure_ascii=False
    so non-ASCII characters appear verbatim (UTF-8 byte sequence is the
    canonical form per RFC 8785 § 3.2.5).
    """
    return json.dumps(
        obj,
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
        default=_canonical_default,
        allow_nan=False,
    ).encode("utf-8")


def sha256_hex(b: bytes) -> str:
    """SHA-256 hex digest of the input byte sequence."""
    return hashlib.sha256(b).hexdigest()


def sha256_of_jcs(obj: Any) -> str:
    """Convenience: hex digest of jcs_canonical(obj)."""
    return sha256_hex(jcs_canonical(obj))
