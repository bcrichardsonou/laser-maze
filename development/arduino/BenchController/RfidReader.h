#pragma once
#include <SPI.h>
#include <MFRC522.h>

// Mega hardware SPI: MISO50, MOSI51, SCK52. All reader inputs need 3.3V logic.
const uint8_t RFID_SELECT_PIN = 53;
const uint8_t RFID_RESET_PIN = 49;
MFRC522 entryReader(RFID_SELECT_PIN, RFID_RESET_PIN);
bool rfidReady = false;
unsigned long rfidPollAt = 0;
unsigned long rfidResponses = 0, rfidSelectFailures = 0;
uint8_t rfidRequestStatus = MFRC522::STATUS_TIMEOUT;
uint8_t rfidSelectStatus = MFRC522::STATUS_TIMEOUT;

void rfidInitialize() {
  entryReader.PCD_Init();
  // Receiver amplification only; does not increase transmitter power.
  entryReader.PCD_SetAntennaGain(MFRC522::RxGain_max);
}

bool rfidProbe() {
  uint8_t version = entryReader.PCD_ReadRegister(MFRC522::VersionReg);
  return version == 0x90 || version == 0x91 || version == 0x92 || version == 0x88;
}

void rfidBegin() {
  SPI.begin();
  rfidInitialize();
  rfidReady = rfidProbe();
}

bool rfidCommand(const char *text) {
  if (strcmp(text, "RFID DIAG") == 0) {
    Serial.print("RFID DIAG ");Serial.print(rfidResponses);Serial.print(' ');
    Serial.print(rfidSelectFailures);Serial.print(' ');Serial.print(rfidRequestStatus);
    Serial.print(' ');Serial.print(rfidSelectStatus);Serial.print(' ');
    Serial.println(entryReader.PCD_GetAntennaGain());return true;
  }
  if (strcmp(text, "RFID") != 0) return false;
  if (!rfidReady) rfidInitialize();
  rfidReady = rfidProbe();
  Serial.println(rfidReady ? "RFID READY" : "RFID MISSING");
  return true;
}

void updateRfid(bool subscribed) {
  unsigned long now = millis();
  if ((unsigned long)(now-rfidPollAt) < 100 || !rfidReady) return;
  rfidPollAt = now;
  // Same Type-A request/select sequence as the library helper, retaining status.
  entryReader.PCD_WriteRegister(MFRC522::TxModeReg, 0x00);
  entryReader.PCD_WriteRegister(MFRC522::RxModeReg, 0x00);
  entryReader.PCD_WriteRegister(MFRC522::ModWidthReg, 0x26);
  uint8_t answer[2], size=2;
  rfidRequestStatus = entryReader.PICC_RequestA(answer, &size);
  if (rfidRequestStatus != MFRC522::STATUS_OK && rfidRequestStatus != MFRC522::STATUS_COLLISION) return;
  ++rfidResponses;
  rfidSelectStatus = entryReader.PICC_Select(&entryReader.uid);
  if (rfidSelectStatus != MFRC522::STATUS_OK) {++rfidSelectFailures;return;}
  // A halted tag does not continually grant access while held in front of the reader.
  entryReader.PICC_HaltA();
  entryReader.PCD_StopCrypto1();
  if (subscribed) Serial.println("RFID TAG"); // Never transmit or log the tag UID.
}
