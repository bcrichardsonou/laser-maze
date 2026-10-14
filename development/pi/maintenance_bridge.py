"""Authenticated command delivery; no serial access and no game-loop networking."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import time
import urllib.parse
import urllib.request
from game_reporting import atomic_json
from maintenance import validate,ID


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):raise ValueError('redirect_rejected')


class Bridge:
    def __init__(self,config,folder):
        self.config=json.loads(Path(config).expanduser().read_text());self.folder=Path(folder).expanduser()
        self.identity=self.config['device_id']
        url=urllib.parse.urljoin(self.config['url'],'maintenance-api.php');parsed=urllib.parse.urlsplit(url)
        if parsed.scheme!='https' or parsed.username or parsed.password or parsed.fragment:raise ValueError('https_endpoint_required')
        self.url=url
        for name in ('inbox','results','outbox','acked'):(self.folder/name).mkdir(parents=True,exist_ok=True,mode=0o700)
        # Recovery of durable local results whose delivery was interrupted.
        for result in (self.folder/'results').glob('*.json'):
            if ID.fullmatch(result.stem) and not (self.folder/'acked'/result.name).exists():
                atomic_json(self.folder/'outbox'/result.name,json.loads(result.read_text()))

    def post(self,body):
        request=urllib.request.Request(self.url,json.dumps(dict(body,device_id=self.identity)).encode(),
            {'Content-Type':'application/json','X-ZoCo-Key':self.config['upload_key']})
        with urllib.request.build_opener(NoRedirect).open(request,timeout=5) as response:
            data=json.loads(response.read(65537))
        if not isinstance(data,dict):raise ValueError('invalid_response')
        return data

    def result(self,command,status,reason):
        value=dict(id=command['id'],device_id=self.identity,status=status,reason=reason,
            executed_at=int(time.time()),snapshot={})
        atomic_json(self.folder/'results'/(command['id']+'.json'),value)
        atomic_json(self.folder/'outbox'/(command['id']+'.json'),value)

    def restart(self,command):
        # A crash during restart must never automatically repeat the operation.
        marker=self.folder/('restart-'+command['id']+'.json')
        if marker.exists():self.result(command,'failed','restart_outcome_unconfirmed');return
        path=Path.home()/'zoco-monitor/laser-maze/game-status.json'
        try:
            m=json.loads(path.read_text())['metrics']
            state=json.loads((self.folder/'state.json').read_text())
            ready=time.time()-path.stat().st_mtime<20 and m.get('maintenance_enabled') is True and m.get('maintenance_local_enabled') is True and state.get('local_until',0)>time.time()
        except (OSError,ValueError,KeyError):ready=False
        if not ready:self.result(command,'failed','press_C_in_maintenance_first');return
        atomic_json(marker,dict(started_at=int(time.time())))
        try:
            subprocess.run(['sudo','-n','/usr/bin/systemctl','stop','zoco-game.service'],check=True,timeout=12,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
            subprocess.run(['sudo','-n','/usr/bin/systemctl','start','zoco-game.service'],check=True,timeout=12,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
            started=time.time()
            for _ in range(40):
                try:
                    status=json.loads(path.read_text())['metrics']
                    if path.stat().st_mtime>=started and status.get('arduino_connected') is True and status.get('maintenance_enabled') is True:
                        self.result(command,'completed','game_restarted_in_maintenance');return
                except (OSError,ValueError,KeyError):pass
                time.sleep(.25)
            self.result(command,'failed','restart_health_unconfirmed')
        except (OSError,subprocess.SubprocessError):self.result(command,'failed','restart_failed_inspect_service')

    def once(self):
        for path in list((self.folder/'outbox').glob('*.json'))[:20]:
            if not ID.fullmatch(path.stem):continue
            result=json.loads(path.read_text());reply=self.post(dict(action='ack',result=result))
            if reply.get('acknowledged')!=result['id']:raise ValueError('acknowledgment_mismatch')
            atomic_json(self.folder/'acked'/path.name,dict(acknowledged_at=int(time.time())))
            path.unlink()
        reply=self.post(dict(action='poll'))
        for command in reply.get('commands',[])[:10]:
            try:action,params=validate(command,self.identity,time.time())
            except (ValueError,KeyError,TypeError):continue
            done=self.folder/'results'/(command['id']+'.json')
            if done.exists():atomic_json(self.folder/'outbox'/done.name,json.loads(done.read_text()));continue
            if action=='restart_game':self.restart(command)
            else:atomic_json(self.folder/'inbox'/(command['id']+'.json'),command)


def main():
    os.umask(0o077)
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--config',default='~/zoco-monitor/device-config.json')
    parser.add_argument('--folder',default='~/zoco-monitor/laser-maze/control')
    parser.add_argument('--once',action='store_true')
    args=parser.parse_args();bridge=Bridge(args.config,args.folder)
    previous=''
    while True:
        try:
            bridge.once()
            if previous:print('Maintenance command delivery restored.',flush=True)
            previous=''
        except (OSError,ValueError,KeyError) as error:
            name=type(error).__name__
            if name!=previous:print('Maintenance delivery unavailable: '+name,flush=True)
            previous=name
        if args.once:
            if previous:parser.exit(1,'Maintenance delivery did not complete.\n')
            break
        time.sleep(2)


if __name__=='__main__':main()
