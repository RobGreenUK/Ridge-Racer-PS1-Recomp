#!/usr/bin/env python3
"""Run isolated, repeatable scene captures. Per-run settings and saves are private."""
import argparse
import json
import os
from pathlib import Path
import shutil
import subprocess
import time

ROOT=Path(__file__).resolve().parents[1]

def run(name,live=None,headless=False,frames=1600,route=None,build_dir=None):
    build=Path(build_dir).resolve() if build_dir else ROOT/'build-macos'
    directory=ROOT/'diagnostics/runs'/name
    directory.mkdir(parents=True,exist_ok=False)
    runtime=directory/('RidgeRacer_Recompiled.exe' if os.name=='nt' else 'RidgeRacer_Recompiled')
    shutil.copy2(build/runtime.name,runtime)
    for item in ['bios','assets']:
        shutil.copytree(build/item,directory/item)
    shutil.copytree(build/'mods/bundled',directory/'mods/bundled')
    env=dict(os.environ,RIDGE_INPUT_REPLAY=str(route or ROOT/'tests/routes/driving.txt'),
             RIDGE_VRAM_DUMP=str(directory/'vram.bin'),RIDGE_SCENE_CAPTURE=str(directory/'capture.jsonl'),RIDGE_SCENE_CAPTURE_FRAMES=str(frames))
    if live:env['RIDGE_SCENE_SOCKET']=live
    else:env.pop('RIDGE_SCENE_SOCKET',None)
    cmd=[str(runtime),'--game',str(ROOT/'game.toml'),'--disc',os.environ.get('RIDGE_DISC',str(ROOT/'Ridge Racer (USA)/Ridge Racer (USA).cue')),
         '--no-launcher','--debug-port','9945','--memcard-dir',str(directory/'saves')]
    if headless:cmd.append('--headless')
    log=(directory/'runtime.log').open('w')
    process=subprocess.Popen(cmd,cwd=ROOT,env=env,stdout=log,stderr=subprocess.STDOUT)
    print(json.dumps(dict(pid=process.pid,directory=str(directory))),flush=True)
    try:
        deadline=time.monotonic()+max(300,frames/25+60)
        while process.poll() is None and time.monotonic()<deadline:
            capture=directory/'capture.jsonl'
            if capture.exists():
                # Producer flushes and closes at its requested cap. End on a
                # complete final record, not a file-size heuristic.
                with capture.open('rb') as stream:
                    stream.seek(max(0,capture.stat().st_size-1048576));tail=stream.read().splitlines()
                if tail:
                    try:last=json.loads(tail[-1])
                    except (json.JSONDecodeError,UnicodeDecodeError):last={}
                    if last.get('sequence')==frames-1:break
            time.sleep(.5)
        else:
            raise RuntimeError(f'Capture incomplete: process={process.poll()}')
    finally:
        if process.poll() is None:
            process.terminate()
            try:process.wait(timeout=5)
            except subprocess.TimeoutExpired:process.kill();process.wait()
        log.close()
    return directory

if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('name');parser.add_argument('--live');parser.add_argument('--headless',action='store_true')
    parser.add_argument('--route',type=Path,help='Alternate deterministic pad route')
    parser.add_argument('--frames',type=int,default=1600)
    args=parser.parse_args()
    if not 1<=args.frames<=18000:parser.error('frames must be 1..18000')
    if Path(args.name).name!=args.name:parser.error('name must be one directory name')
    run(args.name,args.live,args.headless,args.frames,args.route.resolve() if args.route else None)
