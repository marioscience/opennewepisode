#!/usr/bin/env python3
"""Scanner for discovering and parsing TV show episodes from directories."""

import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Tuple

VIDEO_EXTENSIONS = {
    ".mkv", ".mp4", ".avi", ".mov", ".wmv",
    ".m4v", ".webm", ".ts", ".m2ts", ".flv",
    ".mpg", ".mpeg", ".vob", ".ogv"
}

IGNORE_PATTERNS = [
    re.compile(r"(?i)\b(?:sample|trailer|featurette|preview)\b"),
    re.compile(r"(?i)^sample[-._]"),
]

RELEASE_TAGS = re.compile(
    r"(?i)[.\s\-_](?:2160p|1080p|720p|480p|4k|uhd|web-?dl|webrip|bluray|brrip|bdrip|dvdrip|hdtv|"
    r"x264|x265|hevc|h\.?264|h\.?265|avc|10bit|8bit|"
    r"ddp?[57]\.1|ddp?|ac3|aac(?:\d\.\d)?|dts(?:-hd)?|truehd|atmos|mp3|"
    r"repack|proper|remux|multi|ita|eng|rus|fre|ger|es|spa|sub|dub|i_c|amzn|nf|atvp|hulu|disney|"
    r"[a-z0-9]+-[a-z0-9]+$)",
)


@dataclass
class Episode:
    """Represents a single TV show episode file."""
    path: Path
    relative_path: str
    season: int
    episode: int
    title: str = ""

    @property
    def code(self) -> str:
        """Formatted code like S01E01."""
        return f"S{self.season:02d}E{self.episode:02d}"

    @property
    def display_name(self) -> str:
        """Friendly display name like 'S01E01 - Pilot'."""
        if self.title:
            return f"{self.code} - {self.title}"
        return self.code

    @property
    def sort_key(self) -> Tuple[int, int, str]:
        """Key for natural sorting by season and episode."""
        return (self.season, self.episode, self.relative_path)


def clean_title(raw_title: str) -> str:
    """Cleans up raw filename segment into human-readable episode title."""
    # Strip leading/trailing separators
    raw_title = raw_title.strip(" .-_")

    # Split off release tags
    parts = RELEASE_TAGS.split(raw_title)
    cleaned = parts[0] if parts else raw_title

    # If it contains dots or underscores without spaces, replace with spaces
    if "." in cleaned and " " not in cleaned:
        cleaned = cleaned.replace(".", " ")
    if "_" in cleaned and " " not in cleaned:
        cleaned = cleaned.replace("_", " ")

    cleaned = re.sub(r"\s+", " ", cleaned).strip(" .-_")
    return cleaned


def extract_metadata(file_path: Path, root_path: Path) -> Tuple[int, int, str]:
    """Extracts (season, episode, title) from file path."""
    stem = file_path.stem
    name = file_path.name
    rel_path = file_path.relative_to(root_path)

    # Check SxxExx or 1x02 pattern in filename
    m = re.search(r"(?:[sS](\d+)[eE](\d+)|(\d+)[xX](\d+))", stem)
    if m:
        if m.group(1) is not None:
            season = int(m.group(1))
            episode = int(m.group(2))
        else:
            season = int(m.group(3))
            episode = int(m.group(4))

        after = stem[m.end():]
        title = clean_title(after)
        return season, episode, title

    # Check folder hierarchy for Season info
    season = None
    for part in reversed(rel_path.parts[:-1]):
        m_s = re.search(r"(?:Season|Series|S)\s*(\d+)", part, re.IGNORECASE)
        if m_s:
            season = int(m_s.group(1))
            break

    if season is None:
        season = 1

    # Check filename for Episode pattern (e.g. Episode 01, Ep 01, or leading/isolated numbers)
    m_e = re.search(r"(?:Episode|Ep|E)\s*(\d+)", stem, re.IGNORECASE)
    if m_e:
        episode = int(m_e.group(1))
        after = stem[m_e.end():]
        title = clean_title(after)
        return season, episode, title

    # Look for isolated episode number like ' - 01 - ' or '01. Title' or '01 - Title'
    m_num = re.search(r"(?:^|[^\d])(\d{1,3})(?:[^\d]|$)", stem)
    if m_num:
        episode = int(m_num.group(1))
        after = stem[m_num.end():]
        title = clean_title(after)
        return season, episode, title

    return season, 999, clean_title(stem)


def scan_episodes(directory: Path) -> List[Episode]:
    """Recursively scans a show directory and returns a sorted list of Episodes."""
    directory = directory.expanduser().resolve()
    if not directory.exists() or not directory.is_dir():
        return []

    episodes: List[Episode] = []

    for root, _, files in os.walk(directory):
        root_path = Path(root)
        for fname in files:
            file_path = root_path / fname
            suffix = file_path.suffix.lower()

            if suffix not in VIDEO_EXTENSIONS:
                continue

            # Ignore sample/trailer files
            if any(p.search(fname) for p in IGNORE_PATTERNS):
                continue

            # Ignore hidden files or temporary files
            if fname.startswith("."):
                continue

            rel_path = str(file_path.relative_to(directory))
            season, episode_num, title = extract_metadata(file_path, directory)

            episodes.append(
                Episode(
                    path=file_path,
                    relative_path=rel_path,
                    season=season,
                    episode=episode_num,
                    title=title,
                )
            )

    episodes.sort(key=lambda ep: ep.sort_key)
    return episodes
