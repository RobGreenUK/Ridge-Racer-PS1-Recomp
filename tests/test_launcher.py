import copy
import tempfile
import fcntl
import json
import subprocess
import sys
import unittest
from unittest.mock import patch
import tomllib
from pathlib import Path
from launcher.settings import DEFAULTS, save_settings, read_settings, validate

class LauncherTests(unittest.TestCase):
    def test_pacing_trial_rejects_inapplicable_settings_before_launch(self):
        from launcher.settings import perform_action
        root=Path(self.temp.name);build=root/'build-macos';build.mkdir()
        (build/'RidgeRacer_Recompiled').touch();cue=root/'test.cue';cue.touch()
        for change in [dict(nativeScene=False),dict(fullscreen=0),dict(vsync='off'),dict(nativeFps=60)]:
            values=dict(DEFAULTS,nativeScene=True,fullscreen=2,vsync='on',nativeFps=0)
            values.update(change)
            with self.subTest(change=change), patch.dict('os.environ',{'RIDGE_PRESENT_TEST':'phase2ms','RIDGE_DISC':str(cue)}), \
                 patch('launcher.settings.read_settings',return_value=values), patch('launcher.settings.subprocess.run') as run:
                with self.assertRaises(ValueError):perform_action('launch',root,self.path)
                run.assert_not_called()

    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.path = Path(self.temp.name) / 'settings.toml'
    def test_all_display_modes_roundtrip_without_guest_clock_changes(self):
        for mode in ['4:3', '16:9', 'adaptive']:
            expected = dict(DEFAULTS, aspect=mode, width=1736, blending=True, target=120)
            save_settings(self.path, expected)
            self.assertEqual(read_settings(self.path), expected)
            doc = tomllib.loads(self.path.read_text())
            self.assertNotIn('runtime', doc)
            self.assertNotIn('native_vblank_rate', self.path.read_text())
            self.assertEqual(doc['video']['aspect_ratio'], '4:3')
    def test_native_scene_settings_roundtrip(self):
        for fps in (0, 60, 120, 144, 165):
            values = dict(DEFAULTS, nativeScene=True, nativeFps=fps, aspect="16:9", nativeWidth=2560, nativeHeight=1440)
            save_settings(self.path, values)
            self.assertEqual(read_settings(self.path), values)
            document = tomllib.loads(self.path.read_text())
            self.assertFalse(document['video']['frame_interpolation'])
        for change in (dict(nativeFps=-1), dict(nativeFps=361), dict(nativeHeight=0), dict(nativeScene=1)):
            with self.assertRaises(ValueError): validate(dict(DEFAULTS, **change))

    def test_graph_roundtrip_and_previous_launcher_save(self):
        values=dict(DEFAULTS,frameGraph=True)
        save_settings(self.path,values)
        self.assertTrue(read_settings(self.path)['frameGraph'])
        legacy={k:v for k,v in values.items() if k!='frameGraph'}
        legacy['nativeFps']=0
        save_settings(self.path,legacy)
        self.assertEqual(read_settings(self.path),dict(legacy,frameGraph=True))

    def test_retired_physics_selection_preserves_rendering_preferences(self):
        from launcher.settings import read_document, serialize
        values=dict(DEFAULTS,nativeScene=True,nativeFps=120,aspect='16:9',
                    nativeWidth=3840,nativeHeight=2160,perspective=True)
        for engine in ('native30','native60'):
            save_settings(self.path,values)
            document=read_document(self.path)
            document['ridge_native_scene']['physicsEngine']=engine
            self.path.write_text(serialize(document))
            self.assertEqual(read_settings(self.path),values)
            save_settings(self.path,read_settings(self.path))
            self.assertNotIn('physicsEngine',read_document(self.path)['ridge_native_scene'])

    def test_native_perspective_migration_and_removed_effects(self):
        self.path.write_text('[video]\nperspective_texturing=false\ncrt_filter="crt"\nscanlines=true\n[ridge_native_scene]\nnativeScene=true\n')
        values=read_settings(self.path)
        self.assertTrue(values['perspective']) # Previously native was always corrected.
        self.assertNotIn('screen',values);self.assertNotIn('scanlines',values)
        for enabled in (False,True):
            values['perspective']=enabled;save_settings(self.path,values)
            self.assertEqual(read_settings(self.path)['perspective'],enabled)
            video=tomllib.loads(self.path.read_text())['video']
            self.assertEqual(video['crt_filter'],'raw');self.assertFalse(video['scanlines'])

    def test_car_draw_distance_roundtrip_and_bounds(self):
        for distance in range(0,6):
            values=dict(DEFAULTS,nativeScene=True,nativeCarDistance=distance)
            save_settings(self.path,values)
            self.assertEqual(read_settings(self.path),values)
        for distance in (-1,6,2.5,True):
            with self.assertRaises(ValueError):validate(dict(DEFAULTS,nativeCarDistance=distance))
        self.path.write_text('[ridge_native_scene]\nnativeScene=true\n')
        self.assertEqual(read_settings(self.path)['nativeCarDistance'],0)

    def test_full_course_can_be_disabled_and_old_distance_migrates(self):
        values=dict(DEFAULTS,nativeFullCourse=False,nativeCarDistance=3)
        save_settings(self.path,values)
        self.assertEqual(read_settings(self.path),values)
        self.path.write_text('[ridge_native_scene]\nnativeCarDistance=4\n')
        migrated=read_settings(self.path)
        self.assertTrue(migrated['nativeFullCourse'])
        self.assertEqual(migrated['nativeCarDistance'],0)

    def test_native_resolution_ratio_and_migration(self):
        for aspect,w,h in [('4:3',1280,960),('16:9',1920,1080)]:
            values=dict(DEFAULTS,nativeScene=True,aspect=aspect,nativeWidth=w,nativeHeight=h)
            save_settings(self.path,values)
            self.assertEqual(read_settings(self.path),values)
            with self.assertRaisesRegex(ValueError,'aspect ratio'):
                save_settings(self.path,dict(values,nativeHeight=h+1))
        self.path.write_text('[ridge_native_scene]\nnativeScene=true\nnativeWidth=1280\nnativeHeight=720\n')
        (self.path.parent/'mods/state.toml').unlink()
        migrated=read_settings(self.path)
        self.assertEqual((migrated['aspect'],migrated['nativeWidth'],migrated['nativeHeight']),('4:3',1280,960))

    def test_preserves_other_settings_and_mod_features(self):
        self.path.write_text('[controller]\nmode="digital"\n[audio]\nvolume=73\n')
        state_path = self.path.parent / 'mods/state.toml'
        state_path.parent.mkdir()
        state_path.write_text('format_version=2\n[[package]]\nid="other"\nversion="1.0.0"\n[[feature]]\npackage_id="other"\nid="example"\nenabled=true\n[feature.values]\noption="custom"\n')
        save_settings(self.path, DEFAULTS.copy())
        doc = tomllib.loads(self.path.read_text())
        self.assertEqual(doc['audio']['volume'], 73)
        self.assertEqual(doc['controller']['mode'], 'digital')
        state = tomllib.loads(state_path.read_text())
        self.assertEqual(state['feature'][0]['values']['option'], 'custom')
        self.assertTrue(state['feature'][0]['enabled'])
    def test_bad_toml_is_not_overwritten(self):
        self.path.write_text('[broken')
        with self.assertRaises(tomllib.TOMLDecodeError): save_settings(self.path, DEFAULTS.copy())
        self.assertEqual(self.path.read_text(), '[broken')
    def test_bad_mod_state_does_not_overwrite_settings(self):
        self.path.write_text('[audio]\nvolume=50\n')
        state = self.path.parent / 'mods/state.toml'; state.parent.mkdir()
        state.write_text('[broken')
        with self.assertRaises(tomllib.TOMLDecodeError): save_settings(self.path, DEFAULTS.copy())
        self.assertEqual(self.path.read_text(), '[audio]\nvolume=50\n')
    def test_bounds_and_types_rejected_before_writes(self):
        for changes in [dict(width=4000),dict(scale=8),dict(target=30),dict(blending=1),dict(width=True),dict(aspect='32:9')]:
            with self.subTest(changes=changes), self.assertRaises(ValueError):
                save_settings(self.path, dict(DEFAULTS, **changes))
        self.assertFalse(self.path.exists())
    def test_repeated_save_does_not_duplicate_mods(self):
        for i in range(3): save_settings(self.path,dict(DEFAULTS,aspect='16:9'))
        state = tomllib.loads((self.path.parent/'mods/state.toml').read_text())
        self.assertEqual(len(state['feature']),2)
        self.assertEqual(len(state['package']),1)
    def test_external_mod_change_is_visible(self):
        save_settings(self.path,dict(DEFAULTS,aspect='16:9'))
        state = self.path.parent/'mods/state.toml'
        state.write_text(state.read_text().replace('"enabled" = true','"enabled" = false'))
        self.assertEqual(read_settings(self.path)['aspect'],'4:3')

    def test_cli_rejects_save_while_game_lock_is_held(self):
        root = Path(self.temp.name)
        build = root / 'build-macos'; build.mkdir()
        with (build / '.service-menu.lock').open('a') as lock:
            fcntl.flock(lock.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            result = subprocess.run([sys.executable, 'launcher/settings.py', 'save', '--root', str(root)],
                                    input=json.dumps(DEFAULTS), text=True, capture_output=True)
        self.assertEqual(result.returncode, 1)
        self.assertIn('already running', result.stderr)
        self.assertFalse((build/'settings.toml').exists())

if __name__ == '__main__': unittest.main()
