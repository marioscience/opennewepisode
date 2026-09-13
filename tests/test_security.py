#!/usr/bin/env python3
"""Unit tests for defensive security hardening and vulnerability prevention."""

import os
import stat
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch, MagicMock

from opennewepisode.scanner import Episode, clean_title, sanitize_text
from opennewepisode.storage import ConfigManager, PlayerSettings
from opennewepisode.player import build_vlc_command, launch_vlc_direct
import opennewepisode.dialogs as dialogs


class TestSecurityHardening(unittest.TestCase):
    """Tests security controls across the application."""

    def test_pango_markup_escaping_in_dialogs(self):
        """SEC-1: Verify that filenames with XML entities (&, <, >) are escaped for Pango markup."""
        special_ep = Episode(
            path=Path("/shows/test/S01E01 - Tom & Jerry <Special>.mkv"),
            relative_path="S01E01 - Tom & Jerry <Special>.mkv",
            season=1,
            episode=1,
            title="Tom & Jerry <Special>",
        )
        curr_ep = Episode(
            path=Path("/shows/test/S01E02 - Jack & Jill > Up the Hill.mkv"),
            relative_path="S01E02 - Jack & Jill > Up the Hill.mkv",
            season=1,
            episode=2,
            title="Jack & Jill > Up the Hill",
        )

        with patch("opennewepisode.dialogs.is_gui_mode", return_value=True), \
             patch("shutil.which", return_value="/usr/bin/zenity"), \
             patch("subprocess.run") as mock_run:

            mock_run.return_value = MagicMock(returncode=0, stdout="Play S01E01 and switch progress here\n")

            # Out-of-order prompt test
            dialogs.prompt_out_of_order(special_ep, curr_ep, resume_seconds=120)
            self.assertTrue(mock_run.called)
            called_cmd = mock_run.call_args[0][0]
            text_arg = next(arg for arg in called_cmd if arg.startswith("--text="))

            # Must contain escaped entities, NOT raw unescaped ones
            self.assertIn("Tom &amp; Jerry &lt;Special&gt;", text_arg)
            self.assertIn("Jack &amp; Jill &gt; Up the Hill", text_arg)
            self.assertNotIn("Tom & Jerry <Special>", text_arg)

            # Resume prompt test
            mock_run.reset_mock()
            dialogs.prompt_resume_or_start(special_ep, resume_seconds=120)
            self.assertTrue(mock_run.called)
            called_cmd = mock_run.call_args[0][0]
            text_arg = next(arg for arg in called_cmd if arg.startswith("--text="))
            self.assertIn("Tom &amp; Jerry &lt;Special&gt;", text_arg)

    def test_vlc_argument_injection_delimiter(self):
        """SEC-2: Verify VLC commands use '--' before the media path to prevent flag injection."""
        malicious_filename = "--sout=#transcode:std{access=file,dst=/tmp/pwned}.mp4"
        ep = Episode(
            path=Path(f"/shows/{malicious_filename}"),
            relative_path=malicious_filename,
            season=1,
            episode=1,
            title="Exploit Attempt",
        )
        settings = PlayerSettings()
        cmd = build_vlc_command(ep, settings)

        # The second to last item should be '--' and the last item should be the path
        self.assertEqual(cmd[-2], "--")
        self.assertEqual(cmd[-1], str(ep.path))

    def test_launch_vlc_direct_argument_injection(self):
        """SEC-2: Verify direct VLC launch uses '--' before arbitrary file paths."""
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)
            launch_vlc_direct(Path("--arbitrary-flag.mp4"), vlc_cmd="vlc")
            self.assertTrue(mock_run.called)
            cmd = mock_run.call_args[0][0]
            self.assertEqual(cmd[-2], "--")
            self.assertEqual(cmd[-1], "--arbitrary-flag.mp4")

    def test_secure_config_permissions_and_atomic_save(self):
        """SEC-3: Verify config dir is 0700 and saved config file is 0600 with atomic replace."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            config_dir = Path(tmp_dir) / "sub_config"
            config_file = config_dir / "config.json"

            cfg = ConfigManager(config_file=config_file)
            cfg.save()

            self.assertTrue(config_file.exists())

            # Verify directory permissions (0700)
            dir_mode = stat.S_IMODE(os.stat(config_dir).st_mode)
            self.assertEqual(dir_mode, 0o700)

            # Verify file permissions (0600)
            file_mode = stat.S_IMODE(os.stat(config_file).st_mode)
            self.assertEqual(file_mode, 0o600)

    def test_ansi_and_control_character_sanitization(self):
        """SEC-4: Verify ANSI escape codes and control characters are stripped from titles (CWE-150)."""
        malicious_raw = "\x1b[31;1mRed Alert\x1b[0m \x1b]52;c;evil\x07Title\x00\x1f"
        sanitized = sanitize_text(malicious_raw)
        self.assertNotIn("\x1b", sanitized)
        self.assertNotIn("\x07", sanitized)
        self.assertNotIn("\x00", sanitized)
        self.assertNotIn("\x1f", sanitized)
        self.assertEqual(sanitized, "Red Alert Title")

        cleaned = clean_title(malicious_raw)
        self.assertNotIn("\x1b", cleaned)

        ep = Episode(
            path=Path("/shows/test.mp4"),
            relative_path="test.mp4",
            season=1,
            episode=1,
            title="\x1b[2JInjected",
        )
        self.assertNotIn("\x1b", ep.display_name)
        self.assertEqual(ep.display_name, "S01E01 - Injected")

    def test_add_show_without_name_re_import(self):
        """SEC-7: Verify add_show without name succeeds and cleans release tags without NameError."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            config_file = Path(tmp_dir) / "config.json"
            cfg = ConfigManager(config_file=config_file)

            show_dir = Path(tmp_dir) / "Breaking Bad 1080p WEB x264"
            show_dir.mkdir()

            name, show_data = cfg.add_show(show_dir)
            self.assertEqual(name, "Breaking Bad")
            self.assertIn("Breaking Bad", cfg.shows)


if __name__ == "__main__":
    unittest.main()
