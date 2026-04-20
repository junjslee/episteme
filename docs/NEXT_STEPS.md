# Next Steps

Exact next actions, in priority order. Update this file at every handoff.

---

## Immediate (post-rename)

1. **Verify marketplace install path** — `/plugin marketplace add junjslee/episteme`
   (GitHub repo renamed; old `junjslee/cognitive-os` URL still 301-redirects).

2. **Run push-readiness checklist**
   ```bash
   PYTHONPATH=src:. pytest -q
   python3 -m py_compile src/episteme/cli.py
   python3 -m py_compile core/hooks/reasoning_surface_guard.py
   episteme doctor
   ```

3. **Tag the migration** — `git tag v0.8.0 && git push --tags`

2. **Run push-readiness checklist**
   ```bash
   PYTHONPATH=. pytest -q tests/test_profile_cognition.py
   python3 -m py_compile src/episteme/cli.py
   episteme doctor
   git status && git rev-list --left-right --count @{u}...HEAD
   ```

3. **Commit 0.6.0** — once marketplace fix is verified, create a single commit covering all changes in this cycle (see `docs/PROGRESS.md` for full file list).

---

## Short-term (next cycle)

- Replace ASCII control-plane diagram in `README.md` with an SVG asset (see TODO comment removed in this cycle; concept is now defined)
- Add `last_elicited` timestamp field to operator profile schema (Gap B in KERNEL_LIMITS.md)
- Implement calibration telemetry stub — `decisions/*.md` append-only log (Gap A)

---

## Medium-term (roadmap)

- Multi-operator mode design (Gap C)
- `tacit-call` decision marker in Reasoning Surface schema (Gap D)
- Cynefin domain classification field in `reasoning-surface.json` schema (companion to KERNEL_LIMITS.md addition)
