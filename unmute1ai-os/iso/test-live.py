#!/usr/bin/env python3
"""Boot kernel+initrd against the generated ISO, checking live root and GDM.
This is not a firmware/GRUB or visual accessibility test.
"""
import pathlib, subprocess, sys, time
out=pathlib.Path(sys.argv[1]).resolve()
log=out/'boot-serial.log'
args=['qemu-system-x86_64','-accel','tcg','-m','4096','-smp','2',
 '-kernel',str(out/'test-vmlinuz'),'-initrd',str(out/'test-initrd'),
 '-append','boot=casper console=tty0 console=ttyS0,115200n8 u1.selftest=1',
 '-cdrom',str(out/'Unmute1AI-OS-0.1-live-amd64.iso'),
 '-display','none','-serial','file:'+str(log),'-monitor','none',
 '-nic','none','-no-reboot']
process=subprocess.Popen(args)
try:
 deadline=time.monotonic()+600
 while time.monotonic()<deadline:
  data=log.read_text(errors='replace') if log.exists() else ''
  if 'U1_LIVE_READY' in data:
   (out/'BOOT-RESULT.txt').write_text('PASS: kernel/initrd loaded the live ISO root, display manager active, live user and U1 assets present. Firmware boot, rendered desktop, installation and hardware support remain untested.\n')
   print('Live root and display-manager boot check passed.');break
  if 'U1_LIVE_FAILED' in data or process.poll() is not None:
   raise RuntimeError('Live boot failed; inspect boot-serial.log')
  time.sleep(3)
 else: raise TimeoutError('Live boot did not become ready within 10 minutes')
finally:
 process.terminate()
 try:process.wait(timeout=15)
 except subprocess.TimeoutExpired:process.kill();process.wait()
