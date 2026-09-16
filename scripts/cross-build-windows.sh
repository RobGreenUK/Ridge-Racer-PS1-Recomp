#!/bin/sh
# Cross-build on Apple Silicon using Homebrew mingw-w64; output is Windows x64.
set -eu
RIDGE_ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$RIDGE_ROOT"
. "$RIDGE_ROOT/scripts/macos-env.sh"
sh scripts/apply-runtime-patches.sh
cmake -S . -B build-windows -G Ninja \
  -DCMAKE_TOOLCHAIN_FILE=cmake/windows-x64.cmake -DCMAKE_BUILD_TYPE=Release \
  -DPSX_ENABLE_VULKAN=OFF -DPSX_RECOMP_UI=OFF -DPSX_STATIC_RUNTIME=ON -DPSX_GAME_VERSION=0.1.0
cmake --build build-windows --target psx-runtime RidgeScenePreview RidgeTransportCheck -j "${RIDGE_JOBS:-8}"
