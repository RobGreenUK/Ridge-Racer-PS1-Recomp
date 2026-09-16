#!/bin/sh
# Keep the pinned upstream revision while recording the local runtime fixes.
set -eu
RIDGE_PATCH_ROOT=$(CDPATH= cd -- "$(dirname -- "$0")/.." && pwd)
for RIDGE_RUNTIME_PATCH in "$RIDGE_PATCH_ROOT"/patches/psxrecomp-*.patch; do
    if git -C "$RIDGE_PATCH_ROOT/psxrecomp" apply --reverse --check "$RIDGE_RUNTIME_PATCH" 2>/dev/null; then
        continue
    fi
    git -C "$RIDGE_PATCH_ROOT/psxrecomp" apply --check "$RIDGE_RUNTIME_PATCH"
    git -C "$RIDGE_PATCH_ROOT/psxrecomp" apply "$RIDGE_RUNTIME_PATCH"
done
