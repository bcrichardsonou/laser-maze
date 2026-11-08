# Automatic bench game service

Service name: zoco-game.service. Default game timing is normal (150 seconds); starts in USB mode with outputs off and waits for keypad A. Keys 1–4 select modes, D stops a game. Selecting a mode/game never starts automatically after reboot, service restart or crash. Raspberry Pi reporting services are independent.

SIGTERM uses the same output-OFF and stopped-result/status cleanup as Ctrl-C. The Arduino watchdog remains a separate fallback if the process crashes or cannot send OFF. systemd retries startup every 10 seconds, including when the Arduino is initially disconnected. Interrupted active sessions are recovered by the existing reporting outbox. No game may auto-resume after interruption.

Deployments serialize service lifecycle with upload.lock, stop the service before acquiring deploy.lock, archive before flashing, verify both versions, and resume a previously running service after controller lock release. A deliberately stopped service remains stopped. Any failed deployment stays stopped for review, even if failure happened before flashing. Report-only sync uses reports.lock and does not stop or compete with the game controller. If the uploader is killed or the Pi loses power, inspect deployment history and installed.json before restarting; this workflow is not an automatic rollback system.

The narrow sudoers rule allows only /usr/bin/systemctl stop/start zoco-game.service for brent, so the existing one-command Mac deployment does not require an interactive password. Unit/policy installation still requires sudo. It grants no generic service-management commands and never puts passwords in scripts.

## Operate from Mac

Connect with `ssh laser-maze`. On the Pi:

```bash
systemctl status zoco-game --no-pager -l
journalctl -u zoco-game -n 30 --no-pager
sudo /usr/bin/systemctl stop zoco-game.service
sudo /usr/bin/systemctl start zoco-game.service
```

Stop the service before running serial diagnostics manually. Return to the service with start afterward. A normal service stop disables autorestart until explicitly started; it does not disable startup on the next boot. To disable startup use `sudo systemctl disable --now zoco-game.service` (requires the regular sudo password).

## Acceptance

Verify service active, fresh game phase idle, Arduino connected and normal timing in portal. Use A to start and D to stop; confirm a durable stopped result and return to idle. Confirm a second game and mode selection work without a terminal. Reboot and verify idle returns automatically. Stop/start service and verify OFF/stopped reporting; disconnect/reconnect Arduino and verify eventual idle recovery. Run a later versioned deployment while idle to confirm stop → verified upload → restart and continuing release-report synchronization. Live reboot, physical controls and disconnected-Arduino acceptance require observation and are not implied by unit tests.
