"""Own the experimental viewer and game as one launch, retaining normal saves."""
import os
import json
import hashlib
from datetime import datetime
from pathlib import Path
import subprocess
import shutil
import tomllib
import tempfile
import time


def stop(process):
    if process is not None and process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait()


def stage_companion(root, directory, game_command):
    """Give the runtime a private video config; persistent game paths stay shared."""
    # Runtime settings are resolved beside the executable, independently of cwd.
    # A real copy is necessary because the runtime resolves executable symlinks.
    host=Path(directory);build=root/'build-macos'
    binary=host/Path(game_command[0]).name
    shutil.copy2(game_command[0],binary)
    for name in ('assets','bios','lib'):
        if (build/name).exists():(host/name).symlink_to(build/name,target_is_directory=True)
    if (build/'mods').exists():shutil.copytree(build/'mods',host/'mods')
    settings=build/'settings.toml'
    config=tomllib.loads(settings.read_text()) if settings.exists() else {}
    config.setdefault('video',{}).update(fullscreen=0,window_width=640,supersampling=1,
                                        frame_interpolation=False,frame_interpolation_fps=0)
    # Use the same serializer as the launcher, preserving controls, paths and audio.
    try:
        from launcher.settings import serialize
    except ImportError:
        from settings import serialize
    (host/'settings.toml').write_text(serialize(config))
    return [str(binary),*game_command[1:]]


def launch(root, game_command, values, env, log, *, physics_capture=None):
    profiling = env.get('RIDGE_PRESENT_PROFILE') == '1'
    presentation_test = env.get('RIDGE_PRESENT_TEST', '')
    if presentation_test not in ('', 'phase2ms'):
        raise ValueError('Unknown presentation test')
    if profiling and presentation_test:
        raise ValueError('Run the presentation test separately from stack profiling')
    comparison = env.get('RIDGE_PACING_BUILD', '')
    if comparison not in ('', 'pre-mirror') or (comparison and not presentation_test):
        raise ValueError('The pre-mirror comparison requires the pacing test launcher')
    viewer = root / ('build-macos/RidgeSceneProfile' if profiling else 'build-macos/RidgeScenePreview')
    if presentation_test:
        viewer = root / ('build-macos/RidgeScenePreMirror' if comparison else 'build-macos/RidgeScenePacingTest')
        if not viewer.is_file():
            raise ValueError('Build the pacing test first: sh scripts/build-pacing-test.sh')
    if profiling and not viewer.is_file():
        raise ValueError('Build the presentation profiler first: sh scripts/build-presentation-profiler.sh')
    assets = root / 'build-macos/native-scene/course.rrassets'
    if not viewer.is_file() or not assets.is_file():
        raise ValueError('Prepare native scene mode first: sh scripts/prepare-native-scene.sh')
    # Short private path fits macOS sockaddr_un, independently of project path.
    with tempfile.TemporaryDirectory(prefix='ridge-scene-', dir='/tmp') as directory:
        socket = str(Path(directory) / 'scene')
        child_env = dict(env, RIDGE_SCENE_SOCKET=socket, RIDGE_SCENE_INPUT='1',
                         RIDGE_NATIVE_SCENE='1', RIDGE_SCENE_FULL_COURSE='1' if values['nativeFullCourse'] else '0', RIDGE_SCENE_CAR_DISTANCE=str(values['nativeCarDistance']), SDL_RENDER_DRIVER='opengl')
        # Hidden from creation; the runtime retains its GL context, original
        # drawing and deadline pacer. Explicit opt-out is useful for debugging.
        child_env['PSX_HIDDEN_COMPANION'] = '0' if env.get('RIDGE_VISIBLE_COMPANION') == '1' else '1'
        if presentation_test:
            child_env['RIDGE_HANDOFF_TRACE'] = env.get('RIDGE_HANDOFF_TRACE', '1')
        # A normal launch never inherits a diagnostic route or recording request.
        for name in ['RIDGE_PHYSICS_ENGINE', 'RIDGE_PHYSICS_TRACE', 'RIDGE_MOVEMENT_CAPTURE', 'RIDGE_PHYSICS_SHADOW', 'RIDGE_PHYSICS_CAPTURE', 'RIDGE_PHYSICS_CAPTURE_LIMIT', 'RIDGE_PHYSICS_CAPTURE_SKIP', 'RIDGE_INPUT_REPLAY', 'RIDGE_SCENE_CAPTURE', 'RIDGE_VRAM_DUMP', 'RIDGE_RAM_DUMP', 'RIDGE_SKY_DUMP', 'RIDGE_TEST_DRIVE', 'RIDGE_TEST_SPEED', 'RIDGE_VRAM_DUMP_FRAME']:
            child_env.pop(name, None)
        if physics_capture is not None:
            child_env.update(RIDGE_PHYSICS_CAPTURE=str(physics_capture),
                             RIDGE_PHYSICS_CAPTURE_LIMIT='18000', RIDGE_PHYSICS_SHADOW='1')
        recording = root / 'diagnostics/frame-times' / datetime.now().strftime('%Y%m%d-%H%M%S-%f')
        recording.mkdir(parents=True)
        (recording / 'build.json').write_text(json.dumps({'viewer': str(viewer), 'comparison': comparison or 'current', 'sha256': hashlib.sha256(viewer.read_bytes()).hexdigest(), 'companion_sha256': hashlib.sha256(Path(game_command[0]).read_bytes()).hexdigest(), 'handoff_trace_version': 1, 'hidden_companion': child_env['PSX_HIDDEN_COMPANION'] == '1'}, indent=2)+'\n')
        (recording / 'settings.json').write_text(json.dumps(values, indent=2)+'\n')
        command = [str(viewer), '--live', socket, '--assets', str(assets),
                   '--metrics', str(recording / 'frames.csv'), '--game-camera', '--control', '--fps', str(values['nativeFps']),
                   '--vsync', values['vsync'], '--width', str(values['nativeWidth']), '--height', str(values['nativeHeight'])]
        if values['frameGraph']:
            command.append('--frame-graph')
        if not values['perspective']:
            command.append('--affine-textures')
        if not values['nativeFullCourse']:
            command.append('--legacy-distance')
        if values['fullscreen']:
            command.append('--fullscreen')
        companion_command=stage_companion(root,directory,game_command)
        scene = game = profiler = None
        try:
            scene = subprocess.Popen(command, cwd=root, env=child_env, stdout=log, stderr=log)
            if profiling:
                try:
                    from launcher.presentation_profile import PresentationProfile
                except ImportError:
                    from presentation_profile import PresentationProfile
                profiler = PresentationProfile(scene.pid, recording)
            deadline = time.monotonic() + 10
            while not Path(socket).exists():
                if scene.poll() is not None or time.monotonic() > deadline:
                    raise RuntimeError('Native renderer failed to start; see launcher-game.log')
                time.sleep(.02)
            game = subprocess.Popen(companion_command, cwd=root, env=child_env, stdout=log, stderr=log)
            (recording / 'processes.json').write_text(json.dumps({'renderer_pid': scene.pid, 'companion_pid': game.pid}, indent=2)+'\n')
            while game.poll() is None and scene.poll() is None:
                time.sleep(.1)
            for process, name in [(game, 'Game'), (scene, 'Native renderer')]:
                if process.poll() not in (None, 0):
                    raise RuntimeError(f'{name} exited with code {process.returncode}; see launcher-game.log')
        finally:
            stop(game)
            stop(scene)
            if profiler is not None:
                profiler.close()
            metrics = recording / 'frames.csv'
            if metrics.exists():
                try:
                    subprocess.run([os.sys.executable, str(root / 'tools/analyze_frame_times.py'),
                                    str(metrics), '--fps', str(values['nativeFps'])],
                                   cwd=root, stdout=log, stderr=log, timeout=15, check=False)
                except (OSError, subprocess.TimeoutExpired):
                    pass  # Raw CSV remains usable if post-processing fails.
