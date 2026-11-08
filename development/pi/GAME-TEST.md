# One-beam game test 0.3.0

Bench wiring stays unchanged: active-high powered button OUT to D2, verified 5 V supply, common GND; LED_BUILTIN represents one laser. No physical exhibit actuators are implemented.

The engine supports four modes independently of hardware. This runner maps only one beam and uses keyboard simulations for USB/key objectives. There is no RFID/code-entry authorization or automatic game start. Each launch starts one bench game and exits after its result.

Deploy with the existing Mac command using a new release label `bench-game-0.3.0`. It now transfers/archives game_engine.py and game_test.py as well as the previous bench files, and verifies the game runner version. Stop other tests before deploying.

On the Pi:

```sh
python3 ~/laser-maze/deployments/current/game_test.py \
  /dev/serial/by-id/usb-Arduino_UNO_R4_Minima_EXAMPLE_UNO_SERIAL-if00 \
  --mode usb --fast
```

Fast mode explicitly uses 2-second startup, 30-second running duration, 2-second beam cooldown and 1-second warmup. Without --fast, timings are 5/150/7/5 seconds, matching the recovered behavior baseline. Normal-mode third-break loss is the same in both timing profiles.

1. Keep the button released during startup. Wait for RUNNING.
2. Press/release once: break count increments, LED goes off for cooldown and then on for warmup. Presses during cooldown/warmup do not count. A continuously held button can count again when warmup ends, matching legacy behavior.
3. Wait until cooldown AND warmup finish, then press/release again. A third eligible break ends the game with beam_limit and turns the LED off.
4. Relaunch; type u followed by Enter during RUNNING to simulate USB completion and win. Commands during startup do not complete the objective.
5. Relaunch without completing the objective; it must timeout after the running duration, excluding startup.
6. For --mode keys, enter 1, 3, 2, 4 on separate lines. Wrong keys are ignored.
7. For --mode usb-break-all, complete u and break the one configured beam in either order. For --mode keys-break-all, complete the key sequence and break the beam in either order.

q followed by Enter, or Control+C, stops the test. Lost acknowledgments, reset/unexpected serial responses or watchdog faults end the test and request OFF; if USB is unavailable, the independent Arduino watchdog handles output shutdown. A blocked input at start is refused; one still blocked when startup ends becomes startup_blocked rather than silently starting an unready game.

This runner sends no live game readiness/results to the portal yet. Release tracking still records the software deployment. A game status adapter and persistent result reporting are later steps after bench acceptance.
