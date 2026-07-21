#!/usr/bin/env bash
# Build Episteme.app and an UNSIGNED Episteme.pkg installer (E176).
#
# Personal-use packaging: an unsigned .pkg installs cleanly on the machine
# that built it (and any Mac past a right-click → Open). Distribution-grade
# signing + notarization is a separate, operator-gated decision — see the
# ledger; do NOT add credentials here.
#
# Usage: scripts/build_app_pkg.sh        (from the repo root)
# Output: dist/Episteme.app, dist/Episteme.pkg

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
APP_DIR="$REPO_ROOT/app"
DIST="$REPO_ROOT/dist"
APP="$DIST/Episteme.app"
VERSION="$(grep -m1 '^version' "$APP_DIR/Cargo.toml" | cut -d'"' -f2)"

echo "==> cargo build --release (app shell v$VERSION)"
(cd "$APP_DIR" && cargo build --release)

echo "==> assembling $APP"
rm -rf "$APP"
mkdir -p "$APP/Contents/MacOS"
cp "$APP_DIR/target/release/episteme-app" "$APP/Contents/MacOS/episteme-app"
cat > "$APP/Contents/Info.plist" << PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleName</key><string>Episteme</string>
  <key>CFBundleDisplayName</key><string>Episteme</string>
  <key>CFBundleIdentifier</key><string>com.episteme.app</string>
  <key>CFBundleVersion</key><string>$VERSION</string>
  <key>CFBundleShortVersionString</key><string>$VERSION</string>
  <key>CFBundleExecutable</key><string>episteme-app</string>
  <key>CFBundlePackageType</key><string>APPL</string>
  <key>LSMinimumSystemVersion</key><string>12.0</string>
  <key>NSHighResolutionCapable</key><true/>
</dict>
</plist>
PLIST

echo "==> pkgbuild (unsigned)"
pkgbuild \
  --component "$APP" \
  --install-location /Applications \
  --identifier com.episteme.app \
  --version "$VERSION" \
  "$DIST/Episteme.pkg"

echo "done:"
ls -lh "$DIST/Episteme.pkg"
echo "install: open dist/Episteme.pkg  (unsigned — right-click → Open on first run)"
