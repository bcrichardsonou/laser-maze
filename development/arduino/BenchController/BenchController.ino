// Bench only: LED_BUILTIN represents a laser. No field outputs are connected.
const unsigned long WATCHDOG_MS = 1000;
const char VERSION[] = "bench-0.3.0";
const int BEAM_PIN = 2;
// Active-high powered button module: OUT -> D2, GND -> GND.
const int BEAM_BROKEN_LEVEL = HIGH;
const unsigned long DEBOUNCE_MS = 30;
bool rawBroken = false;
bool stableBroken = false;
unsigned long inputChangedAt = 0;
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
}

void handleCommand() {
  if (strcmp(command, "HELLO") == 0) {
    disableOutput();
    Serial.print("HELLO 1 ");
    Serial.println(VERSION);
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
      Serial.println("OK ON");
    } else {
      Serial.println("ERR DISARMED");
    }
  } else if (strcmp(command, "PAUSE") == 0) {
    digitalWrite(LED_BUILTIN, LOW);
    ledOn = false;
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
  pinMode(BEAM_PIN, INPUT);
  rawBroken = stableBroken = digitalRead(BEAM_PIN) == BEAM_BROKEN_LEVEL;
  inputChangedAt = millis();
  disableOutput();
  Serial.begin(115200);
}

void loop() {
  bool reading = digitalRead(BEAM_PIN) == BEAM_BROKEN_LEVEL;
  if (reading != rawBroken) {
    rawBroken = reading;
    inputChangedAt = millis();
  }
  if (rawBroken != stableBroken &&
      (unsigned long)(millis() - inputChangedAt) >= DEBOUNCE_MS) {
    stableBroken = rawBroken;
    if (armed) Serial.println(stableBroken ? "BEAM BROKEN" : "BEAM CLEAR");
  }
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
