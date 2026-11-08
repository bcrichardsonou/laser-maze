import json,os,sys,tempfile,time,subprocess,unittest,uuid
from pathlib import Path
from types import SimpleNamespace
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from hazer_dmx import Hazer,DEFAULTS,frame,validate_settings
from maintenance import Maintenance,validate
from panel_game import Controls
from game_reporting import atomic_json
from test_maintenance_extended import Audio

class DmxTests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.addCleanup(self.tmp.cleanup);self.path=Path(self.tmp.name)/'dmx-settings.json'
  self.path.write_text(json.dumps(dict(port='/dev/serial/by-id/usb-FTDI_test',settings=DEFAULTS)))
  self.h=Hazer(self.path)
 def test_frame_full_universe_start_code_and_adjacent_slots(self):
  f=frame(10,16,64);self.assertEqual(len(f),513);self.assertEqual(f[0],0);self.assertEqual((f[10],f[11]),(16,64));self.assertEqual(sum(f),80)
  self.assertEqual(frame(511,1,2)[511:],bytes([1,2]))
  for args in ((512,0,0),(0,0,0),(10,True,0),(10,0,256)):
   with self.assertRaises(ValueError):frame(*args)
 def test_settings_and_test_validation(self):
  validate_settings(DEFAULTS)
  for p in (dict(DEFAULTS,address=512),dict(DEFAULTS,automatic=1),dict(DEFAULTS,burst_seconds=31)):
   with self.assertRaises(ValueError):validate_settings(p)
  for p in (dict(mode='adapter',pump=1,fan=0,seconds=5),dict(mode='fan',pump=2,fan=64,seconds=5),dict(mode='haze',pump=1,fan=1,seconds=11)):
   with self.assertRaises(ValueError):validate(dict(id=str(uuid.uuid4()),device_id='dev',action='hazer_test',params=p,expires_at=1060),'dev',1000)
 def test_default_off_then_single_preparation_burst(self):
  c=SimpleNamespace(game=object());m=SimpleNamespace(test=None,enabled=False,pending=None)
  self.h.connected=True;self.assertEqual(self.h.targets(c,m,0),(0,0))
  self.h.settings=dict(DEFAULTS,automatic=True);c.game=object()
  self.assertEqual(self.h.targets(c,m,1),(16,64));self.assertEqual(self.h.targets(c,m,11.9),(16,64));self.assertEqual(self.h.targets(c,m,12),(0,0))
  c.game=None;self.assertEqual(self.h.targets(c,m,13),(0,0))
  c.game=object();self.assertEqual(self.h.targets(c,m,14),(16,64))
 def test_connection_loss_blocks_same_session_and_stop_disables_auto(self):
  c=SimpleNamespace(game=object());m=SimpleNamespace(test=None,enabled=False,pending=None)
  self.h.settings=dict(DEFAULTS,automatic=True);self.h.connected=True;self.h.targets(c,m,0)
  self.h.blocked=self.h.session;self.assertEqual(self.h.targets(c,m,1),(0,0))
  self.h.stop();self.assertFalse(json.loads(self.path.read_text())['settings']['automatic'])
  c.game=object();self.assertEqual(self.h.targets(c,m,2),(0,0))
 def test_maintenance_target_requires_grant_and_expires(self):
  c=SimpleNamespace(game=None);m=SimpleNamespace(test=dict(kind='hazer',command={'id':'test'},pump=16,fan=64,until=5),enabled=True,pending=None,local_enabled=lambda:True)
  self.assertEqual(self.h.targets(c,m,1),(16,64));self.assertEqual(self.h.targets(c,m,5),(0,0))
  m.local_enabled=lambda:False;self.assertEqual(self.h.targets(c,m,1),(0,0))
 def test_maintenance_completion_waits_for_zero_frame_status(self):
  c=Controls();c.hazer=self.h;self.h.connected=True;self.h.frames=20
  m=Maintenance(Path(self.tmp.name)/'control','dev',Audio(),Audio(),wall=lambda:1000);m.enabled=True;m.local_until=1300
  cmd=dict(id=str(uuid.uuid4()),device_id='dev',action='hazer_test',params=dict(mode='fan',pump=0,fan=64,seconds=5),expires_at=1060)
  atomic_json(m.folder/'inbox'/(cmd['id']+'.json'),cmd);m.tick(c,0)
  self.assertEqual(m.test['kind'],'hazer');m.tick(c,5.1);self.assertIsNotNone(m.test)
  self.h.frames=21;self.h.last_status=5.2;m.tick(c,5.2);self.assertIsNone(m.test)
  result=json.loads((m.folder/'results'/(cmd['id']+'.json')).read_text());self.assertEqual(result['reason'],'dmx_frames_written_physical_hazer_unconfirmed')
 def test_live_payload_with_calibration_and_both_input_tests_fits(self):
  from receiver_calibrate import propose,summarize
  c=Controls();c.hazer=self.h;c.reader_diagnostics=dict(source='usb_pcsc',model='ACS ACR1552U',tag_responses=100,selection_failures=0,card_present=False,error='')
  m=Maintenance(Path(self.tmp.name)/'full','dev',Audio(),Audio(),wall=lambda:1000)
  m.capture_values=dict(blocked=[5]*100,clear=[70]*100,blocked_check=[5]*100)
  m.candidate=dict(id=str(uuid.uuid4()),created_at=999,mode='automatic_off_on_off',proposal=propose([5]*100,[70]*100,[5]*100),applied=True)
  m.beam_check=dict(command_id=str(uuid.uuid4()),started_at=900,finished_at=920,status='completed',all_clear=True,configured_count=1,tested_count=1,outputs_off_confirmed=True,modules=[dict(module=1,pin='A0',state='clear',clear_above=48,**summarize([70]*100))])
  m.keypad_session=dict(status='ended',seen=list('0123456789*#'),last_key='#',press_count=12,started_at=800,ends_at=920,last_key_at=900)
  m.rfid_session=dict(status='ended',scans=20,last_scan_at=999,tag_responses=20,selection_failures=0,responses_at_start=80,failures_at_start=0)
  self.assertLess(len(json.dumps(m.live(c,1))),6000)
 def test_worker_lease_expires_and_eof_sends_zero(self):
  fake=Path(self.tmp.name)/'serial.py';log=Path(self.tmp.name)/'frames.jsonl'
  fake.write_text('''import json,os,time
EIGHTBITS=8
PARITY_NONE='N'
STOPBITS_TWO=2
SerialException=OSError
class Serial:
 def __init__(self,port,baudrate,**kw):
  assert baudrate==250000 and kw['stopbits']==2 and kw['exclusive'];self.break_condition=False
 def write(self,data):
  assert len(data)==513 and data[0]==0
  with open(os.environ['DMX_TEST_LOG'],'a') as f:f.write(json.dumps([time.monotonic(),data[10],data[11]])+'\\n')
  return len(data)
 def flush(self):pass
 def close(self):pass
''')
  env=dict(os.environ,PYTHONPATH=self.tmp.name,DMX_TEST_LOG=str(log))
  worker=Path(__file__).resolve().parents[1]/'hazer_dmx.py'
  p=subprocess.Popen([sys.executable,str(worker),'--worker',str(self.path)],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.PIPE,env=env)
  try:
   # First open deliberately starts at zero; send after initial adapter status.
   p.stdout.readline()
   p.stdin.write((json.dumps(dict(pump=16,fan=64,expires=time.monotonic()+.5,signal=True))+'\n').encode());p.stdin.flush()
   time.sleep(.8);p.stdin.close();p.stdin=None;out,err=p.communicate(timeout=3)
   self.assertEqual(p.returncode,0,err)
   rows=[json.loads(x) for x in log.read_text().splitlines()]
   self.assertTrue(any(r[1:]==[16,64] for r in rows));self.assertTrue(all(r[1:]==[0,0] for r in rows[-3:]))
   self.assertEqual(rows[-5][1:],[0,0])
  finally:
   if p.poll() is None:p.kill();p.wait()
