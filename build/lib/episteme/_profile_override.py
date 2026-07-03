"""Per-project profile override mechanism — CP-CONTEXT-AWARE-PROFILE-OVERRIDE-01
first slice (Event 85).

The kernel's central thesis is *context-fit, not statistical-fit*. The
operator profile is currently a SINGLE profile applied to all projects
— but operators legitimately have different cognitive postures across
contexts (prototype vs production; research vs operational). Single-
profile-globally conflates "who I am" with "how I should behave RIGHT
NOW in THIS context." That conflation is itself a Doxa-class problem
applied to operator self-modeling.

This module ships the per-project override mechanism: each project
may carry a `<project>/.episteme/profile-override.yaml` file that
supersedes specific axes from the global operator profile for that
project's scope.

## Resolution chain

For any axis read at runtime:

```
project override   →   operator global   →   kernel default
       │                      │                    │
   (highest specificity)  (~/episteme...)    (schema fallback)
```

Highest specificity wins. An axis NOT named in the project override
falls through to global / kernel default; an axis named overrides
ONLY for that project.

## Override file format

```yaml
# <project>/.episteme/profile-override.yaml
overrides:
  testing_rigor:
    value: 5
    rationale: "Production critical-path; max test discipline regardless of global posture."
    applied_since: "2026-04-29"
    evidence_refs: []
  risk_tolerance:
    value: 1
    rationale: "Production migration scope; lowest-risk posture for this project."
    applied_since: "2026-04-29"
    evidence_refs: ["Event 65"]
```

Each override carries the same metadata structure as a global axis
(value + rationale + applied_since + evidence_refs) so the audit
trail at the project tier is identical to the global tier.

## Scope

This module ships:

1. read_project_override(project_path) — parse the YAML file.
2. resolve_axis(axis_name, project_path, global_value) — implement the
   resolution chain.
3. write_project_override(axis_name, value, rationale, ...) — CLI-side
   helper for `episteme profile override`.
4. validate_axis_name + validate_rationale (mirrors _profile_history.py
   discipline).

Deferred to follow-up Events:
- Auto-integration into core/hooks/_derived_knobs.py (so derived knobs
  consult overrides automatically at runtime).
- Auto-integration into core/hooks/_profile_audit.py (so Phase 12 audit
  reads project context + applies overrides).
- Override-history journal at ~/.episteme/memory/reflective/
  profile_override_history.jsonl (mirrors profile_history.jsonl pattern;
  CP-TEMPORAL-INTEGRITY-EXPANSION-01 Item 1 generalized to project
  scope).
- Audit-log enrichment recording which override applied to a decision.

Spec: ~/episteme-private/docs/cp-v1.1-architectural.md §
CP-CONTEXT-AWARE-PROFILE-OVERRIDE-01.
"""
from __future__ import annotations

import os
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

# YAML import is conditional — prefer PyYAML when available, fall back
# to a minimal parser for the simple key:value structure we use.
try:
    import yaml as _yaml  # type: ignore  # pyright: ignore[reportMissingImports]
    _HAS_YAML = True
except ImportError:
    _yaml = None  # type: ignore[assignment]
    _HAS_YAML = False


OVERRIDE_FILENAME = "profile-override.yaml"
OVERRIDE_DIR = ".episteme"


# Valid axis names — same enumeration as _profile_history.py (mirrors
# kernel/OPERATOR_PROFILE_SCHEMA.md v2 schema).
VALID_AXIS_NAMES: frozenset[str] = frozenset({
    "planning_strictness",
    "risk_tolerance",
    "testing_rigor",
    "parallelism_preference",
    "documentation_rigor",
    "automation_level",
    "dominant_lens",
    "noise_signature",
    "abstraction_entry",
    "decision_cadence",
    "explanation_depth",
    "feedback_mode",
    "uncertainty_tolerance",
    "asymmetry_posture",
    "fence_discipline",
    "expertise_map",
})

LAZY_RATIONALE_TOKENS: frozenset[str] = frozenset({
    "n/a", "na", "tbd", "todo",
    "none", "nothing", "nil", "null",
    "ack", "acked", "acknowledged",
    "ok", "okay", "fine",
    "later", "fix later", "do later", "address later",
    "wip", "in progress",
    "해당 없음", "없음", "없다", "추후", "나중에",
})

MIN_RATIONALE_CHARS = 15


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------


def validate_axis_name(axis_name) -> None:
    if not isinstance(axis_name, str):
        raise ValueError("axis_name must be a string")
    stripped = axis_name.strip()
    if not stripped:
        raise ValueError("axis_name must be a non-empty string")
    if stripped not in VALID_AXIS_NAMES:
        raise ValueError(
            f"unknown axis_name {axis_name!r}. Must be one of the 16 "
            f"declared axes in kernel/OPERATOR_PROFILE_SCHEMA.md."
        )


def validate_rationale(text) -> None:
    if not isinstance(text, str):
        raise ValueError("rationale must be a string")
    stripped = text.strip()
    lowered = stripped.lower()
    for token in LAZY_RATIONALE_TOKENS:
        if lowered == token.lower():
            raise ValueError(
                f"rationale matches lazy-token {token!r}. "
                f"Provide a substantive reason — what context-fit consideration "
                f"makes this override warranted in this project?"
            )
    if len(stripped) < MIN_RATIONALE_CHARS:
        raise ValueError(
            f"rationale must be at least {MIN_RATIONALE_CHARS} characters; "
            f"got {len(stripped)}."
        )


# ---------------------------------------------------------------------------
# Path resolution
# ---------------------------------------------------------------------------


def _override_path(project_path: Path) -> Path:
    return project_path / OVERRIDE_DIR / OVERRIDE_FILENAME


# ---------------------------------------------------------------------------
# YAML I/O (with fallback)
# ---------------------------------------------------------------------------


def _parse_yaml(text: str) -> dict:
    """Parse the override YAML. Uses PyYAML when available; otherwise
    falls back to a minimal parser for the documented schema (overrides
    map of axis-name → {value, rationale, applied_since, evidence_refs}).
    """
    if _HAS_YAML and _yaml is not None:
        try:
            data = _yaml.safe_load(text)
        except Exception as exc:
            raise ValueError(f"YAML parse error: {exc}") from exc
        return data if isinstance(data, dict) else {}
    # Minimal fallback parser: top-level "overrides:" then axis-keyed
    # nested dicts. We only support the documented shape.
    return _minimal_yaml_parse(text)


def _minimal_yaml_parse(text: str) -> dict:
    """Bare-bones YAML parser for the override file schema. Supports:

    - top-level `overrides:` key with axis-keyed nested mappings
    - per-axis `value`, `rationale`, `applied_since`, `evidence_refs`
      (scalar or list)

    NOT a general YAML parser. Operators with complex YAML should
    install PyYAML.
    """
    out_overrides: dict[str, dict] = {}
    lines = text.splitlines()
    in_overrides = False
    current_axis: str | None = None
    current_axis_dict: dict | None = None
    for raw in lines:
        line = raw.rstrip()
        if not line or line.lstrip().startswith("#"):
            continue
        if not line.startswith(" "):
            in_overrides = (line.strip().rstrip(":") == "overrides")
            current_axis = None
            current_axis_dict = None
            continue
        if not in_overrides:
            continue
        # 2-space indent = axis name; 4-space indent = field within axis
        stripped = line.lstrip(" ")
        indent = len(line) - len(stripped)
        if indent == 2:
            # axis-name:
            axis = stripped.rstrip(":").strip()
            if axis:
                current_axis = axis
                current_axis_dict = {}
                out_overrides[axis] = current_axis_dict
        elif indent >= 4 and current_axis_dict is not None and ":" in stripped:
            key, _, val = stripped.partition(":")
            key = key.strip()
            val = val.strip()
            # Handle list inline `["a", "b"]` or single quoted scalar
            if val.startswith("[") and val.endswith("]"):
                # very-rough list parse
                items = [
                    item.strip().strip('"').strip("'")
                    for item in val[1:-1].split(",")
                    if item.strip()
                ]
                current_axis_dict[key] = items
            else:
                # Strip surrounding quotes if any
                if val.startswith('"') and val.endswith('"'):
                    val = val[1:-1]
                elif val.startswith("'") and val.endswith("'"):
                    val = val[1:-1]
                # Try int conversion for numeric values
                try:
                    current_axis_dict[key] = int(val)
                except ValueError:
                    current_axis_dict[key] = val
    return {"overrides": out_overrides}


def _serialize_yaml(data: dict) -> str:
    """Serialize the override dict to YAML. Uses PyYAML when available;
    otherwise emits a hand-formatted version of the documented schema."""
    if _HAS_YAML and _yaml is not None:
        return _yaml.safe_dump(data, sort_keys=False, allow_unicode=True)  # type: ignore[no-any-return]
    # Fallback emit
    overrides = data.get("overrides", {})
    if not isinstance(overrides, dict):
        return "overrides: {}\n"
    out = ["overrides:"]
    for axis, fields in overrides.items():
        out.append(f"  {axis}:")
        if isinstance(fields, dict):
            for k, v in fields.items():
                if isinstance(v, list):
                    items = ", ".join(f'"{str(x)}"' for x in v)
                    out.append(f"    {k}: [{items}]")
                elif isinstance(v, str):
                    out.append(f'    {k}: "{v}"')
                else:
                    out.append(f"    {k}: {v}")
    return "\n".join(out) + "\n"


# ---------------------------------------------------------------------------
# Read paths
# ---------------------------------------------------------------------------


def read_project_override(project_path: Path) -> dict:
    """Read and parse the project's profile-override.yaml. Returns the
    full overrides dict (axis-name → {value, rationale, ...}) or empty
    dict when no override file exists.
    """
    path = _override_path(project_path)
    if not path.exists():
        return {}
    try:
        text = path.read_text(encoding="utf-8")
    except OSError:
        return {}
    parsed = _parse_yaml(text)
    overrides = parsed.get("overrides", {}) if isinstance(parsed, dict) else {}
    return overrides if isinstance(overrides, dict) else {}


def resolve_axis(
    axis_name: str,
    project_path: Path,
    global_value: Any | None = None,
) -> dict:
    """Resolve an axis value via the project → global → kernel-default
    chain. Returns ``{source, value, rationale?, applied_since?}``.

    - ``source`` is one of ``"project_override"``, ``"global"``,
      ``"kernel_default"``.
    - When ``source == "project_override"``, the override's full
      metadata (rationale + applied_since + evidence_refs) is included.
    """
    validate_axis_name(axis_name)
    overrides = read_project_override(project_path)
    if axis_name in overrides:
        override = overrides[axis_name]
        if isinstance(override, dict):
            return {
                "source": "project_override",
                "value": override.get("value"),
                "rationale": override.get("rationale"),
                "applied_since": override.get("applied_since"),
                "evidence_refs": override.get("evidence_refs", []),
            }
    if global_value is not None:
        return {
            "source": "global",
            "value": global_value,
        }
    return {
        "source": "kernel_default",
        "value": None,
    }


# ---------------------------------------------------------------------------
# Write path
# ---------------------------------------------------------------------------


def _resolve_recorder() -> str:
    explicit = os.environ.get("EPISTEME_RECORDER", "").strip()
    if explicit:
        return explicit
    user = os.environ.get("USER", "").strip()
    if user:
        return user
    try:
        result = subprocess.run(
            ["git", "config", "--get", "user.name"],
            capture_output=True, text=True, timeout=2,
        )
        if result.returncode == 0 and result.stdout.strip():
            return result.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        pass
    return "unknown"


def write_project_override(
    project_path: Path,
    axis_name: str,
    value: Any,
    rationale: str,
    *,
    evidence_refs: Iterable[str] | None = None,
    _now: datetime | None = None,  # test seam
) -> Path:
    """Write or replace an override entry for ``axis_name`` in the
    project's profile-override.yaml. Returns the path written.

    Validation: axis_name must be one of the 16 declared axes;
    rationale must be ≥15 chars + non-lazy-token.
    """
    validate_axis_name(axis_name)
    validate_rationale(rationale)
    now = _now or datetime.now(timezone.utc)

    overrides = read_project_override(project_path)
    overrides[axis_name] = {
        "value": value,
        "rationale": rationale.strip(),
        "applied_since": now.strftime("%Y-%m-%d"),
        "evidence_refs": list(evidence_refs) if evidence_refs else [],
    }
    full_doc = {"overrides": overrides}
    path = _override_path(project_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    text = _serialize_yaml(full_doc)
    path.write_text(text, encoding="utf-8")
    return path


def list_project_overrides(project_path: Path) -> dict:
    """Convenience wrapper. Returns the full overrides dict."""
    return read_project_override(project_path)


def remove_project_override(
    project_path: Path,
    axis_name: str,
) -> bool:
    """Remove an axis override. Returns True if an override existed
    and was removed; False otherwise."""
    validate_axis_name(axis_name)
    overrides = read_project_override(project_path)
    if axis_name not in overrides:
        return False
    del overrides[axis_name]
    path = _override_path(project_path)
    if overrides:
        text = _serialize_yaml({"overrides": overrides})
        path.write_text(text, encoding="utf-8")
    else:
        # Empty overrides — write empty doc rather than delete file
        path.write_text("overrides: {}\n", encoding="utf-8")
    return True
