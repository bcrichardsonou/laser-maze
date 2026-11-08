import json,sys,tempfile,unittest,uuid
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from maintenance import Maintenance
from panel_game import Controls
from game_reporting import atomic_json
from test_maintenance_extended import Audio
class RfidSessionTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.wall=1000;self.now=0
  self.c=Controls(rfid_entry=True);self.c.reader_ready=True;self.c.reader_diagnostics=dict(tag_responses=10,selection_failures=2)
  self.m=Maintenance(Path(self.tmp.name)/'control','device',Audio(),Audio(),wall=lambda:self.wall);self.m.enabled=True;self.m.local_until=1300;self.sent=[];self.m.send=lambda *args:self.sent.append(args)
 def cmd(self,action):
  c=dict(id=str(uuid.uuid4()),device_id='device',action=action,params={},expires_at=self.wall+60)
  atomic_json(self.m.folder/'inbox'/(c['id']+'.json'),c);self.now+=.2;self.m.tick(self.c,self.now);return c
 def result(self,c):return json.loads((self.m.folder/'results'/(c['id']+'.json')).read_text())
 def test_scans_are_test_only_and_counts_start_at_zero(self):
  self.cmd('rfid_start');self.assertEqual(self.m.rfid_snapshot(self.c)['tag_responses'],0)
  self.m.rfid_scan();self.m.rfid_scan();self.c.reader_diagnostics.update(tag_responses=13,selection_failures=3)
  s=self.m.rfid_snapshot(self.c);self.assertEqual(s['scans'],2);self.assertEqual(s['last_scan_at'],1000);self.assertEqual(s['tag_responses'],3);self.assertEqual(s['selection_failures'],1)
  self.assertIsNone(self.c.game);self.assertTrue(self.m.enabled);self.assertFalse(self.m.display()[0])
 def test_missing_reader_can_be_diagnosed_without_faking_success(self):
  self.c.reader_ready=False;c=self.cmd('rfid_start');self.assertEqual(self.result(c)['status'],'completed');self.assertEqual(self.m.rfid_session['scans'],0)
  self.assertFalse(self.m.live(self.c,1)['rfid']['ready'])
 def test_end_and_timeout_stop_recording(self):
  self.cmd('rfid_start');self.cmd('rfid_end');self.m.rfid_scan();self.assertEqual(self.m.rfid_session['scans'],0)
  self.cmd('rfid_start');self.wall=1061;self.m.tick(self.c,61);self.assertTrue(self.m.rfid_active())
  self.wall=1120;self.m.tick(self.c,120);self.assertFalse(self.m.rfid_active());self.assertTrue(self.m.enabled)
 def test_ended_test_counts_do_not_change_from_later_scans(self):
  self.cmd('rfid_start');self.c.reader_diagnostics['tag_responses']=12;self.cmd('rfid_end')
  self.c.reader_diagnostics['tag_responses']=20;self.m.rfid_scan();self.assertEqual(self.m.rfid_snapshot(self.c)['tag_responses'],2);self.assertEqual(self.m.rfid_snapshot(self.c)['scans'],0)
 def test_local_confirmation_required(self):
  self.m.local_until=0;c=self.cmd('rfid_start');self.assertEqual(self.result(c)['status'],'failed')
 def test_grant_expiry_and_star_cancel(self):
  self.cmd('rfid_start');self.m.local_key('*',self.c);self.assertFalse(self.m.rfid_active())
  self.cmd('rfid_start');self.m.local_until=1001;self.wall=1002;self.m.tick(self.c,2);self.assertFalse(self.m.rfid_active())
 def test_other_tests_blocked_and_reset_allowed_during_rfid_test(self):
  self.cmd('rfid_start');c=self.cmd('laser_align');self.assertEqual(self.result(c)['reason'],'test_busy')
  c=self.cmd('rfid_reset');self.assertEqual(self.sent[-1][:2],('RFID RESET','RFID STATUS'));self.assertFalse((self.m.folder/'results'/(c['id']+'.json')).exists())
  self.sent[-1][2]();self.assertEqual(self.result(c)['status'],'completed');self.assertTrue(self.m.rfid_active())
 def test_reset_requires_ack_and_checks_hardware_ready(self):
  c=self.cmd('rfid_reset');self.c.reader_ready=False;self.sent[-1][2]();self.assertEqual(self.result(c)['status'],'failed')
 def test_late_reset_ack_does_not_override_cancellation(self):
  c=self.cmd('rfid_reset');ack=self.sent[-1][2];self.cmd('stop_game');ack();self.assertEqual(self.result(c)['status'],'failed');self.assertIsNone(self.m.test)
 def test_end_available_without_local_grant(self):
  self.cmd('rfid_start');self.m.local_until=0;c=self.cmd('rfid_end');self.assertEqual(self.result(c)['status'],'completed')
 def test_result_fits_after_other_diagnostics(self):
  from receiver_calibrate import propose,summarize
  self.m.capture_values=dict(blocked=[5]*100,clear=[70]*100,blocked_check=[5]*100)
  self.m.candidate=dict(id=str(uuid.uuid4()),created_at=999,mode='automatic_off_on_off',proposal=propose([5]*100,[70]*100,[5]*100),applied=True)
  self.m.beam_check=dict(command_id=str(uuid.uuid4()),started_at=900,finished_at=920,status='completed',all_clear=True,configured_count=1,tested_count=1,outputs_off_confirmed=True,modules=[dict(module=1,pin='A0',state='clear',clear_above=48,**summarize([70]*100))])
  self.cmd('keypad_start')
  for k in '0123456789*#':self.m.keypad_key(k)
  self.cmd('keypad_end');self.cmd('rfid_start');self.m.rfid_scan();cmd=self.cmd('rfid_end')
  self.assertLess(len(json.dumps(self.result(cmd))),4096);self.assertLess(len(json.dumps(self.m.live(self.c,2))),6000)
 def test_keypad_and_rfid_tests_are_exclusive(self):
  self.cmd('keypad_start');c=self.cmd('rfid_start');self.assertEqual(self.result(c)['status'],'failed')
  self.cmd('keypad_end');self.cmd('rfid_start');c=self.cmd('keypad_start');self.assertEqual(self.result(c)['status'],'failed')
if __name__=='__main__':unittest.main()
