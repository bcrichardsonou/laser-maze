import sys,time,tempfile,unittest
from pathlib import Path
from types import SimpleNamespace
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from usb_rfid import USBRFID,ScanLatch,select_reader
from panel_game import Controls,update_usb_reader
from maintenance import Maintenance
from test_maintenance_extended import Audio
class USBReaderTests(unittest.TestCase):
 def test_unique_model_selection_ignores_sam_and_unrelated(self):
  n='ACS ACR1552 1S CL Reader PICC 00 00'
  self.assertEqual(select_reader(['other reader',n,'ACS ACR1552 SAM 00 01']),n)
  for names in ([],['other'],[n,n+' alternate']):
   with self.assertRaises(ValueError):select_reader(names)
 def test_initial_held_card_and_reconnect_need_removal(self):
  l=ScanLatch();self.assertFalse(l.update(True));self.assertFalse(l.update(True))
  self.assertFalse(l.update(False));self.assertTrue(l.update(True));self.assertFalse(l.update(True))
  self.assertFalse(l.update(False));self.assertTrue(l.update(True))
  l=ScanLatch();self.assertFalse(l.update(True))
 def test_only_fresh_valid_events_count_no_identity(self):
  r=USBRFID();p=dict(ready=True,present=True,error='',scan=True,failed=False,at=1)
  self.assertTrue(r.accept(p,1.1));self.assertEqual(r.scans,1)
  self.assertFalse(r.accept(p,2));self.assertEqual(r.scans,1)
  p.update(scan=False,failed=True,at=3);r.accept(p,3.1)
  self.assertEqual(r.diagnostics()['selection_failures'],1)
  self.assertNotIn('uid',r.diagnostics())
 def test_reader_loss_clears_pending_auth_but_not_running_game(self):
  c=Controls(rfid_entry=True);c.reader_ready=True;c.swipe(0)
  reader=SimpleNamespace(poll=lambda n:0,ready=False,diagnostics=lambda:{'source':'usb_pcsc'})
  m=SimpleNamespace(enabled=False,pending=None)
  update_usb_reader(reader,c,m,1);self.assertFalse(c.entry.scanned);self.assertFalse(c.reader_ready)
 def test_reader_recovery_restores_entry_prompt_without_grant(self):
  c=Controls(rfid_entry=True);c.entry.reset('reader_unavailable')
  r=SimpleNamespace(poll=lambda n:0,ready=True,diagnostics=lambda:{'source':'usb_pcsc'})
  update_usb_reader(r,c,SimpleNamespace(enabled=False,pending=None),1)
  self.assertEqual(c.entry.reason,'waiting_for_scan_or_code');self.assertFalse(c.entry.scanned)
 def test_usb_scan_authorizes_or_goes_only_to_maintenance(self):
  for maintenance in (False,True):
   c=Controls(rfid_entry=True);m=SimpleNamespace(enabled=maintenance,pending=None,rfid_scan=lambda:None,next_live=99)
   r=SimpleNamespace(poll=lambda n:1,ready=True,diagnostics=lambda:{'source':'usb_pcsc'})
   update_usb_reader(r,c,m,0);self.assertEqual(c.entry.scanned,not maintenance);self.assertEqual(c.scan_count,1)
   for k in '16646#':
    if not maintenance:c.key(k,1)
   self.assertEqual(c.game is not None,not maintenance)
 def test_reconnect_does_not_send_removed_mega_reader_commands(self):
  with tempfile.TemporaryDirectory() as d:
   c=Controls();calls=[];c.usb_reader=SimpleNamespace(restart=lambda n:calls.append(n))
   m=Maintenance(Path(d),'dev',Audio(),Audio(),wall=lambda:1000)
   cmd=dict(id='a7b7d9e0-1111-1111-1111-111111111111',action='rfid_reset',expires_at=1060)
   m.reset_rfid(cmd,c,1);self.assertEqual(calls,[1]);self.assertFalse(c.reader_ready)
   c.reader_ready=True;m.enabled=True;m.local_until=1100;m.tick(c,2)
   self.assertIsNone(m.test)
