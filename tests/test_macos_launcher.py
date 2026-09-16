"""Integration checks for the built Mac app and its real settings bridge."""
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
APP = ROOT / 'build-macos/Ridge Racer.app/Contents/MacOS/RidgeRacerLauncher'


@unittest.skipUnless(APP.is_file(), 'Build the macOS service menu first')
class MacLauncherTests(unittest.TestCase):
    def check(self, cwd, override=None):
        env = os.environ.copy()
        env.pop('RIDGE_PROJECT_ROOT', None)
        if override is not None:
            env['RIDGE_PROJECT_ROOT'] = str(override)
        return subprocess.run([str(APP), '--check-settings'], cwd=cwd,
                              env=env, text=True, capture_output=True, timeout=15)

    def test_staged_config_does_not_hide_source_root(self):
        self.assertTrue((ROOT / 'build-macos/game.toml').exists())
        for cwd in (ROOT, ROOT / 'build-macos', Path(tempfile.gettempdir())):
            with self.subTest(cwd=cwd):
                result = self.check(cwd)
                self.assertEqual(result.returncode, 0, result.stderr)
                lines = result.stdout.splitlines()
                self.assertEqual(Path(lines[0]), ROOT)
                self.assertIn('aspect', json.loads(lines[1]))

    def test_valid_override_reads_settings(self):
        result = self.check(tempfile.gettempdir(), ROOT)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_build_folder_override_reports_clear_error(self):
        result = self.check(ROOT, ROOT / 'build-macos')
        self.assertEqual(result.returncode, 1)
        self.assertIn('Cannot find the Ridge Racer project', result.stderr)
        self.assertNotIn("can't open file", result.stderr)
