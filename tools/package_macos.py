#!/usr/bin/env python3
"""Create a private, relocatable Apple Silicon build from locally built binaries."""
import argparse, hashlib, json, os, shutil, subprocess, sys, tomllib
from pathlib import Path
from package_notices import stage_notices
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT))
from launcher.settings import serialize, DEFAULTS, save_settings

def run(*args):
    return subprocess.check_output([str(x) for x in args],text=True,stderr=subprocess.PIPE)
def macho(p):
    if not p.is_file() or p.is_symlink(): return False
    with p.open('rb') as f:return f.read(4) in (b'\xcf\xfa\xed\xfe',b'\xca\xfe\xba\xbe')
def package(name,viewer):
    if Path(name).name!=name:raise ValueError('Name must be one folder name')
    dest=ROOT/'dist'/name
    dest.mkdir(parents=True,exist_ok=False)
    build=dest/'build-macos';build.mkdir()
    for n in ['RidgeRacer_Recompiled','RidgeScenePacingTest','Ridge Racer.app','bios','mods','assets']:
        src=ROOT/'build-macos'/n
        if src.is_dir():shutil.copytree(src,build/n,ignore=shutil.ignore_patterns('.DS_Store','state.toml'))
        else:shutil.copy2(src,build/n)
    shutil.copy2(viewer,build/'RidgeScenePreview')
    (build/'native-scene').mkdir();shutil.copy2(ROOT/'build-macos/native-scene/course.rrassets',build/'native-scene/course.rrassets')
    for n in ['launcher','scripts']:
        shutil.copytree(ROOT/n,dest/n,ignore=shutil.ignore_patterns('__pycache__','.DS_Store'))
    for n in ['game.toml','game_options.toml','CMakeLists.txt','Test Ridge Racer Pacing.command']:shutil.copy2(ROOT/n,dest/n)
    shutil.copytree(ROOT/'Ridge Racer (USA)',dest/'Ridge Racer (USA)',ignore=shutil.ignore_patterns('.DS_Store'))
    shutil.copytree(ROOT/'disc',dest/'disc',ignore=shutil.ignore_patterns('.DS_Store'))
    (dest/'saves').mkdir();(dest/'diagnostics').mkdir()
    config=tomllib.loads((dest/'game.toml').read_text());config['game']['disc']='Ridge Racer (USA)/Ridge Racer (USA).cue'
    (dest/'game.toml').write_text(serialize(config))
    settings=dict(DEFAULTS,aspect='16:9',nativeScene=True,nativeWidth=1920,nativeHeight=1080,nativeFps=0,fullscreen=1,perspective=True)
    save_settings(build/'settings.toml',settings)
    prefix=dest/'runtime/python';shutil.copytree(Path(sys.prefix).resolve(),prefix,symlinks=False,ignore=shutil.ignore_patterns('site-packages','__pycache__','_CodeSignature'))
    lib=build/'lib';lib.mkdir()
    pending=[p for p in dest.rglob('*') if macho(p)];seen=set()
    while pending:
        p=pending.pop()
        if p in seen:continue
        seen.add(p)
        for line in run('otool','-L',p).splitlines()[1:]:
            dep=line.strip().split(' (')[0]
            if not dep.startswith('/opt/homebrew/'):continue
            target=prefix/'Python' if Path(dep).name=='Python' else lib/Path(dep).name
            if not target.exists():shutil.copy2(Path(dep).resolve(),target);pending.append(target)
            replacement='@loader_path/'+os.path.relpath(target,p.parent)
            run('install_name_tool','-change',dep,replacement,p)
        if len(run('otool','-D',p).splitlines())>1:run('install_name_tool','-id','@loader_path/'+p.name,p)
    for p in seen:
        assert '/opt/homebrew/' not in run('otool','-L',p),p
        run('codesign','--force','--sign','-',p)
    run('codesign','--force','--deep','--sign','-',build/'Ridge Racer.app')
    play=dest/'Play.command';play.write_text('#!/bin/sh\nset -eu\nRIDGE_ROOT=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)\nexec "$RIDGE_ROOT/build-macos/Ridge Racer.app/Contents/MacOS/RidgeRacerLauncher"\n');play.chmod(0o755)
    # The optional pacing launcher must use the bundled interpreter too.
    p=dest/'scripts/macos-env.sh';p.write_text(p.read_text()+'\nexport PYTHONHOME="$RIDGE_ROOT/runtime/python"\nexport PYTHONNOUSERSITE=1\nexport PATH="$PYTHONHOME/bin:$PATH"\n')
    (prefix/'bin/python3').symlink_to('python3.13')
    shutil.copy2(ROOT/'docs/PLAY.md',dest/'READ ME.md')
    shutil.copy2(ROOT/'THIRD_PARTY_NOTICES.md',dest/'THIRD_PARTY_NOTICES.md')
    stage_notices(dest)
    return dest
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--name',default='macos');p.add_argument('--viewer',type=Path,default=ROOT/'build-macos/RidgeScenePreview');a=p.parse_args();print(package(a.name,a.viewer))
