import json,sys,tempfile,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from usb_objective import USBObjective,usb_location
from panel_game import Controls

class PortTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.base=Path(self.tmp.name)
  self.sys=self.base/'sys';self.ctrl=self.sys/'devices/controller';self.root=self.ctrl/'usb3';self.root.mkdir(parents=True);(self.root/'version').write_text('2.00')
  (self.sys/'bus/usb/devices').mkdir(parents=True);(self.sys/'bus/usb/devices/usb3').symlink_to(self.root)
  (self.sys/'class/block').mkdir(parents=True)
  self.loc=dict(controller=str(self.ctrl),family=2,route='1')
  self.config=self.base/'usb-port.json';self.config.write_text(json.dumps(dict(locations=[self.loc])))
  self.mon=USBObjective(self.config,self.sys)
 def disk(self,name='sda',route='1',partition=False):
  device=self.root/('3-'+route);device.mkdir(exist_ok=True);(device/'idVendor').write_text('abcd');(device/'devpath').write_text(route)
  block=device/'storage'/name;block.mkdir(parents=True,exist_ok=True)
  if partition:(block/'partition').write_text('1')
  (self.sys/'class/block'/name).symlink_to(block);return block
 def test_accepts_socket_not_device_name_and_ignores_partitions(self):
  self.mon.poll(0);self.assertFalse(self.mon.present);self.disk();self.disk('sda1',partition=True);self.mon.poll(1)
  self.assertTrue(self.mon.present);self.assertEqual(self.mon.insertions,1)
  (self.sys/'class/block/sda').unlink();self.mon.poll(2);self.assertFalse(self.mon.present)
  self.disk('sdb');self.mon.poll(3);self.assertTrue(self.mon.present)
 def test_ignores_other_ports_and_nonstorage_equipment(self):
  self.disk(route='2');self.mon.poll(0);self.assertFalse(self.mon.present)
  d=self.root/'3-1';d.mkdir();(d/'idVendor').write_text('1234');(d/'devpath').write_text('1')
  self.mon.poll(1);self.assertFalse(self.mon.present)
 def test_bus_renumbering_does_not_change_location(self):
  d=self.disk();old=usb_location(d.parents[1]);newroot=self.ctrl/'usb9';self.root.rename(newroot)
  self.assertEqual(usb_location(newroot/'3-1'),old)
 def test_unknown_config_or_missing_controller_never_reports_inserted(self):
  self.config.unlink();m=USBObjective(self.config,self.sys);m.poll(0);self.assertIsNone(m.present)
  (self.sys/'bus/usb/devices/usb3').unlink();self.mon.poll(0);self.assertIsNone(self.mon.present)
 def test_failure_recovery_does_not_fabricate_insertion(self):
  self.mon.poll(0);self.assertFalse(self.mon.present)
  node=self.sys/'bus/usb/devices/usb3';node.unlink();self.mon.poll(1);self.assertIsNone(self.mon.present)
  node.symlink_to(self.root);self.disk();self.mon.poll(2);self.assertTrue(self.mon.present);self.assertEqual(self.mon.insertions,0)

class GameUsbTests(unittest.TestCase):
 def test_pin4_is_ignored(self):
  c=Controls(True);c.key('A',0);c.tick(2);c.inputs([False,False,True],3);c.tick(3);self.assertFalse(c.game.objective)
 def test_fresh_usb_insertion_completes_game_once(self):
  c=Controls(True);c.usb_update(False,0);c.key('A',0);c.usb_update(False,2);c.usb_update(True,3);c.tick(3);self.assertEqual(c.result,('win',0))
 def test_drive_during_startup_requires_remove_and_reinsert(self):
  c=Controls(True);c.key('A',0);c.usb_update(True,1);c.usb_update(True,3);self.assertFalse(c.game.objective)
  c.usb_update(False,4);c.usb_update(True,5);c.tick(5);self.assertEqual(c.result,('win',0))
 def test_unknown_reading_disarms_and_maintenance_cannot_win(self):
  c=Controls(True);c.key('A',0);c.usb_update(False,2);c.usb_update(None,2.5);c.usb_update(True,3);self.assertFalse(c.game.objective)
  c.usb_update(False,4);c.usb_update(True,5,allow_objective=False);self.assertFalse(c.game.objective)
 def test_key_mode_and_new_game_never_reuse_an_insertion(self):
  c=Controls(True);c.mode='keys';c.key('A',0);c.usb_update(False,2);c.usb_update(True,3);self.assertFalse(c.game.objective)
  c.game.finish('stopped');c.tick(4);c.mode='usb';c.key('A',5);c.usb_update(True,8);self.assertFalse(c.game.objective)

if __name__=='__main__':unittest.main()
