#!/usr/bin/env python3
"""Summarize player simulation cadence from an existing local scene capture.
Guest-cycle time and host wall time are deliberately reported separately.
"""
import argparse
from collections import Counter
import json
from pathlib import Path

CLOCK = 33868800
EXE_SHA = 'bde353330bf4032d8c4b86a04dbcc78c95e6b2c5aa17dc15b79de613b52cf8c5'

def analyze(path):
    previous = None
    histograms = {key: Counter() for key in ('race_entries', 'car_entries', 'sim_entries')}
    count = cycles = host_ns = 0
    header = None
    with path.open() as stream:
        for line in stream:
            row = json.loads(line)
            if row.get('type') == 'header':
                header = row
            if row.get('type') != 'frame':
                continue
            if previous and all(f['state'] == 1 and f['phase'] == 3 and not f['paused'] for f in (previous, row)):
                if row['sequence'] != previous['sequence'] + 1:
                    raise ValueError('Missing scene boundary')
                dc = row['cycles'] - previous['cycles']
                dh = row['host_ns'] - previous['host_ns']
                if dc <= 0 or dh <= 0:
                    raise ValueError('Non-increasing capture clock')
                count += 1
                cycles += dc
                host_ns += dh
                for key, histogram in histograms.items():
                    delta = row[key] - previous[key]
                    if delta < 0:
                        raise ValueError('Counter reset within race')
                    histogram[delta] += 1
            previous = row
    if not header or header.get('version') != 1 or header.get('exe_sha256') != EXE_SHA:
        raise ValueError('Unsupported capture identity')
    if not count:
        raise ValueError('No consecutive unpaused phase-3 race boundaries')
    return dict(boundaries=count, guest_cycle_seconds=cycles / CLOCK,
                boundaries_per_guest_cycle_second=count * CLOCK / cycles,
                host_seconds=host_ns / 1e9, boundaries_per_host_second=count * 1e9 / host_ns,
                counter_deltas={key: dict(sorted(value.items())) for key, value in histograms.items()},
                scope='Player routine counters, not proof of AI/internal solver cadence; host rate depends on pacing/headless mode.')

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('capture', type=Path)
    print(json.dumps(analyze(parser.parse_args().capture), indent=2))
