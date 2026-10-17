"""Physical-panel two-beam game. No keyboard entry, RFID or field actuators."""
import argparse
from collections import deque
import fcntl
import math
import json
import signal
from pathlib import Path
import time
from game_engine import Game, Settings, MODES

VERSION = "bench-0.15.1"


class Controls:
    def __init__(self, fast=False, reporting=None):
        self.reporting = reporting
        self.settings = Settings(beam_count=2, startup=2, duration=30, cooldown=2, warmup=1) if fast else Settings(beam_count=2)
        self.levels = [False, False, False]
        self.mode = MODES[0]
        self.game = None
        self.result = None
        self.last_enabled = None
        self.play_locked = False
        self.allowed_modes = list(MODES)

    def configure(self, value):
        from operator_settings import validate_settings
        value=validate_settings(value)
        self.settings=Settings(beam_count=2,enabled_beams=tuple(value['enabled_beams']),**{k:value[k] for k in ('duration','startup','cooldown','warmup','max_breaks')})
        self.allowed_modes=list(value['available_modes'])
        if self.mode not in self.allowed_modes:self.mode=self.allowed_modes[0]

    def inputs(self, levels, now):
        rising = levels[2] and not self.levels[2]
        self.levels = list(levels)
        if self.game:
            self.game.broken = list(levels[:2])
            self.game.tick(now)
            if rising: self.game.objective_usb(now)

    def key(self, key, now):
        self.tick(now)
        if self.game and self.game.state in ("starting", "running"):
            if key == "D": self.game.finish("stopped")
            elif key in "1234": self.game.key(int(key), now)
            return
        if key in "1234":
            selected=MODES[int(key) - 1]
            if selected not in self.allowed_modes:return
            self.mode = selected
            self.result = None
        elif key == "A":
            if self.play_locked:return
            self.game = Game(self.mode, self.settings)
            self.game.broken = list(self.levels[:2])
            self.game.start(now)
            if self.reporting: self.reporting.begin(self.game, now)
            self.result = None
        elif key == "D": self.result = None

    def tick(self, now):
        if self.game:
            self.game.tick(now)
            if self.game.state in ("finished", "fault"):
                if self.reporting: self.reporting.finish(self.game, now)
                self.last_enabled = list(self.game.enabled)
                self.result = (self.game.outcome, self.game.breaks)
                self.game = None

    def display(self, now):
        if not self.game:
            return (False, False, 0, "GREEN" if self.result and self.result[0] == "win" else "RED" if self.result else "PURPLE")
        game = self.game
        outputs = game.outputs(now)
        color = "GREEN"
        if game.state == "starting": color = "YELLOW"
        elif any(enabled and not on for enabled, on in zip(game.enabled, outputs)): color = "RED"
        elif not all(game.enabled): color = "YELLOW"
        elif any(t is not None and now < t for t in game.monitor_at): color = "YELLOW"
        return (*outputs, math.ceil(game.remaining(now)), color)


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
    controls = Controls(args.fast, reporting)
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
        def send(text, expected, callback=None):
            port.write((text + "\n").encode()); port.flush()
            replies.append((expected, time.monotonic() + 1, callback))
        try:
            time.sleep(2); port.reset_input_buffer()
            initial("HELLO", "HELLO 1 bench-0.15.1")
            initial("KEYPAD", "KEYPAD READY")
            initial("CAL {break_below} {clear_above}".format(**maintenance.thresholds),"OK CAL {break_below} {clear_above}".format(**maintenance.thresholds))
            # Initialize all levels BEFORE enabling event subscription.
            port.write(b"INPUTS\n"); port.flush()
            row = port.readline().decode().strip().split()
            if len(row) != 4 or row[0] != "INPUTS" or any(v not in ("0", "1") for v in row[1:]):
                raise RuntimeError("Invalid initial inputs")
            controls.inputs([v == "1" for v in row[1:]], time.monotonic())
            initial("ARM", "OK ARM")
            initial("CONTROL", "OK CONTROL")
            connected = True
            maintenance.connected=True;maintenance.version=VERSION;maintenance.serial_port=args.port;maintenance.send=send
            port.timeout = 0.03
            pending = bytearray()
            next_hb = next_poll = next_light = 0
            previous = None
            shown = None
            print("PHYSICAL PANEL: 1 USB | 2 USB break-all | 3 keys | 4 keys break-all", flush=True)
            print("A starts; D stops. Unavailable beams are excluded at startup; at least one beam must be available.", flush=True)
            print("Portal maintenance requires local C confirmation. C renews test enable; D cancels tests/sound; B exits maintenance locally.",flush=True)
            print("Latch requires a fresh OFF→ON during RUNNING. Keys objective: 1,3,2,4.", flush=True)
            print("Beam 1 input = calibrated TEMT6000 A0; Mega D9 = Nano module 1 / beam 1; built-in LED = beam 1; D5 = beam 2; RGB = combined status.", flush=True)
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
                    elif line == "KEY UP": pass
                    elif line == "KEY INVALID": print("Press one keypad key at a time.", flush=True)
                    elif len(words) == 2 and words[0] == "KEY" and len(words[1]) == 1 and words[1] in "0123456789ABCD*#":
                        maintenance.last_key=words[1];maintenance.last_key_at=maintenance.wall()
                        if not maintenance.local_key(words[1],controls):controls.key(words[1],now)
                    elif replies and line == replies[0][0]:
                        reply=replies.popleft()
                        if reply[2]:reply[2]()
                    elif line: raise RuntimeError(f"Controller fault: {line}")
                if replies and now > replies[0][1]: raise RuntimeError("Controller acknowledgment timed out")
                controls.tick(now)
                sounds.update(controls, now)
                maintenance.tick(controls,now,serial_idle=not replies,previous=previous)
                desired = maintenance.display() if maintenance.enabled or maintenance.pending else controls.display(now)
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
                    next_light=now+(.04 if maintenance.test and maintenance.test['kind']=='capture' else .2)
                maintenance.publish(controls,now)
                g = controls.game
                status = (controls.mode, g.state if g else "idle", desired[2], g.breaks if g else 0,
                    g.key_progress if g else 0, g.objective if g else False, controls.result, tuple(g.enabled if g else (controls.last_enabled or [])))
                if status != shown:
                    if controls.result: print(f"RESULT: {controls.result[0]} | breaks {controls.result[1]} | A to play again", flush=True)
                    elif g: print(f"{g.state.upper()} | {desired[2]}s | breaks {g.breaks}/{g.settings.max_breaks} | keys {g.key_progress}/4 | objective {g.objective} | excluded beams {','.join(str(i+1) for i,v in enumerate(g.enabled) if not v) or 'none'}", flush=True)
                    else: print(f"IDLE — selected {controls.mode}; A to start", flush=True)
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
