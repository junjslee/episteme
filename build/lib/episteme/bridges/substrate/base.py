"""Base types for substrate adapters.

A substrate adapter is a thin translator between memory-contract-v1 envelopes and
whatever API/SDK/filesystem a given external memory system exposes. Adapters must
be honest: `describe()` declares capabilities, and operations the substrate cannot
honor must be returned as `skipped` in the push result, not silently dropped or
mocked.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field, asdict
from typing import Any


@dataclass
class ScopeMap:
    """Neutral scope keys. Adapters declare which they honor natively in their
    descriptor's `scope_keys`. Keys not in that list are stored as substrate
    metadata (when possible), not used for filtering."""

    user_id: str | None = None
    project_id: str | None = None
    agent_id: str | None = None
    session_id: str | None = None
    run_id: str | None = None
    app_id: str | None = None
    org_id: str | None = None

    def as_dict(self) -> dict[str, str]:
        return {k: v for k, v in asdict(self).items() if v}


@dataclass
class AdapterDescriptor:
    name: str
    version: str
    capabilities: dict[str, bool]
    scope_keys: list[str]
    substrate: dict[str, Any] = field(default_factory=dict)
    lossy_fields: list[str] = field(default_factory=list)
    config_schema: dict[str, Any] | None = None
    contract_version: str = "substrate-v1"

    def as_dict(self) -> dict[str, Any]:
        d = asdict(self)
        if self.config_schema is None:
            d.pop("config_schema", None)
        return d


@dataclass
class PullQuery:
    query: str | None = None
    scope: ScopeMap = field(default_factory=ScopeMap)
    limit: int = 50
    since: str | None = None


@dataclass
class PushResult:
    adapter: str
    pushed: list[dict[str, Any]] = field(default_factory=list)
    skipped: list[dict[str, Any]] = field(default_factory=list)
    failed: list[dict[str, Any]] = field(default_factory=list)
    lossy: list[str] = field(default_factory=list)
    contract_version: str = "substrate-v1"

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


class SubstrateAdapter(ABC):
    """Every substrate adapter subclasses this. The class is the only integration
    point the kernel needs; discovery happens through `registry.list_adapters`."""

    name: str = ""

    @abstractmethod
    def describe(self) -> AdapterDescriptor:
        """Return a capability descriptor. Validated against
        `core/schemas/substrate/adapter_descriptor.schema.json` by `verify`."""

    @abstractmethod
    def push(self, envelope: dict[str, Any], scope: ScopeMap) -> PushResult:
        """Push a memory-contract-v1 envelope into the substrate. Records that
        cannot be honored must land in `PushResult.skipped` with a reason, never
        silently dropped."""

    def pull(self, query: PullQuery) -> dict[str, Any]:
        """Pull from substrate into a memory-contract-v1 envelope. Default:
        unsupported — adapters must override to claim the `pull` capability."""
        raise NotImplementedError(f"{self.name}: pull not supported")

    def delete(self, substrate_id: str) -> bool:
        """Delete a single record by substrate-native id. Default: unsupported."""
        raise NotImplementedError(f"{self.name}: delete not supported")
