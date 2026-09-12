# OpenNewEpisode (onep) 📺

A clean, terminal-based TV show manager and VLC launcher that keeps track of your watched episodes and automatically continues where you left off.

Designed to be **generic for any TV series**, with automatic episode detection, progress tracking, and interactive terminal dashboard.

---

## 🚀 Features

- **Progress Memory**: Tracks exactly which episode you watched, whether it was finished, and automatically queues the next one.
- **Resume Capability**: If you close an episode mid-way, it can reopen that same episode to continue from where you stopped (using VLC's native playback position resume).
- **Multi-Show Support**: Manage multiple TV series simultaneously; switch between shows with one command.
- **Smart Episode Scanner**:
  - Automatically sorts episodes across seasons (`S01E01`, `1x01`, `Season 1/01`, scene releases, etc.).
  - Extracts clean human-readable episode titles.
  - Filters out sample/trailer files.
- **VLC Integration**:
  - Launches VLC with optional `--fullscreen` and `--play-and-exit`.
  - Suppresses noisy player terminal logs.
  - Interactive post-playback prompt to mark watched, advance, or binge-watch the next episode.
- **Zero External Dependencies**: Pure Python 3 standard library. No `pip install` required.
- **Global Terminal Access**: Run `opennewepisode` or shortcut `onep` anywhere in your terminal.

---

## 📦 Quick Start

### 1. Installation
The symlink is installed into `~/.local/bin` (already in your `$PATH`):

```bash
./install.sh
```

Now you can invoke either `opennewepisode` or `onep`.

---

## 🎮 How to Use

### Interactive Mode (Recommended)
Simply type:
```bash
onep
```
This opens the interactive dashboard:

```text
════════════════════════════════════════════════════════════════════════════════
                             📺  OPEN NEW EPISODE
════════════════════════════════════════════════════════════════════════════════
 Show:         Fear the Walking Dead
 Folder:       /media/mario/Short-TANK/TEMP TO LONG/Fear the Walking Dead 2015 Complete Series 1080p WEB x264 [i_c]
 Progress:     [░░░░░░░░░░░░░░░░░░░░░░░░]   0.0% (0/113 episodes)
 Last Played:  None (Ready to start series!)
 Up Next:      S01E01 - Pilot
--------------------------------------------------------------------------------
  [1] ▶  Play Up Next (S01E01)
  [2] ↺  Replay / Resume Last (None)
  [3] ⏩ Advance Next without playing
  [4] ⏮  Step back to Previous episode
  [5] 📜 Browse Seasons & Episodes (Pick any episode)
  [6] ✔  Mark Progress (Jump ahead or mark as watched)
  [7] 📁 Switch Show / Add New Show (1 registered)
  [8] ⚙  Player Settings (Fullscreen, VLC options)
  [q] Quit
--------------------------------------------------------------------------------
Select an option [1]:
```

- Just press **Enter** to start playing the next episode!
- After VLC closes, you will be prompted whether you finished the episode:
  - **`[Y]` (Enter)**: Marks watched, advances next episode pointer.
  - **`[p]`**: Marks watched and immediately starts playing the next episode (binge mode).
  - **`[n]`**: Keeps this episode as current (so next time it reopens it to continue).

---

### Command Line Shortcuts

For quick execution without entering the menu:

| Command | Description |
|---|---|
| `onep play` (or `onep p`) | Immediately plays the Up Next episode |
| `onep resume` (or `onep r`) | Reopens / resumes the last watched episode |
| `onep list` (or `onep ls`) | Displays all tracked shows and progress |
| `onep episodes [show]` | Lists all seasons & episodes with `[✓]` watched status |
| `onep add <folder>` | Adds a new show folder to track |
| `onep switch <show>` | Switches the active show |
| `onep set <season> <episode>` | Jump progress up to a specific episode (e.g. `onep set 1 3`) |
| `onep remove <show>` | Removes a show from the tracker |

---

## ⚙️ Configuration & State

State and settings are stored in standard XDG JSON format at:
```
~/.config/opennewepisode/config.json
```

Settings customizable through the menu or file:
- `fullscreen`: Whether VLC opens in fullscreen mode (`true`/`false`).
- `play_and_exit`: Closes VLC automatically when episode finishes (`true`/`false`).
- `vlc_command`: VLC binary path (default: `vlc`).
- `extra_vlc_args`: Custom flags passed to VLC (e.g., subtitle preferences, audio tracks).

---

## 🧪 Testing

Run the automated test suite:
```bash
python3 -m unittest discover tests
```
