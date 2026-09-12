#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"
. /etc/os-release
if [[ "${ID:-}" != ubuntu || "${VERSION_ID:-}" != 24.04 ]]; then
    echo "This release requires Ubuntu Desktop 24.04 LTS. It cannot install Ubuntu over Alpine, Garuda or Windows."
    exit 1
fi
if [[ $EUID == 0 ]]; then
    echo "Run: bash install.sh from your Ubuntu desktop account, without sudo."
    exit 1
fi
if [[ -z "${DBUS_SESSION_BUS_ADDRESS:-}" ]] || ! command -v gnome-shell >/dev/null; then
    echo "Open Terminal inside your Ubuntu GNOME desktop and run this installer there."
    exit 1
fi
sha256sum --check SHA256SUMS
sudo apt-get update
sudo apt-get install -y ./dist/unmute1ai-os-desktop_0.1.0_all.deb
sudo u1-os-boot enable
u1-start --apply
printf '
Installed. Open Unmute1AI Start from Applications. Reboot when ready.
'
