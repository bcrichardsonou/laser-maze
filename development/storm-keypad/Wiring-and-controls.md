# Storm keypad — current Laser Maze setup

Storm Interface PLX12T201, 12 keys, via the existing TK85 PCF8574 adapter at I2C 0x20.

Power off the exhibit before changing wiring. The Storm matrix contacts do not require separate power or ground. Identify Storm connector pin numbers using the rear-view drawing supplied with the keypad. TK85 P0–P7 are signal labels, not left-to-right physical pin numbers.

| Storm pin | Function | TK85 |
|---|---|---|
| 1 | Row A (top) | P0 |
| 2 | Row B | P1 |
| 8 | Row C | P2 |
| 7 | Row D (bottom) | P3 |
| 3 | Column 1 (left) | P4 |
| 4 | Column 2 | P5 |
| 5 | Column 3 (right) | P6 |
| 6 | Unused | Unconnected |

Leave TK85 P7 unconnected. Keep TK85 5V, GND, SDA to Mega 20 and SCL to Mega 21 unchanged.

## Staff controls

- Request maintenance through the administrator portal, then press 5 on the keypad to confirm locally. Press 5 again while in maintenance to renew the five-minute test grant. A normal 5 outside requested/active maintenance stays a mission-code digit.
- In requested/active maintenance, * immediately cancels the current hardware test and sound. It does not exit active maintenance. Outside maintenance it retains its mission-entry cancellation behavior.
- Hold 0 continuously for ten seconds to stop gameplay/tests/audio, cancel pending maintenance, clear the local grant and exit maintenance to idle. The display temporarily counts down the hold after the first second. Releasing 0 or an invalid/missing-key event resets the hold. It fires once until release. A normal 0 press remains a code digit.
- Normal RFID + mission code starts games. No separate A start key required. The 1,3,2,4 objective keys remain unchanged.
- The hold is a software staff control, not a hardware emergency stop or the independent door-release button. Portal Stop controls remain available.

## Acceptance after swapping

1. Reconnect power and refresh the administrator portal. Confirm keypad diagnostics show 0–9, * and # correctly, one at a time.
2. Enter a mission code with a normal short 0; confirm RFID/code startup still works.
3. Request maintenance in the portal and press 5; confirm test enable. Press * during a bounded test; confirm laser/test/audio stops while maintenance remains active.
4. Hold 0 for less than ten seconds, release and verify it does not stop/exit. Then hold it for ten seconds and verify countdown, stop, idle and maintenance exit.

Installed software: mega-storm-keypad-0.19.0 / bench-0.19.0. The previous flexible keypad uses a different pin order/keymap and is no longer the configured keypad. Nano firmware unchanged.

## Keypad diagnostic exception — bench-0.19.1

Start keypad test in the maintenance card enables two minutes of read-only testing. All shortcuts and game key actions are suppressed during it, including a long 0 hold. Last key and detected keys appear inside that card. End keypad test, automatic timeout, local-grant expiry or portal Stop ends it. Release held keys before normal shortcuts resume.
