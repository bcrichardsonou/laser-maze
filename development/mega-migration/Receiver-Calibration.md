# Receiver calibration — bench-0.12.0

Confirmed plan: one TEMT6000 module VCC→Mega5V, GND→MegaGND, OUT/S→MegaA0. The user has no MOSFET yet and leaves the physical laser continuously powered by its appropriate supply. The controller must not claim to switch that physical laser. Never connect laser power to an Arduino I/O pin.

New firmware `LIGHT` command replies `LIGHT A0 <0..1023>` without arming or changing outputs. The interactive Pi command is:

```
python3 ~/laser-maze/deployments/current/receiver_calibrate.py
```

The tool reads the current installed Mega stable serial path/version, acquires the upload/controller locks, stops the managed game, verifies disarmed firmware, then prompts for blocked, clear and blocked-check samples. Press Enter only after positioning the opaque card. Each sample collects 100 readings over approximately two seconds, with live values every 20 readings. No console/portal real-time graphs are implemented yet. Game service is restarted after port/lock cleanup when it was active before the test, including on Ctrl-C.

Local private records: ~/zoco-monitor/laser-maze/calibration/a0-<UTC>.json, including raw readings, current firmware and proposed thresholds, applied_to_game=false. Calibration is not part of the generic source archive; do not silently reuse one receiver's values for others.

Bright-beam-high is expected. Use the larger blocked/recheck 95th percentile and clear 5th percentile; require at least 20 ADC counts separation and reject clear95>=1020 saturation. Proposed break threshold is one-third across that gap, clear threshold two-thirds, providing hysteresis. These are initial bench acceptance rules, not validated installation thresholds. A disconnected/floating A0 or changed light conditions may still produce misleading samples; physical observation and repeated tests are needed. No thresholds are applied, no analog receiver is wired into the game engine, and the existing beam1 button continues simulating breaks until a later reviewed integration.
