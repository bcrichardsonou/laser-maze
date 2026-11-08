# Control panel diagnostic 0.4.1

Wiring: active-high beam buttons D2/D3; active-high latching objective D4; indicator positive D5 through 1 kΩ and negative GND; one WS2812 DIN D6 through 330–470 Ω; flexible keypad adapter SDA A4/SCL A5, VCC 5 V and GND. All modules share ground. TK97 is not needed for the confirmed 5 V keypad interface.

TK51 timer CLOCK/CLK connects to D7, DATA/DIO to D8, with 5 V and common GND. Center-colon version uses MM:SS and brightness 2/7. Install Adafruit NeoPixel and TM1637 Arduino libraries on the Pi before compilation. The keypad scanner uses Wire directly and needs no keypad library. It uses the manufacturer's soft-keypad keymap at I2C address 0x20:
https://learn.lonelybinary.com/tinkerblock/blocks/matrix-keypad

Deploy through the Mac wrapper using a new release label bench-panel-0.4.1. Then, on the Pi:

```sh
python3 ~/laser-maze/deployments/current/panel_test.py \
  /dev/serial/by-id/usb-Arduino_UNO_R4_Minima_EXAMPLE_UNO_SERIAL-if00
```

Expect the D5 indicator to light briefly, then the single RGB pixel to cycle red/green/blue at brightness 32. TK51 then shows 88:88, 02:30, 02:29, 02:28, and a short 00:05 to 00:00 countdown. This is a display test, not a full game. The simulated laser LED stays off. Afterwards each debounced button/latch change prints its name and active/released state; every keypad key prints its actual character. Holding a key reports once; release prints KEY UP. Press one key at a time. All sixteen labels must match the keys before connecting gameplay.

In diagnostic mode button activation lights D5. Either beam active makes RGB red; with beams clear the latch makes it blue; with all inputs released a subsequent change makes it green. Control+C sends OFF; heartbeat loss also disarms and turns lights off. The existing one-beam game remains available but has not been changed to consume this new panel. Keypad-driven gameplay is the next implementation after hardware acceptance.

Local tests simulate the scanner, debounce, watchdog and input message parsing. They do not establish real WS2812 timing/color order, electrical wiring or the adapter's actual mapping. The first Pi compile and physical test remain required.
