// Bench only: LED_BUILTIN represents a laser. No field outputs are connected.
#include "InputPanel.h"
const unsigned long WATCHDOG_MS = 1000;
const char VERSION[] = "bench-0.6.0";
bool stableBroken = false;
char command[32];
unsigned int used = 0;
bool overflow = false;
bool armed = false;
bool ledOn = false;
unsigned long lastHeartbeat = 0;

void disableOutput() {
  digitalWrite(LED_BUILTIN, LOW);
  ledOn = false;
  armed = false;
  panelOff();
}

void handleCommand() {
  if (strcmp(command, "HELLO") == 0) {
    panelDiagnostic = false;
    panelAutoLights = true;
    disableOutput();
    Serial.print("HELLO 1 ");
    Serial.println(VERSION);
  } else if (panelCommand(command, armed)) {
    // Panel commands never energize the simulated laser output.
  } else if (strcmp(command, "ARM") == 0) {
    lastHeartbeat = millis();
    armed = true;
    Serial.println("OK ARM");
  } else if (strcmp(command, "HB") == 0) {
    if (armed) {
      lastHeartbeat = millis();
      Serial.println("OK HB");
    } else {
      Serial.println("ERR DISARMED");
    }
  } else if (strcmp(command, "ON") == 0) {
    if (armed) {
      digitalWrite(LED_BUILTIN, HIGH);
      ledOn = true;
      if (panelAutoLights) {digitalWrite(5, HIGH); panelColor(0, 255, 0);}
      Serial.println("OK ON");
    } else {
      Serial.println("ERR DISARMED");
    }
  } else if (strcmp(command, "PAUSE") == 0) {
    digitalWrite(LED_BUILTIN, LOW);
    ledOn = false;
    if (panelAutoLights) {
      digitalWrite(5, LOW);
      if (armed) panelColor(255, 180, 0); else panelOff();
    }
    Serial.println("OK PAUSE");
  } else if (strcmp(command, "OFF") == 0) {
    disableOutput();
    Serial.println("OK OFF");
  } else if (strcmp(command, "BEAM") == 0) {
    Serial.println(stableBroken ? "BEAM BROKEN" : "BEAM CLEAR");
  } else if (strcmp(command, "STATUS") == 0) {
    Serial.print("STATUS ");
    Serial.print(armed ? "ARMED " : "DISARMED ");
    Serial.println(ledOn ? "ON" : "OFF");
  } else {
    disableOutput();
    Serial.println("ERR COMMAND");
  }
}

void setup() {
  pinMode(LED_BUILTIN, OUTPUT);
  panelBegin();
  stableBroken = panelStable[0];
  disableOutput();
  Serial.begin(115200);
}

void loop() {
  updatePanel(armed);
  stableBroken = panelStable[0];
  if (armed && (unsigned long)(millis() - lastHeartbeat) >= WATCHDOG_MS) {
    disableOutput();
    Serial.println("FAULT WATCHDOG");
  }
  // Bound work per loop so incoming traffic cannot starve the watchdog.
  for (unsigned int n = 0; n < 32 && Serial.available(); n++) {
    char c = Serial.read();
    if (c == '\r') continue;
    if (c == '\n') {
      if (overflow) {
        disableOutput();
        Serial.println("ERR LENGTH");
      } else if (used) {
        command[used] = '\0';
        handleCommand();
      }
      used = 0;
      overflow = false;
    } else if (!overflow) {
      if (used < sizeof(command) - 1) command[used++] = c;
      else {
        overflow = true;
        disableOutput();
      }
    }
  }
}
