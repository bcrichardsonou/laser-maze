import json,sys,tempfile,unittest,uuid
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from maintenance import Maintenance
from panel_game import Controls,StaffKeys
from game_reporting import atomic_json
from test_maintenance_extended import Audio

class StaffKeyTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
  self.c=Controls(rfid_entry=True);self.c.reader_ready=True
  self.m=Maintenance(Path(self.tmp.name)/'control','device',Audio(),Audio(),wall=lambda:1000)
  self.keys=StaffKeys(self.m,self.c)
 def request(self):
  command=dict(id=str(uuid.uuid4()),device_id='device',action='enter_maintenance',params={},expires_at=1060)
  atomic_json(self.m.folder/'inbox'/(command['id']+'.json'),command);self.m.tick(self.c,0);return command
 def test_5_is_normal_code_digit_without_portal_request(self):
  self.keys.key('5',0);self.assertEqual(self.c.entry.code,'5');self.assertFalse(self.m.enabled)
 def test_5_confirms_then_renews_maintenance(self):
  self.request();self.keys.key('5',1)
  self.assertTrue(self.m.local_enabled());self.assertIsNone(self.m.pending);self.assertEqual(self.c.entry.code,'')
  self.m.local_until=1001;self.keys.key(None,2);self.keys.key('5',3);self.assertEqual(self.m.local_until,1300)
 def test_star_cancels_test_and_sound_but_stays_in_maintenance(self):
  self.request();self.keys.key('5',1)
  cmd=dict(id=str(uuid.uuid4()),device_id='device',action='laser_align',params={},expires_at=1060)
  self.m.test=dict(kind='alignment',command=cmd,until=30);self.m.audio.queue('entrance')
  self.keys.key('*',2);self.assertIsNone(self.m.test);self.assertTrue(self.m.enabled);self.assertFalse(self.m.display()[0]);self.assertFalse(self.m.audio.cues)
 def test_short_zero_is_code_digit_and_release_cancels_hold(self):
  self.keys.key('0',0);self.keys.tick(9.9);self.assertEqual(self.c.entry.code,'0');self.assertEqual(self.keys.countdown(9.9),1)
  self.keys.key(None,9.99);self.keys.tick(20);self.assertFalse(self.keys.fired);self.assertIsNone(self.keys.countdown(20))
 def test_hold_0_stops_game_after_ten_seconds_and_only_once(self):
  self.c.start(0);self.assertIsNotNone(self.c.game)
  self.keys.key('0',0);self.keys.tick(9.99);self.assertIsNotNone(self.c.game)
  self.keys.tick(10);self.assertIsNone(self.c.game);self.assertTrue(self.keys.fired);self.assertEqual(self.c.entry.code,'')
  self.c.result=('sentinel',0);self.keys.tick(11);self.assertEqual(self.c.result,('sentinel',0))
 def test_hold_exits_maintenance_cancels_test_and_clears_enable(self):
  self.request();self.keys.key('5',1);self.keys.key('0',2);self.keys.tick(12)
  self.assertFalse(self.m.enabled);self.assertEqual(self.m.local_until,0);self.assertFalse(self.m.local_enabled())
  self.assertFalse(json.loads((self.m.folder/'state.json').read_text())['enabled'])
 def test_hold_cancels_pending_portal_entry(self):
  cmd=self.request();self.keys.key('0',1);self.keys.tick(11)
  self.assertIsNone(self.m.pending);self.assertFalse(self.m.enabled)
  self.assertEqual(json.loads((self.m.folder/'results'/(cmd['id']+'.json')).read_text())['status'],'failed')
 def test_invalid_or_missing_key_event_resets_hold(self):
  self.keys.key('0',0);self.keys.key(None,9);self.keys.tick(15);self.assertFalse(self.keys.fired)
 def test_zero_then_different_key_resets_hold_and_preserves_digits(self):
  self.keys.key('0',0);self.keys.key('5',1);self.keys.tick(11);self.assertFalse(self.keys.fired)
  self.assertEqual(self.c.entry.code,'05')
 def test_mission_code_still_starts_with_rfid(self):
  self.c.swipe(0)
  for i,k in enumerate('77004#'):self.keys.key(k,.1+i*.1);self.keys.key(None,.15+i*.1)
  self.assertIsNotNone(self.c.game)

if __name__=='__main__':unittest.main()
