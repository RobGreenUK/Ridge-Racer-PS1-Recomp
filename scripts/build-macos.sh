#!/bin/sh
set -eu
RIDGE_ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
. "$RIDGE_ROOT/scripts/macos-env.sh"
cd "$RIDGE_ROOT"
RIDGE_DISC=${RIDGE_DISC:-"$RIDGE_ROOT/Ridge Racer (USA)/Ridge Racer (USA).cue"}
if [ ! -f "$RIDGE_DISC" ]; then
    echo "Disc missing: $RIDGE_DISC (set RIDGE_DISC to your CUE path)" >&2
    exit 1
fi
sh scripts/apply-runtime-patches.sh
bash psxrecomp/tools/ci/build_emitters.sh
python3 psxrecomp/psxrecomp_cli.py generate --config game.toml --project-root "$RIDGE_ROOT" --disc "$RIDGE_DISC"
cmake -S . -B build-macos -G Ninja -DCMAKE_BUILD_TYPE=RelWithDebInfo -DPSX_ENABLE_VULKAN=OFF -DPSX_GAME_VERSION=0.1.0
cmake --build build-macos --target psx-runtime -j "${RIDGE_JOBS:-8}"
sh scripts/build-scene-preview.sh
sh scripts/build-launcher-macos.sh
