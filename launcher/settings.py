"""Game-owned launcher bridge; PSXRecomp settings.toml is the source of truth."""
from __future__ import annotations
import argparse
import datetime
import json
import math
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import tomllib

DEFAULTS = dict(aspect='4:3', width=1280, scale=2, fullscreen=0,
                filtering='nearest', antialiasing=True, perspective=False,
                vsync='on', blending=False,
                target=0, lowLatency=True, rewind=False, nativeScene=False,
                frameGraph=False, nativeFullCourse=True, nativeCarDistance=0, nativeFps=60, nativeWidth=960, nativeHeight=720)
KEYS = dict(aspect='aspect_ratio', width='window_width', scale='supersampling',
            fullscreen='fullscreen', filtering='texture_filtering',
            antialiasing='antialiasing', perspective='perspective_texturing',
            vsync='vsync',
            blending='frame_interpolation', target='frame_interpolation_fps',
            lowLatency='low_latency_input', rewind='rewind')
CHOICES = dict(nativeCarDistance=[0,1,2,3,4,5], aspect=['4:3', '16:9', 'adaptive'], scale=[1,2,3,4],
               fullscreen=[0,1,2], filtering=['nearest','bilinear'],
               vsync=['on','off','adaptive'],
               target=[0,60,90,120,144,165,240])

def validate(values):
    if set(values) != set(DEFAULTS):
        raise ValueError('Incomplete or unknown launcher settings')
    for key, value in values.items():
        if type(value) is not type(DEFAULTS[key]):
            raise ValueError(f'Invalid type for {key}')
        if key in CHOICES and value not in CHOICES[key]:
            raise ValueError(f'Invalid {key}: {value}')
    if not 640 <= values['width'] <= 3840:
        raise ValueError('Window width must be between 640 and 3840')
    if values['nativeFps'] != 0 and not 30 <= values['nativeFps'] <= 360:
        raise ValueError('Native scene frame rate must be 30–360, or 0 to match the display')
    if not 320 <= values['nativeWidth'] <= 7680 or not 240 <= values['nativeHeight'] <= 4320:
        raise ValueError('Native rendering resolution must be 320–7680 by 240–4320')
    if values['nativeScene']:
        ratio={'4:3':(4,3),'16:9':(16,9)}.get(values['aspect'])
        if not ratio or values['nativeWidth']*ratio[1]!=values['nativeHeight']*ratio[0]:
            raise ValueError('Native resolution must match the selected 4:3 or 16:9 aspect ratio')
    return values

def read_document(path):
    return tomllib.loads(path.read_text()) if path.exists() else {}

def read_settings(path):
    video = read_document(path).get('video', {})
    values = DEFAULTS.copy()
    native = read_document(path).get('ridge_native_scene', {})
    for key in ['frameGraph', 'nativeFullCourse', 'nativeScene', 'nativeFps', 'nativeWidth', 'nativeHeight', 'nativeCarDistance']:
        if key in native: values[key] = native[key]
    if 'nativeFullCourse' not in native: values['nativeCarDistance'] = 0
    for k, field in KEYS.items():
        if field in video:
            values[k] = video[field]
    if video.get('adaptive_view', False):
        values['aspect'] = 'adaptive'
    # Widescreen is exclusively activated by the title-owned mod in this pin.
    values['aspect'] = '4:3'
    values['blending'] = False
    values['target'] = 0
    state = read_document(path.parent / 'mods/state.toml')
    for feature in state.get('feature', []):
        if feature.get('package_id') == 'ridge.presentation' and feature.get('id') == 'view' and feature.get('enabled'):
            values['aspect'] = 'adaptive' if feature.get('values', {}).get('mode') == 'adaptive' else '16:9'
        if feature.get('package_id') == 'ridge.presentation' and feature.get('id') == 'motion':
            values['blending'] = bool(feature.get('enabled', False))
            values['target'] = int(feature.get('values', {}).get('target', '0'))
    if values['nativeScene']:
        values['perspective']=native.get('perspective',True)
        values['aspect']=native.get('aspect',values['aspect'])
        # Migrate the old independent width/height configuration once on read.
        if 'aspect' not in native:
            if values['aspect']=='adaptive': values['aspect']='16:9'
            a,b={'4:3':(4,3),'16:9':(16,9)}[values['aspect']]
            units=max((240+b-1)//b,min(7680//a,4320//b,round(values['nativeWidth']/a)))
            values['nativeWidth'],values['nativeHeight']=units*a,units*b
    # The upstream launcher can save legacy bool fullscreen values.
    values['fullscreen'] = int(values['fullscreen'])
    return validate(values)

def literal(value):
    if isinstance(value, bool): return 'true' if value else 'false'
    if isinstance(value, str): return json.dumps(value, ensure_ascii=False)
    if isinstance(value, (datetime.datetime, datetime.date, datetime.time)): return value.isoformat()
    if isinstance(value, int): return str(value)
    if isinstance(value, float):
        if not math.isfinite(value): raise ValueError('Non-finite setting')
        return repr(value)
    if isinstance(value, list): return '[' + ', '.join(literal(x) for x in value) + ']'
    if isinstance(value, dict):
        return '{' + ', '.join(json.dumps(k)+ ' = ' + literal(v) for k,v in value.items()) + '}'
    raise ValueError(f'Unsupported TOML value {type(value)}')

def serialize(document):
    # Inline nested tables preserve all unrelated settings semantically, including
    # controller arrays/tables, without inventing a second runtime config format.
    return '# Saved by Ridge Racer Service Menu\n' + '\n'.join(
        json.dumps(k) + ' = ' + literal(v) for k,v in document.items()) + '\n'

def save_settings(path, values):
    # A launcher left open across a rebuild may omit the new graph control.
    if set(DEFAULTS)-set(values)=={'frameGraph'}:
        values=dict(values,frameGraph=read_settings(path)['frameGraph'])
    validate(values)
    document = read_document(path)  # A malformed file fails without overwriting it.
    document['ridge_native_scene'] = {key: values[key] for key in ['frameGraph', 'nativeFullCourse', 'nativeScene', 'nativeFps', 'nativeWidth', 'nativeHeight', 'nativeCarDistance']}
    document['ridge_native_scene']['aspect'] = values['aspect']
    document['ridge_native_scene']['perspective'] = values['perspective']
    video = document.setdefault('video', {})
    for k, field in KEYS.items():
        video[field] = values[k]
    video['crt_filter'] = 'raw'
    video['scanlines'] = False
    video['renderer'] = 'opengl'
    video['adaptive_view'] = False
    video['aspect_ratio'] = '4:3'
    video['frame_interpolation'] = False
    video['frame_interpolation_fps'] = 0
    # Vertex correction is excluded: upstream documents partial-provenance seams.
    # Blending changes presentation, not the guest clock, scheduler or game logic.
    document.setdefault('launcher', {})['skip_launcher'] = False
    state_path = path.parent / 'mods/state.toml'
    state = read_document(state_path)
    if state and state.get('format_version') != 2:
        raise ValueError('Open advanced settings to migrate the legacy mod state before saving.')
    state['format_version'] = 2
    packages = state.setdefault('package', [])
    packages[:] = [p for p in packages if p.get('id') != 'ridge.presentation']
    packages.append(dict(id='ridge.presentation', version='1.0.0'))
    features = state.setdefault('feature', [])
    features[:] = [f for f in features if not (f.get('package_id') == 'ridge.presentation' and f.get('id') in ('view', 'motion'))]
    features.append(dict(package_id='ridge.presentation', id='view', enabled=values['aspect'] != '4:3',
                         values=dict(mode='adaptive' if values['aspect'] == 'adaptive' else 'wide')))
    features.append(dict(package_id='ridge.presentation', id='motion', enabled=values['blending'],
                         values=dict(target=str(values['target']))))
    # Validate both documents before replacing either. Writes are individually atomic.
    assert tomllib.loads(serialize(state)) == state
    content = serialize(document)
    assert tomllib.loads(content) == document
    atomic_write(state_path, serialize(state))
    atomic_write(path, content)

def atomic_write(path, content):
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix='.ridge-settings-')
    try:
        with os.fdopen(fd, 'w') as f:
            f.write(content); f.flush(); os.fsync(f.fileno())
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp): os.unlink(tmp)

def main():
    # Only the macOS interactive bridge needs POSIX file locking.
    # Windows packaging imports the portable TOML serializer from this module.
    import fcntl
    parser = argparse.ArgumentParser()
    parser.add_argument('action', choices=['read','save','launch','advanced'])
    parser.add_argument('--root', type=Path, required=True)
    args = parser.parse_args()
    root = args.root.resolve()
    settings = root / 'build-macos/settings.toml'
    if args.action == 'read':
        print(json.dumps(read_settings(settings))); return
    settings.parent.mkdir(parents=True, exist_ok=True)
    with (settings.parent / '.service-menu.lock').open('a') as lock:
        try:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise RuntimeError('A game launched by the service menu is already running. Close it before saving or launching again.')
        perform_action(args.action, root, settings)

def perform_action(action, root, settings):
    if action == 'save':
        save_settings(settings, json.load(sys.stdin)); return
    binary = root / 'build-macos/RidgeRacer_Recompiled'
    cue = Path(os.environ.get('RIDGE_DISC', str(root / 'Ridge Racer (USA)/Ridge Racer (USA).cue')))
    if not binary.is_file(): raise ValueError('Build the game first: sh scripts/build-macos.sh')
    if not cue.is_file(): raise ValueError(f'Disc not found: {cue}')
    env = os.environ.copy()
    # Retired experimental engine settings must not leak into normal launches.
    for name in ('RIDGE_PHYSICS_ENGINE', 'RIDGE_PHYSICS_TRACE', 'RIDGE_MOVEMENT_CAPTURE',
                 'RIDGE_PHYSICS_SHADOW', 'RIDGE_PHYSICS_CAPTURE',
                 'RIDGE_PHYSICS_CAPTURE_LIMIT', 'RIDGE_PHYSICS_CAPTURE_SKIP'):
        env.pop(name, None)
    env['RIDGERACERRECOMP_BUILD_DIR'] = str(root / 'build-macos')
    log = root / 'diagnostics/launcher-game.log'
    log.parent.mkdir(exist_ok=True)
    with log.open('a') as out:
        values = read_settings(settings)
        if env.get('RIDGE_PRESENT_PROFILE') == '1' and not values['nativeScene']:
            raise ValueError('Enable native scene rendering in the service menu before profiling presentation.')
        if env.get('RIDGE_PRESENT_TEST'):
            if not values['nativeScene'] or not values['fullscreen'] or values['vsync'] != 'on':
                raise ValueError('The pacing test requires native scene rendering, fullscreen and V-sync On.')
            if values['nativeFps'] != 0:
                raise ValueError('Select Display (0) for the native frame rate before the pacing test.')
        if action == 'launch' and values['nativeScene']:
            from native_scene import launch
            launch(root, [str(binary), '--game', str(root/'game.toml'), '--disc', str(cue), '--no-launcher'], values, env, out)
            return
        result = subprocess.run([str(binary), '--game', str(root/'game.toml'), '--disc', str(cue),
                                 '--launcher' if action == 'advanced' else '--no-launcher'],
                                cwd=root, env=env, stdout=out, stderr=out)
    if result.returncode:
        raise RuntimeError(f'Game exited with code {result.returncode}. See {log}')

if __name__ == '__main__':
    try: main()
    except Exception as exc:
        print(str(exc), file=sys.stderr); sys.exit(1)
