#!/bin/sh
set -eu
RIDGE_ROOT=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
. "$RIDGE_ROOT/scripts/macos-env.sh"
printf '%s\n' 'Experimental presentation timing: play the course where you noticed spikes.' 'Press M when motion stutters (timing marker only); P still saves an image capture. Your normal launcher still uses the existing viewer.'
unset RIDGE_PRESENT_PROFILE RIDGE_PACING_BUILD
export RIDGE_PRESENT_TEST=phase2ms
if ! python3 "$RIDGE_ROOT/launcher/settings.py" launch --root "$RIDGE_ROOT"; then
    printf '%s\n' 'Pacing test failed. See the error above and diagnostics/launcher-game.log.'
    read -r ridge_pacing_reply
    exit 1
fi
printf '%s\n' 'Test recording saved under diagnostics/frame-times. You may close this window.'
