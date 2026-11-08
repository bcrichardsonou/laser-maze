from pathlib import Path
import hashlib,sqlite3,json,importlib.util,os,tempfile,time,stat
home=Path.home();target=home/'zoco-monitor/zoco_agent.py';stage=Path(__file__).resolve().parent
expected='f0e3716bc7612cfc0f50146b004840c7339b921d72d9ad717eb614ed385b984a'
if hashlib.sha256(target.read_bytes()).hexdigest()!=expected:raise SystemExit('Agent changed; no modification made')
spec=importlib.util.spec_from_file_location('compat',stage/'zoco_agent.py');m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
p=home/'zoco-logs/events.sqlite3';db=sqlite3.connect(f'file:{p}?mode=ro',uri=True)
count=0
for kind,raw in db.execute('SELECT kind,payload FROM events WHERE sent=0'):
 payload=m.transport_payload(kind,json.loads(raw))
 if kind in ('heartbeat','status') and len(payload.get('metrics',{}))>40:raise SystemExit('Invalid projected metrics')
 if len(json.dumps(payload).encode())>8192:raise SystemExit('Invalid projected payload size')
 count+=1
backup=home/'zoco-monitor/backups'/('reporting-compat-'+time.strftime('%Y%m%d-%H%M%S'));backup.mkdir(parents=True,mode=0o700)
(backup/'zoco_agent.py').write_bytes(target.read_bytes());os.chmod(backup/'zoco_agent.py',0o600)
out=sqlite3.connect(backup/'events.sqlite3');db.backup(out);out.close();db.close();os.chmod(backup/'events.sqlite3',0o600)
source=(stage/'zoco_agent.py').read_bytes();compile(source,str(target),'exec')
fd,temp=tempfile.mkstemp(dir=target.parent,prefix='.agent-compat-')
with os.fdopen(fd,'wb') as f:f.write(source);f.flush();os.fsync(f.fileno())
os.chmod(temp,stat.S_IMODE(target.stat().st_mode));os.replace(temp,target)
print('Agent compatibility installed. Pending records validated:',count,'Private source/queue backup:',backup)
