#!/usr/bin/env python3
"""Player module for launching VLC and handling playback lifecycle."""

import shutil
import subprocess
import sys
from enum import Enum
from pathlib import Path
from typing import List, Optional

from opennewepisode.scanner import Episode
from opennewepisode.storage import PlayerSettings


class PostWatchAction(Enum):
    MARK_WATCHED_AND_ADVANCE = "advance"  # Mark watched, advance next pointer
    KEEP_CURRENT = "keep"                 # Keep current episode to resume next time
    PLAY_NEXT = "play_next"               # Mark watched and immediately launch next episode
    QUIT = "quit"                         # Cancel / quit


def resolve_vlc_binary(preferred_cmd: str = "vlc") -> Optional[str]:
    """Finds the VLC binary path."""
    which_path = shutil.which(preferred_cmd)
    if which_path:
        return which_path

    # Common Linux locations
    for candidate in ["/usr/bin/vlc", "/snap/bin/vlc", "/usr/local/bin/vlc"]:
        if Path(candidate).is_file():
            return candidate

    return None


def launch_vlc(
    episode: Episode,
    settings: PlayerSettings,
    extra_args: Optional[List[str]] = None,
) -> int:
    """
    Launches VLC to play the specified episode.
    Blocks until VLC closes.
    Returns the exit code.
    """
    vlc_bin = resolve_vlc_binary(settings.vlc_command)
    if not vlc_bin:
        raise FileNotFoundError(
            f"VLC player not found. Checked '{settings.vlc_command}' and common locations. "
            "Please ensure VLC is installed."
        )

    cmd = [vlc_bin]
    if settings.fullscreen:
        cmd.append("--fullscreen")
    if settings.play_and_exit:
        cmd.append("--play-and-exit")

    if settings.extra_vlc_args:
        cmd.extend(settings.extra_vlc_args)

    if extra_args:
        cmd.extend(extra_args)

    cmd.append(str(episode.path))

    try:
        # Run VLC with suppressed stdout/stderr to keep the terminal pristine
        proc = subprocess.run(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        return proc.returncode
    except KeyboardInterrupt:
        # User pressed Ctrl+C in terminal
        return -1


def prompt_post_watch(episode: Episode, next_ep: Optional[Episode]) -> PostWatchAction:
    """
    Interactively asks user what to do after VLC closes.
    """
    print()
    print(f"\033[1;36m▶ Finished watching:\033[0m \033[1m{episode.display_name}\033[0m")
    print("\033[90m--------------------------------------------------\033[0m")
    if next_ep:
        print(f"  \033[1;32m[Y]\033[0m Mark watched & advance to \033[1m{next_ep.code}\033[0m (Default)")
        print(f"  \033[1;33m[p]\033[0m Mark watched & \033[1;32mplay next episode now\033[0m ({next_ep.code})")
    else:
        print("  \033[1;32m[Y]\033[0m Mark as completed (Series Finale!)")
    print(f"  \033[1;34m[n]\033[0m Didn't finish: keep current (resume here next time)")
    print(f"  \033[1;31m[q]\033[0m Return to menu / quit without changes")
    print("\033[90m--------------------------------------------------\033[0m")

    while True:
        try:
            choice = input("\033[1mYour choice [Y/n/p/q]: \033[0m").strip().lower()
        except (KeyboardInterrupt, EOFError):
            print()
            return PostWatchAction.KEEP_CURRENT

        if choice in ("", "y", "yes"):
            return PostWatchAction.MARK_WATCHED_AND_ADVANCE
        elif choice in ("n", "no"):
            return PostWatchAction.KEEP_CURRENT
        elif choice in ("p", "play") and next_ep:
            return PostWatchAction.PLAY_NEXT
        elif choice in ("q", "quit", "exit"):
            return PostWatchAction.QUIT
        else:
            print("\033[31mInvalid option. Enter Y, n, p, or q.\033[0m")
