# Beam 1 TEMT6000 input — bench-0.13.0

Hardware: Mega A0 receives TEMT6000 OUT, VCC5V/GND; the Nano remains a separate laser/ring output module. Mega D2's former beam1 button no longer supplies game input. Beam2 remains active-high D3; objective latch active-high D4. Current physical laser is always on because the MOSFET has not arrived.

Calibration reference: a0-20261016T205122966715Z.json. Blocked median6 range3–6; clear median1008 range998–1016; blocked recheck median6 range3–6. Applied source constants in ReceiverConfig.h: strictly below337 BROKEN, strictly above668 CLEAR, retain prior state at/between thresholds. On boot, an uncertain mid-band value starts BROKEN until a clear level is observed. Keep the existing30ms debounce for analog transitions. These thresholds belong to the measured receiver/aim/lighting and must be rechecked if changed; they are not global defaults for future modules.

Receiver calibration JSON remains the immutable original proposal (applied_to_game=false at capture); a separate application record is saved after verified deployment. Archived header/code and the new firmware release identify the applied thresholds. Re-running calibration only proposes values and does not automatically rewrite this header.

Game, reporting and maintenance consume the same INPUT0/INPUTS protocol, now from analog classification. No application-side analog polling or extra metrics were added; existing beam1_input_active becomes actual A0-derived state. Read-only LIGHT still returns raw A0 readings for the calibration tool. This version does not detect receiver disconnection independently of measured light and cannot prove analog wiring health from a single value.

Existing behavior: five-second preparation outputs off; brief beam1 blockage during RUNNING counts a break and lowers D9/Nano red fade. In normal mode D9 rises again after seven-second cooldown, with five-second monitoring warmup. Holding the beam blocked can count again after recovery. Third normal-mode break ends game. Break-all modes latch the completed beam off. Stop/results/maintenance/communication shutdown keep commanded outputs off; none of those can physically turn off the laser until its MOSFET is installed.

Physical acceptance pending: keep beam clear at A, wait five seconds, briefly block and remove opaque card; confirm one counted break/sound/Nano red pulse, cooldown recovery and D stop. Validate in actual lighting and cable routing, including false-trigger checks. No physical break was simulated remotely during deployment.

## Replacement laser — October 17 / bench-0.13.1

User changed laser; old thresholds337/668 rejected clear readings around70. New captured calibration a0-20261017T143523978650Z: both blocked captures0, clear59–80 median70, clear05=62. Applied proposal is strictly below20 broken, strictly above41 clear, retain state20–41; same30ms debounce and conservative boot state. Old calibration is historical, not current. Firmware/Pythonbench0.13.1 and release mega-recalibrated-beam1-0.13.1 identify this new pairing. Physical laser remains continuously powered pendingMOSFET. Always clear the card after the final blocked sample before starting a game.
