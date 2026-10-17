#pragma once
// Module 1, TEMT6000 OUT -> Mega A0. Bright beam is CLEAR.
// Applied from a0-20261017T143523978650Z.json: blocked95=0, clear05=62.
// These thresholds belong to this receiver/aim; recalibrate changed hardware.
const uint16_t RECEIVER_BREAK_THRESHOLD = 20;
const uint16_t RECEIVER_CLEAR_THRESHOLD = 41;
static_assert(RECEIVER_BREAK_THRESHOLD < RECEIVER_CLEAR_THRESHOLD, "Receiver thresholds must have hysteresis");

bool receiverBroken(uint16_t reading, bool previousBroken) {
  if (reading < RECEIVER_BREAK_THRESHOLD) return true;
  if (reading > RECEIVER_CLEAR_THRESHOLD) return false;
  return previousBroken;
}
