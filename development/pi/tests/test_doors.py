import json,sys,tempfile,unittest,uuid
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from panel_game import Controls
from maintenance import Maintenance,validate
from game_reporting import atomic_json
from test_maintenance_extended import Audio

class Doors(unittest.TestCase):
 def test_game_timing_and_every_finish(self):
  for outcome in ('win','timeout','beam_limit','stopped','communication_fault'):
   c=Controls(physical_single=True)
   self.assertEqual(c.doors(0),(True,True));c.key('A',0)
   self.assertEqual(c.doors(0),(True,True));c.tick(5)
   self.assertEqual(c.doors(5),(False,True));c.tick(10)
   self.assertEqual(c.doors(10),(True,True))
   c.game.finish(outcome);c.tick(11);self.assertEqual(c.doors(11),(True,False))
   self.assertEqual(c.doors(20.999),(True,False));self.assertFalse(c.entry_idle(20.999))
   c.tick(21);self.assertEqual(c.doors(21),(True,True));self.assertTrue(c.entry_idle(21))
 def test_scan_or_code_alone_cannot_open_entry(self):
  for scan_first in (True,False):
   c=Controls(rfid_entry=True,physical_single=True);c.reader_ready=True
   self.assertTrue(c.doors(0)[0])
   if scan_first:c.swipe(0)
   else:
    for key in '16646#':c.key(key,0)
   self.assertIsNone(c.game);self.assertTrue(c.doors(0)[0])
   if scan_first:
    for key in '16646#':c.key(key,1)
   else:c.swipe(1)
   self.assertEqual(c.game.state,'starting');self.assertTrue(c.doors(0)[0])
   c.tick(6);self.assertEqual(c.doors(6),(False,True))
   c.tick(11);self.assertEqual(c.doors(11),(True,True))
 def test_retired_beam_not_required_for_break_all(self):
  c=Controls(True,physical_single=True);c.key('2',0);c.key('A',0);c.tick(2)
  self.assertEqual(c.game.enabled,[True,False]);c.inputs([True,False,False],3)
  c.usb_update(False,3.1);c.usb_update(True,4);c.tick(4)
  self.assertEqual(c.result,('win',1))
 def test_old_settings_cannot_reenable_retired_button(self):
  from operator_settings import DEFAULT_SETTINGS
  c=Controls(physical_single=True);c.configure(DEFAULT_SETTINGS)
  self.assertEqual(c.settings.enabled_beams,(True,False))
 def test_maintenance_bounded_ack_and_release_without_grant(self):
  with tempfile.TemporaryDirectory() as d:
   c=Controls(physical_single=True);m=Maintenance(Path(d),'dev',Audio(),Audio(),wall=lambda:1000)
   sends=[];m.send=lambda *a:sends.append(a);m.enabled=True;m.local_until=1300
   def command(action,p):
    cmd=dict(id=str(uuid.uuid4()),device_id='dev',action=action,params=p,expires_at=1060)
    atomic_json(m.folder/'inbox'/(cmd['id']+'.json'),cmd);return cmd
   cmd=command('door_test',{'door':'exit'});m.tick(c,0)
   self.assertEqual(sends[0][:2],('DOORTEST 1','OK DOORTEST 1'));sends[0][2]()
   self.assertEqual(m.door_commanded,(False,True));m.tick(c,5.1)
   self.assertEqual(sends[1][:2],('DOORS 0 0','OK DOORS 0 0'))
   self.assertFalse((m.folder/'results'/(cmd['id']+'.json')).exists());sends[1][2]()
   self.assertIsNone(m.test);self.assertEqual(m.door_commanded,(False,False))
   m.enabled=False;m.local_until=0;c.key('A',6)
   release=command('doors_release',{});m.tick(c,6)
   self.assertTrue(m.enabled);self.assertIsNone(c.game)
   self.assertEqual(json.loads((m.folder/'results'/(release['id']+'.json')).read_text())['status'],'completed')
 def test_stop_and_clear_result_cannot_cut_exit_window_short(self):
  c=Controls(physical_single=True);c.key('A',0);c.tick(10)
  c.key('D',11);c.tick(11);c.result=None;c.result_red_at=11
  c.key('A',20);self.assertIsNone(c.game)
  self.assertEqual(c.doors(20),(True,False));self.assertEqual(c.display(20)[3],'BLUE')
  c.tick(21);self.assertEqual(c.doors(21),(True,True));self.assertEqual(c.display(21)[3],'RED')
 def test_invalid_door(self):
  cmd=dict(id=str(uuid.uuid4()),device_id='dev',action='door_test',params={'door':'all'},expires_at=1060)
  with self.assertRaises(ValueError):validate(cmd,'dev',1000)
