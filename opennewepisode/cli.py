#!/usr/bin/env python3
"""Command-line interface parser and dispatcher for OpenNewEpisode."""

import argparse
import sys
from pathlib import Path
from typing import List, Optional

from opennewepisode.scanner import scan_episodes
from opennewepisode.storage import ConfigManager, ShowData
from opennewepisode.player import (
    launch_vlc,
    launch_vlc_direct,
    prompt_post_watch,
    PostWatchAction,
)
from opennewepisode.ui import Colors, TerminalUI, render_progress_bar

__version__ = "1.0.0"


def cmd_play_next(
    ui: TerminalUI,
    resume_last: bool = False,
    show_name: Optional[str] = None,
    auto_play: Optional[bool] = None,
    from_start: bool = False,
):
    """Plays either next or last episode directly."""
    if auto_play is not None:
        ui.cfg.settings.auto_play_next = auto_play
    cfg = ui.cfg
    if show_name:
        if not cfg.set_active_show(show_name):
            print(f"{Colors.RED}Show '{show_name}' not found.{Colors.RESET}")
            sys.exit(1)

    active_info = cfg.get_active_show()
    if not active_info:
        print(f"{Colors.RED}No active show configured. Use 'opennewepisode add <folder>' first.{Colors.RESET}")
        sys.exit(1)

    name, show_data = active_info
    episodes = ui.get_episodes_for_show(show_data)
    if not episodes:
        print(f"{Colors.RED}No video files found in show path: {show_data.path}{Colors.RESET}")
        sys.exit(1)

    if resume_last:
        ep = show_data.get_last_watched_episode(episodes)
        if not ep:
            print(f"{Colors.YELLOW}No previous episode watched yet. Starting from beginning.{Colors.RESET}")
            ep = episodes[0]
    else:
        ep = show_data.get_next_episode(episodes)
        if not ep:
            print(f"{Colors.BRIGHT_GREEN}Series Complete! All {len(episodes)} episodes have been watched.{Colors.RESET}")
            return

    ui.play_episode(name, show_data, episodes, ep, from_start=from_start)


def cmd_list_shows(cfg: ConfigManager, ui: TerminalUI):
    """Prints all tracked shows with progress."""
    if not cfg.shows:
        print("No shows currently tracked.")
        return

    print(f"\n{Colors.BRIGHT_CYAN}Tracked TV Shows:{Colors.RESET}")
    for name in sorted(cfg.shows.keys()):
        s_data = cfg.shows[name]
        is_active = (name == cfg.active_show_name)
        active_mark = f" {Colors.BRIGHT_GREEN}[Active]{Colors.RESET}" if is_active else ""
        eps = ui.get_episodes_for_show(s_data)
        w_cnt, t_cnt, pct = s_data.get_progress(eps)
        p_bar = render_progress_bar(w_cnt, t_cnt, width=16)

        last_ep = s_data.get_last_watched_episode(eps)
        next_ep = s_data.get_next_episode(eps)
        last_str = last_ep.code if last_ep else "None"
        next_str = next_ep.code if next_ep else "Completed"

        print(f"  • {Colors.BOLD}{name}{Colors.RESET}{active_mark}")
        print(f"    Folder:    {Colors.DIM}{s_data.path}{Colors.RESET}")
        print(f"    Progress:  {Colors.CYAN}{p_bar}{Colors.RESET}")
        print(f"    Last/Next: {last_str} / {next_str}")
        print()


def cmd_list_episodes(ui: TerminalUI, show_name: Optional[str] = None):
    """Prints all episodes for a show."""
    cfg = ui.cfg
    if show_name:
        if show_name not in cfg.shows:
            print(f"{Colors.RED}Show '{show_name}' not found.{Colors.RESET}")
            sys.exit(1)
        target_name = show_name
    else:
        active_info = cfg.get_active_show()
        if not active_info:
            print("No active show.")
            sys.exit(1)
        target_name = active_info[0]

    s_data = cfg.shows[target_name]
    episodes = ui.get_episodes_for_show(s_data)

    print(f"\n{Colors.BRIGHT_CYAN}Episodes for {target_name} ({len(episodes)} total):{Colors.RESET}")
    current_season = None
    for ep in episodes:
        if ep.season != current_season:
            current_season = ep.season
            print(f"\n{Colors.BOLD}--- Season {current_season:02d} ---{Colors.RESET}")

        is_w = s_data.is_watched(ep)
        is_curr = (s_data.last_watched and s_data.last_watched.relative_path == ep.relative_path)
        check = f"{Colors.BRIGHT_GREEN}[✓]{Colors.RESET}" if is_w else f"{Colors.DIM}[ ]{Colors.RESET}"
        curr_indicator = f" {Colors.BRIGHT_YELLOW}◀ (Current){Colors.RESET}" if is_curr else ""
        print(f"  {check} {ep.display_name}{curr_indicator}")
    print()


def cmd_add_show(cfg: ConfigManager, path_str: str, name: Optional[str] = None):
    """Adds a new show path."""
    p = Path(path_str).expanduser().resolve()
    if not p.is_dir():
        print(f"{Colors.RED}Error: '{p}' is not a valid directory.{Colors.RESET}")
        sys.exit(1)

    eps = scan_episodes(p)
    if not eps:
        print(f"{Colors.RED}Warning: No video files detected in '{p}'.{Colors.RESET}")

    added_name, _ = cfg.add_show(p, name)
    print(f"{Colors.BRIGHT_GREEN}✓ Successfully added '{added_name}' ({len(eps)} episodes) as active show.{Colors.RESET}")


def cmd_set_episode(ui: TerminalUI, season: int, episode: int, show_name: Optional[str] = None):
    """Jumps progress to a specific season and episode."""
    cfg = ui.cfg
    if show_name and show_name in cfg.shows:
        s_data = cfg.shows[show_name]
    else:
        active_info = cfg.get_active_show()
        if not active_info:
            print("No active show.")
            sys.exit(1)
        s_data = active_info[1]

    episodes = ui.get_episodes_for_show(s_data)
    target = None
    for ep in episodes:
        if ep.season == season and ep.episode == episode:
            target = ep
            break

    if not target:
        print(f"{Colors.RED}Episode S{season:02d}E{episode:02d} not found in this show.{Colors.RESET}")
        sys.exit(1)

    s_data.mark_all_up_to(target, episodes)
    cfg.save()
    print(f"{Colors.BRIGHT_GREEN}✓ Updated progress: marked up to {target.display_name} as watched.{Colors.RESET}")


def cmd_open_file(
    ui: TerminalUI,
    file_path: str,
    from_start: bool = False,
    auto_play: Optional[bool] = None,
):
    """
    Handles opening a video file, whether triggered from GUI file manager
    (e.g. double click) or command line ('onep open <path>').
    """
    path_obj = Path(file_path).expanduser().resolve()
    if not path_obj.exists():
        print(f"{Colors.RED}File not found: {file_path}{Colors.RESET}")
        sys.exit(1)

    if auto_play is not None:
        ui.cfg.settings.auto_play_next = auto_play

    cfg = ui.cfg
    # Find which show (if any) contains this file
    matched_show_name = None
    matched_show_data = None
    for name, s_data in cfg.shows.items():
        show_root = Path(s_data.path).expanduser().resolve()
        try:
            path_obj.relative_to(show_root)
            matched_show_name = name
            matched_show_data = s_data
            break
        except ValueError:
            continue

    # Non-show video: pass directly to VLC
    if not matched_show_data:
        print(f"{Colors.GRAY}File does not belong to a tracked show. Launching VLC directly...{Colors.RESET}")
        launch_vlc_direct(path_obj, vlc_cmd=cfg.settings.vlc_command)
        return

    # Tracked show video: match episode
    episodes = ui.get_episodes_for_show(matched_show_data)
    show_root = Path(matched_show_data.path).expanduser().resolve()
    rel_path_str = str(path_obj.relative_to(show_root))
    target_ep = next((ep for ep in episodes if ep.relative_path == rel_path_str), None)

    if not target_ep:
        # File is inside show folder, but not recognized as a standard episode (e.g. extra/trailer)
        launch_vlc_direct(path_obj, vlc_cmd=cfg.settings.vlc_command)
        return

    # Episode recognized! Check current progress and resume state
    next_ep = matched_show_data.get_next_episode(episodes)
    resume_sec = matched_show_data.get_resume_seconds(target_ep)
    is_up_next = (next_ep and next_ep.relative_path == target_ep.relative_path)

    update_last_watched = True
    actual_from_start = from_start

    # If opened out of order (not current Up Next), prompt user
    if not is_up_next:
        from opennewepisode.dialogs import prompt_out_of_order, prompt_resume_or_start
        action = prompt_out_of_order(target_ep, next_ep, resume_seconds=resume_sec)
        if action == "cancel":
            return
        elif action == "current" and next_ep:
            # User chose to open current Up Next episode instead
            cur_resume = matched_show_data.get_resume_seconds(next_ep)
            if cur_resume > 0 and not actual_from_start:
                actual_from_start = prompt_resume_or_start(next_ep, cur_resume)
            ui.play_episode(
                matched_show_name,
                matched_show_data,
                episodes,
                next_ep,
                from_start=actual_from_start,
                update_last_watched=True,
            )
            return
        elif action == "one_off":
            update_last_watched = False
        elif action == "switch":
            update_last_watched = True
    else:
        # It is the current Up Next episode
        if resume_sec > 0 and not actual_from_start:
            actual_from_start = False

    ui.play_episode(
        matched_show_name,
        matched_show_data,
        episodes,
        target_ep,
        from_start=actual_from_start,
        update_last_watched=update_last_watched,
    )


def cmd_associate():
    """Associates OpenNewEpisode with video MIME types via xdg-mime."""
    import shutil
    import subprocess
    desktop_name = "opennewepisode.desktop"
    mime_types = [
        "video/x-matroska",
        "video/mp4",
        "video/x-msvideo",
        "video/quicktime",
        "video/webm",
        "video/x-flv",
    ]
    if not shutil.which("xdg-mime"):
        print(f"{Colors.RED}xdg-mime not found. Please associate OpenNewEpisode in your file manager.{Colors.RESET}")
        return

    for m in mime_types:
        subprocess.run(["xdg-mime", "default", desktop_name, m], check=False)
    print(f"{Colors.BRIGHT_GREEN}✓ Successfully set OpenNewEpisode as default video player for desktop double-click!{Colors.RESET}")
    print("Videos in your tracked TV shows will now automatically resume or ask what to do when double-clicked.")
    print("Non-show videos will open directly in VLC as usual.")


def main(argv: Optional[List[str]] = None):
    """Main CLI entrypoint."""
    cfg = ConfigManager()
    ui = TerminalUI(cfg)

    parser = argparse.ArgumentParser(
        prog="opennewepisode",
        description="Terminal-based TV show manager & VLC launcher that remembers where you left off.",
    )
    parser.add_argument("-v", "--version", action="version", version=f"%(prog)s {__version__}")

    subparsers = parser.add_subparsers(dest="command", help="Sub-commands")

    # play
    p_play = subparsers.add_parser("play", aliases=["p"], help="Play the up next episode")
    p_play.add_argument("--show", "-s", help="Show name (optional)")
    p_play.add_argument("--auto-play", action="store_true", default=None, help="Force auto-play next episode on")
    p_play.add_argument("--no-auto-play", action="store_true", default=None, help="Disable auto-play next episode")
    p_play.add_argument("--from-start", "--restart", action="store_true", help="Start playback from 0:00 instead of resuming")

    # resume
    p_res = subparsers.add_parser("resume", aliases=["r"], help="Reopen/resume the last watched episode")
    p_res.add_argument("--show", "-s", help="Show name (optional)")
    p_res.add_argument("--auto-play", action="store_true", default=None, help="Force auto-play next episode on")
    p_res.add_argument("--no-auto-play", action="store_true", default=None, help="Disable auto-play next episode")
    p_res.add_argument("--from-start", "--restart", action="store_true", help="Start playback from 0:00 instead of resuming")

    # list
    subparsers.add_parser("list", aliases=["ls"], help="List all tracked shows and watch progress")

    # episodes
    p_ep = subparsers.add_parser("episodes", aliases=["ep"], help="List all episodes for a show")
    p_ep.add_argument("show", nargs="?", help="Show name (optional, defaults to active show)")

    # add
    p_add = subparsers.add_parser("add", help="Add a new show folder to track")
    p_add.add_argument("path", help="Path to show folder")
    p_add.add_argument("--name", "-n", help="Custom name for the show")

    # switch
    p_sw = subparsers.add_parser("switch", help="Switch the active show")
    p_sw.add_argument("show", help="Show name to activate")

    # set
    p_set = subparsers.add_parser("set", help="Set progress to a specific season & episode")
    p_set.add_argument("season", type=int, help="Season number")
    p_set.add_argument("episode", type=int, help="Episode number")
    p_set.add_argument("--show", "-s", help="Show name (optional)")

    # remove
    p_rm = subparsers.add_parser("remove", aliases=["rm"], help="Stop tracking a show")
    p_rm.add_argument("show", help="Show name to remove")

    # open
    p_open = subparsers.add_parser("open", aliases=["o"], help="Open a video file with automatic show detection & resume")
    p_open.add_argument("file", help="Path to video file")
    p_open.add_argument("--from-start", "--restart", action="store_true", help="Start playback from 0:00 instead of resuming")
    p_open.add_argument("--auto-play", action="store_true", default=None, help="Force auto-play next episode on")
    p_open.add_argument("--no-auto-play", action="store_true", default=None, help="Disable auto-play next episode")

    # associate
    subparsers.add_parser("associate", help="Set OpenNewEpisode as default video player for desktop double-click")

    raw_args = list(argv) if argv is not None else sys.argv[1:]
    # If first argument is a video file path (and not a subcommand/flag), route directly to 'open'
    if raw_args and not raw_args[0].startswith("-"):
        first_arg = Path(raw_args[0]).expanduser()
        known_cmds = {
            "play", "p", "resume", "r", "list", "ls", "episodes", "ep",
            "add", "switch", "set", "remove", "rm", "open", "o", "associate"
        }
        if raw_args[0] not in known_cmds and (first_arg.is_file() or first_arg.suffix.lower() in {".mkv", ".mp4", ".avi", ".mov", ".wmv", ".m4v", ".webm", ".ts"}):
            raw_args = ["open"] + raw_args

    args = parser.parse_args(raw_args)

    if not args.command:
        # Launch interactive UI loop
        ui.run_main_loop()
        return

    auto_play = None
    if getattr(args, "no_auto_play", False):
        auto_play = False
    elif getattr(args, "auto_play", False):
        auto_play = True

    from_start = getattr(args, "from_start", False)

    if args.command in ("play", "p"):
        cmd_play_next(
            ui,
            resume_last=False,
            show_name=getattr(args, "show", None),
            auto_play=auto_play,
            from_start=from_start,
        )
    elif args.command in ("resume", "r"):
        cmd_play_next(
            ui,
            resume_last=True,
            show_name=getattr(args, "show", None),
            auto_play=auto_play,
            from_start=from_start,
        )
    elif args.command in ("open", "o"):
        cmd_open_file(
            ui,
            args.file,
            from_start=from_start,
            auto_play=auto_play,
        )
    elif args.command == "associate":
        cmd_associate()
    elif args.command in ("list", "ls"):
        cmd_list_shows(cfg, ui)
    elif args.command in ("episodes", "ep"):
        cmd_list_episodes(ui, show_name=getattr(args, "show", None))
    elif args.command == "add":
        cmd_add_show(cfg, args.path, name=getattr(args, "name", None))
    elif args.command == "switch":
        if cfg.set_active_show(args.show):
            print(f"{Colors.BRIGHT_GREEN}Switched active show to '{args.show}'.{Colors.RESET}")
        else:
            print(f"{Colors.RED}Show '{args.show}' not found.{Colors.RESET}")
    elif args.command == "set":
        cmd_set_episode(ui, args.season, args.episode, show_name=getattr(args, "show", None))
    elif args.command in ("remove", "rm"):
        if cfg.remove_show(args.show):
            print(f"{Colors.BRIGHT_GREEN}Removed show '{args.show}'.{Colors.RESET}")
        else:
            print(f"{Colors.RED}Show '{args.show}' not found.{Colors.RESET}")


if __name__ == "__main__":
    main()
