#!/bin/sh
set -eu
RIDGE_ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
. "$RIDGE_ROOT/scripts/macos-env.sh"
c++ -std=c++17 -O2 -g -DGL_SILENCE_DEPRECATION -DRIDGE_PRESENT_PROBE=1 -DRIDGE_PRESENT_PHASE_TEST=1 \
    "$RIDGE_ROOT/src/scene/preview.cpp" $(pkg-config --cflags --libs sdl3) \
    -framework OpenGL -lobjc -o "$RIDGE_ROOT/build-macos/RidgeScenePacingTest"
