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

echo -e "\033[1;32m✓ OpenNewEpisode installed successfully!\033[0m"
echo -e "You can now run either:"
echo -e "  \033[1;36mopennewepisode\033[0m   (Launch interactive menu or CLI commands)"
echo -e "  \033[1;36monep\033[0m             (Short shortcut)"
echo
echo -e "Try it now:"
echo -e "  \033[1monep\033[0m            -> Launch interactive dashboard"
echo -e "  \033[1monep play\033[0m       -> Play up next episode immediately"
echo -e "  \033[1monep resume\033[0m     -> Resume/reopen last episode"
echo -e "  \033[1monep list\033[0m       -> List all shows and progress"
