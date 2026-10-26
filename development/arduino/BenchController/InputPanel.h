#pragma once
#include <Wire.h>
#include <Adafruit_NeoPixel.h>
#include <TM1637Display.h>
#include "ReceiverConfig.h"

// Beam 1 is calibrated analog A0. Beam 2/button D3 and objective D4 are active-high.
const uint8_t PANEL_INPUT_PINS[] = {A0, 3, 4};
bool panelRaw[3], panelStable[3];
unsigned long panelChanged[3];
bool panelDiagnostic = false;
bool panelAutoLights = true;
bool keypadReady = false;
unsigned long keypadPollAt = 0;
char rawKey = 'N', stableKey = 'N';
unsigned long keyChangedAt = 0;
const char SOFT_KEYMAP[] = "DCBA#9630852*741";
const uint8_t STATUS_PIXEL_COUNT = 8;
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

void panelColor(uint8_t r, uint8_t g, uint8_t b) {
  uint32_t color = panelPixel.Color(r, g, b);
  if (panelPixel.getPixelColor(0) != color) {
    for (uint8_t i = 0; i < STATUS_PIXEL_COUNT; ++i) panelPixel.setPixelColor(i, color);
    panelPixel.show();
  }
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
  panelPixel.setBrightness(32);
  panelPixel.clear();
  panelPixel.show();
  for (uint8_t i = 0; i < 3; i++) {
    pinMode(PANEL_INPUT_PINS[i], INPUT);
    // Start unknown/mid-band receiver readings as broken until a clear level is observed.
    panelRaw[i] = panelStable[i] = i == 0 ? receiverBroken(analogRead(A0), true) : digitalRead(PANEL_INPUT_PINS[i]) == HIGH;
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

// PCF8574 two-read scanner/keymap from Lonely Binary's TK85 reference.
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
  return SOFT_KEYMAP[column + 4 * row];
}

void panelInputSnapshot() {
  Serial.print("INPUTS ");
  for (uint8_t i = 0; i < 3; i++) {
    Serial.print(panelStable[i] ? 1 : 0);
    if (i < 2) Serial.print(' ');
  }
  Serial.println();
}

bool panelCommand(const char *text, bool armed) {
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
    bool value = i == 0 ? receiverBroken(analogRead(A0), panelRaw[0]) : digitalRead(PANEL_INPUT_PINS[i]) == HIGH;
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
