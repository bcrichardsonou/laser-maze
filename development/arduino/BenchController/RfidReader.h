#pragma once
#include <SPI.h>
#include <MFRC522.h>

// Mega hardware SPI: MISO50, MOSI51, SCK52. All reader inputs need 3.3V logic.
const uint8_t RFID_SELECT_PIN = 53;
const uint8_t RFID_RESET_PIN = 49;
MFRC522 entryReader(RFID_SELECT_PIN, RFID_RESET_PIN);
bool rfidReady = false;
unsigned long rfidPollAt = 0;

bool rfidProbe() {
  uint8_t version = entryReader.PCD_ReadRegister(MFRC522::VersionReg);
  return version == 0x90 || version == 0x91 || version == 0x92 || version == 0x88;
}

void rfidBegin() {
  SPI.begin();
  entryReader.PCD_Init();
  rfidReady = rfidProbe();
}

bool rfidCommand(const char *text) {
  if (strcmp(text, "RFID") != 0) return false;
  if (!rfidReady) entryReader.PCD_Init();
  rfidReady = rfidProbe();
  Serial.println(rfidReady ? "RFID READY" : "RFID MISSING");
  return true;
}

void updateRfid(bool subscribed) {
  unsigned long now = millis();
  if ((unsigned long)(now-rfidPollAt) < 100 || !rfidReady) return;
  rfidPollAt = now;
  if (!entryReader.PICC_IsNewCardPresent() || !entryReader.PICC_ReadCardSerial()) return;
  // A halted tag does not continually grant access while held in front of the reader.
  entryReader.PICC_HaltA();
  entryReader.PCD_StopCrypto1();
  if (subscribed) Serial.println("RFID TAG"); // Never transmit or log the tag UID.
}
