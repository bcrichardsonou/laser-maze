# Maintenance controls v2 — bench-0.15.1

Prepared October17 for Laser Maze component5/device example-device. Custom Bluehost portal, Mega2560 main controller, one16-pixel Nano ring/laser module controlled by HIGH/LOW and one TEMT6000A0 plus bench beam2buttonD3. Physical laser continuously powered; no MOSFET yet. No serial owner was added: panel_game.py remains the only game/maintenance serial process, while the separate bridge does HTTPS/service operations.

## Added supported controls

- Fast live A0 raw0..1023, threshold state, capture summary/progress, last keypad key, objective and beam2 levels, actual configured audio target and controller version/connection.
- Receiver blocked/clear/blocked-check capture,100 samples each(~5s). Same measurement proposal rules:>=20 count margin, reject saturation; candidate IDs bind apply to the observed samples, expire30minutes. Blocked capture resets old candidate. Manual thresholds also supported. Values apply through strict CAL command and persist only after matching Mega ACK. Late ACK after cancel queues previous thresholds again. Live readings continue without mixing networking into the serial loop.
- Persistent Pi receiver-settings.json canonical thresholds, reapplied after every HELLO/reconnect. Compiled defaults20/41 are fallback only when no runtime settings exist. No EEPROM changes. Future recalibration needs no firmware reflash. Capture data saved privately, not in generic source archives. Apply requests/results and telemetry retained by existing private portal.
- Game duration10..3600s, startup1..30s,cooldown1..60s,recoverywarmup1..30s,breaklimit1..20, two enabled-channel booleans(atleastone), supported mode list(atleastone). Persisted game-settings.json, applied only in locally enabled maintenance; no auto game start. Runtime configuration is separate from immutable source defaults.
- New-game enable/disable independently of maintenance, does not interrupt current game; enabling allows a local A press, never a remote game start.
- Saved playback gain0..100% using installed PipeWire pw-play--volume (relative to hardware output volume), existing mute/known clips, configured output test via entrance clip.
- One Nano module sequence5s (D9 HIGH then LOW/redfade), local D/portal Stop aborts; benchRGB/display tests retained. Arbitrary module color/brightness/animation cannot be selected over the existing one-bit wire.
- Game service stop/start; start is available to admin while worker is live even if old local test enable expired, because start only restores idle/maintenance with outputs off. Stop/restart/reinstall/reboot require valid local maintenance enable.
- Reinstall only current immutable archived Mega release through existing deploy.py; hash/source/version checks and archive-before-flash retained. Durable per-request marker prevents blind repeat. Time-bounded process group; timeout remains failed/unconfirmed and requires inspecting controller. Nanos not flashed. Cross-version remote update remains unavailable.
- Optional reboot: narrow root installer permits only `/usr/bin/systemctl reboot --no-block`. No reboot is performed by installation. Bridge saves original bootID and confirms only after bootID changes. Late completion may remain unconfirmed in ledger due60s expiry, preserving honest timing. Permission not installed automatically; button stays disabled until user root installer.

## Data and transport

Private Pi folder ~/zoco-monitor/laser-maze/control: state.json(existing+volume/play_locked), receiver-settings.json, game-settings.json, live.json, inbox/results/outbox/acked/rejected. Existing component HTTPS upload key is never copied into telemetry or release source. Worker polls every2s with bounded live telemetry; the API stores latest authenticated component-scoped snapshot under zp_settings maintenance_live:<id>. Admin-only status endpoint returns it; stale receiver data/connection becomes unconfirmed, no high-level/public control data exposure. Existing agent heartbeat remains unchanged.

Protocol2 capabilities gate new UI actions; old protocol1 controls still work. Local C five-minute enable, D cancels tests/audio, B exits. Commands keep UUID/expiry/component scope/CSRF/admin/actor audit and strict typed params. Bad permanent result acknowledgments are quarantined privately so one malformed result cannot stall all polling; no false success is asserted.

## Deployment / acceptance

Public update changes only six guarded public maintenance/dashboard files; backs up previous files privately. No database schema or private config change. Install helpers before routes. Deploy new source/firmware via managed Mac wrapper, restart user-owned worker through its systemd Restart=always, verify fresh live path and read-only snapshot delivery. Do not fabricate calibration capture or physical C on actual exhibit for testing.

Optional Pi command after staging: sudo bash ~/laser-maze/tools/install-maintenance-reboot.sh. It validates sudoers, refuses an unexpected preexisting policy, and restarts maintenance worker. Other features work without this installer.

Tests: prior rules/reporting/deployment retained; new unit cases for staged captures/candidate+ACK persistence/cancel restore/invalid settings/local expiry/bounded module test/play lock; bridge quarantine/stale telemetry/stopped-service recovery/no duplicate reboot; PHP admin/staff/CSRF/params/scope/telemetry freshness and stopped-service recovery. Physical capture/apply, volume/module tests, software reinstall and reboot need user acceptance.

## Installed evidence
Portal installed with private file backup maintenance-v2-update/backup-20261017-090812-575277. Firmware/Python0.15.0 was archived/deployed, then0.15.1 archived/deployed to correct reboot capability detection: sudo listing permission alone does not prove NOPASSWD; require the explicit !authenticate option in the matched long listing. Optional permission script remains staged, NOT installed. Actual Pi pw-play confirms --volume support. Root policy is not modified by deployment. Physical maintenance C/captures/apply/output/reinstall/reboot acceptance is pending.

Actual read-only queue round trip passed: snapshot d379afd1-6ea4-83a9-cd38-1c33d93725bb completed/observed_inputs_captured in MySQL. Fast telemetry receiver raw5/blocked with applied defaults20/41 and connected firmware0.15.1; reboot_supported false as intended. Four services active. Latest validation totals:78Pi tests,17deployment,1firmwarehost,59PHP checks; actual Mega build11340flash/971RAM. Source archives retained portal/Pi/Mac. No physical C or measurement sequence was simulated remotely.
