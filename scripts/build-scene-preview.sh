#!/bin/sh
set -eu
RIDGE_ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
. "$RIDGE_ROOT/scripts/macos-env.sh"
mkdir -p "$RIDGE_ROOT/build-macos"
c++ -std=c++17 -O2 -Wall -Wextra "$RIDGE_ROOT/src/scene/preview.cpp" \
    $(pkg-config --cflags --libs sdl3) -framework OpenGL -o "$RIDGE_ROOT/build-macos/RidgeScenePreview"
printf '%s\n' "$RIDGE_ROOT/build-macos/RidgeScenePreview"
