// Two-beam bench controller; D9 commands Nano module 1 (5V logic only).
#include "InputPanel.h"
#include "RfidReader.h"
const unsigned long WATCHDOG_MS = 1000;
const uint8_t MODULE1_PIN = 9; // Mega D9 -> Nano D2, with Nano-side 10k pulldown.
// Active-high relay modules; external 10k pulldowns hold inputs LOW during reset.
const uint8_t ENTRY_RELAY_PIN = 22;
const uint8_t EXIT_RELAY_PIN = 23;
bool doorTestActive = false;
unsigned long doorTestStarted = 0;
void releaseDoors() {
  doorTestActive = false;
  digitalWrite(ENTRY_RELAY_PIN, LOW);
  digitalWrite(EXIT_RELAY_PIN, LOW);
}
const char VERSION[] = "bench-0.26.3";
bool stableBroken = false;
char command[32];
unsigned int used = 0;
bool overflow = false;
bool armed = false;
bool ledOn = false;
unsigned long lastHeartbeat = 0;

void setLaserOutput(bool on) {
  digitalWrite(LED_BUILTIN, on ? HIGH : LOW);
  digitalWrite(MODULE1_PIN, on ? HIGH : LOW);
  ledOn = on;
}

void disableOutput() {
  releaseDoors();
  setLaserOutput(false);
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
  } else if (rfidCommand(command)) {
    // Reader health query; never energizes outputs.
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
  } else if (strncmp(command, "DOORTEST ", 9) == 0) {
    if (!armed || strlen(command) != 10 || (command[9] != '0' && command[9] != '1')) {
      disableOutput(); Serial.println("ERR DOORTEST");
    } else {
      releaseDoors();
      digitalWrite(command[9] == '0' ? ENTRY_RELAY_PIN : EXIT_RELAY_PIN, HIGH);
      doorTestStarted = millis(); doorTestActive = true;
      Serial.print("OK "); Serial.println(command);
    }
  } else if (strncmp(command, "DOORS ", 6) == 0) {
    // Exact protocol: two bits, entry then exit. Never accept malformed output commands.
    if (strlen(command) != 9 || (command[6] != '0' && command[6] != '1') || command[7] != ' ' || (command[8] != '0' && command[8] != '1') || !armed) {
      disableOutput(); Serial.println("ERR DOORS");
    } else {
      doorTestActive = false;
      digitalWrite(ENTRY_RELAY_PIN, command[6] == '1' ? HIGH : LOW);
      digitalWrite(EXIT_RELAY_PIN, command[8] == '1' ? HIGH : LOW);
      Serial.print("OK "); Serial.println(command);
    }
  } else if (strcmp(command, "ON") == 0) {
    if (armed) {
      setLaserOutput(true);
      if (panelAutoLights) {digitalWrite(5, HIGH); panelColor(0, 255, 0);}
      Serial.println("OK ON");
    } else {
      Serial.println("ERR DISARMED");
    }
  } else if (strcmp(command, "PAUSE") == 0) {
    setLaserOutput(false);
    if (panelAutoLights) {
      digitalWrite(5, LOW);
      if (armed) panelColor(255, 180, 0); else panelOff();
    }
    Serial.println("OK PAUSE");
  } else if (strcmp(command, "OFF") == 0) {
    disableOutput();
    Serial.println("OK OFF");
  } else if (strncmp(command, "CAL ", 4) == 0) {
    if (ledOn || !setReceiverCalibration(command+4)) {
      Serial.println("ERR CAL");
    } else {
      Serial.print("OK CAL ");Serial.print(receiverBreakThreshold);
      Serial.print(' ');Serial.println(receiverClearThreshold);
    }
  } else if (strcmp(command, "OUTPUT") == 0) {
    Serial.print("OUTPUT ");Serial.print(armed ? 1 : 0);Serial.print(' ');
    Serial.print(ledOn ? 1 : 0);Serial.print(' ');Serial.println(digitalRead(MODULE1_PIN) == HIGH ? 1 : 0);
  } else if (strcmp(command, "LEVEL") == 0) {
    analogRead(A1); // Discard first sample after switching ADC channels.
    unsigned int level = analogRead(A1);
    analogRead(A0); // Restore receiver channel before normal beam polling.
    Serial.print("LEVEL A1 "); Serial.println(level);
  } else if (strcmp(command, "LIGHT") == 0) {
    Serial.print("LIGHT A0 ");
    Serial.println(analogRead(A0)); // Read only; allowed while disarmed.
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
  // Set output latch LOW before enabling drivers, before peripheral initialization.
  releaseDoors();
  pinMode(ENTRY_RELAY_PIN, OUTPUT);
  pinMode(EXIT_RELAY_PIN, OUTPUT);
  digitalWrite(MODULE1_PIN, LOW);
  pinMode(MODULE1_PIN, OUTPUT);
  digitalWrite(LED_BUILTIN, LOW);
  pinMode(LED_BUILTIN, OUTPUT);
  pinMode(A1, INPUT);
  digitalWrite(A1, LOW); // External divider supplies the signal; internal pull-up stays off.
  panelBegin();
  rfidBegin();
  stableBroken = panelStable[0];
  disableOutput();
  Serial.begin(115200);
}

void loop() {
  if (doorTestActive && (unsigned long)(millis() - doorTestStarted) >= 5000) releaseDoors();
  updatePanel(armed);
  updateRfid(armed && panelDiagnostic);
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
