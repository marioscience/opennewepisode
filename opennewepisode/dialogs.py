#!/usr/bin/env python3
"""
GUI and CLI dialog helpers for OpenNewEpisode.
Provides native desktop dialogs (zenity) when launched without a terminal (e.g. file manager double click),
with seamless fallback to terminal prompts when running interactively.
"""

import html
import shutil
import subprocess
import sys
from typing import Optional

from opennewepisode.player import format_seconds
from opennewepisode.scanner import Episode


def is_gui_mode() -> bool:
    """Returns True if the program is running without an interactive terminal."""
    return not sys.stdin.isatty()


def notify_desktop(title: str, message: str, timeout_ms: int = 5000) -> None:
    """Sends a desktop notification using notify-send if available."""
    if shutil.which("notify-send"):
        try:
            subprocess.run(
                ["notify-send", "-a", "OpenNewEpisode", title, message, "-t", str(timeout_ms)],
                check=False,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except Exception:
            pass


def prompt_out_of_order(
    target_ep: Episode,
    current_up_next: Optional[Episode],
    resume_seconds: int = 0,
) -> str:
    """
    Prompts the user when an episode is opened out of order.
    Returns one of:
      - 'switch': Play target episode and update progress / Up Next here.
      - 'one_off': Play target episode as one-off without updating Up Next.
      - 'current': Play the current Up Next episode instead.
      - 'cancel': Cancel playback.
    """
    curr_text = current_up_next.display_name if current_up_next else "None"
    resume_info = f" (paused at {format_seconds(resume_seconds)})" if resume_seconds > 0 else ""

    if is_gui_mode() and shutil.which("zenity"):
        opt_switch = f"Play {target_ep.code} and switch progress here"
        opt_one_off = f"Play {target_ep.code} as a one-off (keep {current_up_next.code if current_up_next else 'current'} as Up Next)"
        opt_current = f"Open {current_up_next.code if current_up_next else 'current'} instead (where you left off)"

        target_name_esc = html.escape(target_ep.display_name, quote=False)
        curr_text_esc = html.escape(curr_text, quote=False)
        resume_info_esc = html.escape(resume_info, quote=False)

        prompt_text = (
            f"You opened: <b>{target_name_esc}</b>{resume_info_esc}\n"
            f"Your current progress is at: <b>{curr_text_esc}</b>\n\n"
            f"What would you like to do?"
        )

        cmd = [
            "zenity",
            "--list",
            "--title=OpenNewEpisode",
            f"--text={prompt_text}",
            "--radiolist",
            "--column=Select",
            "--column=Action",
            "--hide-header",
            "TRUE",
            opt_switch,
            "FALSE",
            opt_one_off,
            "FALSE",
            opt_current,
            "--width=560",
            "--height=260",
        ]
        try:
            res = subprocess.run(cmd, capture_output=True, text=True, check=False)
            if res.returncode == 1:
                # User clicked Cancel or closed dialog
                return "cancel"
            elif res.returncode == 0:
                choice = res.stdout.strip()
                if choice == opt_one_off:
                    return "one_off"
                elif choice == opt_current:
                    return "current"
                return "switch"
            return "switch"
        except Exception:
            return "switch"

    # Terminal CLI mode
    print(f"\n▶ Opened: {target_ep.display_name}{resume_info}")
    print(f"▶ Current Up Next: {curr_text}")
    print("--------------------------------------------------")
    print(f"  [1] Play {target_ep.code} and switch progress here (Default)")
    print(f"  [2] Play {target_ep.code} as a one-off (keep {current_up_next.code if current_up_next else 'current'} as Up Next)")
    if current_up_next:
        print(f"  [3] Open {current_up_next.code} instead (resume where you left off)")
    print("  [c] Cancel")
    print("--------------------------------------------------")
    try:
        ans = input("Choice [1]: ").strip().lower()
        if ans in ("", "1"):
            return "switch"
        elif ans == "2":
            return "one_off"
        elif ans == "3" and current_up_next:
            return "current"
        return "cancel"
    except (EOFError, KeyboardInterrupt):
        return "cancel"


def prompt_resume_or_start(ep: Episode, resume_seconds: int) -> bool:
    """
    Prompts whether to resume playback or restart from 0:00.
    Returns:
      True if user wants to start from 0:00 (from_start=True).
      False if user wants to resume from resume_seconds (from_start=False).
    """
    if resume_seconds <= 0:
        return False

    time_str = format_seconds(resume_seconds)

    if is_gui_mode() and shutil.which("zenity"):
        ep_name_esc = html.escape(ep.display_name, quote=False)
        time_str_esc = html.escape(time_str, quote=False)
        prompt_text = (
            f"<b>{ep_name_esc}</b> was stopped at <b>{time_str_esc}</b>.\n\n"
            f"Do you want to resume playback from {time_str_esc} or start from the beginning?"
        )
        cmd = [
            "zenity",
            "--question",
            "--title=OpenNewEpisode",
            f"--text={prompt_text}",
            f"--ok-label=Resume ({time_str})",
            "--cancel-label=Restart (0:00)",
            "--width=450",
        ]
        try:
            res = subprocess.run(cmd, check=False)
            # OK (0) means resume (from_start=False), Cancel (1) means restart (from_start=True)
            return res.returncode != 0
        except Exception:
            return False

    # CLI mode
    try:
        ans = input(f"Episode was stopped at {time_str}. Resume from there? [Y/n]: ").strip().lower()
        return ans in ("n", "no")
    except (EOFError, KeyboardInterrupt):
        return False
