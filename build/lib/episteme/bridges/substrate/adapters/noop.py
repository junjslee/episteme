"""Noop adapter — local filesystem substrate.

Zero external dependencies. Stores pushed envelopes under
`core/memory/substrates/noop/<scope-slug>/<timestamp>-<source_id>.json`.
Exists to (a) exercise the full bridge pipeline without network or SDK installs,
(b) give tests and CI a deterministic substrate, (c) serve as the minimal
reference implementation for anyone writing a new adapter.

Preserves the full memory-contract record losslessly — no fields coerced.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..base import AdapterDescriptor, PullQuery, PushResult, ScopeMap, SubstrateAdapter


_REPO_ROOT = Path(__file__).resolve().parents[5]
_DEFAULT_ROOT = _REPO_ROOT / "core" / "memory" / "substrates" / "noop"


def _slug(value: str | None) -> str:
    if not value:
        return "none"
    return re.sub(r"[^a-zA-Z0-9._-]+", "-", value).strip("-").lower() or "none"


def _scope_slug(scope: ScopeMap) -> str:
    parts = [
        f"u={_slug(scope.user_id)}",
        f"p={_slug(scope.project_id)}",
        f"s={_slug(scope.session_id)}",
    ]
    return "_".join(parts)


class NoopAdapter(SubstrateAdapter):
    name = "noop"

    def __init__(self, config: dict | None = None) -> None:
        cfg = config or {}
        root = cfg.get("root")
        self.root = Path(root).expanduser() if root else _DEFAULT_ROOT

    def describe(self) -> AdapterDescriptor:
        return AdapterDescriptor(
            name=self.name,
            version="1.0.0",
            substrate={"name": "local-filesystem", "transport": "filesystem"},
            capabilities={
                "push": True,
                "pull": True,
                "delete": True,
                "update": False,
                "search": False,
                "filter_by_scope": True,
                "preserve_provenance": True,
                "native_entity_linking": False,
            },
            scope_keys=["user_id", "project_id", "agent_id", "session_id", "run_id"],
            lossy_fields=[],
            config_schema={
                "type": "object",
                "properties": {"root": {"type": "string"}},
                "additionalProperties": False,
            },
        )

    def push(self, envelope: dict[str, Any], scope: ScopeMap) -> PushResult:
        result = PushResult(adapter=self.name)
        if envelope.get("contract_version") != "memory-contract-v1":
            result.failed.append({
                "source_id": "(envelope)",
                "error": f"unsupported contract_version: {envelope.get('contract_version')!r}",
            })
            return result

        scope_dir = self.root / _scope_slug(scope)
        scope_dir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")

        for record in envelope.get("records") or []:
            source_id = str(record.get("id") or "unknown")
            try:
                out = scope_dir / f"{stamp}-{_slug(source_id)}.json"
                payload = {"record": record, "scope": scope.as_dict()}
                out.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
                result.pushed.append({"source_id": source_id, "substrate_id": str(out)})
            except OSError as exc:
                result.failed.append({"source_id": source_id, "error": str(exc)})
        return result

    def pull(self, query: PullQuery) -> dict[str, Any]:
        scope_dir = self.root / _scope_slug(query.scope)
        records: list[dict[str, Any]] = []
        if scope_dir.exists():
            files = sorted(scope_dir.glob("*.json"), reverse=True)[: query.limit]
            for f in files:
                try:
                    payload = json.loads(f.read_text(encoding="utf-8"))
                    rec = payload.get("record")
                    if rec:
                        records.append(rec)
                except (OSError, json.JSONDecodeError):
                    continue
        return {"contract_version": "memory-contract-v1", "records": records}

    def delete(self, substrate_id: str) -> bool:
        p = Path(substrate_id)
        if p.exists():
            p.unlink()
            return True
        return False


ADAPTER = NoopAdapter
