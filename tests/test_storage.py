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
        self.cm.settings.auto_play_next = True
        self.cm.settings.auto_play_delay = 3
        self.cm.save()

        # Reload in new instance
        new_cm = ConfigManager(self.config_path)
        self.assertIn("My Show", new_cm.shows)
        loaded_show = new_cm.shows["My Show"]
        self.assertTrue(loaded_show.is_watched(self.episodes[0]))
        self.assertEqual(loaded_show.last_watched.episode, 1)
        self.assertTrue(new_cm.settings.auto_play_next)
        self.assertEqual(new_cm.settings.auto_play_delay, 3)

    def test_next_episode_cross_season(self):
        multi_season_eps = [
            Episode(Path("/show/S01E01.mkv"), "S01E01.mkv", 1, 1, "Pilot"),
            Episode(Path("/show/S01E02.mkv"), "S01E02.mkv", 1, 2, "Season 1 Finale"),
            Episode(Path("/show/S02E01.mkv"), "S02E01.mkv", 2, 1, "Season 2 Premiere"),
        ]
        show = ShowData(path="/show")
        # Mark season 1 finale completed
        show.mark_watched(multi_season_eps[1], completed=True)
        next_ep = show.get_next_episode(multi_season_eps)
        self.assertIsNotNone(next_ep)
        self.assertEqual(next_ep.code, "S02E01")
        self.assertEqual(next_ep.season, 2)
        self.assertEqual(next_ep.episode, 1)

    def test_mark_watched_resume_progress(self):
        show = ShowData(path="/show")
        # Watch halfway
        show.mark_watched(self.episodes[0], completed=False, resume_seconds=1450, duration_seconds=3000)
        self.assertFalse(show.is_watched(self.episodes[0]))
        self.assertEqual(show.last_watched.resume_seconds, 1450)
        self.assertEqual(show.last_watched.duration_seconds, 3000)
        self.assertFalse(show.last_watched.completed)

        # Later completed
        show.mark_watched(self.episodes[0], completed=True, resume_seconds=0, duration_seconds=3000)
        self.assertTrue(show.is_watched(self.episodes[0]))
        self.assertEqual(show.last_watched.resume_seconds, 0)
        self.assertTrue(show.last_watched.completed)

    def test_config_progress_settings_persistence(self):
        self.cm.settings.track_playback_progress = True
        self.cm.settings.completion_threshold = 0.85
        self.cm.add_show(Path("/show"), "My Show")
        show_data = self.cm.shows["My Show"]
        show_data.mark_watched(self.episodes[0], completed=False, resume_seconds=900, duration_seconds=1800)
        self.cm.save()

        new_cm = ConfigManager(self.config_path)
        self.assertTrue(new_cm.settings.track_playback_progress)
        self.assertAlmostEqual(new_cm.settings.completion_threshold, 0.85)
        loaded_show = new_cm.shows["My Show"]
        self.assertEqual(loaded_show.last_watched.resume_seconds, 900)
        self.assertEqual(loaded_show.last_watched.duration_seconds, 1800)
        self.assertFalse(loaded_show.last_watched.completed)


    def test_multi_episode_resume_positions(self):
        show = ShowData(path="/show")
        # Pause ep 0 at 500s
        show.mark_watched(self.episodes[0], completed=False, resume_seconds=500, duration_seconds=2000)
        # Pause ep 1 at 1200s
        show.mark_watched(self.episodes[1], completed=False, resume_seconds=1200, duration_seconds=2000)

        # Most recent episode should be ep 1
        self.assertEqual(show.last_watched.episode, 2)
        # Both episodes should retain their individual resume timestamps
        self.assertEqual(show.get_resume_seconds(self.episodes[0]), 500)
        self.assertEqual(show.get_resume_seconds(self.episodes[1]), 1200)

        # Complete ep 0
        show.mark_watched(self.episodes[0], completed=True, duration_seconds=2000)
        self.assertEqual(show.get_resume_seconds(self.episodes[0]), 0)
        # Ep 1 should still retain 1200s
        self.assertEqual(show.get_resume_seconds(self.episodes[1]), 1200)

    def test_one_off_watch_preserves_last_watched(self):
        show = ShowData(path="/show")
        # Complete Ep 0 as linear progress
        show.mark_watched(self.episodes[0], completed=True)
        self.assertEqual(show.get_next_episode(self.episodes).code, "S01E02")

        # Watch Ep 2 as a one-off (stopped mid-way)
        show.mark_watched(self.episodes[2], completed=False, resume_seconds=850, update_last_watched=False)
        # last_watched is STILL Ep 0!
        self.assertEqual(show.last_watched.episode, 1)
        # Up Next is STILL Ep 1!
        self.assertEqual(show.get_next_episode(self.episodes).code, "S01E02")
        # But Ep 2 has its resume timestamp saved!
        self.assertEqual(show.get_resume_seconds(self.episodes[2]), 850)

    def test_resume_positions_json_roundtrip(self):
        self.cm.add_show(Path("/show"), "My Show")
        show = self.cm.shows["My Show"]
        show.mark_watched(self.episodes[0], completed=False, resume_seconds=350, duration_seconds=1800)
        show.mark_watched(self.episodes[2], completed=False, resume_seconds=950, duration_seconds=2400)
        self.cm.save()

        new_cm = ConfigManager(self.config_path)
        loaded_show = new_cm.shows["My Show"]
        self.assertEqual(loaded_show.get_resume_seconds(self.episodes[0]), 350)
        self.assertEqual(loaded_show.get_resume_seconds(self.episodes[2]), 950)


if __name__ == "__main__":
    unittest.main()
