#!/bin/bash
set -euo pipefail
for attempt in $(seq 1 90); do
    if systemctl is-active --quiet display-manager.service && id u1 >/dev/null 2>&1; then
        test -f /usr/share/unmute1ai-os/artwork/desktop.jpg
        test -x /usr/bin/u1-start
        test -f /usr/share/plymouth/themes/unmute1ai/unmute1ai.plymouth
        echo U1_LIVE_READY > /dev/ttyS0
        exit 0
    fi
    sleep 2
done
echo U1_LIVE_FAILED > /dev/ttyS0
exit 1
