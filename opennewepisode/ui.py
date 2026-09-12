#!/usr/bin/env python3
"""Interactive Terminal User Interface for OpenNewEpisode."""

import os
import readline
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from opennewepisode.scanner import Episode, scan_episodes
from opennewepisode.storage import ConfigManager, ShowData
from opennewepisode.player import PostWatchAction, launch_vlc, prompt_post_watch


class Colors:
    """ANSI color codes for terminal rendering."""
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    CYAN = "\033[36m"
    BRIGHT_CYAN = "\033[1;36m"
    GREEN = "\033[32m"
    BRIGHT_GREEN = "\033[1;32m"
    YELLOW = "\033[33m"
    BRIGHT_YELLOW = "\033[1;33m"
    RED = "\033[31m"
    BRIGHT_RED = "\033[1;31m"
    BLUE = "\033[34m"
    BRIGHT_BLUE = "\033[1;34m"
    MAGENTA = "\033[35m"
    GRAY = "\033[90m"


def setup_path_completion():
    """Configures readline to support tab completion for directory paths."""
    def path_completer(text: str, state: int):
        exp = os.path.expanduser(text)
        dirname, rest = os.path.split(exp)
        search_dir = dirname if dirname else "."
        try:
            entries = os.listdir(search_dir)
        except Exception:
            return None
        matches = []
        for e in sorted(entries):
            if e.startswith(rest):
                full = os.path.join(dirname, e) if dirname else e
                if os.path.isdir(os.path.expanduser(full)):
                    full += "/"
                matches.append(full)
        return matches[state] if state < len(matches) else None

    readline.set_completer_delims(" \t\n\"'")
    readline.set_completer(path_completer)
    readline.parse_and_bind("tab: complete")


def disable_completion():
    """Disables readline custom completer."""
    readline.set_completer(None)


def render_progress_bar(watched: int, total: int, width: int = 24) -> str:
    """Returns a visual progress bar string."""
    if total == 0:
        return f"[{'░' * width}] 0.0% (0/0)"
    frac = min(1.0, max(0.0, watched / total))
    filled = int(frac * width)
    empty = width - filled
    pct = frac * 100.0
    return f"[{'█' * filled}{'░' * empty}] {pct:5.1f}% ({watched}/{total} episodes)"


class TerminalUI:
    """Manages interactive terminal menus and commands."""

    def __init__(self, config_manager: ConfigManager):
        self.cfg = config_manager
        # Cache for scanned episodes: {show_path: [Episode, ...]}
        self.show_cache: Dict[str, List[Episode]] = {}

    def get_episodes_for_show(self, show_data: ShowData) -> List[Episode]:
        """Gets sorted episodes for a show, using cache if available."""
        if show_data.path in self.show_cache:
            return self.show_cache[show_data.path]
        eps = scan_episodes(Path(show_data.path))
        self.show_cache[show_data.path] = eps
        return eps

    def invalidate_cache(self, show_data: Optional[ShowData] = None):
        """Clears scan cache."""
        if show_data:
            self.show_cache.pop(show_data.path, None)
        else:
            self.show_cache.clear()

    def run_main_loop(self):
        """Main interactive loop."""
        while True:
            active_info = self.cfg.get_active_show()
            if not active_info:
                print(f"\n{Colors.BRIGHT_YELLOW}No shows currently registered.{Colors.RESET}")
                choice = input(f"Would you like to add a show now? [{Colors.BOLD}Y/n{Colors.RESET}]: ").strip().lower()
                if choice in ("", "y", "yes"):
                    self.menu_add_show()
                    continue
                else:
                    print("Goodbye!")
                    break

            show_name, show_data = active_info
            episodes = self.get_episodes_for_show(show_data)

            if not episodes:
                print(f"\n{Colors.BRIGHT_RED}Warning: No video files found in show path:{Colors.RESET}")
                print(f"  {show_data.path}")
                print("\nOptions: [a] Add another show | [s] Switch show | [r] Rescan | [q] Quit")
                c = input("Choice: ").strip().lower()
                if c == "a":
                    self.menu_add_show()
                elif c == "s":
                    self.menu_switch_show()
                elif c == "r":
                    self.invalidate_cache(show_data)
                elif c == "q":
                    break
                continue

            last_ep = show_data.get_last_watched_episode(episodes)
            next_ep = show_data.get_next_episode(episodes)
            watched_count, total_count, _ = show_data.get_progress(episodes)

            # Print main dashboard
            self.render_dashboard(show_name, show_data, episodes, last_ep, next_ep, watched_count, total_count)

            # Default action prompt
            default_action = "1" if next_ep else ("2" if last_ep else "5")
            try:
                choice = input(f"\n{Colors.BOLD}Select an option [{default_action}]: {Colors.RESET}").strip().lower()
            except (KeyboardInterrupt, EOFError):
                print(f"\n{Colors.CYAN}Goodbye!{Colors.RESET}")
                break

            if not choice:
                choice = default_action

            if choice == "1" and next_ep:
                self.play_episode(show_name, show_data, episodes, next_ep)
            elif choice == "2" and last_ep:
                self.play_episode(show_name, show_data, episodes, last_ep)
            elif choice == "3":
                self.action_skip_next(show_data, episodes)
            elif choice == "4":
                self.action_go_prev(show_data, episodes)
            elif choice == "5":
                self.menu_browse_episodes(show_name, show_data, episodes)
            elif choice == "6":
                self.menu_mark_progress(show_data, episodes)
            elif choice == "7":
                self.menu_shows_manager()
            elif choice == "8":
                self.menu_settings()
            elif choice in ("q", "quit", "exit"):
                print(f"\n{Colors.CYAN}Goodbye!{Colors.RESET}")
                break
            else:
                print(f"{Colors.BRIGHT_RED}Invalid option: {choice}{Colors.RESET}")

    def render_dashboard(
        self,
        show_name: str,
        show_data: ShowData,
        episodes: List[Episode],
        last_ep: Optional[Episode],
        next_ep: Optional[Episode],
        watched_count: int,
        total_count: int,
    ):
        """Renders the main menu dashboard."""
        term_width = min(80, max(60, os.get_terminal_size().columns if sys.stdout.isatty() else 80))
        border = "═" * term_width

        print()
        print(f"{Colors.BRIGHT_CYAN}{border}{Colors.RESET}")
        title_str = "📺  OPEN NEW EPISODE"
        print(f"{Colors.BOLD}{Colors.BRIGHT_CYAN}{title_str.center(term_width)}{Colors.RESET}")
        print(f"{Colors.BRIGHT_CYAN}{border}{Colors.RESET}")

        print(f" {Colors.BOLD}Show:{Colors.RESET}         {Colors.BRIGHT_GREEN}{show_name}{Colors.RESET}")
        print(f" {Colors.BOLD}Folder:{Colors.RESET}       {Colors.DIM}{show_data.path}{Colors.RESET}")
        progress_bar = render_progress_bar(watched_count, total_count)
        print(f" {Colors.BOLD}Progress:{Colors.RESET}     {Colors.CYAN}{progress_bar}{Colors.RESET}")

        if last_ep:
            status_text = "Watched" if (show_data.last_watched and show_data.last_watched.completed) else f"{Colors.YELLOW}Paused / In progress{Colors.RESET}"
            print(f" {Colors.BOLD}Last Played:{Colors.RESET}  {last_ep.display_name} ({status_text})")
        else:
            print(f" {Colors.BOLD}Last Played:{Colors.RESET}  {Colors.DIM}None (Ready to start series!){Colors.RESET}")

        if next_ep:
            print(f" {Colors.BOLD}Up Next:{Colors.RESET}      {Colors.BRIGHT_YELLOW}{next_ep.display_name}{Colors.RESET}")
        else:
            print(f" {Colors.BOLD}Up Next:{Colors.RESET}      {Colors.BRIGHT_GREEN}🎉 Series Complete! All episodes watched.{Colors.RESET}")

        print(f"{Colors.GRAY}{'-' * term_width}{Colors.RESET}")

        # Action options
        if next_ep:
            print(f"  {Colors.BRIGHT_GREEN}[1]{Colors.RESET} ▶  Play Up Next ({Colors.BOLD}{next_ep.code}{Colors.RESET})")
        else:
            print(f"  {Colors.DIM}[1] ▶  Play Up Next (Series complete){Colors.RESET}")

        if last_ep:
            print(f"  {Colors.BRIGHT_YELLOW}[2]{Colors.RESET} ↺  Replay / Resume Last ({Colors.BOLD}{last_ep.code}{Colors.RESET})")
        else:
            print(f"  {Colors.DIM}[2] ↺  Replay / Resume Last (None){Colors.RESET}")

        print(f"  {Colors.CYAN}[3]{Colors.RESET} ⏩ Advance Next without playing")
        print(f"  {Colors.CYAN}[4]{Colors.RESET} ⏮  Step back to Previous episode")
        print(f"  {Colors.CYAN}[5]{Colors.RESET} 📜 Browse Seasons & Episodes (Pick any episode)")
        print(f"  {Colors.CYAN}[6]{Colors.RESET} ✔  Mark Progress (Jump ahead or mark as watched)")
        print(f"  {Colors.MAGENTA}[7]{Colors.RESET} 📁 Switch Show / Add New Show ({len(self.cfg.shows)} registered)")
        print(f"  {Colors.BLUE}[8]{Colors.RESET} ⚙  Player Settings (Fullscreen, VLC options)")
        print(f"  {Colors.RED}[q]{Colors.RESET} Quit")
        print(f"{Colors.GRAY}{'-' * term_width}{Colors.RESET}")

    def play_episode(
        self,
        show_name: str,
        show_data: ShowData,
        episodes: List[Episode],
        episode: Episode,
    ):
        """Launches playback and handles post-watch state transitions."""
        current_ep = episode
        while current_ep:
            # Find next episode relative to current
            try:
                curr_idx = episodes.index(current_ep)
                next_in_line = episodes[curr_idx + 1] if curr_idx + 1 < len(episodes) else None
            except ValueError:
                next_in_line = None

            print(f"\n{Colors.BRIGHT_GREEN}=================================================={Colors.RESET}")
            print(f"▶ {Colors.BOLD}Opening VLC for:{Colors.RESET} {Colors.BRIGHT_CYAN}{show_name}{Colors.RESET}")
            print(f"  {Colors.BOLD}{current_ep.display_name}{Colors.RESET}")
            print(f"{Colors.DIM}  File: {current_ep.path}{Colors.RESET}")

            # Display active player options
            s = self.cfg.settings
            if s.fullscreen and s.minimal_view:
                mode_str = "Fullscreen (Minimal Interface on exit)"
            elif s.fullscreen:
                mode_str = "Fullscreen"
            elif s.minimal_view:
                mode_str = "Minimized Window (--qt-minimal-view)"
            else:
                mode_str = "Standard Window"
            print(f"  {Colors.BOLD}View Mode:{Colors.RESET}  {mode_str}")
            if s.english_audio:
                print(f"  {Colors.BOLD}Audio:{Colors.RESET}      English (first found)")
            if s.english_subtitles:
                print(f"  {Colors.BOLD}Subtitles:{Colors.RESET}  English (first found)")
            print(f"{Colors.BRIGHT_GREEN}=================================================={Colors.RESET}")
            print(f"{Colors.GRAY}(Waiting for VLC playback to finish...){Colors.RESET}")

            # Record that we opened this episode (completed=False until confirmed)
            show_data.mark_watched(current_ep, completed=False)
            self.cfg.save()

            # Launch VLC
            launch_vlc(current_ep, self.cfg.settings)

            # Post-watch prompt
            action = prompt_post_watch(current_ep, next_in_line)

            if action == PostWatchAction.MARK_WATCHED_AND_ADVANCE:
                show_data.mark_watched(current_ep, completed=True)
                self.cfg.save()
                print(f"{Colors.BRIGHT_GREEN}✓ Marked {current_ep.code} as watched.{Colors.RESET}")
                break

            elif action == PostWatchAction.PLAY_NEXT:
                show_data.mark_watched(current_ep, completed=True)
                self.cfg.save()
                print(f"{Colors.BRIGHT_GREEN}✓ Marked {current_ep.code} as watched.{Colors.RESET}")
                current_ep = next_in_line

            elif action == PostWatchAction.KEEP_CURRENT:
                # Keep completed = False so it re-opens this exact one next time
                show_data.mark_watched(current_ep, completed=False)
                self.cfg.save()
                print(f"{Colors.YELLOW}↺ Kept {current_ep.code} as current (will reopen here next time).{Colors.RESET}")
                break

            elif action == PostWatchAction.QUIT:
                break

    def action_skip_next(self, show_data: ShowData, episodes: List[Episode]):
        """Advances pointer to next episode without launching player."""
        next_ep = show_data.get_next_episode(episodes)
        if not next_ep:
            print(f"\n{Colors.YELLOW}Already at the end of the series.{Colors.RESET}")
            return
        show_data.mark_watched(next_ep, completed=True)
        self.cfg.save()
        print(f"\n{Colors.BRIGHT_GREEN}✓ Skipped ahead. Marked {next_ep.code} as watched.{Colors.RESET}")

    def action_go_prev(self, show_data: ShowData, episodes: List[Episode]):
        """Steps back pointer to previous episode."""
        last_ep = show_data.get_last_watched_episode(episodes)
        if not last_ep:
            print(f"\n{Colors.YELLOW}Already at the start of the series.{Colors.RESET}")
            return
        try:
            curr_idx = episodes.index(last_ep)
            if curr_idx > 0:
                prev_ep = episodes[curr_idx - 1]
                show_data.mark_unwatched(last_ep)
                show_data.mark_watched(prev_ep, completed=True)
                self.cfg.save()
                print(f"\n{Colors.BRIGHT_CYAN}⏮ Stepped back to {prev_ep.display_name}.{Colors.RESET}")
            else:
                show_data.mark_unwatched(last_ep)
                show_data.last_watched = None
                self.cfg.save()
                print(f"\n{Colors.BRIGHT_CYAN}⏮ Reset back to start of series.{Colors.RESET}")
        except ValueError:
            pass

    def menu_browse_episodes(self, show_name: str, show_data: ShowData, episodes: List[Episode]):
        """Interactive browser grouped by seasons."""
        # Group episodes by season
        seasons: Dict[int, List[Episode]] = {}
        for ep in episodes:
            seasons.setdefault(ep.season, []).append(ep)

        sorted_seasons = sorted(seasons.keys())

        while True:
            print(f"\n{Colors.BRIGHT_CYAN}--- {show_name}: Select Season ---{Colors.RESET}")
            for idx, s_num in enumerate(sorted_seasons, start=1):
                s_eps = seasons[s_num]
                watched_in_s = sum(1 for e in s_eps if show_data.is_watched(e))
                status = f"{Colors.BRIGHT_GREEN}[✓ All Watched]{Colors.RESET}" if watched_in_s == len(s_eps) else f"{watched_in_s}/{len(s_eps)} watched"
                print(f"  [{Colors.BOLD}{idx}{Colors.RESET}] Season {s_num:02d} ({len(s_eps)} episodes) - {status}")
            print(f"  [{Colors.RED}b{Colors.RESET}] Back to Main Menu")

            choice = input(f"\nSelect season [1-{len(sorted_seasons)}] or 'b': ").strip().lower()
            if choice == "b" or not choice:
                break

            try:
                s_idx = int(choice) - 1
                if 0 <= s_idx < len(sorted_seasons):
                    selected_season = sorted_seasons[s_idx]
                    self._browse_season_episodes(show_name, show_data, episodes, seasons[selected_season])
            except ValueError:
                print(f"{Colors.RED}Invalid input.{Colors.RESET}")

    def _browse_season_episodes(
        self,
        show_name: str,
        show_data: ShowData,
        all_episodes: List[Episode],
        season_episodes: List[Episode],
    ):
        """Browse episodes within a selected season."""
        while True:
            print(f"\n{Colors.BRIGHT_CYAN}--- Season {season_episodes[0].season} Episodes ---{Colors.RESET}")
            for idx, ep in enumerate(season_episodes, start=1):
                is_w = show_data.is_watched(ep)
                is_curr = (show_data.last_watched and show_data.last_watched.relative_path == ep.relative_path)
                check = f"{Colors.BRIGHT_GREEN}[✓]{Colors.RESET}" if is_w else f"{Colors.DIM}[ ]{Colors.RESET}"
                curr_indicator = f" {Colors.BRIGHT_YELLOW}◀ (Current){Colors.RESET}" if is_curr else ""
                print(f"  [{Colors.BOLD}{idx:2d}{Colors.RESET}] {check} {ep.display_name}{curr_indicator}")

            print(f"  [{Colors.RED}b{Colors.RESET}] Back to Seasons")
            choice = input("\nSelect episode number to play, or [m#] to mark watched, or 'b': ").strip().lower()

            if choice == "b" or not choice:
                break

            # Handle marking watched e.g. "m3" or "u3" (unwatched)
            if choice.startswith("m") and choice[1:].isdigit():
                ep_idx = int(choice[1:]) - 1
                if 0 <= ep_idx < len(season_episodes):
                    target = season_episodes[ep_idx]
                    show_data.mark_watched(target, completed=True)
                    self.cfg.save()
                    print(f"{Colors.BRIGHT_GREEN}✓ Marked {target.code} as watched.{Colors.RESET}")
                continue

            try:
                ep_idx = int(choice) - 1
                if 0 <= ep_idx < len(season_episodes):
                    target = season_episodes[ep_idx]
                    print(f"\nActions for {Colors.BOLD}{target.display_name}{Colors.RESET}:")
                    print(f"  [1] ▶ Play now")
                    print(f"  [2] ✔ Mark as current episode (Up Next)")
                    print(f"  [3] ⏩ Mark all episodes UP TO here as watched")
                    print(f"  [b] Cancel")
                    sub = input("Choice [1]: ").strip().lower()
                    if sub in ("", "1"):
                        self.play_episode(show_name, show_data, all_episodes, target)
                    elif sub == "2":
                        target_idx = all_episodes.index(target)
                        if target_idx > 0:
                            prev_ep = all_episodes[target_idx - 1]
                            mark_prev = input(f"Mark all {target_idx} preceding episodes (before {target.code}) as watched? [Y/n]: ").strip().lower()
                            if mark_prev in ("", "y", "yes"):
                                show_data.mark_all_up_to(prev_ep, all_episodes)
                        show_data.mark_watched(target, completed=False)
                        self.cfg.save()
                        print(f"{Colors.BRIGHT_GREEN}✓ Set {target.code} as current episode.{Colors.RESET}")
                    elif sub == "3":
                        show_data.mark_all_up_to(target, all_episodes)
                        self.cfg.save()
                        print(f"{Colors.BRIGHT_GREEN}✓ Marked all episodes up to {target.code} as watched!{Colors.RESET}")
            except ValueError:
                print(f"{Colors.RED}Invalid input.{Colors.RESET}")

    def menu_mark_progress(self, show_data: ShowData, episodes: List[Episode]):
        """Quick jump to mark progress up to an episode."""
        print(f"\n{Colors.BRIGHT_CYAN}--- Jump to Episode / Mark Catchup ---{Colors.RESET}")
        print("Useful if you previously watched episodes outside this program.")
        print("Format: Season and Episode (e.g. '1 5' for S01E05 or 'S02E03')")
        val = input("Enter season and episode [or Enter to cancel]: ").strip()
        if not val:
            return

        import re
        m = re.search(r"(?:[sS]?(\d+)\s*[eE]?(\d+))", val)
        if not m:
            print(f"{Colors.RED}Could not parse format. Example: '1 4' or 'S01E04'{Colors.RESET}")
            return

        target_s = int(m.group(1))
        target_e = int(m.group(2))

        # Find closest match
        target_ep = None
        for ep in episodes:
            if ep.season == target_s and ep.episode == target_e:
                target_ep = ep
                break

        if not target_ep:
            print(f"{Colors.RED}Episode S{target_s:02d}E{target_e:02d} not found in this show.{Colors.RESET}")
            return

        target_idx = episodes.index(target_ep)
        print(f"\nSelected: {Colors.BOLD}{target_ep.display_name}{Colors.RESET}")
        print(f"  [1] Mark up to and INCLUDING this episode as WATCHED ({target_idx + 1} episodes)")
        print(f"  [2] Set this as the NEXT episode to watch (marks {target_idx} prior episodes as watched)")
        print("  [c] Cancel")
        c = input("Choice [1]: ").strip().lower()

        if c in ("", "1"):
            show_data.mark_all_up_to(target_ep, episodes)
            self.cfg.save()
            print(f"{Colors.BRIGHT_GREEN}✓ Marked all {target_idx + 1} episodes up to {target_ep.code} as watched!{Colors.RESET}")
        elif c == "2":
            if target_idx > 0:
                prev_ep = episodes[target_idx - 1]
                show_data.mark_all_up_to(prev_ep, episodes)
            else:
                show_data.last_watched = None
                show_data.watched_rel_paths.clear()
            self.cfg.save()
            print(f"{Colors.BRIGHT_GREEN}✓ Next episode set to {target_ep.code}. Marked {target_idx} preceding episodes as watched!{Colors.RESET}")

    def menu_shows_manager(self):
        """Manager for switching, adding, or deleting shows."""
        while True:
            print(f"\n{Colors.BRIGHT_CYAN}--- Manage Shows ---{Colors.RESET}")
            show_names = sorted(self.cfg.shows.keys())
            for idx, name in enumerate(show_names, start=1):
                s_data = self.cfg.shows[name]
                active_flag = f" {Colors.BRIGHT_GREEN}◀ Active{Colors.RESET}" if name == self.cfg.active_show_name else ""
                eps = self.get_episodes_for_show(s_data)
                w_count, t_count, pct = s_data.get_progress(eps)
                print(f"  [{Colors.BOLD}{idx}{Colors.RESET}] {Colors.BOLD}{name}{Colors.RESET}{active_flag}")
                print(f"      {Colors.DIM}{s_data.path}{Colors.RESET}")
                print(f"      Progress: {w_count}/{t_count} ({pct:.1f}%)")

            print(f"\n  [{Colors.BRIGHT_GREEN}a{Colors.RESET}] ➕ Add New Show")
            print(f"  [{Colors.BRIGHT_RED}d{Colors.RESET}] 🗑  Delete a Show")
            print(f"  [{Colors.RED}b{Colors.RESET}] Back to Main Menu")

            choice = input("\nSelect show number to activate, or [a/d/b]: ").strip().lower()
            if choice == "b" or not choice:
                break
            elif choice == "a":
                self.menu_add_show()
            elif choice == "d":
                self.menu_delete_show()
            else:
                try:
                    s_idx = int(choice) - 1
                    if 0 <= s_idx < len(show_names):
                        selected = show_names[s_idx]
                        self.cfg.set_active_show(selected)
                        print(f"{Colors.BRIGHT_GREEN}Switched active show to: {selected}{Colors.RESET}")
                        break
                except ValueError:
                    print(f"{Colors.RED}Invalid selection.{Colors.RESET}")

    def menu_add_show(self):
        """Prompt to add a new show directory."""
        print(f"\n{Colors.BRIGHT_CYAN}--- Add New TV Show ---{Colors.RESET}")
        print("Enter the folder path where the show episodes are located.")
        print(f"{Colors.DIM}(Tip: You can use Tab for path auto-completion){Colors.RESET}")

        setup_path_completion()
        try:
            path_input = input("Folder path: ").strip()
        except (KeyboardInterrupt, EOFError):
            print()
            disable_completion()
            return
        finally:
            disable_completion()

        if not path_input:
            return

        p = Path(path_input).expanduser().resolve()
        if not p.is_dir():
            print(f"{Colors.RED}Error: '{p}' is not a valid directory.{Colors.RESET}")
            return

        # Scan folder for episodes
        print(f"Scanning '{p}' for video files...")
        eps = scan_episodes(p)
        if not eps:
            print(f"{Colors.RED}No media files found in that directory.{Colors.RESET}")
            return

        print(f"{Colors.BRIGHT_GREEN}Found {len(eps)} episodes!{Colors.RESET}")

        default_name = p.name
        # Clean folder name
        clean_name = p.name
        import re
        clean_name = re.split(r"(?i)\s+(?:1080p|720p|2160p|Complete|WEB|BluRay)", clean_name)[0].strip()

        name_input = input(f"Show Name [{clean_name}]: ").strip()
        show_name = name_input if name_input else clean_name

        self.cfg.add_show(p, show_name)
        self.show_cache[str(p)] = eps
        print(f"{Colors.BRIGHT_GREEN}✓ Added '{show_name}' and set as active show!{Colors.RESET}")

    def menu_delete_show(self):
        """Remove a show from tracking."""
        show_names = sorted(self.cfg.shows.keys())
        if not show_names:
            print("No shows to delete.")
            return

        print("\nSelect show to delete from tracker (does NOT delete any video files):")
        for idx, name in enumerate(show_names, start=1):
            print(f"  [{idx}] {name}")
        c = input("Number to delete (or Enter to cancel): ").strip()
        if not c:
            return
        try:
            idx = int(c) - 1
            if 0 <= idx < len(show_names):
                target_name = show_names[idx]
                confirm = input(f"Are you sure you want to stop tracking '{target_name}'? [y/N]: ").strip().lower()
                if confirm in ("y", "yes"):
                    self.cfg.remove_show(target_name)
                    print(f"{Colors.BRIGHT_GREEN}Removed '{target_name}' from tracker.{Colors.RESET}")
        except ValueError:
            print(f"{Colors.RED}Invalid input.{Colors.RESET}")

    def menu_settings(self):
        """Configure VLC options and preferences."""
        while True:
            s = self.cfg.settings
            print(f"\n{Colors.BRIGHT_CYAN}--- Player Settings ---{Colors.RESET}")
            mv_status = f"{Colors.BRIGHT_GREEN}ON{Colors.RESET}" if s.minimal_view else f"{Colors.RED}OFF{Colors.RESET}"
            fs_status = f"{Colors.BRIGHT_GREEN}ON{Colors.RESET}" if s.fullscreen else f"{Colors.RED}OFF{Colors.RESET}"
            sub_status = f"{Colors.BRIGHT_GREEN}ON{Colors.RESET}" if s.english_subtitles else f"{Colors.RED}OFF{Colors.RESET}"
            aud_status = f"{Colors.BRIGHT_GREEN}ON{Colors.RESET}" if s.english_audio else f"{Colors.RED}OFF{Colors.RESET}"
            pe_status = f"{Colors.BRIGHT_GREEN}ON{Colors.RESET}" if s.play_and_exit else f"{Colors.RED}OFF{Colors.RESET}"

            print(f"  [1] Minimized View Mode (--qt-minimal-view): {mv_status}")
            print(f"  [2] Fullscreen Mode: {fs_status}")
            print(f"  [3] Auto English Subtitles: {sub_status}")
            print(f"  [4] Auto English Audio: {aud_status}")
            print(f"  [5] Auto-Exit on Finish (--play-and-exit): {pe_status}")
            print(f"  [6] VLC Command: {Colors.BOLD}{s.vlc_command}{Colors.RESET}")
            print(f"  [7] Extra VLC Arguments: {s.extra_vlc_args or 'None'}")
            print(f"  [{Colors.RED}b{Colors.RESET}] Back to Main Menu")

            c = input("\nToggle setting [1-7] or 'b': ").strip().lower()
            if c == "b" or not c:
                break
            elif c == "1":
                s.minimal_view = not s.minimal_view
                self.cfg.save()
            elif c == "2":
                s.fullscreen = not s.fullscreen
                self.cfg.save()
            elif c == "3":
                s.english_subtitles = not s.english_subtitles
                self.cfg.save()
            elif c == "4":
                s.english_audio = not s.english_audio
                self.cfg.save()
            elif c == "5":
                s.play_and_exit = not s.play_and_exit
                self.cfg.save()
            elif c == "6":
                new_cmd = input(f"Enter VLC executable path/command [{s.vlc_command}]: ").strip()
                if new_cmd:
                    s.vlc_command = new_cmd
                    self.cfg.save()
            elif c == "7":
                print("Enter space-separated VLC arguments (e.g. '--sub-text-scale 120'):")
                args_str = input("Args: ").strip()
                s.extra_vlc_args = args_str.split() if args_str else []
                self.cfg.save()
