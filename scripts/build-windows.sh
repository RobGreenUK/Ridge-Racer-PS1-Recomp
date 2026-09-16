#!/usr/bin/env bash
# Native Windows x64 build. Run in the MSYS2 UCRT64 terminal.
set -euo pipefail
if [[ "${MSYSTEM:-}" != UCRT64 ]]; then
    echo "Open the MSYS2 UCRT64 terminal; see docs/BUILD_WINDOWS.md." >&2
    exit 1
fi
RIDGE_ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
cd "$RIDGE_ROOT"
export PATH="/ucrt64/bin:$PATH"
export CC=gcc CXX=g++
RIDGE_DISC=${RIDGE_DISC:-"$RIDGE_ROOT/Ridge Racer (USA)/Ridge Racer (USA).cue"}
[[ -f "$RIDGE_DISC" ]] || { echo "Missing disc: $RIDGE_DISC" >&2; exit 1; }
python3 -c 'import sys,tomllib; assert sys.platform == "win32", "Use UCRT64 Python, not MSYS Python"'
sh scripts/apply-runtime-patches.sh
cmake -S psxrecomp/recompiler -B build-recompiler -G Ninja \
    -DCMAKE_BUILD_TYPE=Release -DPSXRECOMP_ENABLE_CHD=OFF
cmake --build build-recompiler --target psxrecomp-game psxrecomp-bios -j "${RIDGE_JOBS:-8}"
python3 psxrecomp/psxrecomp_cli.py generate --config game.toml --project-root "$RIDGE_ROOT" --disc "$RIDGE_DISC"
cmake -S . -B build-windows -G Ninja -DCMAKE_BUILD_TYPE=Release \
    -DPSX_ENABLE_VULKAN=OFF -DPSX_RECOMP_UI=OFF -DPSX_STATIC_RUNTIME=ON -DPSX_GAME_VERSION=0.1.0
cmake --build build-windows --target psx-runtime RidgeScenePreview RidgeTransportCheck -j "${RIDGE_JOBS:-8}"
python3 tools/prepare_native_scene.py --build-dir build-windows
python3 tools/package_windows.py --name windows
