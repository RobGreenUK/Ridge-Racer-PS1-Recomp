#!/usr/bin/env python3
"""Stage a local playable Windows build. Output contains game data; never publish it."""
import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tomllib

from package_notices import stage_notices
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from launcher.settings import serialize

def package(name="windows"):
    if not name or Path(name).name != name:
        raise SystemExit("Package name must be a single folder name")
    build=ROOT/'build-windows'
    destination=ROOT/'dist'/name
    if destination.exists():
        raise SystemExit(f'{destination} already exists; keep it or move it before repackaging')
    destination.mkdir(parents=True)
    for name in ['RidgeRacer_Recompiled.exe','RidgeScenePreview.exe','RidgeTransportCheck.exe']:
        shutil.copy2(build/name,destination/name)
    for name in ['bios','mods','assets']:
        if (build/name).exists():shutil.copytree(build/name,destination/name,ignore=shutil.ignore_patterns('state.toml','.DS_Store'))
    (destination/'native-scene').mkdir()
    shutil.copy2(build/'native-scene/course.rrassets',destination/'native-scene/course.rrassets')
    shutil.copytree(ROOT/'Ridge Racer (USA)',destination/'Ridge Racer (USA)')
    shutil.copytree(ROOT/'disc',destination/'disc')
    config=tomllib.loads((ROOT/'game.toml').read_text())
    config['game']['disc']='Ridge Racer (USA)/Ridge Racer (USA).cue'
    (destination/'game.toml').write_text(serialize(config))
    shutil.copy2(ROOT/'game_options.toml',destination/'game_options.toml')
    for name in ['Launch.ps1','Play.cmd','ProcessHost.ps1']:
        shutil.copy2(ROOT/'launcher/windows'/name,destination/name)
    shutil.copy2(ROOT/'docs/PLAY.md',destination/'READ ME.md')
    shutil.copy2(ROOT/'THIRD_PARTY_NOTICES.md',destination/'THIRD_PARTY_NOTICES.md')
    for folder in ['saves','diagnostics']:(destination/folder).mkdir()
    stage_notices(destination)
    manifest={}
    for path in sorted(destination.rglob('*')):
        if path.is_file():manifest[str(path.relative_to(destination))]=hashlib.sha256(path.read_bytes()).hexdigest()
    (destination/'build-manifest.json').write_text(json.dumps(dict(source_commit=subprocess.check_output(['git','rev-parse','HEAD'],cwd=ROOT,text=True).strip(),files=manifest),indent=2)+'\n')
    print(destination)
if __name__=='__main__':
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--name',default='windows')
    package(parser.parse_args().name)
