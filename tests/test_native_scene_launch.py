import importlib.util
from pathlib import Path
import tempfile
import tomllib
import unittest
from unittest.mock import Mock, patch
from launcher.settings import DEFAULTS
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('native_scene',ROOT/'launcher/native_scene.py')
native=importlib.util.module_from_spec(spec);spec.loader.exec_module(native)

class NativeLaunchTests(unittest.TestCase):
    def test_pacing_trial_rejects_unknown_or_combined_modes(self):
        for env in [{'RIDGE_PACING_BUILD':'pre-mirror'}, {'RIDGE_PRESENT_TEST':'phase2ms','RIDGE_PACING_BUILD':'unknown'}, {'RIDGE_PRESENT_TEST':'unknown'}, {'RIDGE_PRESENT_TEST':'phase2ms','RIDGE_PRESENT_PROFILE':'1'}]:
            with self.subTest(env=env), patch.object(native.subprocess,'Popen') as start:
                with self.assertRaises(ValueError):native.launch(ROOT,['game'],DEFAULTS,env,None)
                start.assert_not_called()

    def test_profile_start_failure_stops_viewer_before_game_start(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'build-macos/native-scene').mkdir(parents=True)
            (root/'build-macos/RidgeSceneProfile').touch()
            (root/'build-macos/native-scene/course.rrassets').touch()
            (root/'game').write_bytes(b'test executable')
            child=Mock(pid=123);child.poll.return_value=None
            with patch.object(native,'stage_companion',return_value=['game']), \
                 patch.object(native.subprocess,'Popen',return_value=child) as start, \
                 patch('launcher.presentation_profile.PresentationProfile',side_effect=OSError('sampler unavailable')):
                with self.assertRaisesRegex(OSError,'sampler unavailable'):
                    native.launch(root,[str(root/'game')],DEFAULTS,{'RIDGE_PRESENT_PROFILE':'1'},None)
            start.assert_called_once()
            self.assertEqual(start.call_args.args[0][0],str(root/'build-macos/RidgeSceneProfile'))
            child.terminate.assert_called_once()
            child.wait.assert_called_once_with(timeout=5)

    def test_missing_assets_does_not_start_game(self):
        with tempfile.TemporaryDirectory() as tmp,patch.object(native.subprocess,'Popen') as popen:
            with self.assertRaisesRegex(ValueError,'prepare-native-scene'):
                native.launch(Path(tmp),['game'],DEFAULTS,{},None)
            popen.assert_not_called()

    def test_companion_is_windowed_without_overwriting_saved_settings(self):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);build=root/'build-macos';build.mkdir()
            binary=build/'RidgeRacer_Recompiled';binary.write_bytes(b'executable')
            (build/'bios').mkdir();(build/'assets').mkdir()
            (build/'mods').mkdir();(build/'mods/state.toml').write_text('enabled=true')
            settings=build/'settings.toml'
            original='[video]\nfullscreen=2\nwindow_width=3840\nsupersampling=4\n[audio]\nvolume=0.7\n[memory_cards]\nslot1="/saved/card.mcd"\n'
            settings.write_text(original)
            host=root/'companion';host.mkdir()
            args=[str(binary),'--disc','disc.cue','--memcard-dir',str(root/'saves')]
            command=native.stage_companion(root,host,args)
            config=tomllib.loads((host/'settings.toml').read_text())
            self.assertEqual(config['video']['fullscreen'],0)
            self.assertEqual(config['video']['window_width'],640)
            self.assertEqual(config['video']['supersampling'],1)
            self.assertEqual(config['audio']['volume'],.7)
            self.assertEqual(config['memory_cards']['slot1'],'/saved/card.mcd')
            self.assertEqual(settings.read_text(),original)
            self.assertEqual(command[1:],args[1:])
            self.assertEqual((host/'bios').resolve(),(build/'bios').resolve())
            self.assertEqual((host/'mods/state.toml').read_text(),'enabled=true')

    def test_viewer_exit_stops_only_owned_game(self):
        self.exercise_owned_launch(False)

    def test_pacing_trial_selects_separate_binary_without_sampler(self):
        self.exercise_owned_launch(True)

    def test_pre_mirror_selects_separate_binary(self):
        self.exercise_owned_launch(True, pre_mirror=True)

    def exercise_owned_launch(self, pacing_test, pre_mirror=False):
        with tempfile.TemporaryDirectory() as tmp:
            root=Path(tmp);(root/'build-macos/native-scene').mkdir(parents=True)
            (root/'build-macos/RidgeScenePreview').touch();(root/'build-macos/native-scene/course.rrassets').touch()
            (root/'build-macos/RidgeScenePacingTest').touch()
            (root/'build-macos/RidgeScenePreMirror').touch()
            (root/'build-macos/RidgeRacer_Recompiled').write_bytes(b'test executable')
            children=[]
            class Child:
                def __init__(self,command,**kwargs):
                    self.pid=1000+len(children)
                    self.command=command;self.env=kwargs['env'];self.returncode=None;self.stopped=False
                    if '--live' in command:Path(command[command.index('--live')+1]).touch()
                    children.append(self)
                def poll(self):
                    # Renderer closes normally after the game has started.
                    if self is children[0] and len(children)==2:self.returncode=0
                    return self.returncode
                def terminate(self):self.stopped=True;self.returncode=-15
                def wait(self,timeout=None):return self.returncode
            with patch.object(native.subprocess,'Popen',Child), patch('launcher.presentation_profile.PresentationProfile') as sampler:
                native.launch(root,[str(root/'build-macos/RidgeRacer_Recompiled')],dict(DEFAULTS,nativeFps=144,nativeWidth=1920,fullscreen=2),{'RIDGE_PACING_BUILD':'pre-mirror' if pre_mirror else '', 'RIDGE_INPUT_REPLAY':'unwanted','RIDGE_VRAM_DUMP':'unwanted','RIDGE_PHYSICS_CAPTURE':'unwanted','RIDGE_PHYSICS_SHADOW':'1','RIDGE_PRESENT_TEST':'phase2ms' if pacing_test else ''},None)
                sampler.assert_not_called()
            import json
            identity=json.loads(next((root/'diagnostics/frame-times').glob('*/build.json')).read_text())
            self.assertEqual(identity['comparison'], 'pre-mirror' if pre_mirror else 'current')
            self.assertEqual(identity['viewer'], children[0].command[0])
            self.assertEqual(len(children),2)
            self.assertEqual(Path(children[0].command[0]).name,'RidgeScenePreMirror' if pre_mirror else ('RidgeScenePacingTest' if pacing_test else 'RidgeScenePreview'))
            self.assertIn('--fullscreen',children[0].command)
            self.assertNotEqual(children[1].command[0],str(root/'build-macos/RidgeRacer_Recompiled'))
            self.assertIn('--affine-textures',children[0].command)
            self.assertFalse(children[0].stopped);self.assertTrue(children[1].stopped)
            self.assertNotIn('RIDGE_INPUT_REPLAY',children[1].env)
            self.assertNotIn('RIDGE_PHYSICS_CAPTURE',children[1].env)
            self.assertNotIn('RIDGE_PHYSICS_SHADOW',children[1].env)
            self.assertEqual(children[1].env['RIDGE_NATIVE_SCENE'],'1')
            self.assertEqual(children[1].env['PSX_HIDDEN_COMPANION'],'1')
            self.assertTrue(identity['hidden_companion'])
            self.assertEqual(len(identity['companion_sha256']),64)
            self.assertEqual(children[1].env['RIDGE_SCENE_CAR_DISTANCE'],'0')
            self.assertIn('144',children[0].command)
            self.assertIn('--metrics',children[0].command)
            self.assertEqual(children[0].command[children[0].command.index('--vsync')+1],'on')
            self.assertEqual(len(list((root/'diagnostics/frame-times').glob('*/settings.json'))),1)
if __name__=='__main__':unittest.main()
