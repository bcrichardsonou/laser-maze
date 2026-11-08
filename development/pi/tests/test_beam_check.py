import json,sys,tempfile,unittest,uuid
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from maintenance import Maintenance,validate
from panel_game import Controls
from game_reporting import atomic_json
from test_maintenance_extended import Audio

class BeamCheckTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.folder=Path(self.tmp.name)/'control';self.c=Controls();self.wall=1000
        self.m=Maintenance(self.folder,'device',Audio(),Audio(),wall=lambda:self.wall)
        self.m.enabled=True;self.m.local_until=1300;self.m.connected=True
        self.sent=[];self.m.send=lambda *a:self.sent.append(a)
        self.cmd=dict(id=str(uuid.uuid4()),device_id='device',action='beams_check',params={},expires_at=1060)
    def start(self):
        atomic_json(self.folder/'inbox'/(self.cmd['id']+'.json'),self.cmd);self.m.tick(self.c,0)
    def result(self):return json.loads((self.folder/'results'/(self.cmd['id']+'.json')).read_text())
    def sample(self,values):
        self.m.tick(self.c,.2,serial_idle=True,previous=self.m.display())
        self.assertEqual(self.m.test['sample_after'],3.2)
        self.m.receive_light(0,3.1);self.assertEqual(self.m.test['values'],[])
        for i,v in enumerate(values):
            now=3.2+(i+1)*.04;self.m.receive_light(v,now);self.m.tick(self.c,now)
    def finish(self):self.m.tick(self.c,8,serial_idle=True,previous=self.m.display())
    def test_clear_requires_low_ack_and_does_not_change_calibration(self):
        self.start();self.assertTrue(self.m.display()[0]);self.sample([70]*100)
        self.assertFalse(self.m.display()[0]);self.assertFalse((self.folder/'results'/(self.cmd['id']+'.json')).exists())
        self.m.tick(self.c,7.8,serial_idle=True,previous=(True,False,0,'YELLOW'))
        self.assertEqual(self.m.beam_check['status'],'running');self.finish()
        b=self.result()['snapshot']['beam_check'];self.assertTrue(b['all_clear']);self.assertTrue(b['outputs_off_confirmed'])
        self.assertEqual(b['modules'][0]['state'],'clear');self.assertEqual(b['modules'][0]['count'],100)
        self.assertFalse(self.sent);self.assertFalse((self.folder/'receiver-settings.json').exists())
        self.assertLess(len(json.dumps(self.result())),4096);self.assertLess(len(json.dumps(self.m.live(self.c,8))),6000)
    def test_not_detected(self):
        self.start();self.sample([5]*100);self.finish()
        self.assertEqual(self.m.beam_check['modules'][0]['state'],'not_detected');self.assertFalse(self.m.beam_check['all_clear'])
        self.assertEqual(self.result()['reason'],'beam_test_attention_required')
    def test_unstable(self):
        self.start();self.sample([5,70]*50);self.finish()
        self.assertEqual(self.m.beam_check['modules'][0]['state'],'unstable')
    def test_waits_for_output_ack_and_times_out_without_fabricated_readings(self):
        self.start();self.m.tick(self.c,.2,serial_idle=False,previous=self.m.display())
        for i in range(100):self.m.receive_light(70,4+i*.04)
        self.assertEqual(self.m.test['values'],[]);self.m.tick(self.c,21)
        self.assertFalse(self.m.display()[0]);self.assertEqual(self.m.beam_check['status'],'unconfirmed')
        self.assertFalse(self.m.beam_check['all_clear']);self.assertEqual(self.result()['status'],'failed')
    def test_local_cancel_and_expiry_return_low(self):
        self.start();self.m.local_key('D',self.c);self.assertFalse(self.m.display()[0])
        self.assertEqual(self.m.beam_check['status'],'cancelled');self.assertFalse(self.m.beam_check['all_clear'])
    def test_local_enable_expiry(self):
        self.start();self.wall=1301;self.m.tick(self.c,1)
        self.assertFalse(self.m.display()[0]);self.assertEqual(self.result()['status'],'failed')
    def test_requires_local_confirmation(self):
        self.m.local_until=0;self.start();self.assertIsNone(self.m.test);self.assertEqual(self.result()['status'],'failed')
    def test_disabled_receiver_is_skipped_not_passed(self):
        self.c.configure(dict(duration=150,startup=5,cooldown=7,warmup=5,max_breaks=3,enabled_beams=[False,True],available_modes=['usb']))
        self.start();self.assertFalse(self.m.display()[0]);self.assertFalse(self.m.beam_check['all_clear'])
        self.assertEqual(self.m.beam_check['tested_count'],0);self.assertEqual(self.m.beam_check['modules'][0]['state'],'disabled')
    def test_result_fits_transport_after_previous_calibration(self):
        from receiver_calibrate import propose
        self.m.capture_values=dict(blocked=[5]*100,clear=[70]*100,blocked_check=[5]*100)
        self.m.candidate=dict(id=str(uuid.uuid4()),created_at=999,mode='automatic_off_on_off',proposal=propose([5]*100,[70]*100,[5]*100),applied=True)
        self.start();self.sample([70]*100);self.finish()
        self.assertLess(len(json.dumps(self.result())),4096)
        self.assertLess(len(json.dumps(self.m.live(self.c,8))),6000)
    def test_strict_empty_params(self):
        with self.assertRaises(ValueError):validate(dict(self.cmd,params={'module':15}),'device',1000)

if __name__=='__main__':unittest.main()
