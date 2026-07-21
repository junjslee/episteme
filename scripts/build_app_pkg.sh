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
mkdir -p "$APP/Contents/MacOS" "$APP/Contents/Resources"
cp "$APP_DIR/target/release/episteme-app" "$APP/Contents/MacOS/episteme-app"
# Icon (E179): committed reproducible artifact; regenerate with
#   swift app/icon/make_icns.swift app/icon
cp "$APP_DIR/icon/episteme.icns" "$APP/Contents/Resources/episteme.icns"
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
  <key>CFBundleIconFile</key><string>episteme</string>
  <key>CFBundlePackageType</key><string>APPL</string>
  <key>LSMinimumSystemVersion</key><string>12.0</string>
  <key>NSHighResolutionCapable</key><true/>
</dict>
</plist>
PLIST

# AppleDouble hygiene (E176 review → E179 measured reality): xattr -cr +
# ditto --noextattr remove the REMOVABLE class (quarantine, FinderInfo,
# resource forks). com.apple.provenance is SIP-protected AND re-stamped by
# the OS on every local write, so local builds ALWAYS carry its 11-byte
# AppleDouble entries in the payload — unavoidable by construction, harmless
# metadata. Release artifacts come from CI (release-assets.yml) where this
# does not gate anything; do not chase the residue further.
xattr -cr "$APP" 2>/dev/null || true
STAGED="$DIST/.staging/Episteme.app"
rm -rf "$DIST/.staging"
mkdir -p "$DIST/.staging"
ditto --noextattr --norsrc --noacl "$APP" "$STAGED"

# Signing tiers (E179): credential-ready, inert without the operator's cert.
#   EPISTEME_SIGN_APP_ID       "Developer ID Application: Name (TEAMID)"
#   EPISTEME_SIGN_INSTALLER_ID "Developer ID Installer: Name (TEAMID)"
#   EPISTEME_NOTARY_PROFILE    notarytool keychain profile name
# FIRST CHECK once a real cert exists: hardened runtime vs the wry webview —
# if the window comes up blank under --options runtime, add an entitlements
# plist (com.apple.security.cs.allow-jit) here.
TIER="unsigned (personal use)"
if [ -n "${EPISTEME_SIGN_APP_ID:-}" ]; then
  echo "==> codesign (hardened runtime, on the STAGED copy — signing must
       follow attribute-stripping, never precede it)"
  codesign --force --deep --options runtime --timestamp \
    --sign "$EPISTEME_SIGN_APP_ID" "$STAGED"
  TIER="signed"
fi

echo "==> pkgbuild"
RAW_PKG="$DIST/Episteme-unsigned.pkg"
COPYFILE_DISABLE=1 pkgbuild \
  --component "$STAGED" \
  --install-location /Applications \
  --identifier com.episteme.app \
  --version "$VERSION" \
  "$RAW_PKG"

if [ -n "${EPISTEME_SIGN_INSTALLER_ID:-}" ]; then
  echo "==> productsign"
  productsign --sign "$EPISTEME_SIGN_INSTALLER_ID" "$RAW_PKG" "$DIST/Episteme.pkg"
  rm -f "$RAW_PKG"
  TIER="signed installer"
else
  mv "$RAW_PKG" "$DIST/Episteme.pkg"
fi

if [ -n "${EPISTEME_NOTARY_PROFILE:-}" ]; then
  echo "==> notarytool submit (waits for Apple)"
  xcrun notarytool submit "$DIST/Episteme.pkg" \
    --keychain-profile "$EPISTEME_NOTARY_PROFILE" --wait
  xcrun stapler staple "$DIST/Episteme.pkg"
  TIER="notarized"
fi

echo "done: tier=$TIER"
ls -lh "$DIST/Episteme.pkg"
if [ "$TIER" = "unsigned (personal use)" ]; then
  echo "install: open dist/Episteme.pkg  (unsigned — right-click → Open on first run)"
fi
