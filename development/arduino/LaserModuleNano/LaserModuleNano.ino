/* ZoCo Laser Maze module: classic Nano 3.0 / ATmega328P, manual USB upload.
   Mega command D2: LOW=off, HIGH=on. No serial command protocol or address.
   Requires external 10k pulldowns on D2 and MOSFET gate/control.
   Mega handles the five-second preparation. See README.md before wiring.
*/
#include <Adafruit_NeoPixel.h>
#include "ModuleState.h"
const char VERSION[] = "nano-module-0.3.0";
const uint8_t COMMAND_PIN = 2;
const uint8_t LASER_PIN = 3; // Active-HIGH MOSFET gate or driver input; NOT laser power.
const uint8_t RING_PIN = 6;
const uint8_t PIXELS = 16;
const uint8_t BLUE_PEAK = 32; // Dim cap; more brightness steps for moving highlights.
const uint8_t RED_PEAK = 20;
const uint32_t FRAME_US = 10000; // 100 frames/sec.
const uint32_t ORBIT_MS = 6000;
const uint8_t TOP_PIXEL = 0; // Set to the LED physically at the top.
Adafruit_NeoPixel ring(PIXELS, RING_PIN, NEO_GRB + NEO_KHZ800);
ModuleState module;
uint32_t lastFrameUs = 0, clockLastUs = 0, clockMs = 0;
uint16_t clockRemainderUs = 0;
ModuleState::Phase lastPhase = ModuleState::DARK;

// Q8 positions: 256 units per pixel. No floating-point or trig work in the renderer.
uint16_t circularDistance(uint16_t a, uint16_t b) {
  uint16_t d = a > b ? a - b : b - a;
  return d > 2048 ? 4096 - d : d;
}
uint8_t glowWeight(uint16_t distance) {
  // Smooth rounded highlight, spanning three pixels on each side of its center.
  static const uint8_t curve[] = {255,253,247,237,223,206,186,163,139,115,92,69,49,32,18,8,2,0};
  if (distance >= 768) return 0;
  uint16_t scaled = uint32_t(distance) * 17;
  uint8_t index = scaled / 768;
  uint16_t fraction = scaled % 768;
  return curve[index] - uint32_t(curve[index] - curve[index + 1]) * fraction / 768;
}
uint16_t bounceHead(uint32_t elapsed, uint16_t period) {
  uint16_t t = elapsed % period;
  uint16_t half = period / 2;
  uint16_t ramp = t <= half ? t : period - t;
  return uint32_t(ramp) * 2048 / half; // top -> bottom -> top.
}
uint8_t mixLevel(uint8_t a, uint8_t b, uint16_t amount) {
  return (uint32_t(a) * (256 - amount) + uint32_t(b) * amount + 128) / 256;
}
void drawAnimation(uint32_t elapsed) {
  ring.clear();
  for (uint8_t i = 0; i < PIXELS; ++i) {
    uint16_t pos = uint16_t(i) * 256;
    uint8_t blue = 0, red = 0;
    if (module.phase == ModuleState::STARTUP) {
      uint16_t head = elapsed < 2000 ? bounceHead(elapsed, 1000) : 0;
      uint8_t weightA = glowWeight(circularDistance(pos, head));
      uint8_t weightB = glowWeight(circularDistance(pos, (4096 - head) % 4096));
      uint8_t weight = weightA > weightB ? weightA : weightB;
      blue = (uint16_t(BLUE_PEAK) * weight + 127) / 255;
      if (elapsed >= 2000) {
        uint16_t blend = elapsed >= 2250 ? 256 : (elapsed - 2000) * 256 / 250;
        uint8_t target = 6 + (uint16_t(BLUE_PEAK - 6) * weight + 127) / 255;
        blue = mixLevel(blue, target, blend);
      }
    } else if (module.phase == ModuleState::ACTIVE) {
      uint16_t head = uint32_t(elapsed % ORBIT_MS) * 4096 / ORBIT_MS;
      uint8_t weight = glowWeight(circularDistance(pos, head));
      blue = 6 + (uint16_t(BLUE_PEAK - 6) * weight + 127) / 255;
    } else if (module.phase == ModuleState::SHUTDOWN) {
      if (elapsed < 80) {
        red = RED_PEAK; // One soft flash; laser has already switched OFF.
      } else {
        uint32_t motion = elapsed - 80;
        uint16_t travel = motion < 1600 ? bounceHead(motion, 800) : 0;
        uint16_t head = 2048 - travel; // bottom -> top -> bottom, twice.
        uint8_t weightA = glowWeight(circularDistance(pos, head));
        uint8_t weightB = glowWeight(circularDistance(pos, (4096 - head) % 4096));
        uint8_t weight = weightA > weightB ? weightA : weightB;
        red = (uint16_t(RED_PEAK) * weight + 127) / 255;
        if (motion >= 1600) red = uint32_t(red) * (motion >= 1800 ? 0 : 1800 - motion) / 200;
      }
    }
    ring.setPixelColor((i + TOP_PIXEL) % PIXELS, red, 0, blue);
  }
  ring.show(); // About 0.5 ms; the command is checked again on the next loop.
}

void setup() {
  digitalWrite(LASER_PIN, LOW); // Set latch before enabling output.
  pinMode(LASER_PIN, OUTPUT);
  pinMode(COMMAND_PIN, INPUT); // External pulldown, never INPUT_PULLUP.
  ring.begin(); ring.clear(); ring.show();
  Serial.begin(115200); Serial.print(F("ZOCO LASER MODULE ")); Serial.println(VERSION);
  clockLastUs = lastFrameUs = micros();
}

void loop() {
  uint32_t nowUs = micros();
  // Accumulate microseconds, including across wrap, instead of relying on millis()
  // while WS2812 transmission briefly masks interrupts on the classic Nano.
  uint32_t delta = uint32_t(nowUs - clockLastUs);
  clockLastUs = nowUs;
  clockMs += delta / 1000;
  clockRemainderUs += delta % 1000;
  if (clockRemainderUs >= 1000) { ++clockMs; clockRemainderUs -= 1000; }
  uint32_t now = clockMs;
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
  if (!changed && module.phase == ModuleState::DARK) return;
  if (!changed && uint32_t(nowUs - lastFrameUs) < FRAME_US) return;
  if (changed) lastFrameUs = nowUs;
  else {
    lastFrameUs += FRAME_US;
    if (uint32_t(nowUs - lastFrameUs) >= FRAME_US) lastFrameUs = nowUs;
  }
  drawAnimation(uint32_t(now - module.phaseSince));
}
