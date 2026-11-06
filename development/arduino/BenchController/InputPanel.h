#pragma once
#include <Wire.h>
#include <Adafruit_NeoPixel.h>
#include <TM1637Display.h>
#include "ReceiverConfig.h"

// Only calibrated analog A0 is fitted. Temporary D2/D3/D4 buttons are retired.
// Third protocol input remains false for compatibility; Pi supplies real USB state.
const uint8_t PANEL_INPUT_PINS[] = {A0};
bool panelRaw[3], panelStable[3];
unsigned long panelChanged[3];
bool panelDiagnostic = false;
bool panelAutoLights = true;
bool keypadReady = false;
unsigned long keypadPollAt = 0;
char rawKey = 'N', stableKey = 'N';
unsigned long keyChangedAt = 0;
// Storm PLX12T201: connector 1/2/8/7 -> P0/P1/P2/P3 (rows),
// connector 3/4/5 -> P4/P5/P6 (columns); connector 6 and P7 unused.
const char STORM_KEYMAP[] = "123F456F789F*0#F";
const uint8_t STATUS_ROWS = 14;
const uint8_t STATUS_PIXELS_PER_ROW = 3;
const uint8_t STATUS_PIXEL_COUNT = STATUS_ROWS * STATUS_PIXELS_PER_ROW;
Adafruit_NeoPixel panelPixel(STATUS_PIXEL_COUNT, 6, NEO_GRB + NEO_KHZ800);
TM1637Display panelTimer(7, 8);

bool panelTime(const char *text) {
  if (text[0] == '\0') return false;
  unsigned int seconds = 0;
  for (const char *p = text; *p; p++) {
    if (*p < '0' || *p > '9') return false;
    seconds = seconds * 10 + (*p - '0');
    if (seconds > 5999) return false;
  }
  panelTimer.showNumberDecEx((seconds / 60) * 100 + seconds % 60, 0x40, true);
  return true;
}

// Center-out bloom: paired rows 6/7, 5/8, ... 0/13 (zero-based).
// Snapshot each row when retargeting so rapid status changes do not snap.
uint32_t statusTarget = 0, statusFrom[STATUS_ROWS] = {};
unsigned long statusStarted = 0, statusFrameAt = 0;
bool statusAnimating = false;
const unsigned long STATUS_TRANSITION_MS = 700;

uint8_t statusBlend(uint8_t from, uint8_t to, uint8_t amount) {
  return ((uint16_t)from * (255 - amount) + (uint16_t)to * amount + 127) / 255;
}

void panelColor(uint8_t r, uint8_t g, uint8_t b) {
  uint32_t color = panelPixel.Color(r, g, b);
  if (color == 0) {
    statusTarget = 0; statusAnimating = false;
    bool changed = false;
    for (uint8_t i = 0; i < STATUS_PIXEL_COUNT; ++i) if (panelPixel.getPixelColor(i)) {changed = true; break;}
    if (changed) {panelPixel.clear(); panelPixel.show();}
    return;
  }
  if (color == statusTarget) return;
  for (uint8_t row = 0; row < STATUS_ROWS; ++row) statusFrom[row] = panelPixel.getPixelColor(row * STATUS_PIXELS_PER_ROW);
  statusTarget = color; statusStarted = millis(); statusFrameAt = statusStarted - 20;
  statusAnimating = true;
}

void updateStatusAnimation() {
  if (!statusAnimating) return;
  unsigned long now = millis(), elapsed = now - statusStarted;
  if ((unsigned long)(now - statusFrameAt) < 20) return;
  statusFrameAt = now;
  bool wigwag = statusTarget == 0xFF0000UL || statusTarget == 0xFFB400UL;
  unsigned long duration = wigwag ? 1250 : STATUS_TRANSITION_MS;
  // Seven symmetric row pairs, with a two-pair feathered edge.
  uint16_t progress = elapsed >= STATUS_TRANSITION_MS ? 8 * 256 : elapsed * (8UL * 256) / STATUS_TRANSITION_MS;
  bool changed = false;
  for (uint8_t row = 0; row < STATUS_ROWS; ++row) {
    uint8_t distance = row < 7 ? 6 - row : row - 7;
    int16_t phase = (int16_t)progress - distance * 256;
    uint16_t t = phase <= 0 ? 0 : phase >= 512 ? 255 : (uint32_t)phase * 255 / 512;
    // Integer smoothstep; bounded 32-bit intermediates on AVR.
    uint8_t fade = ((uint32_t)t * t * (765 - 2 * t) + 32512) / 65025;
    uint32_t from = statusFrom[row];
    uint32_t color;
    if (wigwag) {
      // Two bottom/top alternations, then a 250 ms fade to the solid color.
      bool bright = elapsed < 1000 ? ((row < 7) == ((elapsed / 250) % 2 == 0)) : row >= 7;
      uint8_t gain = bright ? 255 : elapsed >= 1250 ? 255 : elapsed >= 1000 ? 32 + (elapsed - 1000) * 223 / 250 : 32;
      uint8_t red = (uint16_t)(uint8_t)(statusTarget >> 16) * gain / 255;
      uint8_t green = (uint16_t)(uint8_t)(statusTarget >> 8) * gain / 255;
      uint8_t blue = (uint16_t)(uint8_t)statusTarget * gain / 255;
      uint8_t entry = elapsed < 100 ? elapsed * 255 / 100 : 255;
      color = panelPixel.Color(statusBlend(from >> 16, red, entry), statusBlend(from >> 8, green, entry), statusBlend(from, blue, entry));
    } else {
      color = panelPixel.Color(statusBlend(from >> 16, statusTarget >> 16, fade),
        statusBlend(from >> 8, statusTarget >> 8, fade), statusBlend(from, statusTarget, fade));
    }
    for (uint8_t col = 0; col < STATUS_PIXELS_PER_ROW; ++col) {
      uint8_t pixel = row * STATUS_PIXELS_PER_ROW + col;
      if (panelPixel.getPixelColor(pixel) != color) {panelPixel.setPixelColor(pixel, color); changed = true;}
    }
  }
  if (changed) panelPixel.show();
  if (elapsed >= duration) statusAnimating = false;
}

void panelOff() {
  digitalWrite(5, LOW);
  panelColor(0, 0, 0);
  panelTimer.clear();
}

void panelBegin() {
  pinMode(5, OUTPUT);
  panelTimer.setBrightness(2);
  panelTimer.clear();
  panelPixel.begin();
  panelPixel.setBrightness(255);
  panelPixel.clear();
  panelPixel.show();
  for (uint8_t i = 0; i < 1; i++) {
    pinMode(PANEL_INPUT_PINS[i], INPUT);
    // Start unknown/mid-band receiver readings as broken until a clear level is observed.
    panelRaw[i] = panelStable[i] = receiverBroken(analogRead(A0), true);
    panelChanged[i] = millis();
  }
  Wire.begin();
  Wire.setClock(100000);
}

bool keypadRead(uint8_t mask, uint8_t &value) {
  Wire.beginTransmission(0x20);
  Wire.write(mask);
  if (Wire.endTransmission() != 0) return false;
  if (Wire.requestFrom((uint8_t)0x20, (uint8_t)1) != 1) return false;
  value = Wire.read();
  return true;
}

int lowLine(uint8_t nibble) {
  switch (nibble) {
    case 0xE: return 0;
    case 0xD: return 1;
    case 0xB: return 2;
    case 0x7: return 3;
    default: return -1;
  }
}

// PCF8574 two-read scanner; P0-P3 rows, P4-P7 columns.
char readPanelKey() {
  uint8_t upper, lower;
  if (!keypadRead(0xF0, upper) || !keypadRead(0x0F, lower)) {
    keypadReady = false;
    return 'F';
  }
  keypadReady = true;
  upper = (upper >> 4) & 0x0F;
  lower &= 0x0F;
  if (upper == 0x0F || lower == 0x0F) return 'N';
  int column = lowLine(upper), row = lowLine(lower);
  if (column < 0 || row < 0) return 'F';
  return STORM_KEYMAP[column + 4 * row];
}

void panelInputSnapshot() {
  Serial.print("INPUTS ");
  for (uint8_t i = 0; i < 3; i++) {
    Serial.print((i < 2 && panelStable[i]) ? 1 : 0);
    if (i < 2) Serial.print(' ');
  }
  Serial.println();
}

bool panelCommand(const char *text, bool armed) {
  // Pi sends FRAME only with an empty request pipeline, and waits for this ACK
  // before writing again. NeoPixel.show masks interrupts for about 1.3 ms.
  if (strcmp(text, "FRAME") == 0) {
    if (!armed) {Serial.println("ERR DISARMED"); return true;}
    updateStatusAnimation(); Serial.println("OK FRAME"); return true;
  }
  if (strncmp(text, "TIME ", 5) == 0 || strcmp(text, "DISPLAY TEST") == 0) {
    if (!armed) {Serial.println("ERR DISARMED"); return true;}
    if (strcmp(text, "DISPLAY TEST") == 0) {
      panelTimer.showNumberDecEx(8888, 0x40, true);
      Serial.println("OK DISPLAY TEST");
    } else {
      if (!panelTime(text + 5)) return false;
      Serial.println("OK TIME");
    }
    return true;
  }
  if (strcmp(text, "PANEL") == 0 || strcmp(text, "CONTROL") == 0) {
    if (!armed) {Serial.println("ERR DISARMED"); return true;}
    panelDiagnostic = true;
    panelAutoLights = strcmp(text, "PANEL") == 0;
    Serial.print("OK "); Serial.println(text);
    return true;
  }
  if (strcmp(text, "INPUTS") == 0) {panelInputSnapshot(); return true;}
  if (strcmp(text, "KEYPAD") == 0) {
    readPanelKey();
    Serial.println(keypadReady ? "KEYPAD READY" : "KEYPAD MISSING");
    return true;
  }
  if (strncmp(text, "RGB ", 4) == 0 || strncmp(text, "LED ", 4) == 0) {
    if (!armed) {Serial.println("ERR DISARMED"); return true;}
    if (strcmp(text, "RGB RED") == 0) panelColor(255, 0, 0);
    else if (strcmp(text, "RGB GREEN") == 0) panelColor(0, 255, 0);
    else if (strcmp(text, "RGB BLUE") == 0) panelColor(0, 0, 255);
    else if (strcmp(text, "RGB YELLOW") == 0) panelColor(255, 180, 0);
    else if (strcmp(text, "RGB PURPLE") == 0) panelColor(120, 0, 180);
    else if (strcmp(text, "RGB OFF") == 0) panelColor(0, 0, 0);
    else if (strcmp(text, "LED ON") == 0) digitalWrite(5, HIGH);
    else if (strcmp(text, "LED OFF") == 0) digitalWrite(5, LOW);
    else return false;
    Serial.print("OK "); Serial.println(text);
    return true;
  }
  return false;
}

void updatePanel(bool armed) {
  unsigned long now = millis();
  for (uint8_t i = 0; i < 3; i++) {
    bool value = i == 0 ? receiverBroken(analogRead(A0), panelRaw[0]) : false;
    if (value != panelRaw[i]) {panelRaw[i] = value; panelChanged[i] = now;}
    if (value != panelStable[i] && (unsigned long)(now - panelChanged[i]) >= 30) {
      panelStable[i] = value;
      if (armed && panelDiagnostic) {
        Serial.print("INPUT "); Serial.print(i); Serial.print(' '); Serial.println(value ? 1 : 0);
        if (panelAutoLights) {
        digitalWrite(5, (panelStable[0] || panelStable[1] || panelStable[2]) ? HIGH : LOW);
        if (panelStable[0] || panelStable[1]) panelColor(255, 0, 0);
        else if (panelStable[2]) panelColor(0, 0, 255);
        else panelColor(0, 255, 0);
        }
      } else if (armed && i == 0) Serial.println(value ? "BEAM BROKEN" : "BEAM CLEAR");
    }
  }
  if ((unsigned long)(now - keypadPollAt) >= 20) {
    keypadPollAt = now;
    char key = readPanelKey();
    if (key != rawKey) {rawKey = key; keyChangedAt = now;}
    if (key != stableKey && (unsigned long)(now - keyChangedAt) >= 30) {
      stableKey = key;
      if (armed && panelDiagnostic) {
        if (key == 'F') Serial.println(keypadReady ? "KEY INVALID" : "KEYPAD MISSING");
        else if (key == 'N') Serial.println("KEY UP");
        else {Serial.print("KEY ");Serial.println(key);}
      }
    }
  }
}
