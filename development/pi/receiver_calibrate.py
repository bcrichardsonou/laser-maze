"""Interactive A0 light measurements; saves a proposal, never applies game thresholds."""
import argparse
import datetime
import fcntl
import json
from pathlib import Path
import signal
import statistics
import subprocess
import time
from game_reporting import atomic_json


def summarize(values):
    if len(values)<50 or any(type(v) is not int or not 0<=v<=1023 for v in values):
        raise ValueError('Need at least 50 valid 10-bit A0 readings')
    ordered=sorted(values)
    return dict(count=len(values),minimum=ordered[0],maximum=ordered[-1],median=statistics.median(ordered),
        p05=ordered[int((len(ordered)-1)*.05)],p95=ordered[int((len(ordered)-1)*.95)])


def propose(blocked,clear,check):
    b=summarize(blocked);c=summarize(clear);k=summarize(check)
    dark_high=max(b['p95'],k['p95']);light_low=c['p05'];gap=light_low-dark_high
    result=dict(blocked=b,clear=c,blocked_check=k,usable=False)
    if c['p95']>=1020:result['reason']='Receiver is near full scale; reduce/adjust light and recapture.'
    elif gap<20:result['reason']='Blocked and clear readings need more separation; check aim, wiring and ambient light.'
    else:
        result.update(usable=True,reason='Separated samples; thresholds are a proposal only.',
            proposed_break_threshold=dark_high+gap//3,proposed_clear_threshold=dark_high+2*gap//3)
    return result


def exchange(port,command,prefix):
    port.write((command+'\n').encode());port.flush()
    line=port.readline().decode('ascii',errors='replace').strip()
    if not line.startswith(prefix):raise RuntimeError('Unexpected controller response to '+command)
    return line


def capture(port):
    values=[]
    for i in range(100):
        line=exchange(port,'LIGHT','LIGHT A0 ')
        tail=line.removeprefix('LIGHT A0 ')
        if not tail.isdigit() or not 0<=int(tail)<=1023:raise RuntimeError('Invalid A0 reading')
        values.append(int(tail))
        if i%20==19:print('  A0:',values[-1],flush=True)
        time.sleep(.02)
    return values


def main():
    parser=argparse.ArgumentParser(description=__doc__);parser.parse_args()
    home=Path.home();state=home/'laser-maze/deployments'
    target=json.loads((state/'installed.json').read_text())
    if target.get('fqbn')!='arduino:avr:mega:cpu=atmega2560':raise RuntimeError('Calibration currently requires the Mega 2560')
    path=target.get('port','')
    if not path.startswith('/dev/serial/by-id/'):raise RuntimeError('Missing stable controller port')
    import serial
    def interrupted(signum,frame):raise KeyboardInterrupt
    signal.signal(signal.SIGTERM,interrupted)
    print('A0 receiver calibration. Gameplay pauses; the physical laser stays ON because no MOSFET is fitted.',flush=True)
    saved=None
    with (state/'upload.lock').open('a') as upload:
        fcntl.flock(upload,fcntl.LOCK_EX|fcntl.LOCK_NB)
        active=subprocess.check_output(['/usr/bin/systemctl','show','zoco-game.service','--property=ActiveState','--value'],text=True).strip()
        resume=active in ('active','activating','reloading')
        subprocess.run(['sudo','-n','/usr/bin/systemctl','stop','zoco-game.service'],check=True)
        try:
            with (state/'deploy.lock').open('a') as lock:
                fcntl.flock(lock,fcntl.LOCK_EX|fcntl.LOCK_NB)
                with serial.Serial(path,115200,timeout=2,write_timeout=2) as port:
                    try:
                        time.sleep(2);port.reset_input_buffer()
                        hello=exchange(port,'HELLO','HELLO 1 ')
                        if hello!='HELLO 1 '+target['firmware_version']:raise RuntimeError('Controller version mismatch')
                        if exchange(port,'STATUS','STATUS ')!='STATUS DISARMED OFF':raise RuntimeError('Controller must be disarmed')
                        readings={}
                        for phase,prompt in [('blocked','BLOCK the beam with an opaque card near the receiver.'),('clear','REMOVE the card so the laser hits the receiver.'),('blocked_check','BLOCK the beam again to check repeatability.')]:
                            input('\n'+prompt+' Press Enter when ready: ')
                            readings[phase]=capture(port)
                            summary=summarize(readings[phase]);print('  median {median}, range {minimum}–{maximum}'.format(**summary),flush=True)
                        proposal=propose(readings['blocked'],readings['clear'],readings['blocked_check'])
                        stamp=datetime.datetime.now(datetime.timezone.utc)
                        saved=home/'zoco-monitor/laser-maze/calibration'/('a0-'+stamp.strftime('%Y%m%dT%H%M%S%fZ')+'.json')
                        atomic_json(saved,dict(format=1,created_at=stamp.isoformat(),pin='A0',adc_max=1023,
                            firmware_version=target['firmware_version'],physical_laser='continuously_on_no_mosfet',
                            applied_to_game=False,readings=readings,proposal=proposal))
                        print('\nCalibration saved:',saved,flush=True)
                        print('RESULT:',json.dumps(proposal),flush=True)
                        print('These values have NOT been applied to gameplay.',flush=True)
                    finally:
                        try:port.write(b'OFF\n');port.flush()
                        except serial.SerialException:pass
        finally:
            if resume:
                subprocess.run(['sudo','-n','/usr/bin/systemctl','start','zoco-game.service'],check=True)
                print('Game service restarted; waiting for A.',flush=True)


if __name__=='__main__':
    try:main()
    except KeyboardInterrupt:print('\nCalibration cancelled.')
    except (OSError,ValueError,RuntimeError,subprocess.SubprocessError) as error:raise SystemExit('Calibration stopped: '+str(error))
