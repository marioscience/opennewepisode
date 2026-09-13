#!/usr/bin/env bash
# Installation script for OpenNewEpisode
# Creates symlinks in ~/.local/bin for global terminal access

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TARGET_DIR="${HOME}/.local/bin"
ENTRYPOINT="${SCRIPT_DIR}/opennewepisode.py"

mkdir -p "${TARGET_DIR}"
chmod +x "${ENTRYPOINT}"

# Create symlinks
ln -sf "${ENTRYPOINT}" "${TARGET_DIR}/opennewepisode"
ln -sf "${ENTRYPOINT}" "${TARGET_DIR}/onep"

# Install desktop entry for GUI double-click integration
APP_DIR="${HOME}/.local/share/applications"
mkdir -p "${APP_DIR}"
sed "s|^Exec=.*|Exec=${TARGET_DIR}/onep open %f|" "${SCRIPT_DIR}/opennewepisode.desktop" > "${APP_DIR}/opennewepisode.desktop"

if command -v update-desktop-database >/dev/null 2>&1; then
    update-desktop-database "${APP_DIR}" >/dev/null 2>&1 || true
fi

echo -e "\033[1;32m✓ OpenNewEpisode installed successfully!\033[0m"
echo -e "You can now run either:"
echo -e "  \033[1;36mopennewepisode\033[0m   (Launch interactive menu or CLI commands)"
echo -e "  \033[1;36monep\033[0m             (Short shortcut)"
echo
echo -e "Desktop Integration:"
echo -e "  OpenNewEpisode is now registered in your desktop application menu."
echo -e "  Right-click any video file in Files -> Open With Other Application -> OpenNewEpisode."
echo -e "  Or run: \033[1monep associate\033[0m to set it as default video player for double-click."
echo
echo -e "Try it now:"
echo -e "  \033[1monep\033[0m            -> Launch interactive dashboard"
echo -e "  \033[1monep play\033[0m       -> Play up next episode immediately"
echo -e "  \033[1monep resume\033[0m     -> Resume/reopen last episode"
echo -e "  \033[1monep open <file>\033[0m -> Open video with auto-show detection & resume"
echo -e "  \033[1monep list\033[0m       -> List all shows and progress"
