import importlib.machinery
import importlib.util
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import json
import subprocess

ROOT=Path(__file__).resolve().parents[1]
def load(name):
 loader=importlib.machinery.SourceFileLoader(name,str(ROOT/'package/usr/bin'/name))
 spec=importlib.util.spec_from_loader(name,loader)
 module=importlib.util.module_from_spec(spec);loader.exec_module(module);return module

class DesktopState(unittest.TestCase):
 def test_reapply_retains_original_and_restore_resets_unset_key(self):
  app=load('u1-start')
  with tempfile.TemporaryDirectory() as directory:
   app.STATE=Path(directory);app.BACKUP=app.STATE/'desktop.json'
   app.SETTINGS=[('org.test','unset',"'new'"),('org.test','existing',"'new'")]
   calls=[]
   def command(*args):
    calls.append(args)
    if args[:2]==('dconf','read'): return "'original'" if args[2].endswith('existing') else ''
    return ''
   with patch.object(app,'supported',return_value=True),patch.object(app,'command',side_effect=command):
    app.apply_desktop();original=app.BACKUP.read_text();app.apply_desktop()
    self.assertEqual(app.BACKUP.read_text(),original)
    app.restore_desktop()
   self.assertIn(('gsettings','reset','org.test','unset'),calls)
   self.assertIn(('gsettings','set','org.test','existing',"'original'"),calls)
   self.assertFalse(app.BACKUP.exists())
 def test_failed_write_keeps_recovery_state(self):
  app=load('u1-start')
  with tempfile.TemporaryDirectory() as directory:
   app.STATE=Path(directory);app.BACKUP=app.STATE/'desktop.json';app.SETTINGS=[('org.test','x',"'new'")]
   def command(*args):
    if args[:2]==('gsettings','set'):raise subprocess.CalledProcessError(1,args)
    return "'old'"
   with patch.object(app,'supported',return_value=True),patch.object(app,'command',side_effect=command):
    with self.assertRaises(subprocess.CalledProcessError): app.apply_desktop()
   self.assertEqual(json.loads(app.BACKUP.read_text())['org.test|x'],"'old'")

class BootState(unittest.TestCase):
 def test_restore_respects_a_later_user_theme_choice(self):
  boot=load('u1-os-boot')
  with patch.object(boot,'selection',return_value={'Value':'/other/theme'}),patch.object(boot,'run') as run:
   boot.restore_selection();run.assert_not_called()
 def test_restore_manual_selection(self):
  boot=load('u1-os-boot')
  with tempfile.TemporaryDirectory() as directory:
   old=Path(directory)/'old.plymouth';old.touch()
   boot.BACKUP=Path(directory)/'boot.json';boot.BACKUP.write_text(json.dumps({'value':str(old),'status':'manual'}))
   with patch.object(boot,'selection',return_value={'Value':str(boot.THEME)}),patch.object(boot,'run') as run:
    boot.restore_selection()
   run.assert_called_once_with('update-alternatives','--set','default.plymouth',str(old))
 def test_initramfs_failure_restores_selection(self):
  boot=load('u1-os-boot')
  with tempfile.TemporaryDirectory() as directory:
   boot.STATE=Path(directory);boot.BACKUP=boot.STATE/'boot.json';boot.BACKUP.write_text('{}')
   def run(*args):
    if args[0]=='update-initramfs':raise subprocess.CalledProcessError(1,args)
    return ''
   with patch.object(boot,'prepare'),patch.object(boot,'run',side_effect=run),patch.object(boot,'restore_selection') as restore:
    with self.assertRaises(RuntimeError):boot.enable()
    restore.assert_called_once()

if __name__=='__main__':unittest.main()
