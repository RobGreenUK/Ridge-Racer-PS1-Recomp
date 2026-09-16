"""Sampler failure and shutdown must not leave an orphaned recording process."""
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import Mock, patch
from launcher.presentation_profile import PresentationProfile


class PresentationProfileTests(unittest.TestCase):
    def test_target_exit_finalizes_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            (directory / 'presentation-stacks.txt').write_text('sample report')
            child = Mock(returncode=0)
            with patch('launcher.presentation_profile.subprocess.Popen', return_value=child) as start:
                profile = PresentationProfile(123, directory)
                profile.close()
            self.assertEqual(start.call_args.args[0][:5], ['/usr/bin/sample', '123', '600', '1', '-mayDie'])
            child.wait.assert_called_once_with(timeout=15)
            child.terminate.assert_not_called()
            self.assertTrue(profile.log.closed)

    def test_stuck_sampler_is_reaped_and_warns(self):
        with tempfile.TemporaryDirectory() as tmp:
            child = Mock(returncode=-9)
            child.wait.side_effect = [subprocess.TimeoutExpired('sample', 15), subprocess.TimeoutExpired('sample', 5), -9]
            with patch('launcher.presentation_profile.subprocess.Popen', return_value=child):
                profile = PresentationProfile(123, Path(tmp))
                with self.assertWarnsRegex(UserWarning, 'Frame timings remain available'):
                    profile.close()
            child.terminate.assert_called_once()
            child.kill.assert_called_once()
            self.assertTrue(profile.log.closed)

    def test_missing_report_is_reported(self):
        with tempfile.TemporaryDirectory() as tmp:
            with patch('launcher.presentation_profile.subprocess.Popen', return_value=Mock(returncode=0)):
                profile = PresentationProfile(123, Path(tmp))
                with self.assertWarnsRegex(UserWarning, 'sampling failed'):
                    profile.close()
