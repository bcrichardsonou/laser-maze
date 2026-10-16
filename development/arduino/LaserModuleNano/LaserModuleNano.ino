/* ZoCo Laser Maze module: classic Nano 3.0 / ATmega328P, manual USB upload.
   Mega command D2: LOW=off, HIGH=on. No serial command protocol or address.
   Requires external 10k pulldowns on D2 and MOSFET gate/control.
   Mega handles the five-second preparation. See README.md before wiring.
*/
#include <Adafruit_NeoPixel.h>
#include "ModuleState.h"
const char VERSION[] = "nano-module-0.1.0";
const uint8_t COMMAND_PIN = 2;
const uint8_t LASER_PIN = 3; // Active-HIGH MOSFET gate or driver input; NOT laser power.
const uint8_t RING_PIN = 6;
const uint8_t PIXELS = 16;
const uint8_t BLUE_PEAK = 12; // Raw channel cap, about 4.7% of 255.
const uint8_t RED_PEAK = 10;
const uint32_t FRAME_MS = 25;
const uint32_t BREATH_MS = 4000;
Adafruit_NeoPixel ring(PIXELS, RING_PIN, NEO_GRB + NEO_KHZ800);
ModuleState module;
uint32_t lastFrame = 0;
ModuleState::Phase lastPhase = ModuleState::DARK;

void setup() {
  digitalWrite(LASER_PIN, LOW); // Set latch before enabling output.
  pinMode(LASER_PIN, OUTPUT);
  pinMode(COMMAND_PIN, INPUT); // External pulldown, never INPUT_PULLUP.
  ring.begin(); ring.clear(); ring.show();
  Serial.begin(115200); Serial.print(F("ZOCO LASER MODULE ")); Serial.println(VERSION);
}

void loop() {
  uint32_t now = millis();
  module.update(digitalRead(COMMAND_PIN) == HIGH, now);
  digitalWrite(LASER_PIN, module.laser ? HIGH : LOW);
  bool changed = module.phase != lastPhase;
  if (changed) {
    lastPhase = module.phase;
    Serial.print(F("STATE "));
    switch (module.phase) {
      case ModuleState::DARK: Serial.println(F("DARK")); break;
      case ModuleState::STARTUP: Serial.println(F("STARTUP LASER_ON")); break;
      case ModuleState::ACTIVE: Serial.println(F("ACTIVE LASER_ON")); break;
      case ModuleState::SHUTDOWN: Serial.println(F("SHUTDOWN LASER_OFF")); break;
    }
  }
  if (!changed && uint32_t(now - lastFrame) < FRAME_MS) return;
  lastFrame = now;
  uint32_t elapsed = uint32_t(now - module.phaseSince);
  ring.clear();
  if (module.phase == ModuleState::STARTUP) {
    uint8_t count = 1 + (elapsed * (PIXELS - 1)) / ModuleState::STARTUP_MS;
    for (uint8_t i=0; i<count; ++i) ring.setPixelColor(i, 0, 2, BLUE_PEAK);
  } else if (module.phase == ModuleState::ACTIVE) {
    // Smooth cosine breathing, beginning at maximum brightness after the fill.
    float angle = float(elapsed % BREATH_MS) * 6.2831853f / BREATH_MS;
    uint8_t blue = 3 + uint8_t((BLUE_PEAK - 3) * (0.5f + 0.5f * cos(angle)));
    for (uint8_t i=0; i<PIXELS; ++i) ring.setPixelColor(i, 0, blue / 6, blue);
  } else if (module.phase == ModuleState::SHUTDOWN) {
    // A single soft red pulse: 100ms rise, then 400ms fade to dark.
    uint8_t red = elapsed < 100 ? RED_PEAK * elapsed / 100 : RED_PEAK * (ModuleState::SHUTDOWN_MS - elapsed) / 400;
    for (uint8_t i=0; i<PIXELS; ++i) ring.setPixelColor(i, red, 0, 0);
  }
  ring.show(); // 16 pixels take roughly 0.5ms; input is checked again next loop.
}
