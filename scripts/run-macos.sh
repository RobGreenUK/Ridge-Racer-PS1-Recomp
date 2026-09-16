#!/bin/sh
set -eu
RIDGE_ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
. "$RIDGE_ROOT/scripts/macos-env.sh"
cd "$RIDGE_ROOT"
export RIDGERACERRECOMP_BUILD_DIR="$RIDGE_ROOT/build-macos"
if [ "$#" -eq 0 ]; then
    exec "$RIDGE_ROOT/build-macos/Ridge Racer.app/Contents/MacOS/RidgeRacerLauncher"
fi
exec "$RIDGE_ROOT/build-macos/RidgeRacer_Recompiled" --game "$RIDGE_ROOT/game.toml" --disc "${RIDGE_DISC:-$RIDGE_ROOT/Ridge Racer (USA)/Ridge Racer (USA).cue}" "$@"
