# Bootable image — remaining build step

Status: no ISO was generated or boot-tested in this environment. The host has no mount/chroot capabilities or VM device. This is a workflow for a suitable Ubuntu build machine, not a claim of a completed operating-system release.

Use an Ubuntu Desktop 24.04 LTS amd64 base image for an Intel/AMD PC. Obtain it from Ubuntu and verify the signed checksum using Ubuntu's instructions. Build in a disposable Ubuntu VM with sufficient disk space for both extracted and compressed images.

Cubic provides a UI for the extraction, chroot customization and repacking steps. Follow the [maintainer's installation guide](https://github.com/PJ-Singh-001/Cubic/wiki/Install-Cubic). Cubic is a third-party tool with privileged host components; the maintainer documents why an isolated VM is appropriate.

1. Create a Cubic project from the verified Ubuntu 24.04 desktop ISO.
2. At Cubic's Terminal page, change to `/tmp` and drag in `dist/unmute1ai-os-desktop_0.1.0_all.deb`.
3. Inside that virtual root terminal, run:

   ```bash
   apt-get update
   apt-get install -y /tmp/unmute1ai-os-desktop_0.1.0_all.deb
   u1-os-boot enable
   ```

4. Keep Ubuntu's installer and signed kernel/boot components. Do not remove snapd or the installer snap. Complete Cubic's kernel/initramfs and ISO generation pages. Label the output `Unmute1AI-OS-0.1-ubuntu-24.04-amd64.iso`.
5. Boot the result in a VM, install it to a disposable virtual disk, then test that installed system. Newer Ubuntu live-overlay layers can obscure customizations in the live session; Cubic's documentation explicitly distinguishes live appearance from the installed system.
6. Validate the release checks in `VALIDATION.md`. Generate `sha256sum Unmute1AI-OS-0.1-ubuntu-24.04-amd64.iso` and distribute that checksum with the ISO only after passing the checks.

The default wallpaper and dark preference are in system GSettings overrides. The welcome app applies per-user dock settings with backup on **Make this my desktop**. This avoids baking in a real user's home directory or credentials.

Reference: https://github.com/PJ-Singh-001/Cubic/wiki/Terminal-Page
