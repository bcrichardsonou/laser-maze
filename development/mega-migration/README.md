# UNO R4 Minima → Mega 2560 migration

Status: preparation only. Running Pi services/UNO firmware and portal are not changed.

Transfer the existing bench panel with power disconnected:

| Function | Old Minima | Mega 2560 |
| --- | --- | --- |
| Beam simulation button 1 signal | D2 | D2 |
| Beam simulation button 2 signal | D3 | D3 |
| Objective latch signal | D4 | D4 |
| Indicator LED (existing series resistor) | D5 | D5 |
| Bench WS2812 DIN (existing series resistor) | D6 | D6 |
| TM1637 CLK | D7 | D7 |
| TM1637 DIO | D8 | D8 |
| Keypad adapter SDA | A4/SDA | D20/SDA |
| Keypad adapter SCL | A5/SCL | D21/SCL |
| Module logic supply / common ground | 5V/GND | 5V/GND |

D9 can remain reserved for the first Nano command input D2, with common ground and Nano-side 10k pulldown, but CURRENT controller firmware does not drive D9. Leave the actual laser disconnected during migration. Do not connect the Nano D2 test jumper to 5V while connected to a controller output. No analog receiver integration/15-beam expansion is included in this board migration.

The existing BenchController source uses Wire's board-specific I2C pin mapping and is being compile-checked for arduino:avr:mega:cpu=atmega2560. Its current protocol version remains bench-0.10.0. Compilation is not upload or gameplay acceptance.

Next physical step: connect Mega USB to Pi, retaining Minima if practical; inspect `arduino-cli board list` and `/dev/serial/by-id/`. Identify exact Mega board/port before changing anything. The current deployment tools and portal validator still target the Minima. They must be updated to allow the exact Mega board before an archive/upload. A blank Mega does not pass the existing firmware preflight; migration needs an explicit first-upload path rather than pretending the old firmware is present. Archive before upload, verify protocol/watchdog/disarmed state and then update the root-owned game service's serial argument to the new stable path. Preserve/report old deployment; verify bench controls, audio, reporting, maintenance and reboot on the Mega before adding real module outputs.

Reference: https://docs.arduino.cc/hardware/mega-2560/

## October 16 staging completed
Official AVR core 1.8.8 installed on Pi. Portal validator now accepts both exact Minima and Mega 2560 targets. Deployment tools support --board mega|minima; Mac wrapper defaults to this Mega stable USB port. --first-upload is limited to an identified Mega with --stage-only; staged failures preserve installed/current. Verified firmware recorded separately in staged-controller.json. mega-migration-0.10.0 archived on portal/Pi/Mac and flashed to Mega; no behavior/version changes beyond board target. Existing Minima current symlink and service preserved until user runs sudo python3 ~/laser-maze/tools/switch-to-mega.py after transferring wiring. Script saves previous service/metadata/current target; verifies Mega disarmed and keypad; writes only controller-mega.conf override, switches current, waits for connected fresh game status before updating installed.json. Failed switch leaves service stopped/unconfirmed with backups; no automatic rollback claimed. Root script not executed by agent.

## Current keypad replacement — November 3, 2026
Storm PLX12T201 replaces the flexible keypad in release bench-0.19.0. Use ../storm-keypad/Wiring-and-controls.md for current wiring and staff controls; earlier A–D instructions above are historical.
