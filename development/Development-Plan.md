# Laser Maze: Raspberry Pi and Arduino development

Status: proposed architecture, October 12, 2026. User selected Raspberry Pi 5 and Arduino UNO R4 Minima for the first prototype, with a Mega planned for a later prototype. Field electrical interfaces are pending confirmation. No installation wiring or hardware-tested firmware is supplied by this plan.

## Responsibilities

| Raspberry Pi | Arduino |
|---|---|
| Authoritative game state, timer, scoring, four mode definitions | Conditioned and debounced beam, switch, door and objective inputs |
| Operator interface, RFID authorization policy and mode selection | Laser enable outputs through appropriate drivers |
| Display, audio, configuration and local event logs | Output defaults, command validation and communication watchdog |
| Bluehost database / exhibit management portal integration | Hardware status snapshots and timestamped input events |

Use USB serial between the Raspberry Pi 5 and Arduino UNO R4 Minima for the first prototype. Keep board-specific pin assignments separate from the game rules. Use one simulated beam input and one test LED output initially. A Mega is planned for a later prototype with more I/O; confirm the exact Mega model and field signal interfaces before assigning installation pins. Keep firmware portable through standard Arduino APIs; the R4 and Mega use different processors, so processor-specific libraries require review during migration.

Initial bench pin proposal: D2 for a pushbutton connected to GND with INPUT_PULLUP (pressed means beam broken), and LED_BUILTIN for the simulated laser output. Connect the boards by USB rather than their GPIO serial pins. Use a data-capable USB cable. Physical receiver wiring remains pending electrical verification.

UNO R4 Minima reference: https://docs.arduino.cc/hardware/uno-r4-minima/

Arduino Mega reference: https://docs.arduino.cc/hardware/mega-2560/
Raspberry Pi serial/electrical reference: https://www.raspberrypi.com/documentation/computers/configuration.html

## Behavior baseline

Derived from `LaserMaze-Findings.md`, which documents static analysis rather than measured installation behavior:

- 15 configured laser/receiver pairs.
- USB objective and keyswitch objective, each with a normal and break-all variant.
- Normal modes lose on the third detected break; affected beams turn off for 7 seconds and then receive a 5-second warmup before monitoring resumes.
- Break-all modes require both the objective and all configured beams broken, in either order. Track a completion mask explicitly.
- Key order: 1, 3, 2, 4. Incorrect keys do not advance progress.
- 5-second startup and 150-second running period.
- RFID plus mode code starts a game in the legacy system. The authorization policy needs a deliberate decision.
- Define Idle, Starting, Running, Finished and Fault states. Recovery from Fault requires an explicit operator action and successful readiness checks.

Proposed improvement: startup obstruction or a missing receiver prevents Running and reports the affected channel. Switch releases must not count as new objective actions. Door and lock behavior need installation verification before implementation.

## First milestone: one beam

Before the beam prototype, provision the Raspberry Pi 5 with Raspberry Pi OS including a desktop, remote terminal access through SSH, and remote desktop access. Prefer Raspberry Pi Connect for remote shell/screen sharing if compatible with the selected OS/session; keep local-network SSH available for maintenance. Verify access after reboot, use SSH keys, and do not expose SSH or desktop ports directly to the public internet. Record recovery access and service setup in the deployment documentation.

Install Arduino CLI and the UNO R4 board package on the Pi. Provide an update command that stops gameplay, disables outputs, releases serial access, compiles/uploads firmware, discovers the reconnected board, verifies protocol/firmware versions, and leaves the system disarmed. On failure, keep gameplay stopped and report diagnostics.

Stage Bluehost integration during initial provisioning: identify the existing portal/API and database schema, configure an exhibit credential outside source code, and test authentication plus a simulated result against a test endpoint. Production access remains dependent on the actual portal details and authorized credentials. The recommended connection is HTTPS to a server-side API rather than direct remote database access. Do not create production tables or modify the existing schema before inspecting it.

1. Build a Pi game engine with a simulated hardware adapter, so timing and game rules can be exercised without physical equipment.
2. Implement an Arduino bench sketch for one conditioned receiver input and one driver output, initially using a test LED as the output load.
3. Implement a bounded serial protocol with version handshake, command IDs, acknowledgments, input sequence numbers and periodic complete input/output snapshots.
4. Pi sends a heartbeat every 250 ms. Proposed Arduino timeout is 1 second; on timeout, reset, malformed session or explicit stop, disable laser and hazer outputs and report a fault. Validate these timings at the bench.
5. Reconnection starts a new disarmed session; it never resumes an interrupted game automatically. Acknowledgments report applied output state. Stale commands from an earlier session are rejected.
6. Replace the test LED with one actual laser/receiver pair only after verifying power, receiver signal levels, polarity and the driver interface.

Acceptance: start a simulated game, observe one physical break, confirm one score event per validated break, confirm beam recovery timing, then disconnect USB and confirm the Arduino disables the beam within the watchdog deadline. Restart either controller and confirm the system remains disarmed.

## Next milestones

1. Full 15-beam I/O and diagnostics, including mapping validation and simultaneous breaks.
2. Keyswitch and USB objective signals; test both objective completion orders in break-all modes.
3. RFID, operator controls, display and audio.
4. Verified LED panel interface and hazer control. The legacy hazer uses an analog control voltage; it cannot be driven directly by a GPIO pin.
5. Door/lock integration after documenting electrical fail state, emergency release and independent free egress. Emergency release must not depend on Pi software or the serial connection.
6. Installation acceptance, replaceable connector documentation, service startup, backup/restore and any confirmed result reporting integration.

## Hardware survey before pin assignments

Record the board models and, for each device, its label/model, power supply, connector, signal voltage, active polarity and existing driver/interface:

| Device | Needed information |
|---|---|
| Lasers and receivers | Quantity, supply, receiver output type, enable interface, cable lengths |
| Four keyswitches, USB objective, stop and door sensor | Dry contact vs powered signal; polarity; behavior when disconnected |
| RFID | Reader model, tag type and host connection |
| LED panels | Controller, pixel type, count, ordering and supply |
| Hazer | Model, control connector, voltage range and enable behavior |
| Door lock | Supply, driver, energized state, emergency release and free egress |
| Audio/display | Existing amplifier/speakers and screen connections |

Legacy Phidget channel numbers are logical channel references, not Arduino pins. Do not connect field wiring directly to a new board based on those numbers. Outputs require suitable drivers; inputs require compatible signal conditioning.

## Proposed software organization

```text
development/
  pi/          game engine, serial adapter, operator interface
  arduino/     board-specific firmware and I/O drivers
  config/      versioned gameplay and channel settings
  protocol/    serial message specification
  tests/       simulation and communication fault tests
  docs/        verified wiring, connectors and service procedures
```

Implement the simulation before committing to a board pin map. Keep source reference files unchanged.

## Bluehost database and exhibit management portal

October 13 update: user confirmed Pi access through Tailscale SSH (`ssh laser-maze`, username `brent`, IP `100.64.0.10`), SSH-key login and TigerVNC. The hostname is now `lasermaze`. The existing ZoCo agent's setup upload/retry test succeeded, remote access references were saved, and the monitoring service was confirmed active after reboot.

The UNO R4 Minima is attached by USB; Arduino CLI and renesas_uno 1.6.0 are installed. User verified USB firmware uploads, heartbeat-controlled LED shutdown and an active-high powered button module on D2. This is a bench test, not verified field receiver wiring.

Release archive and deployment tracking is prepared under `development/releases/`. It adds private archives and administrator-only downloads to the existing portal with an additive migration. The deployment command archives before flashing, verifies versions/disarmed state, keeps local/Mac copies and queues final reports for retry. It is locally tested but awaits Bluehost access/setup and live Pi validation. It targets bench firmware; production game-service deployment and automatic rollback remain future work.

Existing implementation identified from the chats “Set up remote status logging” and “Add Raspberry Pi booth monitoring,” and their saved `portal/SETUP.md` and `booth-monitoring/VALIDATION.md` in the Ultimate Design Challenge workspace. Reuse the existing ZoCo portal at https://manage.zocoexhibits.com and its `zoco_agent.py` transport rather than build a separate uploader or database.

The saved protocol registers an exhibit component through Manage → Connect a component, generates a private device configuration, uploads to the HTTPS ingestion endpoint, and persists events in a local SQLite queue with duplicate acknowledgment. Laser Maze needs its own component credential and queue; do not reuse the booth or simulator identity. The controller should atomically refresh its own status JSON, and the uploader should read it through `--status-file`. The current agent treats status older than two minutes as unknown. Heartbeat connectivity alone must not imply the maze hardware is ready.

Reuse the existing setup-test, simulated status, fault, and offline queue checks before integrating real game events. Inspect the agent and server validation rules before defining Laser Maze payloads. The saved booth validation describes a prepared reporting implementation; it does not establish live deployment or successful Laser Maze integration.

Remote access context: the Ultimate Design Challenge chat records working SSH through Tailscale. Follow that established access approach for the Laser Maze Pi; select desktop access compatible with its OS/session and test access after reboot. Raspberry Pi Connect remains an option, not an additional required remote-access platform.

User requirement added October 12, 2026: the finished system should communicate with the Bluehost database and exhibit management portal. A saved protocol and agent are available; current deployed schema/API versions and the new Laser Maze credential still need verification.

Proposed architecture: Arduino → Raspberry Pi → authenticated HTTPS API → database and portal. The Pi handles all remote communication. Prefer a portal API over exposing the database directly to the exhibit; if the portal has no suitable API, add a small server-side endpoint compatible with its existing application.

Design the Pi integration as a separate adapter from the start:

- Store completed game results locally before sending them. Assign each result a unique event ID so retries cannot create duplicate records on the server.
- Queue records during network outages and retry with backoff. Restarting the Pi must preserve unsent records. Gameplay remains available when the portal is unavailable, unless a future authorization policy explicitly requires otherwise.
- Proposed result fields: exhibit ID, game/session ID, mode, start/end time, elapsed duration, break count, outcome, software version and optional approved player identifier. Confirm fields and privacy requirements against the actual portal before implementation.
- Send periodic exhibit health information separately from game results: controller connectivity, faults, software version and last successful synchronization. Frequency remains configurable.
- Keep API credentials outside source code, authenticate each exhibit, and use HTTPS with certificate validation.
- If the portal will supply settings, validate and version them, and apply gameplay changes between games. Remote commands and remote start are separate requirements that have not been requested.

First integration milestone: send a simulated completed game to a test endpoint, then demonstrate queued delivery after an outage and duplicate prevention on retries. Use test records before connecting to the production database.

Needed next: portal URL/application name, existing API documentation or backend source, database type and schema, required reporting fields, whether player identification/authorization is part of the integration, and whether the portal should only receive data or also supply settings. Do not place passwords or API keys in this planning document.
