#!/usr/bin/env python3
"""Unit tests for player module and VLC command generation."""

import tempfile
import unittest
from pathlib import Path

from opennewepisode.scanner import Episode
from opennewepisode.storage import PlayerSettings
from opennewepisode.player import build_vlc_command, detect_external_subtitles, countdown_prompt, PostWatchAction


class TestPlayer(unittest.TestCase):
    def setUp(self):
        self.ep = Episode(
            path=Path("/tmp/test_show/S01E01.mkv"),
            relative_path="S01E01.mkv",
            season=1,
            episode=1,
            title="Pilot",
        )

    def test_default_vlc_command(self):
        settings = PlayerSettings()
        cmd = build_vlc_command(self.ep, settings)

        # Opens in fullscreen AND keeps minimal interface mode
        self.assertIn("--qt-minimal-view", cmd)
        self.assertIn("--fullscreen", cmd)
        self.assertNotIn("--no-fullscreen", cmd)

        # English audio & subtitles
        self.assertIn("--audio-language=eng,en,English", cmd)
        self.assertIn("--sub-language=eng,en,English", cmd)

        # Auto-exit
        self.assertIn("--play-and-exit", cmd)
        self.assertEqual(cmd[-1], str(self.ep.path))

    def test_windowed_mode(self):
        settings = PlayerSettings(fullscreen=False, minimal_view=True)
        cmd = build_vlc_command(self.ep, settings)

        self.assertIn("--no-fullscreen", cmd)
        self.assertNotIn("--fullscreen", cmd)
        self.assertIn("--qt-minimal-view", cmd)

    def test_subtitles_disabled(self):
        settings = PlayerSettings(english_subtitles=False, english_audio=False)
        cmd = build_vlc_command(self.ep, settings)

        self.assertNotIn("--sub-language=eng,en,English", cmd)
        self.assertNotIn("--audio-language=eng,en,English", cmd)

    def test_detect_external_subtitles(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = Path(tmpdir)
            video = tmppath / "Show - S01E01.mkv"
            sub_en = tmppath / "Show - S01E01.en.srt"
            video.touch()
            sub_en.touch()

            found = detect_external_subtitles(video)
            self.assertIsNotNone(found)
            self.assertEqual(found.name, "Show - S01E01.en.srt")

    def test_auto_play_settings_defaults(self):
        settings = PlayerSettings()
        self.assertTrue(settings.auto_play_next)
        self.assertEqual(settings.auto_play_delay, 5)

    def test_countdown_prompt_zero_delay(self):
        next_ep = Episode(
            path=Path("/tmp/test_show/S01E02.mkv"),
            relative_path="S01E02.mkv",
            season=1,
            episode=2,
            title="Second",
        )
        action = countdown_prompt(next_ep, delay=0)
        self.assertEqual(action, PostWatchAction.PLAY_NEXT)


if __name__ == "__main__":
    unittest.main()
