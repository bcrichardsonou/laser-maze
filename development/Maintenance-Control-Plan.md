# Administrator maintenance controls

Requested October 14, 2026. This is the control inventory and implementation plan, not an installed remote-control feature.

## Shared portal structure

Add an administrator-only Maintenance section to each exhibit dashboard, scoped to its selected reporting component. Viewing links and basic/staff views do not receive control buttons. Server authorization must enforce admin role, exhibit/component scope and CSRF validation for every mutation. Show only capabilities supported by the component. Keep this layout consistent across future exhibits; do not expose unrelated devices or imply an unimplemented button works.

## Candidate controls

| Group | Controls | Behavior |
|---|---|---|
| Exhibit operation | Enter/leave maintenance; stop current game; disable new starts; resume availability | Enter maintenance stops active play and turns game outputs off. Leaving maintenance returns to idle; no automatic new game. Disable-new-starts can let a current game finish. |
| Diagnostics | Request fresh snapshot; input/serial check; countdown display test | Report genuine connection status and observed input levels; distinguish requested output from physical feedback. |
| Audio | Select known clip; stop playback; volume; mute; selected output; voice/effect channel test | Retain fixed USB output; playback acknowledgment is not proof of audible output. Test events stay separate from visitor activity. |
| Ring lighting | Select one module/all; color; brightness; solid/pulse/chase; all lights off | Use bounded animations and brightness. Current bench has one pixel; 15-ring controls require a new firmware interface. |
| Lasers | Select a channel; short alignment pulse; selected output off; all outputs off; channel disable | Enable only in maintenance with readiness checks and a local time limit. Current beam outputs are simulated LEDs. No physical feedback claim without measured sensor confirmation. |
| Receiver calibration | Live light readings; record ambient and beam-present levels; thresholds/hysteresis; weak-alignment indication; channel enable/disable | Requires actual TEMT6000 wiring and analog firmware. Store versioned calibration per channel. Never adapt thresholds mid-game. |
| Game settings | Running/startup/cooldown/warmup durations; break limit; modes/objective order; enabled channels; demo mode | Validate limits and save a versioned configuration. Apply between games; show saved vs applied versions. Keep bench/demo statistics labeled. |
| Component services | Restart game program; service start/stop; restart reporting; reboot Pi | Explicit actions with status/result. Controller watchdog remains independent. Reboot disconnects the component; acknowledge restart acceptance separately from subsequent successful boot. |
| Software | Versions; deployment attempts; staged update; previous-release reinstall; source/archive downloads | Stored archive is not installed software. Rollback is a tested reinstall path, not a blind symlink change. Existing upload workflow remains authoritative until portal deployment is implemented. |
| Access and commissioning | Separate RFID reader status; tag enrollment/revocation; entry keypad test; input mapping | Requires actual reader, authorization policy and permission design. Do not expose tag identifiers on shared views. |
| Other actuators | Hazer readiness/test; door/lock/entrance indicator status and commissioned controls | Not implemented; electrical interfaces and local behavior must be defined before exposing these controls. Hardware emergency/egress behavior is independent of the portal. |

## First implementation on the bench

1. Add a command/request ledger and Pi-side authenticated HTTPS command delivery, component scoped, alongside the existing reporting API. Do not expose direct MySQL or inbound Pi ports.
2. Integrate local maintenance handling into the running game process, which owns serial. A second worker must never open the Arduino port while that process runs. Do not block the heartbeat/game loop on network requests.
3. Implement maintenance enter/leave, stop game, fresh status, known audio clip/stop/mute, current RGB pixel test/off, display test and current game-service restart.
4. Display requested, accepted, completed, failed, expired or unconfirmed status, with timestamps and a named result. Retain an audit trail of administrator, component and validated parameters. Never label a queued request as completed.
5. Physical tests require a deliberate local maintenance-enable input (or another agreed local enable mechanism) plus maintenance state. Output tests have a local expiry/off deadline even when the portal disconnects. Remote stop is an operational convenience, not a hardware emergency stop.
6. Add real laser/receiver and full ring controls only after their interfaces and acceptance tests exist. Each future exhibit declares supported actions and uses the same Maintenance presentation.

## Delivery and failure semantics

Use unique command IDs, validated allowlisted action names, short expirations for operational actions, and durable execution/result records. Reject stale/replayed/incorrect-component commands. Do not represent actions as ambiguous toggles; request explicit desired state. After component reconnect, do not execute expired starts or output-on tests. Avoid blind automatic retry of non-idempotent actions whose result is unknown. Persist settings separately from immediate commands.

Commands that energize an output execute only under the agreed local enable and maintenance rules. Local watchdog and test timers switch outputs off independently. If service restart or network loss prevents completion acknowledgment, label it unconfirmed until fresh state provides evidence. Browser buttons provide no real-time timing guarantee.

## Acceptance

Verify admin-only API access, CSRF and component isolation; replay and expiry handling; offline reconnect behavior; invalid parameter rejection; acknowledged vs physically measured state; local test timeout; cancel/all-off; simultaneous serial/LED/sensor/audio activity; unchanged gameplay outside maintenance; and durable audit/results. Production installation remains pending implementation and review of live portal source compatibility.
