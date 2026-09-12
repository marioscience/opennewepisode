"""OpenNewEpisode - Terminal-based TV show manager & VLC launcher."""

from opennewepisode.scanner import Episode, scan_episodes
from opennewepisode.storage import ConfigManager, ShowData
from opennewepisode.player import launch_vlc
from opennewepisode.ui import TerminalUI
from opennewepisode.cli import main

__all__ = [
    "Episode",
    "scan_episodes",
    "ConfigManager",
    "ShowData",
    "launch_vlc",
    "TerminalUI",
    "main",
]
