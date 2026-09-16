#!/usr/bin/env python3
"""Read-only SCUS-94300 timing sampler for the PSXRecomp debug server.
Start the game with --no-launcher --debug-port 9945; enter a race manually.
These addresses apply only to the executable with EXPECTED_SHA256 below.
Samples use separate requests, so counters are approximate, not atomic.
"""
import argparse
import hashlib
import json
from pathlib import Path
import socket
import time

EXPECTED_SHA256 = 'bde353330bf4032d8c4b86a04dbcc78c95e6b2c5aa17dc15b79de613b52cf8c5'
FIELDS = {'loop': 0x8007F114, 'wait_scale': 0x80130CF0,
          'state': 0x801D6D28, 'race_calls': 0x80176AE4,
          'race_phase_candidate': 0x801DCB7C, 'pause_candidate': 0x801DB000}


def request(port, cmd, **args):
    with socket.create_connection(('127.0.0.1', port), timeout=5) as connection:
        connection.sendall((json.dumps(dict(id=1, cmd=cmd, **args)) + '\n').encode())
        with connection.makefile() as stream:
            reply = json.loads(stream.readline())
    if not reply.get('ok'):
        raise RuntimeError(reply)
    return reply


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--port', type=int, default=9945)
    parser.add_argument('--seconds', type=float, default=10)
    parser.add_argument('--exe', type=Path, default=Path(__file__).resolve().parents[1] / 'disc/SCUS-943.00')
    args = parser.parse_args()
    if hashlib.sha256(args.exe.read_bytes()).hexdigest() != EXPECTED_SHA256:
        parser.error('Unsupported executable: timing addresses are USA revision specific')
    if not 0 < args.seconds <= 300:
        parser.error('--seconds must be between 0 and 300')
    start = time.monotonic()
    while True:
        sample = {'seconds': round(time.monotonic() - start, 6),
                  'guest_frame': request(args.port, 'frame')['frame']}
        for name, address in FIELDS.items():
            data = request(args.port, 'read_ram', addr=hex(address), len=2)
            sample[name] = int.from_bytes(bytes.fromhex(data['hex']), 'little')
        print(json.dumps(sample), flush=True)
        if time.monotonic() - start >= args.seconds:
            break
        time.sleep(max(0, min(1, args.seconds - (time.monotonic() - start))))


if __name__ == '__main__':
    main()
