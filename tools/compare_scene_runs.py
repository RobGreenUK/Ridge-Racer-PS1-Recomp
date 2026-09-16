#!/usr/bin/env python3
"""Compare captured guest fields at matching outer-loop boundaries.
Host timestamps and capture metadata are excluded; guest cycles are compared.
This is a selected-state oracle, not a whole-machine or full-physics proof.
"""
import argparse
import json
from pathlib import Path
FIELDS=['cycles','loop','state','phase','paused','wait_scale','pad','race_counter',
        'race_entries','car_entries','sim_entries','last_car','track','mirror_x',
        'player','camera_position','camera_matrix','entities']

def compare(a,b):
    def frames(p):return [r for line in p.read_text().splitlines() if (r:=json.loads(line)).get('type')=='frame']
    left,right=frames(a),frames(b)
    if len(left)!=len(right):raise ValueError(f'Frame counts differ: {len(left)} vs {len(right)}')
    if not left:raise ValueError('Empty comparison')
    differences={}
    for i,(x,y) in enumerate(zip(left,right)):
        for field in FIELDS:
            if x[field]!=y[field] and field not in differences:
                differences[field]=dict(sequence=i)
    result=dict(frames=len(left),matched=not differences,first_differences=differences,
                race_frames=sum(f['state']==1 for f in left),paused_frames=sum(bool(f['paused'])for f in left))
    print(json.dumps(result,indent=2));return not differences

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('a',type=Path);parser.add_argument('b',type=Path)
    args=parser.parse_args();raise SystemExit(0 if compare(args.a,args.b) else 1)
