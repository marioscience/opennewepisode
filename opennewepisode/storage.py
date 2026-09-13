#!/usr/bin/env python3
"""Storage and configuration manager for OpenNewEpisode."""

import json
import os
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple

from opennewepisode.scanner import Episode, scan_episodes

DEFAULT_CONFIG_DIR = Path.home() / ".config" / "opennewepisode"
DEFAULT_CONFIG_FILE = DEFAULT_CONFIG_DIR / "config.json"
DEFAULT_SEED_SHOW_PATH = Path("/media/mario/Short-TANK/TEMP TO LONG/Fear the Walking Dead 2015 Complete Series 1080p WEB x264 [i_c]")
DEFAULT_SEED_SHOW_NAME = "Fear the Walking Dead"


@dataclass
class LastWatched:
    relative_path: str
    season: int
    episode: int
    title: str = ""
    completed: bool = False
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())
    resume_seconds: int = 0
    duration_seconds: int = 0


@dataclass
class ShowData:
    path: str
    last_watched: Optional[LastWatched] = None
    watched_rel_paths: List[str] = field(default_factory=list)

    def get_last_watched_episode(self, all_episodes: List[Episode]) -> Optional[Episode]:
        """Finds the last watched Episode instance in all_episodes."""
        if not self.last_watched:
            return None
        # Match by relative_path first
        for ep in all_episodes:
            if ep.relative_path == self.last_watched.relative_path:
                return ep
        # Fallback match by season and episode
        for ep in all_episodes:
            if ep.season == self.last_watched.season and ep.episode == self.last_watched.episode:
                return ep
        return None

    def get_next_episode(self, all_episodes: List[Episode]) -> Optional[Episode]:
        """
        Determines the next episode to watch:
        - If never watched: returns episode 0.
        - If last watched is incomplete (completed == False): returns that same episode to resume.
        - If last watched is complete: returns the next sequential episode.
        """
        if not all_episodes:
            return None

        last_ep = self.get_last_watched_episode(all_episodes)
        if not last_ep or not self.last_watched:
            return all_episodes[0]

        # If user stopped mid-way or chose not to mark completed, reopen the same episode
        if not self.last_watched.completed:
            return last_ep

        try:
            current_idx = all_episodes.index(last_ep)
            if current_idx + 1 < len(all_episodes):
                return all_episodes[current_idx + 1]
            return None  # Series finished!
        except ValueError:
            # If not found directly, find first unwatched episode
            watched_set = set(self.watched_rel_paths)
            for ep in all_episodes:
                if ep.relative_path not in watched_set:
                    return ep
            return None

    def mark_watched(
        self,
        episode: Episode,
        completed: bool = True,
        resume_seconds: int = 0,
        duration_seconds: int = 0,
    ) -> None:
        """Updates last watched status, marks completed if specified, and tracks resume position."""
        self.last_watched = LastWatched(
            relative_path=episode.relative_path,
            season=episode.season,
            episode=episode.episode,
            title=episode.title,
            completed=completed,
            timestamp=datetime.now().isoformat(),
            resume_seconds=0 if completed else resume_seconds,
            duration_seconds=duration_seconds,
        )
        if completed and episode.relative_path not in self.watched_rel_paths:
            self.watched_rel_paths.append(episode.relative_path)

    def mark_unwatched(self, episode: Episode) -> None:
        """Removes episode from watched list."""
        if episode.relative_path in self.watched_rel_paths:
            self.watched_rel_paths.remove(episode.relative_path)
        if self.last_watched and self.last_watched.relative_path == episode.relative_path:
            self.last_watched.completed = False

    def mark_all_up_to(self, target_episode: Episode, all_episodes: List[Episode]) -> None:
        """Marks all episodes from the beginning up to and including target_episode as watched."""
        try:
            target_idx = all_episodes.index(target_episode)
        except ValueError:
            target_idx = 0
            for i, ep in enumerate(all_episodes):
                if ep.sort_key <= target_episode.sort_key:
                    target_idx = i

        for i in range(target_idx + 1):
            ep = all_episodes[i]
            if ep.relative_path not in self.watched_rel_paths:
                self.watched_rel_paths.append(ep.relative_path)

        self.last_watched = LastWatched(
            relative_path=target_episode.relative_path,
            season=target_episode.season,
            episode=target_episode.episode,
            title=target_episode.title,
            completed=True,
            timestamp=datetime.now().isoformat(),
        )

    def is_watched(self, episode: Episode) -> bool:
        """Checks if an episode has been marked watched."""
        return episode.relative_path in self.watched_rel_paths

    def get_progress(self, all_episodes: List[Episode]) -> Tuple[int, int, float]:
        """Returns (watched_count, total_count, percentage)."""
        total = len(all_episodes)
        if total == 0:
            return 0, 0, 0.0
        watched_set = set(self.watched_rel_paths)
        watched = sum(1 for ep in all_episodes if ep.relative_path in watched_set)
        percentage = (watched / total) * 100.0
        return watched, total, percentage


@dataclass
class PlayerSettings:
    vlc_command: str = "vlc"
    fullscreen: bool = True
    minimal_view: bool = True
    english_subtitles: bool = True
    english_audio: bool = True
    play_and_exit: bool = True
    auto_play_next: bool = True
    auto_play_delay: int = 5
    track_playback_progress: bool = True
    completion_threshold: float = 0.90
    extra_vlc_args: List[str] = field(default_factory=list)


class ConfigManager:
    """Manages reading and writing application state and shows."""

    def __init__(self, config_file: Optional[Path] = None):
        self.config_file = config_file or DEFAULT_CONFIG_FILE
        self.config_dir = self.config_file.parent
        self.active_show_name: Optional[str] = None
        self.settings = PlayerSettings()
        self.shows: Dict[str, ShowData] = {}
        self.load()

    def load(self) -> None:
        """Loads configuration from JSON file or initializes defaults."""
        if not self.config_file.exists():
            self._initialize_defaults()
            self.save()
            return

        try:
            with open(self.config_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            self.active_show_name = data.get("active_show")

            # Load settings with migration support for new defaults
            s_data = data.get("settings", {})
            has_minimal_view = "minimal_view" in s_data
            has_auto_play = "auto_play_next" in s_data
            has_track_progress = "track_playback_progress" in s_data
            minimal_view = s_data.get("minimal_view", True)
            fullscreen = s_data.get("fullscreen", True)
            english_subtitles = s_data.get("english_subtitles", True)
            english_audio = s_data.get("english_audio", True)
            auto_play_next = s_data.get("auto_play_next", True)
            auto_play_delay = s_data.get("auto_play_delay", 5)
            track_playback_progress = s_data.get("track_playback_progress", True)
            completion_threshold = float(s_data.get("completion_threshold", 0.90))

            self.settings = PlayerSettings(
                vlc_command=s_data.get("vlc_command", "vlc"),
                fullscreen=fullscreen,
                minimal_view=minimal_view,
                english_subtitles=english_subtitles,
                english_audio=english_audio,
                play_and_exit=s_data.get("play_and_exit", True),
                auto_play_next=auto_play_next,
                auto_play_delay=auto_play_delay,
                track_playback_progress=track_playback_progress,
                completion_threshold=completion_threshold,
                extra_vlc_args=s_data.get("extra_vlc_args", []),
            )

            # Load shows
            self.shows = {}
            for name, s_info in data.get("shows", {}).items():
                lw_info = s_info.get("last_watched")
                last_watched = None
                if lw_info:
                    last_watched = LastWatched(
                        relative_path=lw_info.get("relative_path", ""),
                        season=lw_info.get("season", 1),
                        episode=lw_info.get("episode", 1),
                        title=lw_info.get("title", ""),
                        completed=lw_info.get("completed", False),
                        timestamp=lw_info.get("timestamp", datetime.now().isoformat()),
                        resume_seconds=lw_info.get("resume_seconds", 0),
                        duration_seconds=lw_info.get("duration_seconds", 0),
                    )
                self.shows[name] = ShowData(
                    path=s_info.get("path", ""),
                    last_watched=last_watched,
                    watched_rel_paths=s_info.get("watched_rel_paths", []),
                )

            # Validate active show
            if not self.active_show_name or self.active_show_name not in self.shows:
                if self.shows:
                    self.active_show_name = next(iter(self.shows))
                else:
                    self.active_show_name = None

            if not has_minimal_view or not has_auto_play or not has_track_progress:
                self.save()

        except Exception:
            # In case of corruption, reinit
            self._initialize_defaults()
            self.save()

    def _initialize_defaults(self) -> None:
        """Auto-seeds configuration if starting fresh."""
        self.shows = {}
        if DEFAULT_SEED_SHOW_PATH.exists() and DEFAULT_SEED_SHOW_PATH.is_dir():
            self.shows[DEFAULT_SEED_SHOW_NAME] = ShowData(
                path=str(DEFAULT_SEED_SHOW_PATH),
                last_watched=None,
                watched_rel_paths=[],
            )
            self.active_show_name = DEFAULT_SEED_SHOW_NAME
        else:
            self.active_show_name = None

    def save(self) -> None:
        """Saves current state to JSON configuration file."""
        self.config_dir.mkdir(parents=True, exist_ok=True)

        shows_dict = {}
        for name, s_data in self.shows.items():
            shows_dict[name] = {
                "path": s_data.path,
                "last_watched": asdict(s_data.last_watched) if s_data.last_watched else None,
                "watched_rel_paths": s_data.watched_rel_paths,
            }

        payload = {
            "version": 1,
            "active_show": self.active_show_name,
            "settings": asdict(self.settings),
            "shows": shows_dict,
        }

        tmp_file = self.config_file.with_suffix(".tmp")
        with open(tmp_file, "w", encoding="utf-8") as f:
            json.dump(payload, f, indent=2, ensure_ascii=False)
        tmp_file.replace(self.config_file)

    def get_active_show(self) -> Optional[Tuple[str, ShowData]]:
        """Returns (show_name, ShowData) for active show."""
        if self.active_show_name and self.active_show_name in self.shows:
            return self.active_show_name, self.shows[self.active_show_name]
        if self.shows:
            self.active_show_name = next(iter(self.shows))
            return self.active_show_name, self.shows[self.active_show_name]
        return None

    def set_active_show(self, name: str) -> bool:
        """Sets active show by name."""
        if name in self.shows:
            self.active_show_name = name
            self.save()
            return True
        return False

    def add_show(self, path: Path, name: Optional[str] = None) -> Tuple[str, ShowData]:
        """Adds a new show path and returns (name, ShowData)."""
        resolved_path = path.expanduser().resolve()
        if not name:
            name = resolved_path.name
            # Clean up common release folder tags if name is long
            name = re.split(r"(?i)\s+(?:1080p|720p|2160p|Complete|WEB|BluRay)", name)[0].strip()

        # If name already exists, make unique
        base_name = name
        counter = 2
        while name in self.shows and self.shows[name].path != str(resolved_path):
            name = f"{base_name} ({counter})"
            counter += 1

        if name not in self.shows:
            show_data = ShowData(path=str(resolved_path))
            self.shows[name] = show_data
        else:
            show_data = self.shows[name]

        self.active_show_name = name
        self.save()
        return name, show_data

    def remove_show(self, name: str) -> bool:
        """Removes a show from tracked list."""
        if name in self.shows:
            del self.shows[name]
            if self.active_show_name == name:
                self.active_show_name = next(iter(self.shows)) if self.shows else None
            self.save()
            return True
        return False
