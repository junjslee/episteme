"""Event 169 — adapter registry ⟷ implementation bijection.

The registry (core/adapters/*.json) exists so `episteme sync`'s delivery
surfaces are machine-readable and reviewable. It drifted in BOTH
directions and nothing caught either: codex.json was declared with no
implementation for months (~/.codex silently received nothing — E167),
while omo.py/omx.py shipped with no registry entry. This test is the
gate the registry README promised: every declared adapter has an
implementation, every implementation is declared, and each JSON carries
the fields the sync layer and docs rely on.
"""
from __future__ import annotations

import json
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
REGISTRY = REPO / "core" / "adapters"
IMPL = REPO / "src" / "episteme" / "adapters"

REQUIRED_FIELDS = {"name", "display", "detect", "docs_url", "sync", "project_contract", "notes"}


def _declared() -> dict[str, dict]:
    out = {}
    for f in sorted(REGISTRY.glob("*.json")):
        spec = json.loads(f.read_text(encoding="utf-8"))
        out[spec["name"]] = spec
        assert f.stem == spec["name"], (
            f"{f.name}: filename must match its name field ({spec['name']!r})"
        )
    return out


def _implemented() -> set[str]:
    return {
        p.stem for p in IMPL.glob("*.py")
        if p.stem != "__init__" and not p.stem.startswith("_")
    }


def test_every_declared_adapter_is_implemented():
    missing = set(_declared()) - _implemented()
    assert not missing, (
        f"declared in core/adapters/ but no implementation in "
        f"src/episteme/adapters/: {sorted(missing)} — the codex.json "
        f"failure class (E167): a declaration with no code means a "
        f"delivery surface silently receives nothing"
    )


def test_every_implementation_is_declared():
    undeclared = _implemented() - set(_declared())
    assert not undeclared, (
        f"implemented but absent from the core/adapters/ registry: "
        f"{sorted(undeclared)} — the registry is the reviewable record "
        f"of what sync touches on an operator's machine; an undeclared "
        f"adapter is an unreviewable write surface"
    )


def test_declared_specs_carry_required_fields():
    for name, spec in _declared().items():
        missing = REQUIRED_FIELDS - set(spec)
        assert not missing, f"{name}.json missing fields: {sorted(missing)}"
        assert isinstance(spec["detect"], dict)
        assert isinstance(spec["sync"], dict) and spec["sync"], (
            f"{name}.json: sync must name at least one write target"
        )


def test_every_adapter_module_exposes_sync():
    import importlib
    for name in _implemented():
        mod = importlib.import_module(f"episteme.adapters.{name}")
        assert callable(getattr(mod, "sync", None)), (
            f"episteme.adapters.{name} has no callable sync()"
        )
