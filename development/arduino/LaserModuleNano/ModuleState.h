#pragma once
#include <stdint.h>
// No delays: a LOW command cancels any animation and turns the laser off.
struct ModuleState {
  enum Phase { DARK, STARTUP, ACTIVE, SHUTDOWN };
  Phase phase = DARK;
  bool laser = false;
  bool acceptedHigh = false;
  bool trackingHigh = false;
  uint32_t highSince = 0;
  uint32_t phaseSince = 0;
  static const uint32_t HIGH_FILTER_MS = 5;
  static const uint32_t STARTUP_MS = 1000;
  static const uint32_t SHUTDOWN_MS = 500;
  void update(bool high, uint32_t now) {
    if (!high) {
      trackingHigh = false;
      laser = false;
      if (acceptedHigh) { acceptedHigh = false; phase = SHUTDOWN; phaseSince = now; }
    } else if (!acceptedHigh) {
      if (!trackingHigh) { trackingHigh = true; highSince = now; }
      if (uint32_t(now - highSince) >= HIGH_FILTER_MS) {
        acceptedHigh = true; laser = true; phase = STARTUP; phaseSince = now;
      }
    }
    if (phase == STARTUP && uint32_t(now - phaseSince) >= STARTUP_MS) { phase = ACTIVE; phaseSince = now; }
    if (phase == SHUTDOWN && uint32_t(now - phaseSince) >= SHUTDOWN_MS) phase = DARK;
  }
};
