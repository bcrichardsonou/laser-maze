# Pi game audio

Current prepared release: bench-design-audio-0.9.0. Original audio is converted to mono 11,025 Hz PCM WAV for predictable playback. Source MP3s remain unchanged in the original Downloads/LaserMaze/audio directory. Ten canonical WAV files and a provenance inventory are included in the explicit release archive and copied with the normal deployment command. Original hashes match analysis/original-file-hashes.json. longAlarm.mp3 and Slow 10 Sec Countdown.mp3 are not scheduled.

## Event map

| Event | Original file | Scheduling |
|---|---|---|
| Start accepted | startAlarm.mp3 | Starts during five-second setup; continues into gameplay |
| Gameplay begins | System Shutdown - Entrance.mp3 | Queued behind preparation, with no overlapping voices |
| 90 seconds left | System Shutdown in 90.mp3 | Once per game; preempts older voice |
| 30 seconds left | System Shutdown in 30.mp3 | Once per game; preempts older voice |
| 14 seconds left | System Shutdown in 10.mp3 | Clip measures 14.054 seconds; once per game |
| Eligible beam break | alarm.mp3 | Separate effect player; does not cut off voice announcements |
| Key objective win | Corruptors Disabled.mp3 | Cancels effects and replaces pending/current voice |
| USB objective win (bench mode) | Software Uploaded.mp3 | Cancels effects and replaces pending/current voice |
| Beam-limit loss | Laser Breach - Exit.mp3 | Cancels effects and replaces voice |
| Timeout | Time Up - Exit.mp3 | Cancels effects and replaces voice |
| Manual stop or controller fault | No result announcement | Cancels voice/effects |

The updated manual uses 90 and 30 seconds remaining, versus recovered legacy triggers at 94 and 34. Both use 14 for the final warning. User explicitly retained five-second setup and requested the preparation announcement continue while play starts. The preparation clip measures 8.176 seconds; the entrance clip consequently starts afterward, approximately 3.2 seconds into gameplay. Neither playback completion nor queue position delays the timer. The normal running timer remains 150 seconds. The existing third-break limit, modes, objectives and warmup/cooldown rules are unchanged; this is an audio update, not implementation of every revised rule in the full design document.

Fast demos do not fire already-passed warning thresholds; at 30-second duration they omit the 90/30-second warnings. A delayed scheduler tick plays only the most urgent crossed warning instead of piling obsolete announcements together. Each new game resets the warnings. A completed game interrupts remaining narration rather than waiting to finish it.

## Hardware and activation

Audio remains disabled by default until the ordered USB adapter arrives. Use a wired USB audio DAC/interface feeding the amplifier LINE/AUX input. Match the actual amplifier connectors; RCA line outputs suit RCA amplifier inputs. Connect cables and set a modest amplifier volume for the first test.

Identify the Pi's real USB playback output and stable PipeWire node name. Set ZOCO_AUDIO_ENABLED=1 and ZOCO_AUDIO_TARGET to that stable name in a game-service drop-in. Avoid numeric indices or implicit fallback to HDMI. The player supplies /run/user/<brent uid> when XDG_RUNTIME_DIR is absent. Verify the existing desktop PipeWire service and selected output after reboot and USB reconnect before accepting audio. Hardware is not currently connected, and audio routing/enabling is not yet configured.

The game owns two nonblocking subprocess players: narration and beam effects. Queues are bounded; priority results interrupt prior audio. Each original clip has a timeout based on its measured length plus a margin, rather than the old three-second tone timeout. Player errors/timeouts are reported without faulting gameplay. Arduino OFF is sent before closing audio on service shutdown. The status reports enabled, player availability, original asset readiness, last requested voice/effect and playback errors; these do not establish physical speaker output.

## Listen test after hardware connection

From Mac connect with ssh laser-maze. A standalone test selects the original files and enables only its own player; it does not change the game-service configuration:

```bash
python3 ~/laser-maze/deployments/current/game_audio.py --test --cue entrance
```

Omit --cue to audition all ten original clips at full length. Keep the game idle during the standalone audition. After service audio is enabled, verify preparation continues beyond five-second setup, entrance narration follows, alarms overlap narration, warnings occur at 90/30/14 remaining, each objective has the correct win voice, failures override warnings, and D immediately silences audio. Then verify reboot/output-device recovery. Audible acceptance is pending physical hardware.
