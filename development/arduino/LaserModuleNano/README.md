# Laser Module Nano — nano-module-0.1.0

Target: classic Arduino Nano 3.0 / ATmega328P, 5 V logic. One module has one active-high MOSFET-controlled laser and one WS2812/WS2812B GRB 16-pixel ring. There is no receiver or serial command bus on this Nano. The TEMT6000 analog receiver goes separately to the Mega. All Nanos use the same sketch, with no address.

## Proposed wiring — verify before powering the laser

| Nano connection | Connect to |
| --- | --- |
| D2 | Dedicated Mega digital output, with an external 10 kΩ resistor from Nano D2 to GND |
| D3 | Active-high laser MOSFET driver control/gate; never connect laser supply current to this pin |
| D6 | Ring DIN through a 330–470 Ω series resistor near the ring |
| GND | Common Mega, Nano, ring and laser-driver ground |
| 5V / ring power | Appropriate regulated 5 V supply; ring current must not flow through a Nano I/O pin |

Use a defined LOW at the MOSFET gate/control as well (typically an external 10 kΩ pulldown); driver circuitry must match the actual MOSFET/module. The laser supply and driver have not been electrically verified here. Keep the laser disconnected for the first test; observe D3 or use an LED with a series resistor. Ring power capacitor/wiring should follow the ring vendor's guidance. Do not connect an external 5 V source and USB power together without verifying the board's power arrangement; a simple first bench setup uses USB power only for Nano plus the dim ring if within the available USB current budget.

Run the 10–15 ft command cable as signal paired with a common ground. The pulldown must be at the Nano end. This cable arrangement has not yet been physically validated alongside laser/ring power wiring. This steady signal can default off when disconnected, but cannot detect a Mega frozen with its output HIGH.

## Behavior

- Start with D2 LOW: MOSFET output LOW and ring dark. No red pulse at initial LOW boot.
- Mega owns the five-second game preparation: keep D2 LOW through that interval.
- D2 HIGH accepted after a 5 ms noise filter: laser output HIGH immediately, then the dim blue ring fills over one second. There is no one-second laser delay.
- Held HIGH: slow four-second blue breathing animation. Channel peak defaults to 12/255, about 4.7%; tune in the actual dark room.
- D2 LOW: laser output LOW at the next loop check (no intentional off delay). Ring has a 100 ms red rise and 400 ms fade, then goes dark.
- LOW interrupts startup or active animation. A fresh accepted HIGH interrupts shutdown and restarts startup.
- No delay() calls. A ring frame takes roughly 0.5 ms to transmit, so physical LOW handling is not instantaneous hardware shutdown.
- Nano reset while D2 is already HIGH starts the on sequence once setup and the input filter complete. Put the Mega output LOW before connecting/resetting/flashing a module if the laser must remain off.

Settings are near the top of LaserModuleNano.ino: pin choices, PIXELS, BLUE_PEAK, RED_PEAK and BREATH_MS. Timings are in ModuleState.h. Keep both files in the LaserModuleNano sketch folder.

## Manual upload on the Mac

1. Open LaserModuleNano.ino in Arduino IDE (leave ModuleState.h in the same folder).
2. Install **Adafruit NeoPixel** using Library Manager if missing.
3. Select **Arduino AVR Boards → Arduino Nano**, **Processor → ATmega328P**, then the Nano's USB port.
4. Click Verify, then Upload. If the board does not respond, select **ATmega328P (Old Bootloader)** and retry. Do not burn a bootloader just to change this menu setting.
5. Open Serial Monitor at **115200 baud**. Reset/opening the monitor may restart the Nano. It prints `ZOCO LASER MODULE nano-module-0.1.0`, then state transitions.

With Mega disconnected, test D2 LOW using the pulldown, then use a jumper to this Nano's 5 V to simulate HIGH, and remove it to simulate LOW. Do not connect that jumper while D2 is still connected to a Mega output. Confirm dark boot, startup fill, breathing, immediate laser-control off and red fade. Repeat LOW during startup and HIGH during shutdown. Only attach the actual laser after confirming polarity and driver behavior.

## Versions and archives

The firmware version is independent of the bench Pi/UNO version. Combined ZoCo releases include this source, header, instructions and `nano_modules` metadata. The first combined archive retains existing bench binaries and adds the Nano source; archiving does not flash any board. Nano uploads are manual and their installed versions are unverified until physically checked. No automatic Nano discovery/update is implemented.

Reference: https://support.arduino.cc/hc/en-us/articles/4401874304274-Select-the-right-processor-for-Arduino-Nano
Reference: https://learn.adafruit.com/adafruit-neopixel-uberguide/best-practices
