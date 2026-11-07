"""Raw FTDI DMX output in a separate process; UNIQUE 2.1 has pump + fan slots."""
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import uuid

DEFAULTS=dict(address=10,automatic=False,pump=16,fan=64,burst_seconds=11)

def validate_settings(p):
    if not isinstance(p,dict) or set(p)!=set(DEFAULTS):raise ValueError('invalid_hazer_settings')
    for k,lo,hi in (('address',1,511),('pump',0,255),('fan',0,255),('burst_seconds',1,30)):
        if type(p[k]) is not int or not lo<=p[k]<=hi:raise ValueError('invalid_hazer_'+k)
    if type(p['automatic']) is not bool:raise ValueError('invalid_hazer_automatic')
    return dict(p)

def frame(address,pump,fan):
    if type(address) is not int or not 1<=address<=511 or any(type(x) is not int or not 0<=x<=255 for x in (pump,fan)):raise ValueError('invalid_dmx_frame')
    data=bytearray(513);data[address]=pump;data[address+1]=fan
    return bytes(data)

class Hazer:
    def __init__(self,config):
        self.path=Path(config);self.port=None;self.settings=dict(DEFAULTS);self.configured=False
        self.error='dmx_not_configured';self.connected=False;self.frames=0;self.pump=self.fan=0;self.streaming=False
        self.process=None;self.buffer=bytearray();self.retry_at=0;self.last_status=-100;self.next_send=0
        self.game=None;self.game_session=None;self.started=0;self.blocked=None;self.session=None;self.signal_enabled=True
        try:
            p=json.loads(self.path.read_text());self.settings=validate_settings(p['settings']);self.port=p['port']
            if not isinstance(self.port,str) or not self.port.startswith('/dev/serial/by-id/usb-FTDI_') or '/' in self.port.removeprefix('/dev/serial/by-id/'):raise ValueError()
            self.configured=True;self.error='dmx_starting'
        except (OSError,ValueError,KeyError,TypeError):pass
    def save(self,settings):
        from game_reporting import atomic_json
        value=validate_settings(settings)
        if not self.configured:raise ValueError('dmx_not_configured')
        self.close();self.settings=value
        atomic_json(self.path,dict(port=self.port,settings=value));self.retry_at=0;self.signal_enabled=True
    def stop(self):
        value=dict(self.settings,automatic=False)
        if self.configured:
            from game_reporting import atomic_json
            atomic_json(self.path,dict(port=self.port,settings=value));self.settings=value
        self.blocked=self.session;self.next_send=0
    def close(self):
        if self.process:
            try:self.process.stdin.close()
            except OSError:pass
            try:self.process.wait(timeout=.2)
            except subprocess.TimeoutExpired:self.process.kill();self.process.wait(timeout=.2)
            self.process.stdout.close();self.process=None
        self.connected=False;self.streaming=False;self.pump=self.fan=0
    def _start(self,now):
        self.process=subprocess.Popen([sys.executable,str(Path(__file__).resolve()),'--worker',str(self.path)],stdin=subprocess.PIPE,stdout=subprocess.PIPE,stderr=subprocess.DEVNULL,bufsize=0)
        os.set_blocking(self.process.stdin.fileno(),False);os.set_blocking(self.process.stdout.fileno(),False)
        self.buffer.clear();self.last_status=now;self.next_send=0
    def poll(self,now):
        if not self.configured:return
        previous=self.connected
        if self.process is None and now>=self.retry_at:
            try:self._start(now)
            except OSError:self.error='dmx_worker_unavailable';self.retry_at=now+3;return
        if self.process is None:return
        if self.process.poll() is not None:
            self.close();self.error='dmx_worker_stopped';self.retry_at=now+3
        else:
            try:
                self.buffer.extend(os.read(self.process.stdout.fileno(),4096))
                if len(self.buffer)>8192:raise ValueError()
                while b'\n' in self.buffer:
                    raw,_,self.buffer=self.buffer.partition(b'\n');p=json.loads(raw)
                    if set(p)!={'connected','streaming','frames','pump','fan','error','at'} or any(type(p[k]) is not bool for k in ('connected','streaming')) or any(type(p[k]) is not int or p[k]<0 for k in ('frames','pump','fan')) or p['pump']>255 or p['fan']>255 or not isinstance(p['error'],str) or len(p['error'])>80:raise ValueError()
                    if -.1<=now-p['at']<2:
                        self.last_status=now;self.connected=p['connected'];self.streaming=p['streaming'];self.frames=p['frames'];self.pump=p['pump'];self.fan=p['fan'];self.error=p['error']
            except BlockingIOError:pass
            except (OSError,ValueError,TypeError,KeyError):self.close();self.error='dmx_worker_fault';self.retry_at=now+3
            if self.process and now-self.last_status>3:self.close();self.error='dmx_worker_unresponsive';self.retry_at=now+3
        if previous and not self.connected:self.blocked=self.session
    def targets(self,controls,maintenance,now):
        game=controls.game
        if game is not self.game:
            self.game=game;self.game_session=str(uuid.uuid4()) if game else None;self.started=now
            if game and not self.connected:self.blocked=self.game_session
        test=maintenance.test
        if maintenance.enabled or maintenance.pending:
            if maintenance.local_enabled() and test and test['kind']=='hazer' and now<test['until']:
                session=test['command']['id'];pump=test['pump'];fan=test['fan']
            else:session=None;pump=fan=0
        elif game and self.settings['automatic'] and now-self.started<self.settings['burst_seconds']:
            session=self.game_session;pump=self.settings['pump'];fan=self.settings['fan']
        else:session=None;pump=fan=0
        self.session=session
        return (0,0) if session is not None and session==self.blocked else (pump,fan)
    def update(self,controls,maintenance,now):
        self.poll(now);pump,fan=self.targets(controls,maintenance,now)
        if self.process and now>=self.next_send:
            packet=dict(pump=pump,fan=fan,expires=now+.7,signal=self.signal_enabled)
            try:
                data=(json.dumps(packet)+'\n').encode()
                if os.write(self.process.stdin.fileno(),data)!=len(data):raise OSError()
                self.next_send=now+.2
            except (OSError,BlockingIOError):
                self.blocked=self.session;self.close();self.error='dmx_command_unconfirmed';self.retry_at=now+3
    def status(self):
        return dict(configured=self.configured,adapter_connected=self.connected,transmitting=self.streaming,frames_this_worker=self.frames,pump_command=self.pump,fan_command=self.fan,error=self.error,settings=self.settings,signal_enabled=self.signal_enabled,physical_feedback=False)


def worker(path):
    import serial
    p=json.loads(Path(path).read_text());settings=validate_settings(p['settings']);address=settings['address'];port_path=p['port']
    os.set_blocking(sys.stdin.fileno(),False)
    port=None;buffer=bytearray();pump=fan=0;expires=0;signal_enabled=True;frames=0;next_status=0;next_open=0;stopping=False
    def transmit(data):
        port.break_condition=True;time.sleep(.0002);port.break_condition=False;time.sleep(.00002)
        if port.write(data)!=len(data):raise OSError('partial_dmx_frame')
        port.flush()
    try:
        while not stopping:
            begin=time.monotonic();error=''
            try:
                chunk=os.read(sys.stdin.fileno(),4096)
                if not chunk:break
                buffer.extend(chunk)
                if len(buffer)>8192:raise ValueError()
                while b'\n' in buffer:
                    raw,_,buffer=buffer.partition(b'\n');cmd=json.loads(raw)
                    if set(cmd)!={'pump','fan','expires','signal'} or type(cmd['signal']) is not bool or any(type(cmd[k]) is not int or not 0<=cmd[k]<=255 for k in ('pump','fan')) or type(cmd['expires']) not in (int,float) or not begin-1<=cmd['expires']<=begin+1:raise ValueError()
                    pump=cmd['pump'];fan=cmd['fan'];expires=cmd['expires'];signal_enabled=cmd['signal']
            except BlockingIOError:pass
            except (OSError,ValueError,TypeError):pump=fan=0;expires=0;stopping=True
            if begin>=expires:pump=fan=0
            if port is None and begin>=next_open:
                try:
                    port=serial.Serial(port_path,250000,bytesize=serial.EIGHTBITS,parity=serial.PARITY_NONE,stopbits=serial.STOPBITS_TWO,timeout=0,write_timeout=.15,exclusive=True)
                    port.break_condition=False;pump=fan=0;expires=0
                except (OSError,serial.SerialException):port=None;next_open=begin+1;error='dmx_adapter_unavailable'
            if port and signal_enabled:
                try:transmit(frame(address,pump,fan));frames+=1
                except (OSError,serial.SerialException):
                    port.close();port=None;pump=fan=0;expires=0;next_open=begin+1;error='dmx_transmit_failed'
            if not port and not error:error='dmx_adapter_unavailable'
            if begin>=next_status:
                print(json.dumps(dict(connected=port is not None,streaming=port is not None and signal_enabled,frames=frames,pump=pump,fan=fan,error=error,at=time.monotonic())),flush=True);next_status=begin+.25
            time.sleep(max(0,.033-(time.monotonic()-begin)))
    finally:
        if port:
            try:
                for _ in range(3):transmit(frame(address,0,0))
            except (OSError,serial.SerialException):pass
            port.close()

if __name__=='__main__' and len(sys.argv)==3 and sys.argv[1]=='--worker':worker(sys.argv[2])
