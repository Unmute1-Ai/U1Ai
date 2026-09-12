#!/usr/bin/env bash
# Run only on a disposable Ubuntu 24.04 amd64 build runner.
set -euo pipefail
[[ $EUID == 0 ]] || { echo 'Run with sudo on a disposable build runner.'; exit 1; }
. /etc/os-release
[[ $ID == ubuntu && $VERSION_ID == 24.04 && $(dpkg --print-architecture) == amd64 ]] || exit 1
src=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)
out=${1:?Provide a new output directory}
mkdir -p "$out"
out=$(realpath "$out")
work=$(mktemp -d /var/tmp/u1-live.XXXXXXXX)
root="$work/root"
iso="$work/image"
cleanup() {
    for mountpoint in "$root/dev" "$root/proc" "$root/sys"; do
        if mountpoint -q "$mountpoint"; then umount -R "$mountpoint" || true; fi
    done
    echo "Build workspace retained at $work for diagnosis; disposable runner removes it after the job."
}
trap cleanup EXIT
for cmd in debootstrap mksquashfs grub-mkrescue xorriso; do command -v "$cmd" >/dev/null; done
[[ $(df --output=avail -B1 /var/tmp | tail -1) -gt 18000000000 ]] || { echo 'Need 18 GB free.'; exit 1; }
# debootstrap verifies Ubuntu repository signatures with the installed archive keyring.
debootstrap --arch=amd64 --variant=minbase --include=ca-certificates --components=main,restricted,universe,multiverse noble "$root" https://archive.ubuntu.com/ubuntu
cat > "$root/etc/apt/sources.list" <<'APT'
deb https://archive.ubuntu.com/ubuntu noble main restricted universe multiverse
deb https://archive.ubuntu.com/ubuntu noble-updates main restricted universe multiverse
deb https://security.ubuntu.com/ubuntu noble-security main restricted universe multiverse
APT
mount --rbind /dev "$root/dev"
mount --make-rslave "$root/dev"
mount -t proc proc "$root/proc"
mount -t sysfs sysfs "$root/sys"
cat > "$root/usr/sbin/policy-rc.d" <<'POLICY'
#!/bin/sh
exit 101
POLICY
chmod 755 "$root/usr/sbin/policy-rc.d"
cp "$src/dist/unmute1ai-os-desktop_0.1.0_all.deb" "$root/tmp/u1-desktop.deb"
chroot "$root" /usr/bin/env DEBIAN_FRONTEND=noninteractive /bin/bash <<'CHROOT'
set -euo pipefail
apt-get update
apt-get install -y --no-install-recommends \
 linux-image-generic linux-firmware casper initramfs-tools systemd-sysv \
 dbus-x11 network-manager network-manager-gnome sudo locales ubuntu-keyring \
 xserver-xorg gdm3 gnome-shell gnome-session ubuntu-session ubuntu-settings \
 gnome-shell-extension-ubuntu-dock yaru-theme-gtk yaru-theme-icon \
 gnome-control-center nautilus gnome-terminal gnome-text-editor orca \
 fonts-dejavu-core fonts-noto-core pipewire-audio wireplumber \
 /tmp/u1-desktop.deb
locale-gen en_US.UTF-8
update-locale LANG=en_US.UTF-8
cat > /etc/casper.conf <<'CASPER'
export USERNAME="u1"
export USERFULLNAME="Unmute1AI Live"
export HOST="u1-live"
export BUILD_SYSTEM="Ubuntu"
export FLAVOUR="Ubuntu"
CASPER
cat > /etc/NetworkManager/conf.d/10-u1-live.conf <<'NETWORK'
[main]
plugins=keyfile
[ifupdown]
managed=true
NETWORK
systemctl enable NetworkManager gdm3
systemctl set-default graphical.target
u1-os-boot enable
apt-get clean
rm -f /tmp/u1-desktop.deb /usr/sbin/policy-rc.d
rm -f /var/lib/dbus/machine-id
: > /etc/machine-id
ln -s /etc/machine-id /var/lib/dbus/machine-id
CHROOT
# The readiness probe is enabled only by a test-specific kernel argument.
install -m 755 "$src/iso/live-ready.sh" "$root/usr/local/sbin/u1-live-ready"
install -m 644 "$src/iso/u1-live-ready.service" "$root/etc/systemd/system/u1-live-ready.service"
chroot "$root" systemctl enable u1-live-ready.service
mkdir -p "$iso/casper" "$iso/boot/grub" "$iso/.disk"
kernel=$(find "$root/boot" -maxdepth 1 -name 'vmlinuz-*' | sort -V | tail -1)
[[ -n $kernel ]] || { echo 'No kernel installed'; exit 1; }
version=${kernel##*/vmlinuz-}
cp "$kernel" "$iso/casper/vmlinuz"
cp "$root/boot/initrd.img-$version" "$iso/casper/initrd"
chroot "$root" dpkg-query -W --showformat='${Package} ${Version}\n' > "$iso/casper/filesystem.manifest"
cp "$iso/casper/filesystem.manifest" "$out/packages.txt"
echo 'Unmute1AI OS 0.1 Live Preview — Ubuntu Noble amd64' > "$iso/.disk/info"
printf 'full_cd/single\n' > "$iso/.disk/cd_type"
cat > "$iso/boot/grub/grub.cfg" <<'GRUB'
set timeout=5
set default=0
set menu_color_normal=light-gray/black
set menu_color_highlight=white/blue
menuentry "Try Unmute1AI OS — no installation" {
 linux /casper/vmlinuz boot=casper quiet splash ---
 initrd /casper/initrd
}
menuentry "Unmute1AI OS — compatibility graphics" {
 linux /casper/vmlinuz boot=casper nomodeset ---
 initrd /casper/initrd
}
GRUB
cleanup
# Avoid leaking host mount contents, package download caches or build logs into squashfs.
mksquashfs "$root" "$iso/casper/filesystem.squashfs" -noappend -comp xz -processors 2 -wildcards -e 'dev/*' 'proc/*' 'sys/*' 'tmp/*' 'var/cache/apt/archives/*'
du -sx --block-size=1 "$root" | cut -f1 > "$iso/casper/filesystem.size"
(cd "$iso" && find . -type f ! -name md5sum.txt -print0 | sort -z | xargs -0 md5sum > md5sum.txt)
grub-mkrescue -o "$out/Unmute1AI-OS-0.1-live-amd64.iso" "$iso"
cp "$iso/casper/vmlinuz" "$out/test-vmlinuz"
cp "$iso/casper/initrd" "$out/test-initrd"
(cd "$out" && sha256sum Unmute1AI-OS-0.1-live-amd64.iso > SHA256SUMS)
echo "Built live-only ISO at $out; VM validation is still required."
