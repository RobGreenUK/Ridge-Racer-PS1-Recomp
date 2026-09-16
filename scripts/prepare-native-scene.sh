#!/bin/sh
# Derive all assets locally from the user's USA disc. No game data is downloaded.
set -eu
RIDGE_ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
. "$RIDGE_ROOT/scripts/macos-env.sh"
cd "$RIDGE_ROOT"
sh scripts/build-scene-preview.sh
python3 tools/prepare_native_scene.py
printf '%s\n' 'Native scene mode is ready in the service menu (Motion tab).'
