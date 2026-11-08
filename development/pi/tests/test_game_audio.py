import os
from dataclasses import replace
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import Mock, patch
import wave
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from game_audio import Audio, GameSounds, write_tone
from panel_game import Controls


class SoundTests(unittest.TestCase):
    def test_generated_wave_format_and_envelope(self):
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'tone.wav';write_tone(path,[(440,.1)])
            with wave.open(str(path)) as wav:
                self.assertEqual((wav.getnchannels(),wav.getsampwidth(),wav.getframerate()),(1,2,22050))
                self.assertEqual(wav.getnframes(),2205)
                self.assertEqual(wav.readframes(1),b'\0\0')

    def test_default_disabled_until_output_is_configured(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ,{},clear=True), patch('game_audio.subprocess.Popen') as spawn:
            audio=Audio(tmp);audio.queue('win');audio.update(0)
            spawn.assert_not_called();self.assertFalse(audio.metrics()['audio_enabled'])

    def test_missing_backend_does_not_interrupt_game(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ,ZOCO_AUDIO_ENABLED='1'), patch('game_audio.shutil.which',return_value=None):
            audio=Audio(tmp);audio.queue('beam');audio.update(0)
            self.assertFalse(audio.metrics()['audio_player_available'])

    def test_failed_playback_reported_without_waiting(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ,ZOCO_AUDIO_ENABLED='1'), patch('game_audio.shutil.which',return_value='/usr/bin/pw-play'), patch('game_audio.subprocess.Popen') as spawn:
            proc=Mock();proc.poll.return_value=1;spawn.return_value=proc
            audio=Audio(tmp);audio.queue('win');audio.update(0);audio.update(.1)
            self.assertEqual(audio.error,'audio_playback_failed');proc.wait.assert_not_called()

    def test_priority_preempts_countdown_without_waiting(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ,ZOCO_AUDIO_ENABLED='1'), patch('game_audio.shutil.which',return_value='/usr/bin/pw-play'), patch('game_audio.subprocess.Popen') as spawn:
            proc=Mock();proc.poll.return_value=None;spawn.return_value=proc
            audio=Audio(tmp);audio.queue('countdown');audio.update(0)
            audio.queue('countdown');self.assertFalse(audio.pending)
            audio.queue('win',priority=True);proc.terminate.assert_called_once();proc.wait.assert_not_called()
            self.assertEqual(list(audio.pending),['win'])

    def test_timeout_kills_stuck_playback(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ,ZOCO_AUDIO_ENABLED='1'), patch('game_audio.shutil.which',return_value='/usr/bin/pw-play'), patch('game_audio.subprocess.Popen') as spawn:
            proc=Mock();proc.poll.return_value=None;spawn.return_value=proc
            audio=Audio(tmp);audio.queue('win');audio.update(0);audio.update(4)
            proc.kill.assert_called_once();self.assertEqual(audio.error,'audio_player_timeout')

    def test_entrance_waits_for_preparation_without_cutting_it_off(self):
        with tempfile.TemporaryDirectory() as tmp, patch.dict(os.environ,ZOCO_AUDIO_ENABLED='1'), patch('game_audio.shutil.which',return_value='/usr/bin/pw-play'), patch('game_audio.subprocess.Popen') as spawn:
            proc=Mock();proc.poll.return_value=None;spawn.return_value=proc
            audio=Audio(tmp);audio.queue('preparation',priority=True);audio.update(0)
            audio.queue('entrance');audio.update(5)
            self.assertEqual(spawn.call_count,1);proc.terminate.assert_not_called();proc.kill.assert_not_called()
            self.assertEqual(list(audio.pending),['entrance'])
            proc.poll.return_value=0;audio.update(8.3);self.assertEqual(spawn.call_count,2)

    def test_preparation_and_admission_are_independent_of_long_clip(self):
        voice=Mock();sounds=GameSounds(voice);c=Controls(False)
        c.key('A',0);sounds.update(c,0);c.tick(5);sounds.update(c,5)
        self.assertEqual(c.game.state,'admitting');self.assertEqual(c.display(5)[3],'GREEN')
        c.tick(10);sounds.update(c,10)
        self.assertEqual(c.game.state,'running');self.assertEqual(c.game.remaining(10),150)
        self.assertEqual(voice.queue.call_args_list[-1].args,('entrance',))
        self.assertEqual(voice.queue.call_args_list[-1].kwargs,{})

    def test_design_announcements_and_separate_beam_effect(self):
        voice=Mock();effects=Mock();sounds=GameSounds(voice,effects);c=Controls(False);c.settings=replace(c.settings,startup=11)
        sounds.update(c,0);voice.queue.assert_not_called()
        c.key('A',0);sounds.update(c,0);sounds.update(c,.1)
        c.tick(16);sounds.update(c,16)
        c.inputs([True,False,False],17);sounds.update(c,17)
        self.assertEqual([call.args[0] for call in voice.queue.call_args_list],['preparation','entrance'])
        effects.queue.assert_called_once_with('beam',priority=True)
        c.inputs([False,False,False],18)
        for now in (76,76.1,136,152):c.tick(now);sounds.update(c,now)
        self.assertEqual([call.args[0] for call in voice.queue.call_args_list],['preparation','entrance','warning90','warning30','warning10'])
        c.key('D',153);c.tick(153);sounds.update(c,153)
        self.assertEqual(voice.queue.call_count,5);voice.cancel.assert_called()

    def test_win_voice_depends_on_objective(self):
        for mode,cue in [('usb','win_usb'),('keys','win_keys')]:
            audio=Mock();sounds=GameSounds(audio);c=Controls(True);c.mode=mode;c.result=('win',1)
            sounds.update(c,0);audio.queue.assert_called_once_with(cue,priority=True)

    def test_failure_voices_and_silent_manual_stop(self):
        for outcome,cue in [('timeout','timeout'),('beam_limit','beam_loss'),('stopped',None),('startup_blocked',None),('communication_fault',None)]:
            audio=Mock();sounds=GameSounds(audio);c=Controls(True);c.result=(outcome,1)
            sounds.update(c,0)
            if cue:audio.queue.assert_called_once_with(cue,priority=True)
            else:audio.queue.assert_not_called();audio.cancel.assert_called()

    def test_delayed_tick_skips_obsolete_warnings(self):
        audio=Mock();sounds=GameSounds(audio);c=Controls(False);c.key('A',0);sounds.update(c,0)
        c.tick(10);sounds.update(c,10);c.tick(147);sounds.update(c,147)
        self.assertEqual([call.args[0] for call in audio.queue.call_args_list],['preparation','entrance','warning10'])

    def test_new_game_resets_warning_schedule(self):
        audio=Mock();sounds=GameSounds(audio);c=Controls(False)
        for start in (0,200):
            c.key('A',start);sounds.update(c,start);c.tick(start+10);sounds.update(c,start+10)
            c.tick(start+70);sounds.update(c,start+70);c.key('D',start+71);c.tick(start+71);sounds.update(c,start+71)
        self.assertEqual(sum(call.args[0]=='warning90' for call in audio.queue.call_args_list),2)

if __name__=='__main__':unittest.main()
