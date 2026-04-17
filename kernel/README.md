# The Cognitive Kernel

This directory is the canonical specification of cognitive-os.

It is pure markdown. No code. No tooling. Nothing vendor-specific.

The kernel defines **how an agent should think** — before any platform,
framework, or adapter is involved. Everything else in this repository
(the CLI, the hooks, the adapters, the skills) exists to deliver this
kernel into a specific runtime.

If the kernel is sound, the adapters are small. If an adapter starts
growing, the fix is usually in the kernel's portability, not in more
adapter code.

---

## Files

- **[CONSTITUTION.md](./CONSTITUTION.md)** — the north-star document.
  Root claim, why agents fail, the four principles, and what follows from them.

- **[REASONING_SURFACE.md](./REASONING_SURFACE.md)** — the operational
  protocol that operationalizes Principle I (Explicit > Implicit).
  The minimum viable act of explicitness before any consequential action.

- **[SYSTEM_1_COUNTERS.md](./SYSTEM_1_COUNTERS.md)** — the named counters
  to the six most consequential System 1 failures. Maps each failure mode
  to the specific kernel artifact that blocks it.

- **[OPERATOR_PROFILE_SCHEMA.md](./OPERATOR_PROFILE_SCHEMA.md)** — the
  schema for encoding an operator's cognitive preferences so they can
  travel with the agent across tools and sessions.

---

## How the kernel is delivered

An adapter is a thin shim that injects kernel files into a runtime's
native context-loading mechanism:

- Claude Code: concatenated into `CLAUDE.md` / referenced from global memory.
- Hermes: mounted as `OPERATOR.md`.
- Any future runtime: same files, different destination.

The kernel does not care which runtime loads it. The runtime does not
know what the kernel contains. That decoupling is the point.

---

## What lives here vs. elsewhere

- **kernel/** — portable spec. Markdown only. Vendor-neutral.
- **adapters/** — per-runtime delivery. Should be tiny (<100 LOC each).
- **core/memory/global/** — the *author's* personal instance of the
  operator profile, using the schema defined here.
- **docs/** — project-level documentation about the system itself
  (architecture notes, contract docs, PRDs). Not kernel.
