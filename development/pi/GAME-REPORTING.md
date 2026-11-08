# Bench reporting 0.6.0

Prepared locally; deployment, reporting service activation and portal verification pending. No Bluehost schema/view changes are required for initial scalar metrics and named event logs.

## Architecture

panel_game.py → private durable JSON outbox and fresh status file → separate zoco-game-reports service → existing ZoCo SQLite events queue → existing zoco-monitor HTTPS uploader → portal.

No network requests or shared queue transactions run in gameplay. Local atomic file writes use fsync; storage failure can stop the test and request outputs off rather than falsely claim records were saved. Unsent outbox files remain until the bridge commits them. Transfer uses the original event UUID with INSERT OR IGNORE, so a crash after queue commit and before file deletion does not duplicate the record. The existing uploader's acknowledgment/retry semantics remain unchanged.

Private Pi paths:
- ~/zoco-monitor/laser-maze/outbox/*.json — unsent local game events.
- ~/zoco-monitor/laser-maze/game-status.json — atomic status refreshed on significant change or every 10 seconds.
- ~/zoco-monitor/laser-maze/active-game.json — unfinished session/recovery record.
- ~/zoco-monitor/device-config.json — existing credential, never archived.

No player identifiers, RFID tags, passwords, private keys or raw keypad codes are reported. Only key objective progress is reported.

## Reports

All reports mark bench_prototype true and fast_demo explicitly. Named events bench_game_started and bench_game_result include a unique session ID, selected mode, configured beam count/timings and versions. Final result includes outcome, elapsed running seconds excluding startup, total breaks, key progress and objective completion. A blocked start is a recorded attempted session, not a visitor completion. Abrupt process loss is recovered on the next game-process launch as interrupted, with unconfirmed duration/break count represented as null. Already finalized results keep their prior content/ID.

Status metrics include actual cached button/latch levels; requested beam outputs and RGB color; countdown, mode and phase; per-process bench start/result counts; controller/keypad availability and versions. Requested outputs are not presented as independently measured physical readiness. Serial/keypad failures report faulted with fixed reasons; blocked startup reports faulted. Graceful program exit reports unknown/stopped. The uploader treats a status file older than 120 seconds as unknown. A crash may therefore leave the last ready/running status visible for up to that existing staleness limit.

The game emits status events on significant changes, not every countdown tick. Heartbeats upload their current snapshots every minute; the uploader attempts backlog delivery on its existing cadence (typically up to 30 seconds before the next attempt, plus network time). The portal is not a live sub-second countdown. Persistent counts across all sessions can be derived from archived result events later; current bench counts are labeled since process start. These bench events deliberately do not claim production usage totals.

## Installation after release deployment

1. Copy releases/pi/zoco-game-reports.service to the Pi and install into /etc/systemd/system. Enable it. Its current symlink points to the verified deployed game_reporting.py.
2. Add a systemd override to existing zoco-monitor with:

```ini
[Service]
ExecStart=
ExecStart=/usr/bin/python3 /home/brent/zoco-monitor/zoco_agent.py /home/brent/zoco-monitor/device-config.json run --status-file /home/brent/zoco-monitor/laser-maze/game-status.json
```

3. Reload systemd, restart only zoco-monitor, enable/start zoco-game-reports. Verify both active and inspect logs. This changes the heartbeat status source; it does not modify configuration/credentials, Arduino permissions, remote access or release-sync service.
4. Run panel_game.py --fast and verify one session start/result and status metrics in Laser Maze detail. Test stop and communication faults only on the bench. Result uploads and game controls are separate checks.

For later deployments, the bridge has no physical output controls. It may continue with its existing loaded code after the current link changes; restart it after a release that changes the bridge. Use a new release label if source changes.

## Validation

Unit checks cover results/status persisted without network access; countdown event throttling; interruption recovery; commit-before-unlink retry deduplication; private file permissions; stopped/fault states. Existing gameplay/deployment checks also pass locally. Tests do not prove the deployed service configuration, disk write latency, MySQL ingestion or dashboard display; perform the live acceptance steps.
