#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")"
mkdir -p dist
chmod 0755 package/DEBIAN/postinst package/DEBIAN/prerm package/DEBIAN/postrm package/usr/bin/*
dpkg-deb --root-owner-group --build package dist/unmute1ai-os-desktop_0.1.0_all.deb
sha256sum dist/unmute1ai-os-desktop_0.1.0_all.deb > SHA256SUMS
