import json
from pathlib import Path
import sys
import tempfile
import unittest
import uuid
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from maintenance import Maintenance,validate
from maintenance_bridge import Bridge
from panel_game import Controls
from game_reporting import Reporting,atomic_json


class Audio:
    enabled=True;muted=False;assets_ready=True;backend='pw-play';error=''
    durations={'entrance':5}
    def __init__(self):self.cues=[];self.muted=False
    def queue(self,*a,**kw):self.cues.append(a[0])
    def cancel(self):self.cues=[]


class MaintenanceTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.folder=Path(self.tmp.name)/'control';self.wall=1000
        self.audio=Audio();self.effects=Audio();self.c=Controls(False)
        self.m=Maintenance(self.folder,'device-test',self.audio,self.effects,wall=lambda:self.wall)
    def tearDown(self):self.tmp.cleanup()
    def command(self,action,params=None,expiry=1060,identity='device-test'):
        c=dict(id=str(uuid.uuid4()),device_id=identity,action=action,params=params or {},expires_at=expiry)
        atomic_json(self.folder/'inbox'/(c['id']+'.json'),c);return c
    def result(self,c):return json.loads((self.folder/'results'/(c['id']+'.json')).read_text())
    def enter(self):
        c=self.command('enter_maintenance');self.m.tick(self.c,0)
        self.assertFalse(self.m.enabled);self.assertIsNotNone(self.m.pending)
        self.assertFalse((self.folder/'results'/(c['id']+'.json')).exists())
        self.assertTrue(self.m.local_key('C',self.c));self.assertTrue(self.m.local_enabled())
        return c

    def test_enter_requires_local_confirmation_and_stops_active_game(self):
        self.c.key('A',0);self.c.tick(5);c=self.enter()
        self.assertIsNone(self.c.game);self.assertEqual(self.m.display()[:2],(False,False))
        self.assertEqual(self.result(c)['status'],'completed')

    def test_hardware_test_rejected_without_local_enable(self):
        c=self.command('rgb_test',{'color':'RED'});self.m.tick(self.c,0)
        self.assertEqual(self.result(c)['reason'],'press_5_in_maintenance_first');self.assertIsNone(self.m.test)

    def test_late_C_cannot_activate_an_expired_request(self):
        c=self.command('enter_maintenance');self.m.tick(self.c,0);self.wall=1061
        self.m.local_key('C',self.c)
        self.assertFalse(self.m.enabled);self.assertEqual(self.result(c)['status'],'expired')

    def test_B_returns_to_idle_locally_without_network_or_auto_start(self):
        self.enter();self.assertTrue(self.m.local_key('B',self.c))
        self.assertFalse(self.m.enabled);self.assertFalse(self.m.local_enabled());self.assertIsNone(self.c.game)

    def test_rgb_resets_after_five_seconds_and_waits_for_serial_ack(self):
        self.enter();c=self.command('rgb_test',{'color':'RED'});self.m.tick(self.c,1)
        self.assertEqual(self.m.display(),(False,False,0,'RED'))
        self.m.tick(self.c,6,serial_idle=False,previous=(False,False,0,'RED'))
        self.assertEqual(self.m.display(),(False,False,0,'BLUE'))
        self.assertFalse((self.folder/'results'/(c['id']+'.json')).exists())
        self.m.tick(self.c,6.2,serial_idle=True,previous=(False,False,0,'BLUE'))
        self.assertIsNone(self.m.test);self.assertEqual(self.result(c)['status'],'completed')

    def test_display_is_timed_and_never_enables_beams(self):
        self.enter();self.command('display_test');self.m.tick(self.c,1)
        self.assertEqual(self.m.display(),(False,False,5999,'BLUE'))
        self.m.tick(self.c,6);self.assertEqual(self.m.display()[2],0)

    def test_D_cancels_test_and_sound_without_leaving_maintenance(self):
        self.enter();c=self.command('rgb_test',{'color':'RED'});self.m.tick(self.c,1)
        self.audio.queue('entrance');self.m.local_key('D',self.c)
        self.assertEqual(self.result(c)['status'],'failed');self.assertTrue(self.m.enabled)
        self.assertFalse(self.audio.cues);self.assertEqual(self.m.display()[3],'BLUE')

    def test_local_enable_expires_without_network_or_portal(self):
        self.enter();c=self.command('rgb_test',{'color':'RED'});self.m.tick(self.c,1)
        self.wall=1301;self.m.tick(self.c,2)
        self.assertFalse(self.m.local_enabled());self.assertTrue(self.m.enabled);self.assertIsNone(self.m.test)
        self.assertEqual(self.m.display()[:2],(False,False))

    def test_expired_and_wrong_component_never_execute(self):
        for c in (self.command('rgb_test',{'color':'RED'},expiry=999),self.command('rgb_test',{'color':'RED'},identity='other')):
            self.m.tick(self.c,self.m.next_scan)
            self.assertEqual(self.result(c)['status'],'failed')
        self.assertIsNone(self.m.test)

    def test_duplicate_command_is_not_reexecuted(self):
        self.enter();c=self.command('audio_mute',{'muted':True});self.m.tick(self.c,1)
        self.assertTrue(self.audio.muted);self.audio.muted=False
        atomic_json(self.folder/'inbox'/(c['id']+'.json'),c);self.m.tick(self.c,2)
        self.assertFalse(self.audio.muted)

    def test_leave_returns_idle_and_persisted_mute_survives_restart(self):
        self.enter();self.command('audio_mute',{'muted':True});self.m.tick(self.c,1)
        m=Maintenance(self.folder,'device-test',Audio(),Audio(),wall=lambda:self.wall)
        self.assertTrue(m.enabled);self.assertTrue(m.audio.muted)
        c=self.command('leave_maintenance');m.tick(self.c,2)
        self.assertFalse(m.enabled);self.assertFalse(m.local_enabled());self.assertEqual(self.result(c)['status'],'completed')

    def test_stop_audio_can_cancel_audio_test(self):
        self.enter();test=self.command('audio_play',{'clip':'entrance'});self.m.tick(self.c,1)
        stop=self.command('stop_audio');self.m.tick(self.c,2)
        self.assertFalse(self.audio.cues);self.assertIsNone(self.m.test);self.assertEqual(self.result(stop)['status'],'completed')

    def test_malformed_params_and_arbitrary_actions_rejected(self):
        for action,params in [('shell',{}),('rgb_test',{'color':'RED; reboot'}),('audio_mute',{'muted':'yes'}),('snapshot',{'extra':1})]:
            c=self.command(action,params)
            with self.assertRaises(ValueError):validate(c,'device-test',1000)

    def test_reported_maintenance_state_and_metric_budget(self):
        self.enter();report=Reporting(Path(self.tmp.name)/'report','bench-0.26.3',False)
        audio=dict(audio_enabled=True,audio_player_available=True,audio_assets_ready=True,audio_muted=False,audio_last_cue_requested='none',audio_error='none',audio_effects_error='none',audio_effect_last_cue_requested='none')
        report.status(self.c,self.m.display(),1,audio=audio,maintenance=self.m.metrics())
        d=json.loads((report.folder/'game-status.json').read_text())
        self.assertEqual(d['state'],'maintenance');self.assertEqual(d['metrics']['game_phase'],'maintenance');self.assertLessEqual(len(d['metrics']),40)

    def test_bridge_recovers_results_but_never_opens_serial(self):
        c=self.command('snapshot');self.m.tick(self.c,0)
        config=Path(self.tmp.name)/'config.json';config.write_text(json.dumps(dict(device_id='device-test',upload_key='test-key',url='https://example.test/ingest.php')))
        bridge=Bridge(config,self.folder)
        def post(body):
            if body['action']=='ack':return dict(acknowledged=body['result']['id'])
            return dict(commands=[c])
        with patch.object(bridge,'post',side_effect=post):bridge.once()
        self.assertTrue((self.folder/'acked'/(c['id']+'.json')).exists());self.assertFalse((self.folder/'inbox'/(c['id']+'.json')).exists())

    def test_restart_refused_outside_locally_enabled_maintenance(self):
        config=Path(self.tmp.name)/'config.json';config.write_text(json.dumps(dict(device_id='device-test',upload_key='test-key',url='https://example.test/ingest.php')))
        bridge=Bridge(config,self.folder);c=self.command('restart_game')
        with patch('maintenance_bridge.subprocess.run') as run:bridge.restart(c);run.assert_not_called()
        self.assertEqual(self.result(c)['status'],'failed')

if __name__=='__main__':unittest.main()
