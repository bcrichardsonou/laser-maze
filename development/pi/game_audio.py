"""Short Pi-generated bench sound cues; playback never waits in the game loop."""
import argparse
from collections import deque
import math
import os
from pathlib import Path
import shutil
import struct
import subprocess
import tempfile
import time
import wave

TONES = {
    'select': [(520, .08)],
    'countdown': [(700, .09)],
    'start': [(600, .10), (900, .18)],
    'beam': [(180, .15)],
    'win': [(523, .12), (659, .12), (784, .12), (1047, .25)],
    'loss': [(360, .18), (260, .18), (160, .25)],
    'stop': [(440, .09), (300, .12)],
    'fault': [(160, .12), (0, .08), (160, .12)],
}


def write_tone(path, notes):
    rate = 22050
    data = bytearray()
    for frequency, duration in notes:
        length = int(rate * duration)
        for i in range(length):
            # Quiet test tones and a short envelope avoid clicks.
            envelope = min(1, i / (rate * .008), (length-1-i) / (rate * .008))
            sample = int(6500 * envelope * math.sin(2*math.pi*frequency*i/rate)) if frequency else 0
            data.extend(struct.pack('<h', sample))
    with wave.open(str(path), 'wb') as wav:
        wav.setnchannels(1); wav.setsampwidth(2); wav.setframerate(rate); wav.writeframes(data)


class Audio:
    def __init__(self, folder=None):
        self.backend = shutil.which('pw-play') or shutil.which('aplay')
        self.enabled = os.environ.get('ZOCO_AUDIO_ENABLED', '0') == '1'
        self.process = None
        self.pending = deque(maxlen=3)
        self.last_cue = 'none'
        self.error = ''
        self.deadline = 0
        self.environment = os.environ.copy()
        self.environment.setdefault('XDG_RUNTIME_DIR', f'/run/user/{os.getuid()}')
        self.folder = Path(folder or Path.home()/'laser-maze/audio-cache')
        try:
            self.folder.mkdir(parents=True, exist_ok=True, mode=0o700)
            for cue, notes in TONES.items():
                fd, name = tempfile.mkstemp(dir=self.folder, prefix='.sound-', suffix='.wav')
                os.close(fd)
                try:
                    write_tone(name, notes)
                    os.replace(name, self.folder/(cue+'.wav'))
                finally:
                    if os.path.exists(name): os.unlink(name)
        except OSError:
            self.enabled = False; self.error = 'audio_cache_unavailable'

    def queue(self, cue, priority=False):
        if not self.enabled or not self.backend or cue not in TONES: return
        if priority:
            self.pending.clear()
            if self.process and self.process.poll() is None:
                try: self.process.terminate()
                except ProcessLookupError: pass
                # Reap asynchronously; update() starts the next sound after exit.
                self.deadline = time.monotonic()+1
        if cue == 'countdown' and (self.pending or self.process and self.process.poll() is None): return
        self.pending.append(cue)

    def update(self, now):
        if self.process:
            code = self.process.poll()
            if code is None:
                if now > self.deadline:
                    try: self.process.kill()
                    except ProcessLookupError: pass
                    self.error = 'audio_player_timeout'
                return
            if code != 0 and code > 0: self.error = 'audio_playback_failed'
            self.process = None
        if not self.pending: return
        cue = self.pending.popleft()
        command = [self.backend]
        if Path(self.backend).name == 'aplay': command += ['-q']
        target = os.environ.get('ZOCO_AUDIO_TARGET')
        if target and Path(self.backend).name == 'pw-play': command += ['--target', target]
        command += [str(self.folder/(cue+'.wav'))]
        try:
            self.process = subprocess.Popen(command, env=self.environment,
                stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            self.last_cue = cue
            self.deadline = now + 3
            self.error = ''
        except OSError:
            self.error = 'audio_player_unavailable'

    def metrics(self):
        return dict(audio_enabled=self.enabled, audio_player_available=bool(self.backend),
            audio_last_cue_requested=self.last_cue, audio_error=self.error or 'none')

    def close(self):
        self.pending.clear()
        if self.process:
            try:
                if self.process.poll() is None:
                    self.process.terminate()
                    try: self.process.wait(timeout=.5)
                    except subprocess.TimeoutExpired:
                        self.process.kill(); self.process.wait(timeout=.5)
            except (OSError, subprocess.TimeoutExpired): pass
            self.process = None


class GameSounds:
    def __init__(self, audio):
        self.audio = audio
        self.game = None
        self.phase = None
        self.breaks = 0
        self.countdown = None
        self.result = None
        self.mode = None

    def update(self, controls, now):
        game = controls.game
        if controls.mode != self.mode:
            if self.mode is not None: self.audio.queue('select')
            self.mode = controls.mode
        if game is not self.game:
            self.game = game; self.phase = None; self.breaks = 0; self.countdown = None
        if game:
            if game.state == 'starting':
                second = max(0, math.ceil(game.running_at-now))
                if second != self.countdown:
                    self.audio.queue('countdown'); self.countdown = second
            if game.state == 'running' and self.phase != 'running': self.audio.queue('start', priority=True)
            if game.breaks > self.breaks and game.state == 'running': self.audio.queue('beam')
            self.breaks = game.breaks; self.phase = game.state
        if controls.result is not None and controls.result is not self.result:
            outcome = controls.result[0]
            cue = 'win' if outcome == 'win' else 'stop' if outcome == 'stopped' else 'fault' if outcome in ('startup_blocked','communication_fault') else 'loss'
            self.audio.queue(cue, priority=True)
        self.result = controls.result
        self.audio.update(now)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--test', action='store_true', required=True)
    parser.parse_args()
    audio = Audio()
    audio.enabled = True  # Explicit standalone test; game-service setting stays unchanged.
    try:
        for cue in ('countdown','start','beam','win','loss','stop'):
            print('Sound test:', cue, flush=True)
            audio.queue(cue, priority=True)
            until = time.monotonic()+1.2
            while time.monotonic()<until:
                audio.update(time.monotonic()); time.sleep(.03)
            if audio.error: print('Playback issue:', audio.error, flush=True)
    finally: audio.close()
    print('Playback requests finished; audible sound must be confirmed at the speaker.', flush=True)


if __name__ == '__main__': main()
