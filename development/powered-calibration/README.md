# Powered laser alignment and receiver calibration — bench-0.16.0

Portal installed; Pi/Mega NOT installed because Tailscale SSH timed out. No physical outputs were actuated by the agent.

## Changes
- Physical-panel game uses a powered five-second preparation check: configured outputs HIGH during preparation, exclusion decided from receiver state at its end. Initially dark receivers may become clear and join. No preparation breaks count. Still-dark channels excluded for that game; all dark faults. Legacy standalone Game defaults remain unchanged.
- This deliberately replaces the earlier rule keeping the Nano command LOW throughout preparation. It is necessary to illuminate the switched laser before deciding availability.
- Portal module1 alignment HIGH for30 seconds, then LOW, requires administrator + local C. D, stop, leave, expiry all cancel. Module count is one; no invented15-output controls.
- Captures blocked / clear / blocked-check each independently switch module HIGH, wait for serial acknowledgment plus0.5s, collect100fresh LIGHT replies, turn OFF. Blocked phases require opaque card; laser-off ambient calibration is not implemented. A failed/short/stale sample cannot be applied. Three usable samples create proposal; explicit Apply persists only after Mega CAL ack.
- Portal capability powered_calibration gates alignment/captures; old installed firmware remains unable to request them. Fast feed shows command HIGH/LOW and remaining test time, separately from A0 and physical observation.
- Includes the pending eight-pixel status string on Mega D6, brightness32. Existing game color rules remain, full design-document admission/RFID flow not implemented in this change.

## Next installation
Power Pi and verify Mac `ssh laser-maze`. Run the existing Mac deployment wrapper with release `mega-powered-calibration-0.16.0` and descriptive notes. It archives explicit source/compiled artifacts through the existing portal before flash and retains Mac backup. Verify current installed release before overwriting if user has made other changes.

## Physical acceptance
1. Verify Nano D3 trigger, common grounds, laser supply/polarity. Maintenance C, testHIGH5sec; visually confirm both ring and laser then automatic off. If ring works but laser does not, investigate MOSFET/laser wiring before calibration—software cannot prove emitted light.
2. Align30sec, watch fresh A0; confirm D ends output and countdown stops.
3. Capture100blocked,100clear,100blocked-check; review medians/ranges and proposal. Apply, restart and verify persisted thresholds.
4. Game with receiver initially dark: preparation powers module, clear receiver included at5sec; obstructed receiver excluded. During RUNNING break counts, stop turns off. All unavailable faults; localD and USB loss turn outputs off.
5. Verify all8status LEDs show matching colors/off.
