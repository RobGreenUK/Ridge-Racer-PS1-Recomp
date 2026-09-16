#!/bin/sh
set -eu
RIDGE_ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
. "$RIDGE_ROOT/scripts/macos-env.sh"
RIDGE_APP="$RIDGE_ROOT/build-macos/Ridge Racer.app"
mkdir -p "$RIDGE_APP/Contents/MacOS"
swiftc -parse-as-library -O -framework SwiftUI -framework AppKit "$RIDGE_ROOT/launcher/ServiceMenu.swift" -o "$RIDGE_APP/Contents/MacOS/RidgeRacerLauncher"
cat > "$RIDGE_APP/Contents/Info.plist" <<'PLIST'
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0"><dict>
<key>CFBundleExecutable</key><string>RidgeRacerLauncher</string>
<key>CFBundleIdentifier</key><string>local.ridgeracer.service-menu</string>
<key>CFBundleName</key><string>Ridge Racer</string>
<key>CFBundleVersion</key><string>1</string>
<key>CFBundlePackageType</key><string>APPL</string>
<key>NSHighResolutionCapable</key><true/>
</dict></plist>
PLIST
codesign --force --sign - "$RIDGE_APP"
echo "Built $RIDGE_APP"
