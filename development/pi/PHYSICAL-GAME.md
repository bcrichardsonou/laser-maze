# Physical panel game 0.5.0

User verified the complete 0.4.1 panel diagnostic. Firmware/Python 0.5.0 now connects that panel to the existing game engine. No wiring changes.

On the Pi, after deploying bench-controls-0.5.0:

```sh
python3 ~/laser-maze/deployments/current/panel_game.py \
  /dev/serial/by-id/usb-Arduino_UNO_R4_Minima_EXAMPLE_UNO_SERIAL-if00 --fast
```

While idle, keypad 1 selects USB, 2 USB break-all, 3 keys, 4 keys break-all. A starts a game; D stops. During a keys game the objective sequence is 1,3,2,4. The program remains connected between games so A can start another game. Control+C exits and disarms all outputs. D is a game stop, not an independent emergency release.

Two active-high buttons D2/D3 represent separate beams. Built-in LED represents beam 1 output; D5 indicator represents beam 2 output. RGB shows purple while idle, yellow during startup/warmup, red while a beam is disabled, green when active or after a win, red after other outcomes. One RGB pixel represents aggregate status, not separate rings. TK51 shows the running MM:SS countdown and 00:00 after a game ends. OFF/communication watchdog clears outputs and the display.

The D4 latch completes a USB objective only on a new OFF-to-ON change during RUNNING. A latch already on at start, or switched on during startup and held, does not win. Turn it off, then on during running. Input snapshots initialize and refresh the controller's knowledge of levels.

Fast demo: startup 2 seconds, game 30 seconds, cooldown 2 seconds and warmup 1 second. Without --fast: 5/150/7/5 seconds. A blocked beam prevents startup. Normal modes fail on the third eligible break across both beams; a held beam can count again after cooldown/warmup. Break-all modes require both beams and the selected objective, in either order.

Hardware acceptance:
- Select 1, press A, wait RUNNING and toggle latch: win.
- Restart with latch still on: no automatic win. Turn it off/on during RUNNING: win.
- Select 3 and A, then enter 1,3,2,4: win; wrong keys do not advance.
- Start USB again, break a beam three eligible times, waiting through recovery/warmup: beam_limit.
- Select 2 and A: break both buttons once and toggle latch, then test the reverse objective order on another game.
- Start and press D: both output LEDs off, timer 00:00. A starts again only when beam buttons are released.
- With no objective completion: timeout.

Still a bench prototype: no real lasers, RFID authorization, field keyswitches, door/hazer control, game service or live game result/status reporting. The portal continues to track releases and monitoring connectivity.
