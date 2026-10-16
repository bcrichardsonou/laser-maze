#pragma once
// Module 1, TEMT6000 OUT -> Mega A0. Bright beam is CLEAR.
// Applied from a0-20261016T205122966715Z.json: blocked95=6, clear05=999.
// These thresholds belong to this receiver/aim; recalibrate changed hardware.
const uint16_t RECEIVER_BREAK_THRESHOLD = 337;
const uint16_t RECEIVER_CLEAR_THRESHOLD = 668;
static_assert(RECEIVER_BREAK_THRESHOLD < RECEIVER_CLEAR_THRESHOLD, "Receiver thresholds must have hysteresis");

bool receiverBroken(uint16_t reading, bool previousBroken) {
  if (reading < RECEIVER_BREAK_THRESHOLD) return true;
  if (reading > RECEIVER_CLEAR_THRESHOLD) return false;
  return previousBroken;
}
