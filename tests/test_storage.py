#!/usr/bin/env python3
"""Unit tests for storage and state manager."""

import tempfile
import unittest
from pathlib import Path

from opennewepisode.scanner import Episode
from opennewepisode.storage import ConfigManager, ShowData


class TestStorage(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.config_path = Path(self.tmp_dir.name) / "config.json"
        self.cm = ConfigManager(self.config_path)

        # Mock episodes
        self.episodes = [
            Episode(Path("/show/S01E01.mkv"), "S01E01.mkv", 1, 1, "Pilot"),
            Episode(Path("/show/S01E02.mkv"), "S01E02.mkv", 1, 2, "Second"),
            Episode(Path("/show/S01E03.mkv"), "S01E03.mkv", 1, 3, "Third"),
        ]

    def tearDown(self):
        self.tmp_dir.cleanup()

    def test_next_episode_initial(self):
        show = ShowData(path="/show")
        next_ep = show.get_next_episode(self.episodes)
        self.assertIsNotNone(next_ep)
        self.assertEqual(next_ep.code, "S01E01")

    def test_next_episode_completed_advances(self):
        show = ShowData(path="/show")
        # Mark episode 1 as completed
        show.mark_watched(self.episodes[0], completed=True)
        next_ep = show.get_next_episode(self.episodes)
        self.assertIsNotNone(next_ep)
        self.assertEqual(next_ep.code, "S01E02")

    def test_next_episode_incomplete_resumes_same(self):
        show = ShowData(path="/show")
        # User started watching episode 1, but didn't finish (completed=False)
        show.mark_watched(self.episodes[0], completed=False)
        next_ep = show.get_next_episode(self.episodes)
        self.assertIsNotNone(next_ep)
        # Should return S01E01 to resume/continue opening that one
        self.assertEqual(next_ep.code, "S01E01")

    def test_mark_all_up_to(self):
        show = ShowData(path="/show")
        show.mark_all_up_to(self.episodes[1], self.episodes)
        self.assertTrue(show.is_watched(self.episodes[0]))
        self.assertTrue(show.is_watched(self.episodes[1]))
        self.assertFalse(show.is_watched(self.episodes[2]))

        next_ep = show.get_next_episode(self.episodes)
        self.assertEqual(next_ep.code, "S01E03")

    def test_series_completion(self):
        show = ShowData(path="/show")
        show.mark_all_up_to(self.episodes[2], self.episodes)
        next_ep = show.get_next_episode(self.episodes)
        self.assertIsNone(next_ep)

    def test_config_save_and_reload(self):
        self.cm.add_show(Path("/show"), "My Show")
        show_data = self.cm.shows["My Show"]
        show_data.mark_watched(self.episodes[0], completed=True)
        self.cm.save()

        # Reload in new instance
        new_cm = ConfigManager(self.config_path)
        self.assertIn("My Show", new_cm.shows)
        loaded_show = new_cm.shows["My Show"]
        self.assertTrue(loaded_show.is_watched(self.episodes[0]))
        self.assertEqual(loaded_show.last_watched.episode, 1)


if __name__ == "__main__":
    unittest.main()
