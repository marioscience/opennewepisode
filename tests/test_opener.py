#!/usr/bin/env python3
"""Unit tests for file opener and desktop integration."""

import tempfile
import unittest
from pathlib import Path

from opennewepisode.scanner import Episode
from opennewepisode.storage import ConfigManager, ShowData
from opennewepisode.cli import main


class TestOpener(unittest.TestCase):
    def setUp(self):
        self.tmp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp_dir.name)
        self.show_dir = self.root / "My Show"
        self.show_dir.mkdir(parents=True)

        self.ep1 = self.show_dir / "S01E01.mkv"
        self.ep2 = self.show_dir / "S01E02.mkv"
        self.ep1.touch()
        self.ep2.touch()

        self.non_show_file = self.root / "random_video.mp4"
        self.non_show_file.touch()

        self.config_file = self.root / "config.json"
        self.cm = ConfigManager(self.config_file)
        self.cm.add_show(self.show_dir, "My Show")

    def tearDown(self):
        self.tmp_dir.cleanup()

    def test_file_belongs_to_show(self):
        show_root = Path(self.cm.shows["My Show"].path).resolve()
        ep_path = self.ep1.resolve()
        self.assertTrue(ep_path.is_relative_to(show_root))

        non_show_path = self.non_show_file.resolve()
        self.assertFalse(non_show_path.is_relative_to(show_root))

    def test_auto_route_direct_file_arg(self):
        """Passing a direct video file path to argv should trigger open."""
        # Using sys.argv simulation
        from unittest.mock import patch

        with patch("opennewepisode.cli.cmd_open_file") as mock_open:
            main([str(self.ep1)])
            mock_open.assert_called_once()
            called_file = mock_open.call_args[0][1]
            self.assertEqual(called_file, str(self.ep1))


if __name__ == "__main__":
    unittest.main()
