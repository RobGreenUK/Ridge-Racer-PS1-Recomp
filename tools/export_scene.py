#!/usr/bin/env python3
"""Convert a bounded scene capture into a native diagnostic preview recording.
The ribbon is derived from collision/navigation nodes, not the original road mesh.
The car is a proxy box. Source captures and derived recordings stay local.
"""
import argparse
import json
import io
import math
from pathlib import Path
import struct

EXE_SHA = 'bde353330bf4032d8c4b86a04dbcc78c95e6b2c5aa17dc15b79de613b52cf8c5'
CLOCK = 33868800


def quaternion(m):
    """Row-major rotation matrix to normalized (x,y,z,w)."""
    trace = m[0] + m[4] + m[8]
    if trace > 0:
        s = math.sqrt(trace + 1) * 2
        q = ((m[7]-m[5])/s, (m[2]-m[6])/s, (m[3]-m[1])/s, s/4)
    else:
        i = max(range(3), key=lambda i: m[i*3+i])
        j, k = (i+1) % 3, (i+2) % 3
        s = math.sqrt(max(0, 1+m[i*3+i]-m[j*3+j]-m[k*3+k])) * 2
        if s < 1e-8:
            raise ValueError('Degenerate camera rotation')
        q = [0., 0., 0., (m[k*3+j]-m[j*3+k])/s]
        q[i], q[j], q[k] = s/4, (m[j*3+i]+m[i*3+j])/s, (m[k*3+i]+m[i*3+k])/s
    length = math.sqrt(sum(x*x for x in q))
    return [x/length for x in q]


def model_poses(frame):
    camera=struct.unpack_from('<3i',bytes.fromhex(frame['camera_position']))
    q=quaternion([x/4096 for x in struct.unpack_from('<9h',bytes.fromhex(frame['camera_matrix']))])
    inverse=[-q[0],-q[1],-q[2],q[3]]
    def rotate(p):
        x,y,z,w=inverse
        t=(2*(y*p[2]-z*p[1]),2*(z*p[0]-x*p[2]),2*(x*p[1]-y*p[0]))
        return (p[0]+w*t[0]+y*t[2]-z*t[1],p[1]+w*t[1]+z*t[0]-x*t[2],p[2]+w*t[2]+x*t[1]-y*t[0])
    result=[]
    for model in frame.get('models',[]):
        world=bool(model['model']&0x80000000)
        r=[v/4096 for v in struct.unpack('<10h',struct.pack('<5I',*model['rotation']))[:9]]
        matrix=[0.]*9
        for j in range(3):
            column=(r[j],r[j+3],r[j+6]) if world else rotate((r[j],r[j+3],r[j+6]))
            for i in range(3):matrix[i*3+j]=column[i]
        relative=rotate([x/4 for x in model['translation']])
        position=[x/4 for x in model['translation']] if world else [camera[i]+relative[i] for i in range(3)]
        result.append(((model['owner']<<32)|model['site'],model['model']&0x7fffffff,*position,*matrix,model.get('palette_offset',0)))
    return result


def export(source, destination, state=1):
    tracks, frames = {}, []
    header = None
    with source.open() as stream:
        for line in stream:
            row = json.loads(line)  # Reject partial captures; do not silently truncate.
            if row['type'] == 'header':
                header = row
            elif row['type'] == 'track':
                tracks[row['address']] = row
            elif row['type'] == 'frame':
                frames.append(row)
    if not header or header.get('version') != 1 or header.get('exe_sha256') != EXE_SHA:
        raise ValueError('Unsupported capture header')
    race = [f for f in frames if f['state'] == state and f['track'] in tracks]
    if len(race) < 2:
        raise ValueError('Need at least two playable-race samples with a track')
    # Choose the longest contiguous race/track session. Never bridge a restart,
    # state transition, track replacement or guest-clock rollback.
    sessions, current = [], []
    for frame in frames:
        eligible = frame['state'] == state and frame['track'] in tracks
        if current and (not eligible or frame['track'] != current[-1]['track'] or
                        frame['mirror_x'] != current[-1]['mirror_x'] or
                        frame['cycles'] <= current[-1]['cycles']):
            sessions.append(current)
            current = []
        if eligible:
            current.append(frame)
    if current:
        sessions.append(current)
    selected = max(sessions, key=len)
    if len(selected) < 2:
        raise ValueError('Race session is too short')
    track = tracks[selected[0]['track']]
    raw = bytes.fromhex(track['data'])
    if len(raw) != track['count']*20 or not 3 <= track['count'] <= 368:
        raise ValueError('Invalid track length')
    ribbon = []
    for offset in range(0, len(raw), 20):
        x, z, y, heading, bank, width, _, _ = struct.unpack_from('<iihhhhhh', raw, offset)
        # USA edge consumer 0x80017150: reflected X, >>14 fixed-point X/Z,
        # width *2, trig /4096, /16, /2 => width/16 per side. Banking is
        # deliberately omitted from this diagnostic ribbon.
        ribbon.append((selected[0]['mirror_x'] - math.trunc(x/16384), -y,
                       math.trunc(z/16384), width/16))
    # Validate/encode fully before creating the destination. Bounded by the
    # capture limit; invalid inputs never leave an apparently usable recording.
    if len(selected) > 18000:
        raise ValueError("Capture exceeds frame limit")
    with io.BytesIO() as out:
        out.write(struct.pack('<8sII', b'RRSCENE5', len(ribbon), len(selected)))
        for node in ribbon:
            out.write(struct.pack('<4f', *node))
        origin = selected[0]['cycles']
        for f in selected:
            cam = struct.unpack_from('<8i', bytes.fromhex(f['camera_position']))
            player = struct.unpack_from('<12i', bytes.fromhex(f['player']))
            m = [x/4096 for x in struct.unpack_from('<9h', bytes.fromhex(f['camera_matrix']))]
            if any(abs(x) > 1.02 for x in m):
                raise ValueError('Invalid camera matrix')
            flags = f['phase'] | (f['paused'] << 16) | (bool(f.get('night', False)) << 17)
            if f.get('state') == 5:
                flags |= 0x40000 | ((f.get('replay_camera', 0) & 15) << 20) | ((f.get('replay_target', 0) & 15) << 24)
            out.write(struct.pack('<dI11f', (f['cycles']-origin)/CLOCK, flags,
                                  *cam[:3], *quaternion(m), *player[4:7], player[9]*math.tau/4096))
            poses=model_poses(f)
            if len(poses)>512:raise ValueError('Too many model poses')
            out.write(struct.pack('<I',len(poses)))
            for pose in poses:out.write(struct.pack('<QI12fI',*pose))
            out.write(struct.pack('<3f4I',*f.get('sky',[0]*7)))
            hud=f.get('hud',[])
            if len(hud)>2048:raise ValueError('Oversized HUD')
            out.write(struct.pack('<I',len(hud)))
            out.write(struct.pack('<'+str(len(hud))+'I',*hud))
        encoded = out.getvalue()
    with destination.open('xb') as destination_stream:
        destination_stream.write(encoded)
    duration = (selected[-1]['cycles']-selected[0]['cycles'])/CLOCK
    summary = dict(frames=len(selected), seconds=duration, nodes=len(ribbon),
                   first_sequence=selected[0]["sequence"], last_sequence=selected[-1]["sequence"],
                   car_calls=selected[-1]['car_entries']-selected[0]['car_entries'],
                   sim_calls=selected[-1]['sim_entries']-selected[0]['sim_entries'],
                   paused_samples=sum(bool(f['paused']) for f in selected))
    print(json.dumps(summary, indent=2))
    return summary


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('capture', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument("--state",type=int,choices=(1,5),default=1,help="Race (1) or verified replay (5)")
    args = parser.parse_args()
    export(args.capture, args.output,args.state)
