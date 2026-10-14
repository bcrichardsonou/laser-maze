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
MEDIA = {name: name+'.wav' for name in ('preparation','entrance','warning90','warning30','warning10','beam','win_keys','win_usb','beam_loss','timeout')}


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
        self.muted = False
        self.process = None
        self.pending = deque(maxlen=3)
        self.last_cue = 'none'
        self.error = ''
        self.deadline = 0
        self.environment = os.environ.copy()
        self.environment.setdefault('XDG_RUNTIME_DIR', f'/run/user/{os.getuid()}')
        self.folder = Path(folder or Path.home()/'laser-maze/audio-cache')
        self.paths = {}
        self.durations = {}
        self.assets_ready = False
        try:
            self.folder.mkdir(parents=True, exist_ok=True, mode=0o700)
            for cue, notes in TONES.items():
                fd, name = tempfile.mkstemp(dir=self.folder, prefix='.sound-', suffix='.wav')
                os.close(fd)
                try:
                    write_tone(name, notes)
                    os.replace(name, self.folder/(cue+'.wav'))
                    self.paths[cue] = self.folder/(cue+'.wav')
                    self.durations[cue] = sum(duration for _,duration in notes)
                finally:
                    if os.path.exists(name): os.unlink(name)
        except OSError:
            self.enabled = False; self.error = 'audio_cache_unavailable'
        for cue, filename in MEDIA.items():
            asset = Path(__file__).parent/'audio'/filename
            try:
                with wave.open(str(asset)) as wav:
                    self.durations[cue] = wav.getnframes()/wav.getframerate()
                self.paths[cue] = asset
            except (OSError, wave.Error):
                self.paths.pop(cue, None)
        self.assets_ready = all(self.paths.get(cue) == Path(__file__).parent/'audio'/filename for cue,filename in MEDIA.items())

    def queue(self, cue, priority=False):
        if not self.enabled or self.muted or not self.backend: return
        if cue not in self.paths:
            self.error = 'audio_asset_missing';return
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
        command += [str(self.paths[cue])]
        try:
            self.process = subprocess.Popen(command, env=self.environment,
                stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            self.last_cue = cue
            self.deadline = now + max(3, self.durations[cue]+2)
            self.error = ''
        except OSError:
            self.error = 'audio_player_unavailable'

    def metrics(self):
        return dict(audio_enabled=self.enabled, audio_player_available=bool(self.backend),
            audio_muted=self.muted,
            audio_assets_ready=self.assets_ready, audio_last_cue_requested=self.last_cue, audio_error=self.error or 'none')

    def cancel(self):
        self.pending.clear()
        if self.process and self.process.poll() is None:
            try: self.process.terminate()
            except ProcessLookupError: pass
            self.deadline = time.monotonic()+1

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
    def __init__(self, audio, effects=None):
        self.audio = audio
        self.effects = effects or audio
        self.game = None
        self.phase = None
        self.breaks = 0
        self.countdown = None
        self.result = None
        self.mode = None
        self.remaining = None
        self.warned = set()

    def update(self, controls, now):
        game = controls.game
        self.mode = controls.mode
        if game is not self.game:
            self.game = game; self.phase = None; self.breaks = 0; self.countdown = None
            self.remaining = game.settings.duration if game else None
            self.warned = set()
            if game and game.state == 'starting':
                self.effects.cancel();self.audio.queue('preparation',priority=True)
        if game:
            if game.state == 'running':
                if self.phase != 'running': self.audio.queue('entrance')
                remaining = game.remaining(now)
                crossed = [(threshold,cue) for threshold,cue in [(90,'warning90'),(30,'warning30'),(14,'warning10')]
                    if threshold not in self.warned and self.remaining is not None and self.remaining > threshold >= remaining]
                if crossed:
                    self.warned.update(threshold for threshold,_ in crossed)
                    self.audio.queue(crossed[-1][1],priority=True)
                self.remaining = remaining
            if game.breaks > self.breaks and game.state == 'running': self.effects.queue('beam',priority=True)
            self.breaks = game.breaks; self.phase = game.state
        if controls.result is not None and controls.result is not self.result:
            outcome = controls.result[0]
            self.effects.cancel()
            cue = ('win_keys' if controls.mode.startswith('keys') else 'win_usb') if outcome == 'win' else 'beam_loss' if outcome == 'beam_limit' else 'timeout' if outcome == 'timeout' else None
            if cue:self.audio.queue(cue,priority=True)
            else:self.audio.cancel()  # Manual stop / faults have no result voice in the design.
        self.result = controls.result
        self.audio.update(now)
        if self.effects is not self.audio:self.effects.update(now)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--test', action='store_true', required=True)
    parser.add_argument('--cue', choices=tuple(MEDIA))
    args = parser.parse_args()
    audio = Audio()
    audio.enabled = True  # Explicit standalone test; game-service setting stays unchanged.
    try:
        if not audio.assets_ready: parser.exit(1,'Original game audio files are missing.\n')
        for cue in (args.cue,) if args.cue else tuple(MEDIA):
            print('Sound test:', cue, flush=True)
            audio.queue(cue, priority=True)
            until = time.monotonic()+audio.durations[cue]+.4
            while time.monotonic()<until:
                audio.update(time.monotonic()); time.sleep(.03)
            if audio.error: print('Playback issue:', audio.error, flush=True)
    finally: audio.close()
    print('Playback requests finished; audible sound must be confirmed at the speaker.', flush=True)


if __name__ == '__main__': main()
