# Door relays — mega-door-relays-0.23.0

Installed November 6, 2026. Firmware/Python bench-0.23.0; immutable archive stored on Pi, portal and Mac at development/release-backups/mega-door-relays-0.23.0/release.tar.gz. Mega compile 16,712 bytes flash / 1,205 bytes RAM. All four services active; real live command acknowledgement at idle: entry locked, exit unlocked. No physical relay/door acceptance claimed.

## Wiring

D22 -> entry relay IN. D23 -> exit relay IN. Signal grounds common with Mega. Active HIGH energizes/locks, LOW releases/unlocks. External 10k pulldown from each input to ground required to hold LOW during reset; verify no back-powering through the selected modules. Power relay modules according to rating, never coils from GPIO. Relay COM/NO switches magnet power; independent exit-release circuit interrupts exit magnet power regardless of software. Verify DC inductive contact ratings and suppression from actual equipment instructions. Keep magnet power disconnected until unloaded relay checks and independent exit-release checks pass.

## Timing (user-approved)

At idle: entry locked, exit unlocked. Preparation: both locked. Five-second admission: entry unlocked, exit locked. Running: both locked. All outcomes and local stop: entry locked, exit unlocked. Entering/pending maintenance: both unlocked. Controller startup/disarm/communication watchdog/error: both outputs LOW. Normal idle entry lock reasserts only after controller handshake/arming. No physical door-position or lock-status sensors are fitted; portal reports acknowledged output commands only. The independent exit-release hardware has NOT been verified installed.

D2/D3/D4 temporary buttons retired. Only real A0 receiver enabled in physical runner, including break-all completion and restored older settings. Generic two-beam Controls tests remain for future expansion; physical runner explicitly selects single-receiver mode.

## Maintenance

Doors shortcut/card includes live command status, entry-only/exit-only five-second relay tests, and Release both doors. Tests require maintenance plus local 5 confirmation, exclude other active tests, expire at five seconds, and stop on local *, Stop, grant expiry or maintenance exit. DOORTEST has an independent five-second Mega timeout, even with continuing heartbeat. Release both cancels gameplay/tests and remains in maintenance, avoiding idle entry relock. Release does not need local grant. Portal completion of that action says release requested; acknowledged relay commands appear in the card. No remote control is a substitute for independent exit hardware.

## Validation/evidence

164 Pi tests, 17 deployment tests, host C++ firmware harness (boot/disarm/malformed commands/watchdog/timed relay release), actual Mega compile/upload/handshake, PHP syntax, 50 existing portal checks, installed administrator render, JavaScript syntax. Four live services active and both versions confirmed. Portal source exact-hash guarded with private backup: /srv/zoco/zoco-portal-private/door-controls/backup-20261106-132005-4b15cd. Installed layout screenshot installed-controls.png is a read-only excerpt; buttons disabled in preview. No live door test or game was triggered remotely.

## Physical acceptance remaining

With magnet power disconnected: wire inputs/ground/pulldowns and verify each relay separately, five-second release, cancel, startup/reset and USB-loss release. Then have FAB verify independent timed release, actual power-loss behavior, appropriate fire-system integration and applicable egress approval before connecting/using occupied-room locks. User must verify entry/admission/exit timing with real hardware.
