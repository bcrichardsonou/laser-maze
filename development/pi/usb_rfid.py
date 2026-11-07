"""ACR1552U PC/SC input isolated in a worker; never reads or logs card identity."""
import json
import os
from pathlib import Path
import subprocess
import sys
import time


def select_reader(names):
    candidates=[n for n in names if 'ACR1552' in n.upper() and 'SAM' not in n.upper() and ('PICC' in n.upper() or 'CL READER' in n.upper())]
    if len(candidates)!=1:raise ValueError('usb_reader_missing' if not candidates else 'multiple_usb_readers')
    return candidates[0]


class ScanLatch:
    def __init__(self):self.armed=False;self.previous=None
    def update(self,present):
        trigger=present and self.armed and self.previous is not True
        if not present:self.armed=True
        else:self.armed=False
        self.previous=present
        return trigger

class USBRFID:
    def __init__(self):
        self.process=None;self.buffer=bytearray();self.retry_at=0;self.last_packet=-100
        self.ready=False;self.present=None;self.error='usb_reader_starting'
        self.responses=0;self.failures=0;self.scans=0
    def start(self,now):
        self.close();self.ready=False;self.present=None;self.last_packet=now;self.buffer.clear()
        self.process=subprocess.Popen([sys.executable,str(Path(__file__).resolve()),'--worker'],stdout=subprocess.PIPE,stderr=subprocess.DEVNULL)
        os.set_blocking(self.process.stdout.fileno(),False)
    def restart(self,now):
        self.close();self.retry_at=now;self.ready=False;self.present=None;self.error='usb_reader_reconnecting'
    def close(self):
        if self.process:
            if self.process.poll() is None:
                self.process.terminate()
                try:self.process.wait(timeout=.2)
                except subprocess.TimeoutExpired:self.process.kill();self.process.wait(timeout=.2)
            self.process.stdout.close();self.process=None
    def accept(self,packet,now):
        if not isinstance(packet,dict) or set(packet)!={'ready','present','error','scan','failed','at'}:raise ValueError('invalid_usb_reader_packet')
        if any(type(packet[k]) is not bool for k in ('ready','scan','failed')) or packet['present'] not in (True,False,None) or not isinstance(packet['error'],str) or len(packet['error'])>80 or type(packet['at']) not in (int,float):raise ValueError('invalid_usb_reader_packet')
        age=now-packet['at']
        if not -.1<=age<2: return False
        self.last_packet=now;self.ready=packet['ready'];self.present=packet['present'];self.error=packet['error']
        if packet['failed']:self.responses+=1;self.failures+=1
        scanned=packet['scan'] and self.ready and age<.75
        if scanned:self.responses+=1;self.scans+=1
        return scanned
    def poll(self,now):
        scanned=0
        if self.process is None:
            if now<self.retry_at:return 0
            try:self.start(now)
            except OSError:self.error='usb_reader_worker_unavailable';self.retry_at=now+3;return 0
        if self.process.poll() is not None:
            self.close();self.ready=False;self.present=None;self.error='usb_reader_worker_stopped';self.retry_at=now+3;return 0
        try:
            data=os.read(self.process.stdout.fileno(),4096)
            self.buffer.extend(data)
            if len(self.buffer)>8192:raise ValueError('usb_reader_overflow')
            while b'\n' in self.buffer:
                raw,_,self.buffer=self.buffer.partition(b'\n')
                scanned+=int(self.accept(json.loads(raw),now))
        except BlockingIOError:pass
        except (OSError,ValueError,TypeError):
            self.restart(now);self.error='usb_reader_worker_fault';self.retry_at=now+3
        if now-self.last_packet>3:
            self.restart(now);self.error='usb_reader_unresponsive';self.retry_at=now+3
        return scanned
    def diagnostics(self):
        return dict(source='usb_pcsc',model='ACS ACR1552U',tag_responses=self.responses,selection_failures=self.failures,card_present=self.present,error=self.error)


def worker():
    def emit(ready=False,present=None,error='',scan=False,failed=False):
        print(json.dumps(dict(ready=ready,present=present,error=error,scan=scan,failed=failed,at=time.monotonic())),flush=True)
    try:from smartcard import scard as s
    except ImportError:
        emit(error='install_pcscd_libccid_python3_pyscard');return
    while True:
        context=None
        try:
            rc,context=s.SCardEstablishContext(s.SCARD_SCOPE_USER)
            if rc!=s.SCARD_S_SUCCESS:raise ValueError('pcsc_service_unavailable')
            name=None;state=s.SCARD_STATE_UNAWARE;latch=ScanLatch();previous=None;listed=0
            while True:
                now=time.monotonic()
                if now>=listed:
                    rc,names=s.SCardListReaders(context,[])
                    if rc!=s.SCARD_S_SUCCESS:raise ValueError('usb_reader_missing')
                    selected=select_reader(names);listed=now+1
                    if selected!=name:name=selected;state=s.SCARD_STATE_UNAWARE;latch=ScanLatch();previous=None
                rc,states=s.SCardGetStatusChange(context,100,[(name,state)])
                if rc==s.SCARD_E_TIMEOUT:
                    emit(True,previous);continue
                if rc!=s.SCARD_S_SUCCESS:raise ValueError('usb_reader_connection_lost')
                _,event,atr=states[0];state=event & ~s.SCARD_STATE_CHANGED
                if event & (s.SCARD_STATE_UNKNOWN|s.SCARD_STATE_UNAVAILABLE):raise ValueError('usb_reader_connection_lost')
                present=bool(event&s.SCARD_STATE_PRESENT);scan=False;failed=False;error=''
                if latch.update(present):
                    if event&s.SCARD_STATE_MUTE or not atr:failed=True;error='card_not_readable'
                    else:
                        rc,handle,protocol=s.SCardConnect(context,name,s.SCARD_SHARE_SHARED,s.SCARD_PROTOCOL_T0|s.SCARD_PROTOCOL_T1)
                        if rc==s.SCARD_S_SUCCESS:
                            s.SCardDisconnect(handle,s.SCARD_LEAVE_CARD);scan=True
                        else:failed=True;error='card_connection_failed'
                previous=present
                emit(True,present,error,scan,failed)
        except ValueError as e:emit(error=str(e))
        except Exception:emit(error='usb_reader_pcsc_fault')
        finally:
            if context is not None:
                try:s.SCardReleaseContext(context)
                except Exception:pass
        time.sleep(1)

if __name__=='__main__' and sys.argv[1:]==['--worker']:worker()
