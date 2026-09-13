# OpenNewEpisode (onep) 📺

A clean, terminal-based TV show manager and VLC launcher that keeps track of your watched episodes and automatically continues where you left off.

Designed to be **generic for any TV series**, with automatic episode detection, progress tracking, and interactive terminal dashboard.

---

## 🚀 Features

- **Progress Memory & Smart Resume**:
  - Automatically polls VLC playback progress via Linux MPRIS2 D-Bus during playback and verifies position upon exit.
  - If you close an episode mid-way (< 90% watched), remembers your exact timestamp (e.g. `Resume at 24:15`) and resumes automatically at that point with VLC's native `--start-time`.
  - Restart from the beginning anytime via `--from-start` / `--restart` or from the interactive dashboard.
- **Smart Completion Detection**:
  - If you watch past the completion threshold (default: 90%), the episode is automatically marked complete and clears resume points.
- **Multi-Show Support**: Manage multiple TV series simultaneously; switch between shows with one command.
- **Smart Episode Scanner**:
  - Automatically sorts episodes across seasons (`S01E01`, `1x01`, `Season 1/01`, scene releases, etc.).
  - Extracts clean human-readable episode titles.
  - Filters out sample/trailer files.
- **VLC Integration**:
  - Launches VLC with optional `--fullscreen` and `--play-and-exit`.
  - Suppresses noisy player terminal logs.
  - **Auto-Play Next Episode**: Automatically advances and launches the next episode (including seamless transitions to the next season when a season ends) with a customizable countdown.
  - Automatically marks played episodes as watched by default.
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
| `onep play` (or `onep p`) | Immediately plays the Up Next episode (resumes if paused) |
| `onep play --from-start` | Plays Up Next from 0:00, ignoring any saved resume timestamp |
| `onep resume` (or `onep r`) | Reopens / resumes the last watched episode |
| `onep resume --from-start` | Reopens the last watched episode from the beginning (0:00) |
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

Settings customizable through the menu (Option 8) or in `config.json`:
- `fullscreen`: Whether VLC opens immediately in fullscreen mode (`--fullscreen`, default: `true`).
- `minimal_view`: Keeps VLC in clean minimal view mode (no toolbars or menus) when exiting fullscreen (`--qt-minimal-view`, default: `true`).
- `english_subtitles`: Automatically load and display the first English subtitle track found (`--sub-language=eng,en`, default: `true`).
- `english_audio`: Automatically select the first English audio track found (`--audio-language=eng,en`, default: `true`).
- `play_and_exit`: Closes VLC automatically when episode finishes (`--play-and-exit`, default: `true`).
- `auto_play_next`: Automatically plays the next episode upon completion across seasons (default: `true`).
- `auto_play_delay`: Countdown seconds before auto-playing next episode (default: `5`, set to `0` for immediate).
- `track_playback_progress`: Automatically poll VLC progress via MPRIS2 D-Bus to save resume points (default: `true`).
- `completion_threshold`: Percentage of duration watched to count episode as completed (default: `0.90` / 90%).
- `vlc_command`: VLC binary path (default: `vlc`).
- `extra_vlc_args`: Custom flags passed to VLC (e.g. `--sub-text-scale 120`).

---

## 🧪 Testing

Run the automated test suite:
```bash
python3 -m unittest discover tests
```

---

## 🤔 Why "onep"?

The name **`onep`** has a few fun and practical meanings:

1. **Direct Acronym**: A natural contraction of the project's title:  
   **O**pen**N**ew**EP**isode &rarr; **`onep`**.
2. **"Just One Ep"**: A tribute to the classic, universal binge-watcher's lie:  
   > *"Just **one ep**, and then I swear I'm going to sleep!"* 😴
3. **CLI Ergonomics**: Typing `opennewepisode` is 14 keystrokes. **`onep`** is a punchy 4-letter shortcut easily typed with one hand so you can get straight to watching.

---

## 🤝 Credits

- **Created by**: **Antigravity** (Google DeepMind)
- **Vibe Coding Assistance & Product Direction**: **Mario Matos** ([@marioscience](https://github.com/marioscience))

