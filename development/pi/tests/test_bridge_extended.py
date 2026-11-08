import json,sys,tempfile,time,types,unittest,urllib.error,uuid
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from maintenance_bridge import Bridge
from game_reporting import atomic_json

class BridgeExtraTests(unittest.TestCase):
    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup)
        self.home=Path(self.tmp.name);self.folder=self.home/'control'
        cfg=self.home/'config.json';cfg.write_text(json.dumps(dict(device_id='test-device',url='https://example.test/ingest.php',upload_key='private-test-value')))
        self.b=Bridge(cfg,self.folder)
    def test_permanent_bad_result_preserved_and_poll_still_runs(self):
        ident=str(uuid.uuid4());atomic_json(self.folder/'outbox'/(ident+'.json'),dict(id=ident))
        calls=[]
        def post(body):
            calls.append(body['action'])
            if body['action']=='ack':raise urllib.error.HTTPError('https://example.test',400,'Invalid result',{},None)
            return dict(commands=[])
        with patch.object(self.b,'post',side_effect=post):self.b.once()
        self.assertEqual(calls,['ack','poll'])
        self.assertTrue((self.folder/'rejected'/(ident+'.json')).exists())
        self.assertFalse(list((self.folder/'outbox').glob('*.json')))
    def test_stale_controller_feed_cannot_claim_connected_or_raw_value(self):
        atomic_json(self.folder/'live.json',dict(device_id='test-device',connected=True,receiver=dict(raw=70),protocol=2))
        import os
        os.utime(self.folder/'live.json',(1,1))
        with patch.object(self.b,'grant',return_value=False),patch('maintenance_bridge.subprocess.run',return_value=types.SimpleNamespace(stdout='inactive',returncode=1)):
            live=self.b.telemetry()
        self.assertFalse(live['connected']);self.assertIsNone(live['receiver']['raw'])
    def test_reboot_capability_requires_explicit_password_free_permission(self):
        atomic_json(self.folder/'live.json',dict(device_id='test-device',connected=True,receiver=dict(raw=70),protocol=2))
        for listing,expected in [('Commands: ALL\nMatched: reboot',False),('Options: !authenticate\nCommands: /usr/bin/systemctl reboot --no-block',True)]:
            self.b.next_permission_check=0
            def run(args,**kwargs):return types.SimpleNamespace(stdout='active' if 'is-active' in args else listing,returncode=0)
            with patch.object(self.b,'grant',return_value=False),patch('maintenance_bridge.subprocess.run',side_effect=run):self.assertEqual(self.b.telemetry()['reboot_supported'],expected)

    def test_start_can_recover_stopped_service_without_a_fresh_local_enable(self):
        command=dict(id=str(uuid.uuid4()),action='service_start')
        with patch.object(self.b,'grant',return_value=False),patch('maintenance_bridge.subprocess.run') as run,patch.object(self.b,'health',return_value=True):self.b.service(command)
        self.assertEqual(run.call_args.args[0],['sudo','-n','/usr/bin/systemctl','start','zoco-game.service'])
        self.assertEqual(json.loads((self.folder/'results'/(command['id']+'.json')).read_text())['status'],'completed')
    def test_stop_and_reinstall_require_local_enable(self):
        with patch.object(self.b,'grant',return_value=False),patch('maintenance_bridge.subprocess.run') as run,patch('maintenance_bridge.subprocess.Popen') as popen:
            self.b.service(dict(id=str(uuid.uuid4()),action='service_stop'))
            self.b.reinstall(dict(id=str(uuid.uuid4()),action='software_reinstall'))
        run.assert_not_called();popen.assert_not_called()
    def test_reboot_never_runs_twice_while_outcome_pending(self):
        command=dict(id=str(uuid.uuid4()),action='reboot_pi')
        atomic_json(self.folder/('reboot-'+command['id']+'.json'),dict(requested_at=int(time.time())))
        with patch.object(self.b,'grant',return_value=True),patch('maintenance_bridge.subprocess.run') as run:self.b.reboot(command)
        run.assert_not_called();self.assertFalse(list((self.folder/'results').glob('*.json')))
