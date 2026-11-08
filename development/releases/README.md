# Laser Maze release archive and deployment upgrade

Prepared locally; not uploaded to Bluehost or installed on the Pi yet.
The existing status uploader and portal files are unchanged.

## What this provides

- Private source + compiled firmware archives with SHA-256 checksums.
- Immutable version labels: the same label cannot replace different content.
- Administrator-only archive downloads and deployment history at `/releases.php`.
- A Pi command that compiles, archives, flashes, verifies, and selects Python files.
- Failures are recorded without claiming a version is installed. Interrupted attempts remain started/unconfirmed. Unsent final reports are persisted for retry.
- The Pi retains release packages as a second copy. Keep a copy on the Mac as well; this is not an automatic off-host disaster-recovery backup.

This first workflow supports the LED/button bench controller only. There is no production game service to stop/restart yet. Close the bench monitor before deployment. Firmware verification checks the reported version and disarmed output; Python verification checks source syntax and its version entry point. These checks do not replace hardware/game acceptance tests.

## 1. Prepare Bluehost

Use Bluehost's official SSH Access controls to enable SSH/SFTP if desired. Use a dedicated Mac public key for hosting, authorize only its public key, and keep its private key on the Mac. Record the hosting SSH hostname, username and port from Bluehost; do not guess them from the portal domain. SFTP is needed for initial portal installation, not for each later firmware upload. The Pi uploads archives through authenticated HTTPS.

Official guides:
- https://www.bluehost.com/help/article/ssh-access
- https://www.bluehost.com/help/article/sftp

Before the upgrade, export a database backup and back up the private config. Inspect the actual deployed portal and confirm it still defines the lib.php functions used by this add-on: cfg, db, q, one, transport, session_boot, require_admin, limit, json_reply, audit, header_page, footer_page. This package was built against the saved ZoCo portal; do not replace a changed production index.php with a saved copy.

Import **only** `portal/migration.sql` through phpMyAdmin into the existing ZoCo database. It adds two tables; it does not touch existing exhibit/event data. Do not import the original schema again.

Create a private `releases` directory beside the existing private config, for example:

```text
/srv/zoco/zoco-portal-private/releases
```

Confirm the actual account path. The directory must be writable by the PHP process and outside every website's document root. Start with mode 0700 where the PHP account owns it. Do not use 0777.

Add these entries inside the array in the existing private config.php, preserving every existing setting:

```php
'release_storage' => '/ACTUAL/ACCOUNT/PATH/zoco-portal-private/releases',
'release_components' => ['ACTUAL-LASER-MAZE-DEVICE-ID'],
```

Copy the device_id from the Pi's private device-config.json. This ID is not its upload key. Do not put the key or database password into these new entries. Only specifically opted-in component IDs can upload releases.

Upload only these **new** files into the portal website directory, alongside its existing lib.php:

```text
release-lib.php
release-api.php
releases.php
```

Use filenames exactly as supplied. No existing PHP, CSS, configuration, or status-agent file is overwritten. Open https://manage.zocoexhibits.com/releases.php while signed in as administrator; it should display an empty archive. Signed-out requests redirect to login; staff requests are denied.

The new page is part of the portal and uses its existing sign-in. Bookmark it initially. To place it in the existing navigation, add a link to `/releases.php` inside the admin-only navigation branch in the **live** lib.php. Inspect that file before editing; do not overwrite it with the reference copy. With SSH access established, we can make and verify that small change.

Server limits: 8 MB per compressed archive, 200 releases / 256 MB per component. PHP memory_limit should be at least 128 MB, post_max_size at least 16 MB, and Bluehost must allow the HTTPS JSON request through its hosting controls. The archive is stored opaque and never extracted or executed by PHP. Endpoint responses intentionally omit server paths and secrets. If an upload is rejected, do not disable HTTPS or server security globally; inspect the hosting error and adjust only the required endpoint/limit.

## 2. Copy source and tooling to the Pi

Create `~/laser-maze/source/arduino`, `~/laser-maze/source/pi` and `~/laser-maze/tools` on the Pi. Copy:

- development/arduino/BenchController → source/arduino/BenchController
- development/pi/beam_monitor.py and bench_test.py → source/pi/
- For game release 0.3.0, also copy development/pi/game_engine.py and game_test.py → source/pi/. The updated Mac wrapper includes these automatically.
- development/releases/deploy.py → tools/deploy.py

Install `python3-serial` and `psmisc` on the Pi. Arduino CLI, board support, and upload permissions are already configured. The existing ~/zoco-monitor/device-config.json is read locally and never added to a release.

Find the stable Arduino path with `ls -l /dev/serial/by-id/`. Do not use a changing ttyACM number for the deployment command. For this Pi the observed path is:

```text
/dev/serial/by-id/usb-Arduino_UNO_R4_Minima_EXAMPLE_UNO_SERIAL-if00
```

## 3. One deployment command on the Pi

Keep the button released; close the bench monitor with Control+C. With the portal upgrade installed:

```sh
python3 ~/laser-maze/tools/deploy.py deploy \
  --source ~/laser-maze/source \
  --version bench-release-0.2.1 \
  --notes "Active-high button input, debounce, USB heartbeat shutdown" \
  --port /dev/serial/by-id/usb-Arduino_UNO_R4_Minima_EXAMPLE_UNO_SERIAL-if00
```

The release label identifies the full package. Its separately verified Arduino and Python versions are bench-0.2.1. A new release label is required for each changed package. An unchanged command can retry its exact saved package after a failed network/upload attempt; all saved/source checksums are verified first. Reinstalling a prior archive from the portal is not automated in this first version: prior archives remain downloadable for an operator-controlled recovery. Do not assume the tool provides automatic rollback after a failed flash.

The command first disables the bench output, builds from an explicit source-file allowlist, records compiler/core versions, and saves a local release. It requires the portal to acknowledge the archive and started record before flashing. An archive/network failure prevents firmware upload. The Arduino is left disarmed after success. The Python test is selected through a `current` symlink but is not automatically run.

Test the installed Python files:

```sh
python3 ~/laser-maze/deployments/current/beam_monitor.py \
  /dev/serial/by-id/usb-Arduino_UNO_R4_Minima_EXAMPLE_UNO_SERIAL-if00
```

Final report delivery can fail independently of a successful flash. If so:

```sh
python3 ~/laser-maze/tools/deploy.py sync
```

This retries saved reports and never flashes firmware. After initial live validation, copy the supplied `pi/zoco-release-sync.service` and `pi/zoco-release-sync.timer` into `/etc/systemd/system/`, reload systemd and enable the timer. It retries final reports every two minutes. It shares the deployment lock, so a retry cannot overlap a deployment. These files are supplied but not installed automatically by this package.

### Single command from the Mac

The supplied `deploy_from_mac.py` combines source transfer, Pi deployment and a Mac archive copy. It uses the existing `laser-maze` SSH shortcut and this user's `/home/brent` Pi account. After the portal and Pi tools are set up:

```sh
python3 /ABSOLUTE/PATH/TO/development/releases/deploy_from_mac.py bench-release-0.2.1 \
  --notes "Active-high button input, debounce, USB heartbeat shutdown"
```

Use the actual path in this workspace. The stable USB device observed on this Pi is the default; supply `--port` when hardware is replaced. The command copies only allowlisted source files and the deployment tool. It never transfers the private portal credential. It retains an archive under `development/release-backups/<version>/` even if a built deployment later fails. If compilation failed before an archive existed, no archive can be copied. A failed Mac backup is reported separately from a successful Pi deployment.

For the new game test use release label `bench-game-0.3.0` and firmware/Python version `bench-0.3.0`. See `../pi/GAME-TEST.md` for the test run and timings. Do not deploy changed 0.3.0 source with an already archived 0.2.1 release label.

## 4. Acceptance before relying on it

1. Archive one release; download it through the portal and compare its SHA-256 to the local package.
2. Check the portal displays a verified deployment with both exact versions, and run the physical button/watchdog tests.
3. Try a changed package with an existing version label: it must be rejected without flashing.
4. With a new version label, block internet before archiving: upload must not proceed; the local archive remains.
5. Test retry delivery after a simulated report transport failure; one deployment record must remain, without duplicates.
6. Reboot and confirm status reporting, SSH, and VNC still work. This upgrade does not alter those services.

Do not perform a deliberate power interruption while flashing the physical board. Upload and verification failure paths are tested with simulated tools locally, and actual recovery requires a supervised bench check.

Release tracking is separate from heartbeat connectivity. The software releases page shows attempted/verified installations; the existing dashboard condition remains unknown until game status is connected. A new attempt with no verified result means current firmware is unconfirmed.

## Nano modules (October 16)
Future Mac-wrapper deployments also copy/archive arduino/LaserModuleNano/LaserModuleNano.ino, ModuleState.h and README.md. The manifest has an independent nano_modules firmware_version and manual_usb upload method; installed_version stays unverified. This does not flash Nanos or change the bench version checks. First combined source archive bench-with-nano-0.1.0 retains the previous verified bench files and adds Nano source; no deployment was performed. Manual Nano ZIP is development/arduino/LaserModuleNano-0.1.0.zip.

## Mega 2560 migration support (October 16)
The Mac wrapper now defaults to the identified Mega stable port and --board mega; --board minima plus an explicit Minima --port retains old target support. Builds validate target-specific hex/bin artifacts. For a new blank Mega only, --first-upload --stage-only positively checks USB board identity, archives before flashing, verifies disarmed protocol, and saves staged-controller.json without changing installed.json/current. After wiring transfer, the user runs the staged switch-to-mega.py script with sudo to update the service USB path while retaining audio overrides. Ordinary future uploads use the same wrapper without migration flags. Nano uploads remain manual.
