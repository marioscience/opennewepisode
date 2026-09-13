#!/usr/bin/env python3
"""Player module for launching VLC and handling playback lifecycle."""

import json
import select
import shutil
import subprocess
import sys
import threading
import time
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

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
                "-of", "json", "--", str(video_path)
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


def format_seconds(seconds: int) -> str:
    """Formats integer seconds into human-readable MM:SS or HH:MM:SS."""
    if seconds < 0:
        seconds = 0
    h = seconds // 3600
    m = (seconds % 3600) // 60
    s = seconds % 60
    if h > 0:
        return f"{h}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"


class PlaybackTracker:
    """
    Monitors VLC playback position and duration in a background thread
    via Linux MPRIS2 D-Bus (org.mpris.MediaPlayer2.vlc.instance<PID>).
    """

    def __init__(self, pid: int, poll_interval: float = 0.8):
        self.pid = pid
        self.poll_interval = poll_interval
        self.last_position = 0.0
        self.duration = 0.0
        self.is_running = True
        self._thread = threading.Thread(target=self._poll_loop, daemon=True)
        self._thread.start()

    def _poll_loop(self):
        try:
            import dbus
        except ImportError:
            return

        target_service = f"org.mpris.MediaPlayer2.vlc.instance{self.pid}"
        bus = None
        poll_count = 0
        while self.is_running:
            try:
                if bus is None:
                    bus = dbus.SessionBus()
                services = bus.list_names()
                service_to_use = None
                if target_service in services:
                    service_to_use = target_service
                elif poll_count > 5 and "org.mpris.MediaPlayer2.vlc" in services:
                    # Avoid crosstalk: only fallback if no other instances exist and PID service not found
                    instance_services = [s for s in services if s.startswith("org.mpris.MediaPlayer2.vlc.instance")]
                    if not instance_services:
                        service_to_use = "org.mpris.MediaPlayer2.vlc"

                if service_to_use:
                    player = bus.get_object(service_to_use, "/org/mpris/MediaPlayer2")
                    props = dbus.Interface(player, "org.freedesktop.DBus.Properties")

                    pos_raw = props.Get("org.mpris.MediaPlayer2.Player", "Position")
                    if pos_raw is not None:
                        pos_sec = float(pos_raw) / 1_000_000.0
                        if pos_sec > 0:
                            self.last_position = pos_sec

                    meta = props.Get("org.mpris.MediaPlayer2.Player", "Metadata")
                    if meta:
                        len_raw = meta.get("mpris:length", 0)
                        if len_raw and int(len_raw) > 0:
                            self.duration = float(len_raw) / 1_000_000.0
            except Exception:
                bus = None

            poll_count += 1
            time.sleep(self.poll_interval)

    def stop(self) -> Tuple[int, int]:
        """Stops tracking thread and returns (last_position_seconds, duration_seconds)."""
        self.is_running = False
        return int(round(self.last_position)), int(round(self.duration))


def build_vlc_command(
    episode: Episode,
    settings: PlayerSettings,
    extra_args: Optional[List[str]] = None,
    start_time: Optional[int] = None,
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

    # Start time for resume
    if start_time and start_time > 0:
        cmd.append(f"--start-time={int(start_time)}")

    # Play and Exit
    if settings.play_and_exit:
        cmd.append("--play-and-exit")

    # User-configured extra args
    if settings.extra_vlc_args:
        cmd.extend(settings.extra_vlc_args)

    if extra_args:
        cmd.extend(extra_args)

    cmd.append("--")
    cmd.append(str(episode.path))
    return cmd


def launch_vlc(
    episode: Episode,
    settings: PlayerSettings,
    extra_args: Optional[List[str]] = None,
    start_time: Optional[int] = None,
) -> Tuple[int, int, int]:
    """
    Launches VLC to play the specified episode.
    Blocks until VLC closes.
    Returns (exit_code, last_position_seconds, duration_seconds).
    """
    vlc_bin = resolve_vlc_binary(settings.vlc_command)
    if not vlc_bin:
        raise FileNotFoundError(
            f"VLC player not found. Checked '{settings.vlc_command}' and common locations. "
            "Please ensure VLC is installed."
        )

    cmd = build_vlc_command(episode, settings, extra_args, start_time=start_time)

    tracker = None
    try:
        # Run VLC with suppressed stdout/stderr to keep the terminal pristine
        proc = subprocess.Popen(
            cmd,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        if settings.track_playback_progress:
            tracker = PlaybackTracker(proc.pid)

        returncode = proc.wait()
        last_pos, duration = tracker.stop() if tracker else (0, 0)
        return returncode, last_pos, duration
    except KeyboardInterrupt:
        last_pos, duration = tracker.stop() if tracker else (0, 0)
        return -1, last_pos, duration


def launch_vlc_direct(file_path: Optional[Path] = None, vlc_cmd: str = "vlc", extra_args: Optional[List[str]] = None) -> int:
    """Launches VLC directly for non-show arbitrary video files without tracking."""
    vlc_bin = resolve_vlc_binary(vlc_cmd) or vlc_cmd
    cmd = [vlc_bin]
    if extra_args:
        cmd.extend(extra_args)
    if file_path and str(file_path):
        cmd.append("--")
        cmd.append(str(file_path))
    try:
        proc = subprocess.run(cmd, check=False)
        return proc.returncode
    except Exception as e:
        print(f"Error launching VLC: {e}")
        return 1


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


def countdown_prompt(next_ep: Episode, delay: int = 5) -> PostWatchAction:
    """
    Shows a countdown prompt before automatically playing the next episode.
    Allows user to press Enter/p to play immediately, s/q to stop, or n to keep current episode incomplete.
    If timeout expires or non-interactive, returns PLAY_NEXT.
    """
    print()
    print(f"\033[1;36m▶ Up Next:\033[0m \033[1m{next_ep.display_name}\033[0m")
    print("\033[90m--------------------------------------------------\033[0m")
    print(f"  \033[1;32m[Enter/p]\033[0m Play now")
    print(f"  \033[1;33m[s/q]\033[0m     Stop auto-play (marked watched, return to menu)")
    print(f"  \033[1;34m[n]\033[0m       Didn't finish: keep current (resume here next time)")
    print("\033[90m--------------------------------------------------\033[0m")

    if delay <= 0 or not sys.stdin.isatty():
        return PostWatchAction.PLAY_NEXT

    try:
        for remaining in range(delay, 0, -1):
            sys.stdout.write(f"\r\033[1;33m⏱ Auto-playing in {remaining}s...\033[0m (Enter=Play, s=Stop, n=Keep): ")
            sys.stdout.flush()

            rlist, _, _ = select.select([sys.stdin], [], [], 1.0)
            if rlist:
                choice = sys.stdin.readline().strip().lower()
                sys.stdout.write("\r\033[K")
                sys.stdout.flush()
                if choice in ("", "p", "y", "play", "yes"):
                    return PostWatchAction.PLAY_NEXT
                elif choice in ("s", "q", "stop", "quit", "exit"):
                    return PostWatchAction.QUIT
                elif choice in ("n", "no"):
                    return PostWatchAction.KEEP_CURRENT
                else:
                    return PostWatchAction.PLAY_NEXT

        sys.stdout.write("\r\033[K")
        sys.stdout.flush()
        return PostWatchAction.PLAY_NEXT
    except (KeyboardInterrupt, EOFError):
        print()
        return PostWatchAction.QUIT

