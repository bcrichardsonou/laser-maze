# Laser Module Nano — nano-module-0.3.0

Classic Nano 3.0 / ATmega328P; Adafruit NeoPixel library; 16 GRB WS2812 pixels.

## Wiring unchanged
- D2: Mega command (bench Mega D9), external 10 kOhm pulldown to GND at Nano.
- D3: active-high MOSFET PWM/trigger; MOSFET trigger GND and supply DC- must have the correct common ground. Keep laser return on OUT-, not directly on ground.
- D6: ring DIN through 330–470 Ohm series resistor.
- Regulated 5 V / common GND supply appropriate to all module loads; no load power through signal pins.
- MOSFET trigger must default LOW; external 10 kOhm pulldown unless board already supplies one.

## Animation
- Startup: two blue highlights travel top-bottom-top twice in 2 seconds, then settle for 250 ms.
- Active: steady dim blue background, fixed-speed highlight orbiting once per 6 seconds. No global brightness swell or green-channel stepping.
- OFF: laser control LOW immediately; 80 ms soft red flash, two red bottom-top-bottom bounces in 1.6 seconds, then 200 ms fade. Total LED shutdown 1.88 seconds.
- A valid new HIGH interrupts shutdown and begins startup; LOW interrupts startup and turns the laser off.
- TOP_PIXEL rotates visual top; BLUE_PEAK32/255, RED_PEAK20/255. Colors brighter than0.2.1 but still capped; verify in the dark room.
- Integer rendering at100fps; microsecond-based accumulated clock and frame schedule. No delay(). WS2812 channels remain8-bit, so extremely dim fades still have limited brightness resolution.

## Manual upload
Unzip the download, open LaserModuleNano/LaserModuleNano.ino in Arduino IDE, install Adafruit NeoPixel if needed. Select Arduino Nano, ATmega328P and the Nano USB port; use ATmega328P (Old Bootloader) if required by your board. Version prints at115200 baud on reset.

Test with laser power disconnected first: LOW boot dark; HIGH startup twice then continuous orbit; LOW red twice then dark; LOW during startup; HIGH during red shutdown. Reconnect the laser only with power off and after verifying MOSFET output behavior. If the animation repeatedly restarts, check Serial Monitor for repeated boot/version messages and STATE transitions to distinguish resets or a noisy D2 command from rendering.

Nano does not detect Mega frozen HIGH. No upload or installed-version verification is automatic. Canonical source is included in future combined release archives; uploading a file manually does not itself add a portal release.
