#!/usr/bin/env python3
"""Unit tests for episode scanner."""

import tempfile
import unittest
from pathlib import Path

from opennewepisode.scanner import (
    clean_title,
    extract_metadata,
    scan_episodes,
)


class TestScanner(unittest.TestCase):
    def test_clean_title(self):
        self.assertEqual(clean_title("Pilot.1080p.WEB-DL.x264"), "Pilot")
        self.assertEqual(clean_title("So.Close..Yet.So.Far.720p.HDTV"), "So Close Yet So Far")
        self.assertEqual(clean_title("The.Road.Ahead.1080p.BluRay.DDP5.1"), "The Road Ahead")
        self.assertEqual(clean_title("Down"), "Down")

    def test_extract_metadata_standard(self):
        root = Path("/media/shows/Series")
        f = root / "Season 1" / "Series - S01E05 - Cobalt.mkv"
        s, e, t = extract_metadata(f, root)
        self.assertEqual(s, 1)
        self.assertEqual(e, 5)
        self.assertEqual(t, "Cobalt")

    def test_extract_metadata_scene_style(self):
        root = Path("/media/shows/Series")
        f = root / "Ted.Lasso.S04E02.Curiouser.and.Curiouser.1080p.mkv"
        s, e, t = extract_metadata(f, root)
        self.assertEqual(s, 4)
        self.assertEqual(e, 2)
        self.assertEqual(t, "Curiouser and Curiouser")

    def test_extract_metadata_cross_style(self):
        root = Path("/media/shows/Series")
        f = root / "Anime.1x08.Title.mp4"
        s, e, t = extract_metadata(f, root)
        self.assertEqual(s, 1)
        self.assertEqual(e, 8)
        self.assertEqual(t, "Title")

    def test_extract_metadata_folder_season(self):
        root = Path("/media/shows/Series")
        f = root / "Season 03" / "04 - Down.mp4"
        s, e, t = extract_metadata(f, root)
        self.assertEqual(s, 3)
        self.assertEqual(e, 4)
        self.assertEqual(t, "Down")

    def test_scan_episodes_sorting(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            tmproot = Path(tmpdir)
            s1 = tmproot / "Season 1"
            s2 = tmproot / "Season 2"
            s1.mkdir()
            s2.mkdir()

            # Create out of order files
            (s1 / "Show.S01E02.mkv").touch()
            (s1 / "Show.S01E01.mkv").touch()
            (s2 / "Show.S02E01.mkv").touch()
            (s1 / "sample.mkv").touch()  # Sample should be ignored
            (s1 / "notes.txt").touch()    # Text should be ignored

            episodes = scan_episodes(tmproot)
            self.assertEqual(len(episodes), 3)
            self.assertEqual(episodes[0].code, "S01E01")
            self.assertEqual(episodes[1].code, "S01E02")
            self.assertEqual(episodes[2].code, "S02E01")


if __name__ == "__main__":
    unittest.main()
