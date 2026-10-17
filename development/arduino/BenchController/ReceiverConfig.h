#pragma once
// Module 1, TEMT6000 OUT -> Mega A0. Bright beam is CLEAR.
// Applied from a0-20261017T143523978650Z.json: blocked95=0, clear05=62.
// These thresholds belong to this receiver/aim; recalibrate changed hardware.
const uint16_t RECEIVER_BREAK_THRESHOLD = 20;
const uint16_t RECEIVER_CLEAR_THRESHOLD = 41;
static_assert(RECEIVER_BREAK_THRESHOLD < RECEIVER_CLEAR_THRESHOLD, "Receiver thresholds must have hysteresis");

uint16_t receiverBreakThreshold = RECEIVER_BREAK_THRESHOLD;
uint16_t receiverClearThreshold = RECEIVER_CLEAR_THRESHOLD;

bool receiverBroken(uint16_t reading, bool previousBroken) {
  if (reading < receiverBreakThreshold) return true;
  if (reading > receiverClearThreshold) return false;
  return previousBroken;
}

// Strict two-number parser: no signs, overflow, trailing bytes or reversed bounds.
bool setReceiverCalibration(const char *text) {
  uint16_t values[2] = {0,0};
  for (uint8_t i=0;i<2;i++) {
    if (*text<'0' || *text>'9') return false;
    while (*text>='0' && *text<='9') {
      uint16_t next = values[i]*10 + (*text-'0');
      if (next>1023) return false;
      values[i]=next;text++;
    }
    if (i==0) {if (*text!=' ') return false;text++;}
  }
  if (*text || values[0]==0 || values[0]>=values[1] || values[1]>=1023) return false;
  receiverBreakThreshold=values[0];receiverClearThreshold=values[1];return true;
}
