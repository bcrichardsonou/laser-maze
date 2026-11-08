import json,sys,tempfile,unittest,uuid
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from maintenance import Maintenance,validate
from panel_game import Controls
from game_reporting import atomic_json
from test_maintenance_extended import Audio

class AutomaticCalibrationTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.folder=Path(self.tmp.name)/'control';self.controls=Controls();self.wall=1000
        self.m=Maintenance(self.folder,'device',Audio(),Audio(),wall=lambda:self.wall)
        self.m.enabled=True;self.m.local_until=1300;self.m.connected=True
        self.sent=[];self.m.send=lambda *a:self.sent.append(a)
        self.command=dict(id=str(uuid.uuid4()),device_id='device',action='receiver_auto',params={},expires_at=1060)
        atomic_json(self.folder/'inbox'/(self.command['id']+'.json'),self.command)
        self.m.tick(self.controls,0)
    def result(self):return json.loads((self.folder/'results'/(self.command['id']+'.json')).read_text())
    def phase(self,values,now):
        phase=self.m.test['phase'];self.assertEqual(self.m.display()[0],phase=='clear')
        self.m.tick(self.controls,now,serial_idle=True,previous=self.m.display())
        ready=self.m.test['sample_after'];self.assertGreaterEqual(ready-now,2.5)
        self.m.receive_light(999,ready-.01);self.assertEqual(self.m.test['values'],[])
        for i,v in enumerate(values):
            t=ready+.04*(i+1);self.m.receive_light(v,t);self.m.tick(self.controls,t)
        return ready+4.2
    def run_samples(self,off,on,check):
        t=.2
        for values in (off,on,check):t=self.phase(values,t)
        return t
    def test_off_on_off_auto_saves_only_after_controller_ack(self):
        self.assertFalse(self.m.display()[0]);self.run_samples([0]*100,[70]*100,[0]*100)
        self.assertEqual(self.sent[0][0],'CAL 23 46');self.assertFalse(self.m.display()[0])
        self.assertEqual(self.m.thresholds,dict(break_below=20,clear_above=41))
        self.assertFalse((self.folder/'receiver-settings.json').exists())
        self.sent[0][2]()
        self.assertEqual(self.m.thresholds,dict(break_below=23,clear_above=46))
        self.assertEqual(self.result()['status'],'completed');self.assertTrue(self.m.candidate['applied'])
        self.assertLess(len(json.dumps(self.result())),4096)
        self.assertLess(len(json.dumps(self.m.live(self.controls,30))),6000)
        fresh=Maintenance(self.folder,'device',Audio(),Audio(),wall=lambda:self.wall)
        self.assertEqual(fresh.thresholds,self.m.thresholds)
    def test_waits_for_matching_output_ack(self):
        self.m.tick(self.controls,.2,serial_idle=False,previous=self.m.display())
        for i in range(100):self.m.receive_light(0,1+i*.04)
        self.assertEqual(self.m.test['values'],[])
        self.m.tick(self.controls,41);self.assertFalse(self.m.display()[0])
        self.assertEqual(self.result()['status'],'failed');self.assertFalse(self.sent)
    def test_bad_separation_or_saturation_keeps_previous_calibration(self):
        for on in (10,1023):
            with self.subTest(on=on):
                if on==1023:self.setUp()
                self.run_samples([0]*100,[on]*100,[0]*100)
                self.assertEqual(self.result()['status'],'failed');self.assertFalse(self.sent)
                self.assertEqual(self.m.thresholds,dict(break_below=20,clear_above=41))
                self.assertFalse(self.m.display()[0]);self.assertFalse((self.folder/'receiver-settings.json').exists())
    def test_background_drift_rejected(self):
        self.run_samples([0]*100,[100]*100,[30]*100)
        self.assertFalse(self.m.candidate['proposal']['usable']);self.assertFalse(self.sent)
    def test_noisy_laser_readings_rejected(self):
        self.run_samples([0]*100,[50,100]*50,[0]*100)
        self.assertIn('unstable',self.m.candidate['proposal']['reason']);self.assertFalse(self.sent)
    def test_stop_and_enable_expiry_interrupt_on_phase(self):
        t=self.phase([0]*100,.2);self.assertTrue(self.m.display()[0])
        self.m.local_key('D',self.controls);self.assertFalse(self.m.display()[0]);self.assertFalse(self.sent)
        self.assertEqual(self.result()['status'],'failed')
    def test_late_apply_ack_restores_previous_thresholds(self):
        self.run_samples([0]*100,[70]*100,[0]*100)
        callback=self.sent[0][2];self.m.local_key('D',self.controls);callback()
        self.assertEqual(self.sent[-1][0],'CAL 20 41');self.assertFalse((self.folder/'receiver-settings.json').exists())
    def test_local_enable_expires(self):
        self.phase([0]*100,.2);self.wall=1301;self.m.tick(self.controls,8)
        self.assertFalse(self.m.display()[0]);self.assertEqual(self.result()['status'],'failed')
    def test_auto_params_are_allowlisted(self):
        bad=dict(self.command,params={'threshold':0})
        with self.assertRaises(ValueError):validate(bad,'device',1000)

if __name__=='__main__':unittest.main()
