#!/usr/bin/env python3
"""Select R21 evidence windows; CPU timing candidates are not display misses."""
import argparse,csv,json
from pathlib import Path

def windows(path):
    with path.open() as stream:
        rows=[r for r in csv.DictReader(stream) if r.get('present_end_ns')]
    events=[];previous_marker='0'
    for r in rows:
        marker=r.get('event_marker','0')
        manual=marker!='0' and marker!=previous_marker
        previous_marker=marker
        candidate=int(r.get('handoff_candidate','0'))
        if manual or candidate:
            events.append(dict(frame=int(r['frame']),wall_s=float(r['wall_s']),
                               marker=int(marker) if manual else 0,candidate_bits=candidate))
    merged=[]
    for event in events:
        lo=max(0,event['wall_s']-10);hi=event['wall_s']+3
        if merged and lo<=merged[-1]['end_s']:
            merged[-1]['end_s']=max(hi,merged[-1]['end_s']);merged[-1]['events'].append(event)
        else:merged.append(dict(start_s=lo,end_s=hi,events=[event]))
    for window in merged:
        selected=[r for r in rows if window['start_s']<=float(r['wall_s'])<=window['end_s']]
        window['first_frame']=int(selected[0]['frame']);window['last_frame']=int(selected[-1]['frame'])
        window['post_window_complete']=float(rows[-1]['wall_s'])>=window['end_s']
        window['callback_skips']=sum(int(r.get('callback_skipped',0))for r in selected)
        window['capture_frames']=[int(r['frame'])for r in selected if float(r.get('marker_ms',0))>0]
        window['telemetry_dropped_max']=max(int(r.get('telemetry_dropped',0))for r in selected)
    return dict(source=str(path),evidence='CPU/callback correlation only; physical display unresolved',
                frames=len(rows),windows=merged)

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__);parser.add_argument('csv',type=Path)
    args=parser.parse_args();print(json.dumps(windows(args.csv),indent=2))
