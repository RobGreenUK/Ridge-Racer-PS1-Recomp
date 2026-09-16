#!/bin/sh
# Scene diagnostics are local and opt-in. Pass an output path that does not exist.
set -eu
RIDGE_ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
. "$RIDGE_ROOT/scripts/macos-env.sh"
if [ "$#" -ne 1 ]; then
    echo "Usage: sh scripts/capture-scene.sh diagnostics/new-capture.jsonl" >&2
    exit 2
fi
RIDGE_CAPTURE_PATH=$(python3 - "$1" "$RIDGE_ROOT" <<'PY'
import hashlib
from pathlib import Path
import sys
sys.path.insert(0, str(Path(sys.argv[2]) / 'tools'))
from probe_timing import EXPECTED_SHA256
root = Path(sys.argv[2])
if hashlib.sha256((root / 'disc/SCUS-943.00').read_bytes()).hexdigest() != EXPECTED_SHA256:
    raise SystemExit('Unsupported executable: USA scene addresses are version specific')
p = Path(sys.argv[1]).resolve()
if p.exists():
    raise SystemExit('Capture path already exists; use a new filename')
p.parent.mkdir(parents=True, exist_ok=True)
print(p)
PY
)
export RIDGE_SCENE_CAPTURE="$RIDGE_CAPTURE_PATH"
export RIDGE_SCENE_CAPTURE_FRAMES="${RIDGE_SCENE_CAPTURE_FRAMES:-6000}"
exec sh "$RIDGE_ROOT/scripts/run-macos.sh" --no-launcher --debug-port "${RIDGE_DEBUG_PORT:-9945}"
