"""Physical-panel two-beam game with RC522 + mission-code authorization."""
import argparse
from collections import deque
import fcntl
import math
import json
import signal
from pathlib import Path
import time
from game_engine import Game, Settings, MODES
from entry_authorization import Entry
from usb_objective import USBObjective

def reader_reply(line):
    words=line.split()
    if len(words) not in (7,8) or words[0]!="RFID" or words[1] not in ("READY","MISSING") or any(not v.isdigit() for v in words[2:]):raise RuntimeError("Invalid RFID health reply")
    values=list(map(int,words[2:]))
    if any(v>4294967295 for v in values[:2]) or any(v>255 for v in values[2:]):raise RuntimeError("Invalid RFID diagnostics range")
    return words[1]=="READY",dict(zip(("tag_responses","selection_failures","last_request_status","last_selection_status","receive_gain_register","version_register"),values))


VERSION = "bench-0.23.0"


class Controls:
    def __init__(self, fast=False, reporting=None, rfid_entry=False, physical_single=False):
        self.physical_single=physical_single
        self.rfid_entry = rfid_entry
        self.entry = Entry()
        self.reader_ready = False
        self.reader_diagnostics = {}
        self.last_scan_at = None
        self.scan_count = 0
        self.reporting = reporting
        self.fast = fast
        self.admission = 0 if fast else 5
        self.result_red_at = 0
        self.settings = Settings(beam_count=2, startup=2, duration=30, cooldown=2, warmup=1) if fast else Settings(beam_count=2)
        if self.physical_single:
            from dataclasses import replace
            self.settings=replace(self.settings,enabled_beams=(True,False))
        self.levels = [False, False, False]
        self.usb_present=None;self.usb_armed=False
        self.mode = MODES[0]
        self.game = None
        self.result = None
        self.last_enabled = None
        self.play_locked = False
        self.allowed_modes = list(MODES)

    def configure(self, value):
        from operator_settings import validate_settings
        value=validate_settings(value)
        self.settings=Settings(beam_count=2,enabled_beams=(True,False) if self.physical_single else tuple(value['enabled_beams']),**{k:value[k] for k in ('duration','startup','cooldown','warmup','max_breaks')})
        self.allowed_modes=list(value['available_modes'])
        if self.mode not in self.allowed_modes:self.mode=self.allowed_modes[0]

    def inputs(self, levels, now):
        self.levels = [*levels[:2],self.usb_present is True]
        if self.game:
            self.game.broken = list(levels[:2])
            self.game.tick(now)


    def usb_update(self,present,now,allow_objective=True):
        self.tick(now)
        previous=self.usb_present;self.usb_present=present;self.levels[2]=present is True
        if not allow_objective or not self.game or self.game.state!='running' or not self.mode.startswith('usb'):
            self.usb_armed=False
        elif present is False:self.usb_armed=True
        elif present is None:self.usb_armed=False
        elif previous is False and self.usb_armed:
            self.game.objective_usb(now);self.usb_armed=False

    def entry_idle(self, now):
        return not self.game and not self.play_locked and not (self.result and now < self.result_red_at)

    def start(self, now):
        if not self.entry_idle(now):
            self.entry.reset('entry_locked')
            return
        self.usb_armed=False
        self.game = Game(self.mode, self.settings, powered_startup=True, admission=self.admission)
        self.game.broken = list(self.levels[:2])
        self.game.start(now)
        if self.reporting: self.reporting.begin(self.game, now)
        self.result = None
        self.entry.reset('game_in_progress')

    def swipe(self, now):
        self.tick(now)
        self.last_scan_at = now
        self.scan_count += 1
        if not self.rfid_entry or not self.reader_ready or not self.entry_idle(now):
            self.entry.reset('entry_locked')
            return
        mode = self.entry.swipe(now, self.allowed_modes)
        if mode:
            self.mode = mode
            self.start(now)

    def key(self, key, now):
        self.tick(now)
        if key == 'D':
            self.entry.reset('entry_cancelled')
            if self.game: self.game.finish('stopped')
            else: self.result = None
            return
        if self.game:
            if key in '1234': self.game.key(int(key), now)
            return
        if self.rfid_entry:
            if not self.entry_idle(now) or not self.reader_ready:
                self.entry.reset('reader_unavailable' if not self.reader_ready else 'entry_locked')
                return
            mode = self.entry.key(key, now, self.allowed_modes)
            if mode:
                self.mode = mode
                self.start(now)
            return
        # Explicit standalone bench/test Controls retain manual mode selection.
        if key in '1234':
            selected = MODES[int(key)-1]
            if selected in self.allowed_modes:
                self.mode = selected
                self.result = None
        elif key == 'A':
            self.start(now)

    def tick(self, now):
        self.entry.tick(now)
        if self.play_locked: self.entry.reset("entry_locked")
        if self.game:
            self.game.tick(now)
            if self.game.state in ("finished", "fault"):
                if self.reporting: self.reporting.finish(self.game, now)
                self.last_enabled = list(self.game.enabled)
                self.result = (self.game.outcome, self.game.breaks)
                self.result_red_at = now + (0 if self.fast else 10 if self.game.outcome == "win" else 5 if self.game.outcome in ("timeout", "beam_limit") else 0)
                self.game = None

    def doors(self):
        # Exit releases on every terminal outcome. Entry remains locked at rest,
        # opens only during admission; no door-closed feedback is fitted yet.
        if not self.game:return (True,False)
        return (self.game.state!='admitting',self.game.state in ('starting','admitting','running'))

    def display(self, now):
        if not self.game:
            # Completion/exit delay keeps the occupied indication; beam feedback belongs to modules.
            color = "BLUE" if self.result and now < self.result_red_at else "RED"
            if self.rfid_entry and self.reader_ready and self.entry_idle(now) and self.entry.scanned and self.entry.deadline is not None and now < self.entry.deadline:
                color = "PURPLE"
            return (False, False, 0, color)
        game = self.game
        outputs = game.outputs(now)
        color = "YELLOW" if game.state == "starting" else "GREEN" if game.state == "admitting" else "BLUE"
        countdown = math.ceil(game.remaining(now)) if game.state == "running" else 0
        return (*outputs, countdown, color)



class StatusFrames:
    """Send LED frames with an empty serial pipeline; defer writes until ACK."""
    def __init__(self,port,replies,clock=time.monotonic):
        self.port=port;self.replies=replies;self.clock=clock;self.waiting=False
        self.deferred=deque();self.until=0;self.next_frame=0
    def send(self,text,expected,callback=None):
        if self.waiting:self.deferred.append((text,expected,callback));return
        self.port.write((text+'\n').encode());self.port.flush()
        self.replies.append((expected,self.clock()+1,callback))
        if text.startswith('RGB '):self.until=0 if text=='RGB OFF' else self.clock()+1.4
    def finished(self):
        self.waiting=False
        while self.deferred:self.send(*self.deferred.popleft())
    def tick(self,now):
        if self.waiting or self.replies or self.deferred or now>=self.until or now<self.next_frame:return
        self.next_frame=now+.02;self.waiting=True
        self.port.write(b'FRAME\n');self.port.flush()
        self.replies.append(('OK FRAME',self.clock()+1,self.finished))


class StaffKeys:
    """Release-aware staff controls; no extra firmware queries or serial traffic."""
    def __init__(self,maintenance,controls):
        self.maintenance=maintenance;self.controls=controls;self.held=None;self.since=0;self.fired=False;self.suppressed=False
    def key(self,key,now):
        if key!=self.held:self.held=key;self.since=now;self.fired=False
        self.maintenance.staff_hold_seconds=0
        if key is None:self.suppressed=False;return
        m=self.maintenance;m.last_key=key;m.last_key_at=m.wall()
        if m.keypad_active():
            self.suppressed=True;m.keypad_key(key);return
        if self.suppressed:return
        if m.enabled or m.pending:self.controls.entry.reset('maintenance')
        if not m.local_key(key,self.controls):self.controls.key(key,now)
    def tick(self,now):
        m=self.maintenance
        if m.keypad_active():
            self.suppressed=self.held is not None;m.staff_hold_seconds=0;return
        if self.suppressed:m.staff_hold_seconds=0;return
        elapsed=max(0,now-self.since) if self.held=='0' and not self.fired else 0
        m.staff_hold_seconds=min(10,int(elapsed))
        if elapsed>=10:
            m.local_key('D',self.controls)  # Cancel tests, pending confirmation and sound.
            m.local_key('B',self.controls)  # Clear maintenance and its local enable.
            self.controls.key('D',now)     # Stop gameplay and clear mission entry.
            self.controls.tick(now);self.controls.result=None;self.controls.result_red_at=now
            self.fired=True;m.staff_hold_seconds=0;m.last_key='0 held: stopped';m.last_key_at=m.wall();m.next_live=0
            print('Held 0: game/tests/audio stopped; maintenance exited. Release 0 before entering a code.',flush=True)
    def countdown(self,now):
        if not self.maintenance.keypad_active() and not self.suppressed and self.held=='0' and not self.fired and now-self.since>=1:return max(0,10-int(now-self.since))
        return None


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", action="version", version=VERSION)
    parser.add_argument("port")
    parser.add_argument("--fast", action="store_true")
    args = parser.parse_args()
    # systemd stop must use the same OFF/report cleanup as Ctrl-C.
    def stop_requested(signum, frame):
        raise KeyboardInterrupt
    signal.signal(signal.SIGTERM, stop_requested)
    import serial
    directory = Path.home() / "laser-maze/deployments"
    directory.mkdir(parents=True, exist_ok=True, mode=0o700)
    lock = (directory / "deploy.lock").open("a")
    try: fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except BlockingIOError:
        lock.close()
        parser.exit(1, "Stop other controller tests first.\n")
    from game_reporting import Reporting
    reporting = Reporting(Path.home() / "zoco-monitor/laser-maze", VERSION, args.fast)
    controls = Controls(args.fast, reporting, rfid_entry=True, physical_single=True)
    from game_audio import Audio, GameSounds
    audio = Audio()
    effects = Audio()
    sounds = GameSounds(audio, effects)
    from maintenance import Maintenance
    try:
        identity=json.loads((Path.home()/'zoco-monitor/device-config.json').read_text())['device_id']
    except (OSError,ValueError,KeyError):identity=''
    maintenance=Maintenance(Path.home()/'zoco-monitor/laser-maze/control',identity,audio,effects)
    maintenance.configure_controls(controls)
    usb_input=USBObjective(maintenance.folder/'usb-port.json')
    def audio_metrics():
        return dict(audio.metrics(), audio_effects_error=effects.error or 'none',
            audio_effect_last_cue_requested=effects.last_cue)
    connected = False
    reported_fault = ""
    try:
        connection = serial.Serial(args.port, 115200, timeout=2, write_timeout=1)
    except (OSError, serial.SerialException):
        reporting.status(controls, (False, False, 0, "OFF"), time.monotonic(),
            connected=False, fault="arduino_open_failed", audio=audio_metrics(),maintenance=maintenance.metrics())
        lock.close()
        parser.exit(1, "Cannot open Arduino. Fault saved locally.\n")
    with lock, connection as port:
        def initial(text, expected):
            port.write((text + "\n").encode()); port.flush()
            reply = port.readline().decode("ascii", errors="replace").strip()
            if reply != expected: raise RuntimeError(f"{text}: {reply}")
        replies = deque()
        status_frames=StatusFrames(port,replies)
        send=status_frames.send
        try:
            time.sleep(2); port.reset_input_buffer()
            initial("HELLO", "HELLO 1 bench-0.23.0")
            initial("KEYPAD", "KEYPAD READY")
            initial("CAL {break_below} {clear_above}".format(**maintenance.thresholds),"OK CAL {break_below} {clear_above}".format(**maintenance.thresholds))
            # Initialize all levels BEFORE enabling event subscription.
            port.write(b"INPUTS\n"); port.flush()
            row = port.readline().decode().strip().split()
            if len(row) != 4 or row[0] != "INPUTS" or any(v not in ("0", "1") for v in row[1:]):
                raise RuntimeError("Invalid initial inputs")
            controls.inputs([v == "1" for v in row[1:]], time.monotonic())
            port.write(b"RFID\n"); port.flush()
            reader = port.readline().decode("ascii", errors="replace").strip()
            controls.reader_ready,controls.reader_diagnostics = reader_reply(reader)
            initial("ARM", "OK ARM")
            initial("CONTROL", "OK CONTROL")
            connected = True
            maintenance.connected=True;maintenance.version=VERSION;maintenance.serial_port=args.port;maintenance.send=send
            port.timeout = 0.03
            pending = bytearray()
            next_hb = next_poll = next_light = next_rfid = 0
            previous = None
            previous_doors = None
            staff_keys=StaffKeys(maintenance,controls)
            shown = None
            print("RFID + code: 77004# keys | 40077# keys accessible | 16646# Black Hat/Vexed | 64661# accessible. Five-second entry windows; * clears; hold 0 for ten seconds to stop and return to idle.", flush=True)
            print("Valid RFID + code starts preparation, then five-second admission before countdown. Reader: " + ("ready" if controls.reader_ready else "missing — wire RC522 before starting"), flush=True)
            print("Portal maintenance requires local 5 confirmation. 5 renews test enable; * cancels tests/sound; hold 0 for ten seconds to exit maintenance and stop gameplay.",flush=True)
            print("USB objective: fresh storage insertion at the configured Pi socket during RUNNING; remove any preinserted drive first. Mega D4 is unused. Keys objective: 1,3,2,4.", flush=True)
            print("A0 is the only fitted receiver; D2/D3/D4 retired. D22 entry / D23 exit active-high relay commands. D9 Nano module; D6 status light.", flush=True)
            print(f"Timing preparation/game/cooldown/warmup: {controls.settings.startup}/{controls.settings.duration}/{controls.settings.cooldown}/{controls.settings.warmup} seconds; break limit {controls.settings.max_breaks}", flush=True)
            while True:
                now = time.monotonic()
                pending.extend(port.read(port.in_waiting or 1))
                if len(pending) > 4096: raise RuntimeError("Oversized serial response")
                while b"\n" in pending:
                    raw, _, pending = pending.partition(b"\n")
                    line = raw.decode("ascii", errors="replace").strip()
                    words = line.split()
                    if line.startswith("LIGHT A0 "):
                        value=line.removeprefix("LIGHT A0 ")
                        if not value.isdigit() or not 0<=int(value)<=1023 or not replies or replies[0][0]!="LIGHT A0":raise RuntimeError("Invalid light response")
                        replies.popleft();maintenance.receive_light(int(value),now)
                    elif line.startswith("INPUTS "):
                        if len(words) != 4 or any(v not in ("0", "1") for v in words[1:]): raise RuntimeError("Invalid snapshot")
                        controls.inputs([v == "1" for v in words[1:]], now)
                        if replies and replies[0][0] == "INPUTS": replies.popleft()
                    elif line.startswith("INPUT "):
                        if len(words) != 3 or words[1] not in ("0", "1", "2") or words[2] not in ("0", "1"): raise RuntimeError("Invalid input")
                        values = controls.levels.copy(); values[int(words[1])] = words[2] == "1"
                        controls.inputs(values, now)
                    elif line == "RFID TAG":
                        if maintenance.enabled or maintenance.pending:
                            controls.entry.reset('maintenance')
                            controls.last_scan_at=now;controls.scan_count+=1;maintenance.rfid_scan()
                        else:controls.swipe(now)
                    elif line.startswith(("RFID READY ", "RFID MISSING ")):
                        if not replies or replies[0][0]!="RFID STATUS":raise RuntimeError("Unexpected RFID health reply")
                        reply=replies.popleft();controls.reader_ready,controls.reader_diagnostics=reader_reply(line)
                        if not controls.reader_ready:controls.entry.reset('reader_unavailable')
                        if reply[2]:reply[2]()
                    elif line in ("KEY UP","KEYPAD MISSING"): staff_keys.key(None,now)
                    elif line == "KEY INVALID":
                        staff_keys.key(None,now);print("Press one keypad key at a time.", flush=True)
                    elif len(words) == 2 and words[0] == "KEY" and len(words[1]) == 1 and words[1] in "0123456789ABCD*#":
                        staff_keys.key(words[1],now)
                    elif replies and line == replies[0][0]:
                        reply=replies.popleft()
                        if reply[2]:reply[2]()
                    elif line: raise RuntimeError(f"Controller fault: {line}")
                if replies and now > replies[0][1]: raise RuntimeError("Controller acknowledgment timed out")
                if usb_input.poll(now):
                    controls.usb_update(usb_input.present,now,allow_objective=not (maintenance.enabled or maintenance.pending))
                    maintenance.usb_input=usb_input.status()
                staff_keys.tick(now)
                controls.tick(now)
                sounds.update(controls, now)
                maintenance.tick(controls,now,serial_idle=not replies and not status_frames.deferred,previous=previous)
                if maintenance.enabled or maintenance.pending:controls.entry.reset("maintenance")
                door_testing=maintenance.test and maintenance.test['kind']=='door'
                door_state=(False,False) if maintenance.enabled or maintenance.pending else controls.doors()
                if not door_testing and door_state!=previous_doors:
                    text='DOORS %d %d'%door_state
                    def door_ack(state=door_state):maintenance.door_commanded=state;maintenance.next_live=0
                    send(text,'OK '+text,door_ack)
                    previous_doors=door_state
                if door_testing:previous_doors=None
                desired = maintenance.display() if maintenance.enabled or maintenance.pending else controls.display(now)
                hold_countdown=staff_keys.countdown(now)
                if hold_countdown is not None:desired=(desired[0],desired[1],hold_countdown,desired[3])
                if previous is None or desired[0] != previous[0]: send("ON" if desired[0] else "PAUSE", "OK ON" if desired[0] else "OK PAUSE")
                if previous is None or desired[1] != previous[1]: send("LED ON" if desired[1] else "LED OFF", "OK LED ON" if desired[1] else "OK LED OFF")
                if previous is None or desired[2] != previous[2]: send(f"TIME {desired[2]}", "OK TIME")
                if previous is None or desired[3] != previous[3]: send("RGB " + desired[3], "OK RGB " + desired[3])
                previous = desired
                reporting.status(controls, desired, now, audio=audio_metrics(),maintenance=maintenance.metrics())
                if now >= next_hb: send("HB", "OK HB"); next_hb = now + 0.25
                if now >= next_poll:
                    send("INPUTS", "INPUTS"); send("KEYPAD", "KEYPAD READY"); next_poll = now + 0.5
                if now>=next_light:
                    send("LIGHT","LIGHT A0")
                    next_light=now+(.04 if maintenance.test and maintenance.test['kind'] in ('capture','auto','beams') else .2)
                if now>=next_rfid:
                    send("RFID","RFID STATUS");next_rfid=now+2
                maintenance.publish(controls,now)
                status_frames.tick(now)
                g = controls.game
                status = (controls.mode, g.state if g else "idle", desired[2], g.breaks if g else 0,
                    g.key_progress if g else 0, g.objective if g else False, controls.result, tuple(g.enabled if g else (controls.last_enabled or [])), controls.reader_ready, controls.entry.reason, len(controls.entry.code), controls.scan_count)
                if status != shown:
                    if controls.result: print(f"RESULT: {controls.result[0]} | breaks {controls.result[1]} | RFID + mission code to play again", flush=True)
                    elif g: print(f"{g.state.upper()} | {desired[2]}s | breaks {g.breaks}/{g.settings.max_breaks} | keys {g.key_progress}/4 | objective {g.objective} | excluded beams {','.join(str(i+1) for i,v in enumerate(g.enabled) if not v) or 'none'}", flush=True)
                    else: print(f"IDLE — RFID {'ready' if controls.reader_ready else 'missing'} | {controls.entry.reason} | code {len(controls.entry.code)}/6 characters | scans {controls.scan_count}", flush=True)
                    shown = status
        except KeyboardInterrupt: print("\nPanel game stopped.", flush=True)
        except (OSError, RuntimeError, serial.SerialException) as error:
            connected = False
            maintenance.connected=False
            reported_fault = "controller_communication_fault"
            parser.exit(1, f"FAULT: {error}\n")
        finally:
            try: port.write(b"OFF\n"); port.flush()
            except (OSError, serial.SerialException): pass
            audio.close()
            effects.close()
            if controls.game:
                reporting.finish(controls.game, time.monotonic(), "communication_fault" if reported_fault else "stopped")
            reporting.status(controls, (False, False, 0, "OFF"), time.monotonic(),
                connected=connected, fault=reported_fault, stopped=not reported_fault, audio=audio_metrics(),maintenance=maintenance.metrics())


if __name__ == "__main__": main()
