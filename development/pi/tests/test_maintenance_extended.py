import json,sys,tempfile,unittest,uuid
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from maintenance import Maintenance,validate
from panel_game import Controls
from game_reporting import atomic_json
from operator_settings import DEFAULT_SETTINGS

class Audio:
    enabled=True;muted=False;assets_ready=True;backend='pw-play';error='';durations={'entrance':5}
    def __init__(self):self.cues=[];self.muted=False;self.volume=1
    def queue(self,clip,**kw):self.cues.append(clip)
    def cancel(self):self.cues=[]

class ExtendedTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.folder=Path(self.tmp.name)/'control';self.c=Controls();self.wall=1000
        self.m=Maintenance(self.folder,'device',Audio(),Audio(),wall=lambda:self.wall)
        self.m.enabled=True;self.m.local_until=1300;self.m.save();self.m.configure_controls(self.c)
    def command(self,action,params=None):
        c=dict(id=str(uuid.uuid4()),device_id='device',action=action,params=params or {},expires_at=1060)
        atomic_json(self.folder/'inbox'/(c['id']+'.json'),c);return c
    def result(self,c):return json.loads((self.folder/'results'/(c['id']+'.json')).read_text())
    def capture(self,phase,value,start):
        self.m.receive_light(value,start);c=self.command('receiver_capture',{'phase':phase});self.m.tick(self.c,start)
        self.m.tick(self.c,start+.1,serial_idle=True,previous=(True,False,0,"YELLOW"))
        for i in range(100):
            now=start+.6+.05*(i+1);self.m.receive_light(value,now);self.m.tick(self.c,now)
        self.assertEqual(self.result(c)['status'],'completed');return start+6
    def test_powered_capture_waits_for_ack_and_settling_and_D_stops(self):
        self.m.receive_light(0,0);self.command('receiver_capture',{'phase':'blocked'});self.m.tick(self.c,0)
        self.assertTrue(self.m.display()[0]);self.m.receive_light(900,.1)
        self.assertEqual(self.m.test['values'],[])
        self.m.tick(self.c,.2,serial_idle=True,previous=(True,False,0,'YELLOW'))
        self.m.receive_light(800,.3);self.assertEqual(self.m.test['values'],[])
        self.m.receive_light(12,.8);self.assertEqual(self.m.test['values'],[12])
        self.m.local_key('D',self.c);self.assertFalse(self.m.display()[0])

    def test_module_sequence_uses_shared_dispatch_and_waits_for_ack(self):
        for action,duration in [('module_test',5),('laser_align',30)]:
            sent=[];self.m.send=lambda *args:sent.append(args)
            self.m.next_scan=0;c=self.command(action);self.m.tick(self.c,0)
            self.assertFalse(sent) # No second writer for the serial output.
            self.assertEqual(self.m.display(),(False,False,0,'YELLOW'))
            self.m.tick(self.c,1,serial_idle=False,previous=self.m.display())
            self.assertIsNone(self.m.test['settle_until'])
            self.m.tick(self.c,2,serial_idle=True,previous=self.m.display())
            self.m.tick(self.c,3.99);self.assertFalse(self.m.display()[0])
            self.m.tick(self.c,4.0);self.assertTrue(self.m.display()[0])
            # Receiver blocked throughout does not suppress HIGH.
            self.m.receive_light(0,8.6)
            self.m.tick(self.c,9,serial_idle=False,previous=self.m.display())
            self.assertIsNone(self.m.test['settle_until'])
            self.m.tick(self.c,10,serial_idle=True,previous=self.m.display())
            self.m.tick(self.c,10+duration-.01);self.assertTrue(self.m.display()[0])
            self.m.tick(self.c,10+duration);self.assertFalse(self.m.display()[0])
            self.m.tick(self.c,11+duration,serial_idle=True,previous=self.m.display())
            self.m.tick(self.c,13.5+duration)
            self.assertEqual(self.result(c)['status'],'completed');self.assertFalse(sent)
    def test_module_cancel_timeout_and_late_ack_cannot_restart(self):
        self.command('laser_align');self.m.tick(self.c,0)
        self.m.tick(self.c,1,serial_idle=True,previous=self.m.display());self.m.tick(self.c,3.0)
        self.assertTrue(self.m.display()[0]);self.m.local_key('D',self.c)
        self.m.output_acknowledged(True,8);self.assertFalse(self.m.display()[0]);self.assertIsNone(self.m.test)
        self.m.next_scan=0;c=self.command('module_test');self.m.tick(self.c,10)
        self.m.tick(self.c,36);self.assertEqual(self.result(c)['status'],'failed');self.assertFalse(self.m.display()[0])

    def test_three_captures_candidate_apply_ack_and_persistence(self):
        now=0
        for phase,value in [('blocked',0),('clear',70),('blocked_check',0)]:now=self.capture(phase,value,now)
        self.assertTrue(self.m.candidate['proposal']['usable'])
        sent=[];self.m.send=lambda *args:sent.append(args)
        c=self.command('receiver_apply',{'candidate_id':self.m.candidate['id']});self.m.tick(self.c,now)
        self.assertEqual(self.m.thresholds,dict(break_below=20,clear_above=41))
        self.assertEqual(sent[0][0],'CAL 23 46');sent[0][2]()
        self.assertEqual(self.result(c)['status'],'completed')
        again=Maintenance(self.folder,'device',Audio(),Audio(),wall=lambda:self.wall)
        self.assertEqual(again.thresholds,dict(break_below=23,clear_above=46))
    def test_capture_order_and_stale_candidate_rejected(self):
        c=self.command('receiver_capture',{'phase':'clear'});self.m.tick(self.c,0)
        self.assertEqual(self.result(c)['status'],'failed')
        c=self.command('receiver_apply',{'candidate_id':str(uuid.uuid4())});self.m.tick(self.c,1)
        self.assertEqual(self.result(c)['status'],'failed')
    def test_capture_no_data_timeout(self):
        self.m.receive_light(0,0);c=self.command('receiver_capture',{'phase':'blocked'});self.m.tick(self.c,0)
        self.m.tick(self.c,16);self.assertEqual(self.result(c)['status'],'failed')
        self.assertFalse(self.m.capture_values)
    def test_cancelled_apply_restores_previous_thresholds_on_late_ack(self):
        sent=[];self.m.send=lambda *args:sent.append(args)
        c=self.command('receiver_thresholds',{'break_below':30,'clear_above':60});self.m.tick(self.c,0)
        self.m.local_key('D',self.c);sent[0][2]()
        self.assertEqual(sent[-1][0],'CAL 20 41')
        self.assertFalse((self.folder/'receiver-settings.json').exists())
        self.assertEqual(self.result(c)['status'],'failed')
    def test_game_settings_and_play_lock_persist(self):
        cfg=dict(DEFAULT_SETTINGS,duration=200,enabled_beams=[False,True],available_modes=['keys'])
        c=self.command('game_settings',cfg);self.m.tick(self.c,0)
        self.assertEqual(self.result(c)['status'],'completed');self.assertEqual(self.c.mode,'keys')
        c=self.command('start_lock',{'locked':True});self.m.tick(self.c,1);self.c.key('A',2)
        self.assertIsNone(self.c.game)
        again=Maintenance(self.folder,'device',Audio(),Audio(),wall=lambda:self.wall);fresh=Controls();again.configure_controls(fresh)
        self.assertTrue(fresh.play_locked);self.assertEqual(fresh.settings.duration,200)
        self.assertEqual(fresh.settings.enabled_beams,(False,True))
    def test_live_module_request_uses_game_state_outside_maintenance(self):
        self.m.enabled=False;self.c.key('A',0)
        self.assertTrue(self.m.live(self.c,0)['laser_command_on'])
    def test_settings_and_threshold_validation(self):
        for action,params in [('receiver_thresholds',dict(break_below=80,clear_above=40)),('game_settings',dict(DEFAULT_SETTINGS,enabled_beams=[False,False])),('audio_volume',{'percent':101}),('start_lock',{'locked':1})]:
            with self.assertRaises(ValueError):validate(dict(id=str(uuid.uuid4()),device_id='device',action=action,params=params,expires_at=1060),'device',1000)
    def test_play_lock_does_not_interrupt_current_game_or_require_test_enable(self):
        self.m.enabled=False;self.m.local_until=0;self.c.key('A',0);self.c.tick(10)
        current=self.c.game;c=self.command('start_lock',{'locked':True});self.m.tick(self.c,11)
        self.assertIs(self.c.game,current);self.assertEqual(current.state,'running')
        self.assertEqual(self.result(c)['status'],'completed')
        self.c.key('D',12);self.c.tick(12);self.c.key('A',13);self.assertIsNone(self.c.game)

    def test_volume_saves_and_expired_enable_blocks_capture(self):
        c=self.command('audio_volume',{'percent':42});self.m.tick(self.c,0)
        self.assertEqual(self.m.audio.volume,.42)
        self.m.local_until=999;c=self.command('receiver_capture',{'phase':'blocked'});self.m.tick(self.c,1)
        self.assertEqual(self.result(c)['status'],'failed')
