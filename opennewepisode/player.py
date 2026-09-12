#!/usr/bin/env python3
"""Player module for launching VLC and handling playback lifecycle."""

import json
import shutil
import subprocess
import sys
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

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
    for candidate in ["/snap/bin/vlc", "/usr/bin/vlc", "/usr/local/bin/vlc"]:
        if Path(candidate).is_file():
            return candidate

    return None


def detect_external_subtitles(video_path: Path) -> Optional[Path]:
    """
    Searches for external subtitle files matching the episode,
    prioritizing English subtitle files (.en.srt, .eng.srt, .srt).
    """
    parent = video_path.parent
    stem = video_path.stem

    # High-priority english candidates
    english_candidates = [
        parent / f"{stem}.en.srt",
        parent / f"{stem}.eng.srt",
        parent / f"{stem}.English.srt",
        parent / f"{stem}.en.sub",
        parent / f"{stem}.eng.sub",
        parent / f"{stem}.en.vtt",
    ]
    for cand in english_candidates:
        if cand.is_file():
            return cand

    # Subdirectories like Subs/ or Subtitles/
    for sub_dir_name in ["Subs", "subs", "Subtitles", "subtitles"]:
        sub_dir = parent / sub_dir_name
        if sub_dir.is_dir():
            for f in sorted(sub_dir.glob("*.srt")):
                if "eng" in f.stem.lower() or "en" in f.stem.lower():
                    return f

    # Fallback generic subtitle with same stem
    generic_candidates = [
        parent / f"{stem}.srt",
        parent / f"{stem}.sub",
        parent / f"{stem}.vtt",
    ]
    for cand in generic_candidates:
        if cand.is_file():
            return cand

    return None


def probe_media_info(video_path: Path) -> Dict[str, Any]:
    """
    Probes video file using ffprobe if available to discover audio & subtitle tracks.
    """
    info: Dict[str, Any] = {
        "has_english_audio": False,
        "has_english_sub": False,
        "audio_tracks": [],
        "subtitle_tracks": [],
    }

    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        return info

    try:
        res = subprocess.run(
            [
                ffprobe, "-v", "error",
                "-show_entries", "stream=index,codec_type:stream_tags=language,title",
                "-of", "json", str(video_path)
            ],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if res.returncode == 0:
            data = json.loads(res.stdout)
            for stream in data.get("streams", []):
                ctype = stream.get("codec_type")
                tags = stream.get("tags", {})
                lang = tags.get("language", "und").lower()
                title = tags.get("title", "")
                track_item = {"index": stream.get("index"), "lang": lang, "title": title}

                if ctype == "audio":
                    info["audio_tracks"].append(track_item)
                    if lang in ("eng", "en", "english"):
                        info["has_english_audio"] = True
                elif ctype == "subtitle":
                    info["subtitle_tracks"].append(track_item)
                    if lang in ("eng", "en", "english"):
                        info["has_english_sub"] = True

    except Exception:
        pass

    return info


def build_vlc_command(
    episode: Episode,
    settings: PlayerSettings,
    extra_args: Optional[List[str]] = None,
) -> List[str]:
    """
    Constructs the list of command-line arguments for VLC.
    """
    vlc_bin = resolve_vlc_binary(settings.vlc_command) or settings.vlc_command
    cmd = [vlc_bin]

    # Minimized View Mode (without window menus and toolbars)
    if settings.minimal_view:
        cmd.append("--qt-minimal-view")

    # Fullscreen vs Windowed
    if settings.fullscreen:
        cmd.append("--fullscreen")
    else:
        cmd.append("--no-fullscreen")

    # Auto English Audio
    if settings.english_audio:
        cmd.append("--audio-language=eng,en,English")

    # Auto English Subtitles
    if settings.english_subtitles:
        cmd.append("--sub-language=eng,en,English")
        ext_sub = detect_external_subtitles(episode.path)
        if ext_sub:
            cmd.append(f"--sub-file={ext_sub}")

    # Play and Exit
    if settings.play_and_exit:
        cmd.append("--play-and-exit")

    # User-configured extra args
    if settings.extra_vlc_args:
        cmd.extend(settings.extra_vlc_args)

    if extra_args:
        cmd.extend(extra_args)

    cmd.append(str(episode.path))
    return cmd


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

    cmd = build_vlc_command(episode, settings, extra_args)

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
