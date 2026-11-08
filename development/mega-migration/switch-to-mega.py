#!/usr/bin/env python3
"""Finish the staged Mega migration. Run with sudo after transferring the panel wiring."""
import datetime
import fcntl
import hashlib
import json
import os
from pathlib import Path
import pwd
import re
import shutil
import subprocess
import sys
import time

HOME = Path('/home/brent')
STATE = HOME/'laser-maze/deployments'
MEGA = '/dev/serial/by-id/usb-Arduino__www.arduino.cc__0042_EXAMPLE_MEGA_SERIAL-if00'
DROPIN = Path('/etc/systemd/system/zoco-game.service.d/controller-mega.conf')

def systemctl(*args):subprocess.run(['/usr/bin/systemctl',*args],check=True)

def atomic(path,data,mode=0o600,brent=False):
    temp=path.with_name(path.name+'.mega-next')
    with temp.open('w') as out:
        out.write(data);out.flush();os.fsync(out.fileno())
    os.chmod(temp,mode)
    if brent:
        account=pwd.getpwnam('brent');os.chown(temp,account.pw_uid,account.pw_gid)
    os.replace(temp,path)

def main():
    if os.geteuid()!=0:raise RuntimeError('Run with sudo so the service can be updated.')
    target=json.loads((STATE/'staged-controller.json').read_text())
    version=target.get('version','')
    if not isinstance(version,str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._-]{0,63}',version):raise RuntimeError('No verified staged release.')
    if target.get('port')!=MEGA or target.get('fqbn')!='arduino:avr:mega:cpu=atmega2560':raise RuntimeError('Staged controller is not the expected Mega.')
    release=STATE/'releases'/version
    manifest=json.loads((release/'manifest.json').read_text())
    if manifest.get('fqbn')!=target['fqbn'] or manifest.get('firmware_version')!=target['firmware_version']:raise RuntimeError('Staged manifest mismatch.')
    for name,checksum in manifest['files'].items():
        if '..' in name or not re.fullmatch(r'(source|compiled)/[A-Za-z0-9_./-]+',name):raise RuntimeError('Invalid staged path.')
        path=release/name
        if path.is_symlink() or hashlib.sha256(path.read_bytes()).hexdigest()!=checksum:raise RuntimeError('Staged file changed.')
    if not Path(MEGA).exists():raise RuntimeError('Connect the Mega USB cable to the Pi.')
    if not (STATE/'current').is_symlink():raise RuntimeError('Expected existing current release symlink.')
    backup=STATE/('mega-switch-backup-'+datetime.datetime.now().strftime('%Y%m%d-%H%M%S'))
    backup.mkdir(mode=0o700)
    shutil.copy2(STATE/'installed.json',backup/'installed.json')
    (backup/'previous-current.txt').write_text(str((STATE/'current').resolve())+'\n')
    if DROPIN.exists():shutil.copy2(DROPIN,backup/DROPIN.name)
    (backup/'service-before.txt').write_text(subprocess.check_output(['/usr/bin/systemctl','cat','zoco-game'],text=True))
    print('Previous service and deployment information saved:',backup,flush=True)
    # Exclude uploads for the whole switch, and release the serial-owner lock before start.
    with (STATE/'upload.lock').open('a') as upload:
        fcntl.flock(upload,fcntl.LOCK_EX|fcntl.LOCK_NB)
        systemctl('stop','zoco-game')
        try:
            with (STATE/'deploy.lock').open('a') as controller:
                fcntl.flock(controller,fcntl.LOCK_EX|fcntl.LOCK_NB)
                import serial
                with serial.Serial(MEGA,115200,timeout=2,write_timeout=2) as port:
                    time.sleep(2);port.reset_input_buffer()
                    def exchange(command,expected):
                        port.write((command+'\n').encode());port.flush()
                        actual=port.readline().decode('ascii',errors='replace').strip()
                        if actual!=expected:raise RuntimeError('Mega check failed: '+command+'. Check transferred panel wiring. Service remains stopped.')
                    exchange('HELLO','HELLO 1 '+target['firmware_version'])
                    exchange('STATUS','STATUS DISARMED OFF')
                    exchange('KEYPAD','KEYPAD READY')
                    exchange('OFF','OK OFF')
                DROPIN.parent.mkdir(parents=True,exist_ok=True)
                atomic(DROPIN,'[Service]\nExecStart=\nExecStart=/usr/bin/python3 -u /home/brent/laser-maze/deployments/current/panel_game.py '+MEGA+'\n',0o644)
                temp=STATE/'.mega-current-next'
                if temp.is_symlink():temp.unlink()
                temp.symlink_to(release/'source/pi')
                os.replace(temp,STATE/'current')
            systemctl('daemon-reload')
            started=time.time();systemctl('start','zoco-game')
            status_path=HOME/'zoco-monitor/laser-maze/game-status.json'
            for _ in range(60):
                try:
                    data=json.loads(status_path.read_text());metrics=data['metrics']
                    if status_path.stat().st_mtime>=started and metrics.get('arduino_connected') is True and metrics.get('firmware_version')==target['firmware_version'] and data.get('state') not in ('faulted','fault'):
                        atomic(STATE/'installed.json',json.dumps(target,indent=2)+'\n',brent=True)
                        print('Mega game service connected. Physical panel, audio, maintenance and reboot checks are still required.',flush=True)
                        systemctl('status','zoco-game','--no-pager','-l')
                        return
                except (OSError,ValueError,KeyError):pass
                time.sleep(.5)
            raise RuntimeError('Mega game startup not confirmed. Inspect game logs and panel wiring.')
        except BaseException:
            systemctl('stop','zoco-game')
            atomic(STATE/'installed.json',json.dumps(dict(state='unconfirmed',version=None,reason='mega_service_switch',backup=str(backup)),indent=2)+'\n',brent=True)
            print('Switch incomplete; game service is stopped. Backups are retained at '+str(backup),file=sys.stderr)
            raise

if __name__=='__main__':
    try:main()
    except Exception as error:sys.exit(str(error))
