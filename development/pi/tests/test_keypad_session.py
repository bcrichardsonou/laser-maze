import json,sys,tempfile,unittest,uuid
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from maintenance import Maintenance
from panel_game import Controls,StaffKeys
from game_reporting import atomic_json
from test_maintenance_extended import Audio

class KeypadSessionTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.wall=1000;self.now=0
  self.c=Controls(rfid_entry=True);self.c.reader_ready=True
  self.m=Maintenance(Path(self.tmp.name)/'control','device',Audio(),Audio(),wall=lambda:self.wall)
  self.keys=StaffKeys(self.m,self.c);self.m.enabled=True;self.m.local_until=1300
 def command(self,action):
  cmd=dict(id=str(uuid.uuid4()),device_id='device',action=action,params={},expires_at=self.wall+60)
  atomic_json(self.m.folder/'inbox'/(cmd['id']+'.json'),cmd);self.now+=.2;self.m.tick(self.c,self.now);return cmd
 def result(self,cmd):return json.loads((self.m.folder/'results'/(cmd['id']+'.json')).read_text())
 def start(self):
  c=self.command('keypad_start');self.assertEqual(self.result(c)['status'],'completed');self.assertTrue(self.m.keypad_active());return c
 def test_start_resets_old_reading_and_collects_all_keys(self):
  self.m.local_until=1250;self.m.last_key='9';self.start();self.assertIsNone(self.m.keypad_session['last_key'])
  for i,key in enumerate('123456789*0#'):
   self.keys.key(key,i);self.keys.tick(i+.1);self.keys.key(None,i+.2)
  s=self.m.keypad_session;self.assertEqual(set(s['seen']),set('123456789*0#'));self.assertEqual(s['press_count'],12)
  self.assertTrue(self.m.enabled);self.assertEqual(self.m.local_until,1250);self.assertIsNone(self.c.game);self.assertEqual(self.c.entry.code,'')
  self.assertTrue(self.m.metrics()['maintenance_test_active']);self.assertFalse(self.m.display()[0])
 def test_zero_hold_is_disabled_in_test(self):
  self.start();self.keys.key('0',1);self.keys.tick(20)
  self.assertTrue(self.m.enabled);self.assertTrue(self.m.keypad_active());self.assertIsNone(self.keys.countdown(20));self.assertEqual(self.m.staff_hold_seconds,0)
 def test_end_while_zero_held_does_not_trigger_stop_until_release(self):
  self.start();self.keys.key('0',1);self.keys.tick(20);self.command('keypad_end');self.keys.tick(30)
  self.assertFalse(self.m.keypad_active());self.assertTrue(self.m.enabled)
  self.keys.key(None,31);self.keys.key('0',32);self.keys.tick(42);self.assertFalse(self.m.enabled)
 def test_automatic_end_even_past_original_command_ttl(self):
  self.start();self.wall=1061;self.m.tick(self.c,61);self.assertTrue(self.m.keypad_active())
  self.keys.key('0',62);self.keys.tick(70);self.wall=1120;self.m.tick(self.c,120);self.keys.tick(121)
  self.assertFalse(self.m.keypad_active());self.assertTrue(self.m.enabled);self.assertEqual(self.m.keypad_session['reason'],'time_limit_reached')
 def test_test_cannot_start_without_local_enable(self):
  self.m.local_until=0;c=self.command('keypad_start');self.assertEqual(self.result(c)['status'],'failed');self.assertFalse(self.m.keypad_active())
 def test_remote_stop_cancels_keypad_session(self):
  self.start();self.command('stop_game');self.assertFalse(self.m.keypad_active());self.assertTrue(self.m.enabled)
 def test_hardware_test_cannot_run_at_same_time(self):
  self.start();c=self.command('laser_align');self.assertEqual(self.result(c)['reason'],'test_busy');self.assertIsNone(self.m.test)
 def test_grant_expiry_ends_session(self):
  self.start();self.m.local_until=1001;self.wall=1002;self.m.tick(self.c,2);self.assertFalse(self.m.keypad_active())
 def test_end_does_not_need_local_grant(self):
  self.start();self.m.local_until=0;c=self.command('keypad_end');self.assertEqual(self.result(c)['status'],'completed')
 def test_payload_fits_after_calibration_and_beam_check(self):
  from receiver_calibrate import propose,summarize
  self.m.capture_values=dict(blocked=[5]*100,clear=[70]*100,blocked_check=[5]*100)
  self.m.candidate=dict(id=str(uuid.uuid4()),created_at=999,mode='automatic_off_on_off',proposal=propose([5]*100,[70]*100,[5]*100),applied=True)
  self.m.beam_check=dict(command_id=str(uuid.uuid4()),started_at=900,finished_at=920,status='completed',all_clear=True,configured_count=1,tested_count=1,outputs_off_confirmed=True,modules=[dict(module=1,pin='A0',state='clear',clear_above=48,**summarize([70]*100))])
  self.start()
  for i,k in enumerate('0123456789*#'):self.keys.key(k,i);self.keys.key(None,i+.1)
  cmd=self.command('keypad_end');self.assertLess(len(json.dumps(self.result(cmd))),4096);self.assertLess(len(json.dumps(self.m.live(self.c,5))),6000)
 def test_new_test_clears_previous_keys(self):
  self.start();self.keys.key('8',1);self.keys.key(None,2);self.command('keypad_end');self.start();self.assertEqual(self.m.keypad_session['seen'],[])

if __name__=='__main__':unittest.main()
