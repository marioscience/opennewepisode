#!/usr/bin/env python3
"""Unit tests for player module and VLC command generation."""

import tempfile
import unittest
from pathlib import Path

from opennewepisode.scanner import Episode
from opennewepisode.storage import PlayerSettings
from opennewepisode.player import build_vlc_command, detect_external_subtitles


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

        # Minimized view mode
        self.assertIn("--qt-minimal-view", cmd)
        self.assertIn("--no-fullscreen", cmd)
        self.assertNotIn("--fullscreen", cmd)

        # English audio & subtitles
        self.assertIn("--audio-language=eng,en,English", cmd)
        self.assertIn("--sub-language=eng,en,English", cmd)

        # Auto-exit
        self.assertIn("--play-and-exit", cmd)
        self.assertEqual(cmd[-1], str(self.ep.path))

    def test_fullscreen_toggle(self):
        settings = PlayerSettings(fullscreen=True, minimal_view=False)
        cmd = build_vlc_command(self.ep, settings)

        self.assertIn("--fullscreen", cmd)
        self.assertNotIn("--no-fullscreen", cmd)
        self.assertNotIn("--qt-minimal-view", cmd)

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


if __name__ == "__main__":
    unittest.main()
