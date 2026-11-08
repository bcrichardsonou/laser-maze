# Laser Maze maintenance controls v1

Installed October 14, 2026: private command ledger/API and administrator-only dashboard Maintenance section on Bluehost; controller release bench-maintenance-0.10.0 archived and deployed on Pi. Background command delivery is staged but not enabled yet: Pi sudo requires the user’s password.

## Final setup

Mac:

```bash
ssh laser-maze
```

Pi:

```bash
sudo bash ~/laser-maze/tools/install-maintenance-service.sh
```

Then visit https://manage.zocoexhibits.com/?page=exhibit&id=4#exhibit-4-maintenance as administrator. Browser sign-in is still required; no privileged browser session was created by the installer.

## Controls and local enable

- Enter maintenance stops active play and blocks new games. Press C on the bench keypad within the command’s 60-second window to confirm locally. C renews a five-minute test enable. It is a bench presence check, not staff authentication; the final 12-key keypad will need a separate staff-accessible maintenance-enable input or keyed switch.
- Leave maintenance returns to idle without starting a game. B provides a local exit if the portal/network is unavailable. D cancels tests and sound while remaining in maintenance; outside maintenance D keeps its existing stop-game behavior.
- Stop game and Stop sound are priority commands. Remote Stop is an operational convenience, never a substitute for a physical emergency stop.
- Read input snapshot captures the current two simulated beam inputs and objective latch from the controller’s regularly refreshed input cache.
- Known audio clip test, mute/unmute, five-second RGB test and five-second display test require maintenance plus recent local enable. Mute persists across restarts and leaving maintenance; unmute before normal operation when appropriate. Audio execution/exit and Arduino command acknowledgments do not prove audible/visible physical output.
- Restart game program also requires recent local enable and returns to maintenance. Failed or uncertain restart attempts are not retried blindly.
- Current bench tests never enable beam/laser outputs. Ring test targets the existing single status pixel; display test shows 99:59 briefly, then returns to zero. Fifteen-ring, real laser, analog calibration, RFID, hazer, door and software-update controls are future capabilities, not exposed by v1.

## Architecture

The separate zoco-maintenance service polls authenticated HTTPS using the existing private component configuration. It never opens serial. The game process owns the Arduino and reads small validated local requests. Results, original identities, and delivery acknowledgments are durable private files under ~/zoco-monitor/laser-maze/control. Network requests do not block the game heartbeat loop.

The API requires an active opted-in component; browser mutations require an administrator session, CSRF, a fresh maintenance-capable report, strict action/parameter validation and a component lock. Staff and viewing links cannot read/control the maintenance endpoint. Current opt-in is the existing Laser Maze component only. No direct MySQL connection or inbound Pi port is exposed.

Every command expires after 60 seconds. Reconnected components do not execute expired commands. Accepted indicates the component polled for a request, not completion. Expired claimed work becomes Unconfirmed until a valid final result arrives. Duplicate IDs never repeat execution; conflicting final results are rejected. RGB/display deadlines use local monotonic time; recent local confirmation is a five-minute wall-clock lease. Hardware outputs have the independent Arduino watchdog as well. Commands and administrator identities are recorded in zp_commands and zp_audit.

## Validation and remaining acceptance

54 gameplay/reporting/audio/local-maintenance tests, 14 deployment/lifecycle tests, 37 isolated PHP 8.3/SQLite permission/delivery/rendering checks and 1 firmware host check passed. Actual Pi compilation/upload verified firmware/Python bench-0.10.0 and normal service restart. A live read-only input snapshot passed Bluehost enqueue → authenticated Pi delivery → controller result → authenticated acknowledgment → completed MySQL record. No hardware-energizing test or local C confirmation was simulated on the real Pi.

Installed-source rendering was inspected on desktop and at 390px without document overflow. Layout screenshot is maintenance-controls.png. Live browser session was signed out; the visual preview is explicitly marked as a preview, not an authenticated browser acceptance test.

Remaining: user enables background delivery, signs into portal, requests maintenance and confirms with C, checks timed RGB/display/audio, mute/unmute, D cancellation, local B exit, Leave maintenance, restart in maintenance, and subsequent normal gameplay. Verify game restart/new deployment do not lose command identity, and verify offline expiration and service startup after reboot. Local unit tests alone do not establish those physical/live results.

## Backups and recovery

Before the additive migration and guarded file activation, Bluehost saved changed files, private config and a consistent gzipped NDJSON snapshot of the zp_ tables (schema plus rows) under:

`/srv/zoco/zoco-portal-private/maintenance-upgrade/backup-20261014-112420-c503dd`

Directory mode 0700; saved data/config/files mode 0600. These backups contain private data and must remain outside public_html. The update package and old-source hashes remain in the private upgrade folder and locally in development/maintenance. No private config/database backup was downloaded into the workspace.

For maintenance rollback, stop/disable zoco-maintenance on the Pi, exit maintenance locally with B, disable the component opt-in setting, and restore only the changed public files from the saved backup. Keep the new command table and audit history; do not wipe or broadly restore the active database and discard subsequent reporting. A controller rollback/reinstall is separate and must follow verified archive deployment; no automatic firmware rollback was implemented here.

Future exhibits can reuse the shared Maintenance section and command ledger, but require their own explicitly opted-in component and a compatible local handler. Never reuse the Laser Maze device identity or credentials.

## Full maintenance inventory layout — October 14
The deployed portal now includes all ten approved maintenance groups with uniform heading/body/bottom-action cards. Unimplemented controls have a Planned badge and disabled non-submit buttons. Laser alignment includes all-lasers timed alignment and both individual/all-off placeholders. The existing action allowlist is unchanged; no new field output is enabled. Software navigation links to Equipment & components. The incremental layout-only installer and backup reference are in layout-update/.
