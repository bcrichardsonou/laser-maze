"""Authenticated command delivery; no serial access and no game-loop networking."""
import argparse
import json
import os
from pathlib import Path
import subprocess
import signal
import re
import time
import urllib.parse
import urllib.request
import urllib.error
from game_reporting import atomic_json
from maintenance import validate,ID


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self,*args,**kwargs):raise ValueError('redirect_rejected')


class Bridge:
    def __init__(self,config,folder):
        self.config=json.loads(Path(config).expanduser().read_text());self.folder=Path(folder).expanduser()
        self.identity=self.config['device_id'];self.next_permission_check=0;self.reboot_supported=False
        url=urllib.parse.urljoin(self.config['url'],'maintenance-api.php');parsed=urllib.parse.urlsplit(url)
        if parsed.scheme!='https' or parsed.username or parsed.password or parsed.fragment:raise ValueError('https_endpoint_required')
        self.url=url
        for name in ('inbox','results','outbox','acked','rejected'):(self.folder/name).mkdir(parents=True,exist_ok=True,mode=0o700)
        # Recovery of durable local results whose delivery was interrupted.
        for result in (self.folder/'results').glob('*.json'):
            if ID.fullmatch(result.stem) and not (self.folder/'acked'/result.name).exists() and not (self.folder/'rejected'/result.name).exists():
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
        if not ready:self.result(command,'failed','press_5_in_maintenance_first');return
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

    def grant(self,connected=True):
        try:
            state=json.loads((self.folder/'state.json').read_text())
            valid=state.get('enabled') is True and state.get('local_until',0)>time.time()
            if not connected:return valid
            path=Path.home()/'zoco-monitor/laser-maze/game-status.json';m=json.loads(path.read_text())['metrics']
            return valid and time.time()-path.stat().st_mtime<20 and m.get('maintenance_enabled') is True and m.get('maintenance_local_enabled') is True
        except (OSError,ValueError,KeyError):return False

    def health(self,started):
        path=Path.home()/'zoco-monitor/laser-maze/game-status.json'
        for _ in range(40):
            try:
                m=json.loads(path.read_text())['metrics']
                if path.stat().st_mtime>=started and m.get('arduino_connected') is True and m.get('maintenance_enabled') is True:return True
            except (OSError,ValueError,KeyError):pass
            time.sleep(.25)
        return False

    def service(self,command):
        action=command['action']
        if action!='service_start' and not self.grant():self.result(command,'failed','local_maintenance_enable_required');return
        try:
            started=time.time()
            verb='start' if action=='service_start' else 'stop'
            subprocess.run(['sudo','-n','/usr/bin/systemctl',verb,'zoco-game.service'],check=True,timeout=12,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
            if action=='service_start' and not self.health(started):self.result(command,'failed','service_health_unconfirmed');return
            self.result(command,'completed','game_service_started' if action=='service_start' else 'game_service_stopped')
        except (OSError,subprocess.SubprocessError):self.result(command,'failed','service_action_failed')

    def reboot(self,command):
        if not self.grant():self.result(command,'failed','local_maintenance_enable_required');return
        marker=self.folder/('reboot-'+command['id']+'.json')
        if marker.exists():
            if time.time()-json.loads(marker.read_text()).get('requested_at',0)>60:self.result(command,'failed','reboot_outcome_unconfirmed')
            return
        boot=Path('/proc/sys/kernel/random/boot_id').read_text().strip()
        atomic_json(marker,dict(command=command,boot_id=boot,requested_at=int(time.time())))
        try:subprocess.run(['sudo','-n','/usr/bin/systemctl','reboot','--no-block'],check=True,timeout=5,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL)
        except (OSError,subprocess.SubprocessError):self.result(command,'failed','reboot_permission_not_installed')
        # Completion is recorded after the boot ID changes, never on mere request.

    def recover_reboots(self):
        for marker in self.folder.glob('reboot-*.json'):
            try:
                record=json.loads(marker.read_text());command=record['command'];done=self.folder/'results'/(command['id']+'.json')
                if not done.exists() and Path('/proc/sys/kernel/random/boot_id').read_text().strip()!=record['boot_id']:
                    self.result(command,'completed','pi_reboot_confirmed_after_reconnect')
            except (OSError,ValueError,KeyError):pass

    def reinstall(self,command):
        if not self.grant():self.result(command,'failed','local_maintenance_enable_required');return
        marker=self.folder/('reinstall-'+command['id']+'.json')
        if marker.exists():self.result(command,'failed','reinstall_outcome_unconfirmed');return
        if command['expires_at']-time.time()<35:self.result(command,'failed','reinstall_request_too_old');return
        state=Path.home()/'laser-maze/deployments'
        try:
            installed=json.loads((state/'installed.json').read_text());version=installed['version']
            if not isinstance(version,str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]{0,63}',version):raise ValueError('release')
            if installed.get('fqbn')!='arduino:avr:mega:cpu=atmega2560' or not installed.get('port','').startswith('/dev/serial/by-id/'):raise ValueError('board')
            release=state/'releases'/version;manifest=json.loads((release/'manifest.json').read_text())
            if manifest['version']!=version or manifest['fqbn']!=installed['fqbn']:raise ValueError('manifest')
            atomic_json(marker,dict(started_at=int(time.time()),version=version))
            args=['/usr/bin/python3',str(Path.home()/'laser-maze/tools/deploy.py'),'deploy','--source',str(release/'source'),'--version',version,'--notes',manifest['notes'],'--board','mega','--port',installed['port']]
            process=subprocess.Popen(args,stdin=subprocess.DEVNULL,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,start_new_session=True)
            try:code=process.wait(timeout=min(50,max(1,command['expires_at']-time.time()-3)))
            except subprocess.TimeoutExpired:
                os.killpg(process.pid,signal.SIGTERM)
                try:process.wait(timeout=3)
                except subprocess.TimeoutExpired:os.killpg(process.pid,signal.SIGKILL);process.wait(timeout=3)
                self.result(command,'failed','reinstall_timed_out_inspect_controller');return
            if code:self.result(command,'failed','reinstall_failed_inspect_deployment_history');return
            self.result(command,'completed','current_release_reinstalled_versions_verified')
        except (OSError,ValueError,KeyError,subprocess.SubprocessError):self.result(command,'failed','reinstall_failed_inspect_controller')

    def telemetry(self):
        path=self.folder/'live.json'
        try:
            if path.stat().st_size>=6000:return None
            live=json.loads(path.read_text())
            if live.get('device_id')!=self.identity:return None
            fresh=time.time()-path.stat().st_mtime<6
            if not fresh:
                live['connected']=False;live.get('receiver',{})['raw']=None
                live['maintenance_local_enabled']=False
            status=subprocess.run(['/usr/bin/systemctl','is-active','zoco-game.service'],capture_output=True,text=True,timeout=2).stdout.strip()
            live['service_state']=status;live['sampled_at']=int(time.time())
            live['controller_sampled_at']=int(path.stat().st_mtime)
            live['service_grant']=self.grant(connected=False)
            if time.time()>=self.next_permission_check:
                self.next_permission_check=time.time()+60
                permission=subprocess.run(['sudo','-n','-ll','/usr/bin/systemctl','reboot','--no-block'],capture_output=True,text=True,timeout=2)
                self.reboot_supported=permission.returncode==0 and 'Options: !authenticate' in permission.stdout
            live['reboot_supported']=self.reboot_supported
            return live
        except (OSError,ValueError,subprocess.SubprocessError):return None

    def once(self):
        for path in list((self.folder/'outbox').glob('*.json'))[:20]:
            if not ID.fullmatch(path.stem):continue
            result=json.loads(path.read_text())
            try:reply=self.post(dict(action='ack',result=result))
            except urllib.error.HTTPError as error:
                if error.code not in (400,404,409,413):raise
                atomic_json(self.folder/'rejected'/path.name,dict(result=result,http_status=error.code,rejected_at=int(time.time())))
                error.close();path.unlink();print('Maintenance result rejected; retained locally. HTTP '+str(error.code),flush=True);continue
            if reply.get('acknowledged')!=result['id']:raise ValueError('acknowledgment_mismatch')
            atomic_json(self.folder/'acked'/path.name,dict(acknowledged_at=int(time.time())))
            path.unlink()
        self.recover_reboots()
        body=dict(action='poll');live=self.telemetry()
        if live:body['telemetry']=live
        reply=self.post(body)
        for command in reply.get('commands',[])[:10]:
            try:action,params=validate(command,self.identity,time.time())
            except (ValueError,KeyError,TypeError):continue
            done=self.folder/'results'/(command['id']+'.json')
            if done.exists():atomic_json(self.folder/'outbox'/done.name,json.loads(done.read_text()));continue
            if action=='restart_game':self.restart(command)
            elif action in ('service_start','service_stop'):self.service(command)
            elif action=='reboot_pi':self.reboot(command)
            elif action=='software_reinstall':self.reinstall(command)
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
