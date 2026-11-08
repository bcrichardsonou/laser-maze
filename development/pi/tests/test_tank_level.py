import sys,tempfile,json,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from tank_level import TankLevel,ohms
class TankTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.p=Path(self.tmp.name)/'tank.json';self.t=TankLevel(self.p)
 def test_divider_and_uncalibrated_no_invented_level(self):
  self.assertAlmostEqual(ohms(267),240.16,places=1)
  self.t.receive(267,1);s=self.t.status(1)
  self.assertEqual(s['state'],'uncalibrated');self.assertIsNone(s['float_height_percent']);self.assertFalse(s['alerts_enabled']);self.assertFalse(s['automatic_cutoff'])
 def test_fault_and_stale_readings(self):
  for value,state in ((1023,'open_or_connected_to_5v'),(0,'short_or_connected_to_ground')):
   self.t.receive(value,1);self.assertEqual(self.t.status(1)['state'],state)
  self.assertEqual(self.t.status(4)['state'],'unconfirmed');self.assertIsNone(self.t.status(4)['raw'])
 def test_empty_full_saves_and_percent_uses_resistance_not_voltage(self):
  self.t.capture('empty',[267]*20);self.assertIsNone(self.t.calibration)
  self.t.capture('full',[47]*20);self.assertEqual(TankLevel(self.p).calibration,self.t.calibration)
  self.t.receive(171,1);self.assertAlmostEqual(self.t.status(1)['float_height_percent'],50,delta=1)
  self.t.receive(47,2);self.assertEqual(self.t.status(2)['float_height_percent'],100)
  self.t.receive(267,3);self.assertEqual(self.t.status(3)['float_height_percent'],0)
 def test_unstable_reversed_or_rail_capture_preserves_old_calibration(self):
  self.t.capture('empty',[267]*20);self.t.capture('full',[47]*20);old=self.p.read_bytes()
  for phase,values in (('empty',[0]*20),('empty',[267]*10+[240]*10),('full',[270]*20)):
   with self.assertRaises(ValueError):self.t.capture(phase,values)
   self.assertEqual(self.p.read_bytes(),old)
 def test_full_requires_empty_and_failed_data_never_saves(self):
  with self.assertRaises(ValueError):self.t.capture('full',[47]*20)
  self.assertFalse(self.p.exists())
