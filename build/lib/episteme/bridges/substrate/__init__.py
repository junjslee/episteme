"""Substrate bridge — a generalizable adapter protocol for external memory systems.

The kernel speaks exactly one format: memory-contract-v1 envelopes. Every external
memory substrate (mem0, Memori, MemOS, claude-mem, a vector DB, a filesystem tree,
an MCP server) plugs in by implementing `SubstrateAdapter`. No substrate becomes
authoritative; they are caches with declared capabilities and declared lossy fields.
"""

from .base import SubstrateAdapter, AdapterDescriptor, ScopeMap, PullQuery  # noqa: F401
from .registry import list_adapters, load_adapter  # noqa: F401
