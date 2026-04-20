# Next Steps

Exact next actions, in priority order. Update this file at every handoff.

---

## Immediate (0.9.0 entry)

1. **Scope phase 1 of 0.9.0** — calibration telemetry stub (Gap A): decide append-only file layout (`decisions/YYYY-MM-DD-slug.md`?) and minimum fields (predicted outcome, disconfirmation condition, observed outcome, delta).
2. **Replace ASCII control-plane diagram** in `README.md` with SVG. Concept already defined; asset production only.
3. **Add `last_elicited` timestamp** to operator profile schema (Gap B). Lowest-risk schema extension — additive field, no adapter break.

## Short-term (0.9.0 remainder)

- `tacit-call` decision marker in Reasoning Surface schema (Gap D)
- Cynefin domain classification field in `reasoning-surface.json` (companion to KERNEL_LIMITS.md addition)

## Medium-term (roadmap)

- Multi-operator mode design (Gap C) — deferred past 0.9.0; requires profile schema rework.
- Cross-runtime MCP proxy daemon — blocked on calibration telemetry data.

---

## Closed in 0.8.0
- Remove compat symlink `/Users/junlee/cognitive-os`
- Verify `/plugin marketplace add junjslee/episteme` resolves (user confirmed in-session)
- Tag + push `v0.8.0`
- Reconcile `pyproject.toml`, `plugin.json`, `marketplace.json` versions
- Add `kernel/CHANGELOG.md` 0.8.0 entry
