# Episteme.app — native shell over the local governance dashboard (E176)

A deliberately thin Rust window (`app/src/main.rs`, wry + tao — no Tauri CLI,
no Node build) over `episteme viewer`. All product logic stays in the Python
viewer (`src/episteme/viewer/server.py`); the shell only ensures the server
is running and shows it in a real window, so there is no second
implementation to drift from the kernel.

## Behavior contract

- **Attach-or-spawn:** if `127.0.0.1:37776` already answers (you ran
  `episteme viewer` yourself), the app attaches and spawns nothing; closing
  the window then leaves your viewer running.
- **Spawned lifecycle:** otherwise the app spawns
  `episteme viewer --no-open --exit-with-parent` and kills it on window
  close. If the app dies without a window-close (signal, crash), the viewer
  notices the reparenting via `--exit-with-parent` and shuts itself down
  within ~2s — no orphaned servers.
- **CLI resolution:** `EPISTEME_BIN` env override → `which episteme` → the
  well-known install prefixes (GUI apps do not inherit a login shell's
  PATH). On failure the window shows the reason, never a blank page.

## Build

```
scripts/build_app_pkg.sh
```

Requires Rust ≥ 1.85 (`edition = "2024"` in `app/Cargo.toml`); `app/` is not
built in CI — the build host's toolchain is the only gate.

Produces `dist/Episteme.app` and `dist/Episteme.pkg` (installs to
/Applications), with the icon regenerated on demand:
`swift app/icon/make_icns.swift app/icon` (the committed `episteme.icns` is
a reproducible artifact of that script — no design blob without a source).

**Signing tiers** (E179 — the script is credential-ready and inert without
certs; each tier upgrades by exporting env vars before the build):

| Tier | Requires | Gets you |
|---|---|---|
| unsigned (default) | nothing | installs on the building machine; right-click → Open elsewhere |
| signed | `EPISTEME_SIGN_APP_ID`, `EPISTEME_SIGN_INSTALLER_ID` (Developer ID certs — operator-only Apple enrollment) | Gatekeeper-recognized identity |
| notarized | + `EPISTEME_NOTARY_PROFILE` (notarytool keychain profile) | clean first-run for any downloader |

Local builds carry `com.apple.provenance` AppleDouble entries in the pkg
payload — SIP-protected, re-stamped on write, unremovable by construction;
harmless 11-byte metadata (release artifacts are CI-built via
`release-assets.yml`). First check after enrolling: hardened runtime
(`--options runtime`) vs the wry webview — if the window comes up blank, add a JIT entitlement (noted in
`scripts/build_app_pkg.sh`). Release assets: `.github/workflows/release-assets.yml`
attaches the wheel + pkg to a GitHub release (`workflow_dispatch` today;
`release: published` activates once release-please gets the operator's PAT).
