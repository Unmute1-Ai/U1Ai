#!/usr/bin/env bash
set -euo pipefail
if [[ $EUID == 0 ]]; then
    echo "Run bash uninstall.sh from your desktop account, without sudo."
    exit 1
fi
if command -v u1-start >/dev/null; then u1-start --restore; fi
sudo apt-get remove -y unmute1ai-os-desktop
printf '
Unmute1AI desktop package removed. Reboot when ready.
'
