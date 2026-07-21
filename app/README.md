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

Produces `dist/Episteme.app` and an **unsigned** `dist/Episteme.pkg`
(installs to /Applications). Unsigned is a conscious tier: it installs
cleanly on the machine that built it; distribution-grade signing +
notarization is a separate operator-gated decision recorded in the ledger.
