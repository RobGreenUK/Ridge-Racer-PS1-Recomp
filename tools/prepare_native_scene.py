#!/usr/bin/env python3
"""Build a versioned local asset cache, replacing it only after successful export."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
ROOT=Path(__file__).resolve().parents[1]

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--build-dir',type=Path,default=ROOT/'build-macos')
    args=parser.parse_args()
    cache=args.build_dir.resolve()/'native-scene';cache.mkdir(parents=True,exist_ok=True)
    asset=cache/'course.rrassets';manifest=cache/'manifest.json'
    identity={name:hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in ['tools/extract_scene_assets.py','disc/SCUS-943.00','disc_probe.json']}
    previous={}
    if asset.is_file() and manifest.is_file():
        try: previous=json.loads(manifest.read_text())
        except ValueError: previous={}
        if previous.get('identity')==identity and previous.get('size')==asset.stat().st_size:
            print('Native scene asset cache is current.');return
    vram=cache/'vram.bin'
    source_changed=any(previous.get('identity',{}).get(k)!=identity[k] for k in ['disc/SCUS-943.00','disc_probe.json'])
    if source_changed or not vram.is_file() or vram.stat().st_size!=1048576:
        name=f'native-palette-{time.time_ns()}'
        from run_scene_validation import run
        run(name,headless=True,frames=850,build_dir=args.build_dir)
        source=ROOT/'diagnostics/runs'/name/'vram.bin'
        if source.stat().st_size!=1048576:raise RuntimeError('Incomplete palette capture')
        vram.write_bytes(source.read_bytes())
    with tempfile.TemporaryDirectory(prefix='extract-',dir=cache) as tmp:
        output=Path(tmp)/'course.rrassets'
        subprocess.run([sys.executable,str(ROOT/'tools/extract_scene_assets.py'),str(output),'--vram',str(vram)],cwd=ROOT,check=True)
        os.replace(output,asset)
    document=dict(identity=identity,size=asset.stat().st_size)
    temporary=cache/'manifest.json.tmp';temporary.write_text(json.dumps(document,indent=2)+'\n');os.replace(temporary,manifest)
    print('Native scene assets prepared locally.')
if __name__=='__main__':main()
