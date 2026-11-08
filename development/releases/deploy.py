#!/usr/bin/env python3
"""Build, archive and deploy the Laser Maze bench controller on its Pi.

Stops the managed game before uploads; other serial users still block uploads.
This tool does not deploy door, hazer or installation hardware firmware.
"""
import argparse
import base64
import datetime
from contextlib import contextmanager
import fcntl
import hashlib
import io
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
import time
import urllib.parse
import urllib.request
import uuid

FQBN = "arduino:renesas_uno:minima"
BOARDS = {"minima": FQBN, "mega": "arduino:avr:mega:cpu=atmega2560"}
SOURCES = ("arduino/BenchController/BenchController.ino", "arduino/BenchController/InputPanel.h", "arduino/BenchController/ReceiverConfig.h", "pi/beam_monitor.py", "pi/bench_test.py", "pi/game_engine.py", "pi/game_test.py", "pi/panel_test.py", "pi/panel_game.py", "pi/game_reporting.py", "pi/game_audio.py", "pi/maintenance.py", "pi/maintenance_bridge.py", "pi/receiver_calibrate.py", "pi/operator_settings.py", "tools/install-maintenance-reboot.sh")
SOURCES += tuple('pi/audio/'+name+'.wav' for name in ('preparation','entrance','warning90','warning30','warning10','beam','win_keys','win_usb','beam_loss','timeout')) + ('pi/audio/provenance.json',)
NANO_SOURCES = tuple('arduino/LaserModuleNano/'+name for name in ('LaserModuleNano.ino','ModuleState.h','README.md'))
SOURCES += ("pi/usb_objective.py", "pi/usb_rfid.py", "pi/hazer_dmx.py", "pi/tank_level.py", "tools/set-reader-silent.py", "tools/49-zoco-acr1552.rules")
SOURCES += NANO_SOURCES + ("arduino/BenchController/RfidReader.h", "pi/entry_authorization.py")


def nano_metadata(source):
    text = (source / 'arduino/LaserModuleNano/LaserModuleNano.ino').read_text()
    match = re.search(r'const char VERSION\[\] = "([A-Za-z0-9._-]+)";', text)
    if not match:
        raise ValueError('Nano source is missing a version declaration')
    return dict(firmware_version=match.group(1), fqbn='arduino:avr:nano:cpu=atmega328',
        upload_method='manual_usb', installed_version='unverified',
        sketch='source/arduino/LaserModuleNano/LaserModuleNano.ino')


VERSION = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}\Z")


@contextmanager
def managed_game(state):
    """Serialize upload lifecycle, stop before taking the controller lock.

    Resume only after a successful deployment and after the controller lock closes.
    A failed/terminated deployment deliberately leaves the service stopped.
    """
    with (state / "upload.lock").open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise RuntimeError("Another upload is already running")
        check = subprocess.run(["/usr/bin/systemctl", "show", "zoco-game.service",
            "--property=LoadState", "--value"], capture_output=True, text=True)
        load = check.stdout.strip()
        if load == "not-found":
            yield
            return
        if check.returncode or load != "loaded":
            raise RuntimeError("Cannot inspect the managed game service")
        active = subprocess.check_output(["/usr/bin/systemctl", "show", "zoco-game.service",
            "--property=ActiveState", "--value"], text=True).strip()
        resume = active in ("active", "activating", "reloading")
        subprocess.run(["sudo", "-n", "/usr/bin/systemctl", "stop", "zoco-game.service"], check=True)
        print("Game service stopped for upload.", flush=True)
        try:
            yield
        except BaseException:
            print("Upload incomplete; game service remains stopped. Inspect the result before restarting.", flush=True)
            raise
        if resume:
            subprocess.run(["sudo", "-n", "/usr/bin/systemctl", "start", "zoco-game.service"], check=True)
            print("Game service restarted; waiting for physical Start input.", flush=True)


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, *args, **kwargs):
        raise ValueError("Redirect rejected; configure the final HTTPS endpoint")


def digest(data):
    return hashlib.sha256(data).hexdigest()


def write_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    fd, name = tempfile.mkstemp(dir=path.parent, prefix=".pending-")
    try:
        with os.fdopen(fd, "w") as out:
            json.dump(data, out, indent=2)
            out.flush()
            os.fsync(out.fileno())
        os.replace(name, path)
        directory = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(directory)
        finally:
            os.close(directory)
    finally:
        if os.path.exists(name):
            os.unlink(name)


class Portal:
    def __init__(self, config):
        self.config = json.loads(Path(config).expanduser().read_text())
        parsed = urllib.parse.urlsplit(self.config["url"])
        if (parsed.scheme != "https" or not parsed.hostname or parsed.username or
                parsed.password or parsed.query or parsed.fragment):
            raise ValueError("Use the existing final HTTPS portal configuration")
        self.url = urllib.parse.urljoin(self.config["url"], "release-api.php")
        if len(self.config.get("upload_key", "")) < 48:
            raise ValueError("Invalid component configuration")

    def post(self, body):
        body = dict(body, device_id=self.config["device_id"])
        req = urllib.request.Request(self.url, json.dumps(body).encode(),
            {"Content-Type": "application/json", "Accept": "application/json",
             "X-ZoCo-Key": self.config["upload_key"], "User-Agent": "ZoCo-Releases/1.0"})
        with urllib.request.build_opener(NoRedirect).open(req, timeout=60) as response:
            return json.loads(response.read(65536))

    def archive(self, release):
        data = (release / "release.tar.gz").read_bytes()
        if len(data) > 8_000_000:
            raise ValueError("Release exceeds the 8 MB archive limit")
        manifest = json.loads((release / "manifest.json").read_text())
        result = self.post(dict(action="archive", manifest=manifest,
            sha256=digest(data), archive=base64.b64encode(data).decode("ascii")))
        if result.get("archived") != manifest["version"] or result.get("sha256") != digest(data):
            raise ValueError("Portal did not acknowledge the archive checksum")


def sync_reports(portal, reports):
    for path in sorted(reports.glob("*.json")):
        body = json.loads(path.read_text())
        result = portal.post(body)
        if (result.get("deployment_id") != body["deployment_id"] or
                result.get("accepted") != body["status"]):
            raise ValueError("Portal did not acknowledge deployment report")
        path.unlink()  # Already durable in portal; unsent records stay on disk.


def save_report(reports, deployment_id, version, status, **extra):
    # Separate ordered files preserve the started record before its final result.
    order = "0" if status == "started" else "1"
    path = reports / f"{deployment_id}-{order}.json"
    write_json(path, dict(action="deployment", deployment_id=deployment_id,
        version=version, status=status, **extra))
    return path


def run(*args):
    subprocess.run([str(a) for a in args], check=True)


def build(source, release, version, notes, fqbn=FQBN):
    if fqbn not in BOARDS.values():
        raise ValueError("Unsupported controller board")
    if not VERSION.fullmatch(version) or len(notes.encode()) > 2000:
        raise ValueError("Invalid release version or notes")
    if release.exists():
        # Reuse an exact saved build after a network/upload failure; never rebuild
        # different bytes under a previously assigned version.
        manifest = json.loads((release / "manifest.json").read_text())
        if (manifest.get("version") != version or manifest.get("notes") != notes or
                manifest.get("fqbn") != fqbn):
            raise ValueError("Existing release differs; use a new version")
        for name in SOURCES:
            expected = manifest["files"].get("source/" + name)
            if (source / name).is_symlink() or digest((source / name).read_bytes()) != expected:
                raise ValueError("Source changed; use a new release version")
        with tarfile.open(release / "release.tar.gz") as archive:
            if set(archive.getnames()) != set(manifest["files"]) | {"manifest.json"}:
                raise ValueError("Saved archive file list mismatch")
            if json.loads(archive.extractfile("manifest.json").read()) != manifest:
                raise ValueError("Saved archive manifest mismatch")
            for name, checksum in manifest["files"].items():
                if (".." in name or not re.fullmatch(r"(?:source|compiled)/[A-Za-z0-9_./-]+", name) or
                        digest(archive.extractfile(name).read()) != checksum or
                        digest((release / name).read_bytes()) != checksum):
                    raise ValueError("Saved release checksum mismatch")
        return manifest
    release.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    with tempfile.TemporaryDirectory(dir=release.parent, prefix=".build-") as temp:
        work = Path(temp)
        for name in SOURCES:
            original = source / name
            # Explicit source allowlist; never include device-config, keys or queues.
            if original.is_symlink() or not original.is_file():
                raise ValueError(f"Expected regular source file: {name}")
            data = original.read_bytes()
            if len(data) > 1_000_000:
                raise ValueError("Unexpected oversized source")
            target = work / "source" / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(data)
            if name.endswith(".py"):
                compile(data, name, "exec")
        sketch = work / "source/arduino/BenchController"
        text = (sketch / "BenchController.ino").read_text()
        match = re.search(r'const char VERSION\[\] = "([A-Za-z0-9._-]+)";', text)
        if not match:
            raise ValueError("Firmware has no supported version declaration")
        firmware_version = match.group(1)
        python_version = subprocess.check_output([sys.executable,
            str(work / "source/pi/beam_monitor.py"), "--version"], text=True).strip()
        if not VERSION.fullmatch(python_version):
            raise ValueError("Python version check failed")
        for name in ("beam_monitor.py", "bench_test.py", "game_test.py", "panel_test.py", "panel_game.py"):
            if f"HELLO 1 {firmware_version}" not in (work / "source/pi" / name).read_text():
                raise ValueError("Python and firmware protocol versions disagree")
        game_version = subprocess.check_output([sys.executable,
            str(work / "source/pi/game_test.py"), "--version"], text=True).strip()
        if game_version != python_version:
            raise ValueError("Game runner and monitor versions disagree")
        panel_version = subprocess.check_output([sys.executable,
            str(work / "source/pi/panel_test.py"), "--version"], text=True).strip()
        if panel_version != python_version:
            raise ValueError("Panel diagnostic version mismatch")
        panel_game_version = subprocess.check_output([sys.executable,
            str(work / "source/pi/panel_game.py"), "--version"], text=True).strip()
        if panel_game_version != python_version:
            raise ValueError("Physical-panel game version mismatch")
        compiled = work / "compiled"
        compiled.mkdir()
        build_flags = []
        reader_header = sketch / 'RfidReader.h'
        if reader_header.exists():
            speed = re.search(r'^#define MFRC522_SPICLOCK \((\d+)u\)', reader_header.read_text(), re.M)
            if speed:
                hz = int(speed.group(1))
                if not 1000 <= hz <= 4000000:raise ValueError('Invalid RFID SPI clock')
                # Library .cpp is compiled separately: a sketch-only define is insufficient.
                build_flags = ['--build-property', 'compiler.cpp.extra_flags=-DMFRC522_SPICLOCK='+str(hz)+'u']
        run("arduino-cli", "compile", "--fqbn", fqbn, *build_flags, "--output-dir", compiled, sketch)
        files = {}
        for path in sorted(work.rglob("*")):
            if not path.is_file() or "__pycache__" in path.parts:
                continue
            relative = path.relative_to(work).as_posix()
            if relative.startswith("compiled/") and path.suffix not in (".bin", ".hex", ".elf"):
                continue
            files[relative] = digest(path.read_bytes())
        if not any(p.startswith("compiled/") and p.endswith(".hex" if fqbn == BOARDS["mega"] else ".bin") and not p.endswith(".with_bootloader.hex") for p in files):
            raise ValueError("Compiler produced no firmware binary")
        manifest = dict(format=1, version=version, notes=notes, fqbn=fqbn,
            nano_modules=nano_metadata(work / "source"),
            firmware_version=firmware_version, python_version=python_version,
            created_at=datetime.datetime.now(datetime.timezone.utc).isoformat(),
            arduino_cli=subprocess.check_output(["arduino-cli", "version"], text=True).strip(),
            arduino_cores=subprocess.check_output(["arduino-cli", "core", "list"], text=True).strip(),
            arduino_libraries=subprocess.check_output(["arduino-cli", "lib", "list"], text=True).strip(),
            files=files)
        (work / "manifest.json").write_text(json.dumps(manifest, indent=2))
        with tarfile.open(work / "release.tar.gz", "w:gz") as archive:
            for name in ["manifest.json", *files]:
                data = (work / name).read_bytes()
                info = tarfile.TarInfo(name)
                info.size = len(data)
                info.mode = 0o600
                archive.addfile(info, io.BytesIO(data))
        if (work / "release.tar.gz").stat().st_size > 8_000_000:
            raise ValueError("Release exceeds server archive limit")
        # Retain only allowlisted source/build assets and manifest locally as well.
        keep = set(files) | {"manifest.json", "release.tar.gz"}
        for path in work.rglob("*"):
            if path.is_file() and path.relative_to(work).as_posix() not in keep:
                path.unlink()
        os.rename(work, release)
        return manifest


def exchange(port, command, expected):
    port.write((command + "\n").encode())
    port.flush()
    line = port.readline().decode("ascii", errors="replace").strip()
    if line != expected:
        raise RuntimeError("Arduino response verification failed")


def verify_firmware(device, version):
    import serial
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        try:
            with serial.Serial(str(device), 115200, timeout=2, write_timeout=2) as port:
                time.sleep(2)
                port.reset_input_buffer()
                exchange(port, "HELLO", f"HELLO 1 {version}")
                exchange(port, "STATUS", "STATUS DISARMED OFF")
                return
        except (serial.SerialException, RuntimeError, OSError):
            time.sleep(0.5)
    raise RuntimeError("Firmware version or disarmed-state verification failed")


def preflight(device):
    import serial
    if not device.exists():
        raise ValueError("Arduino device is missing")
    if not shutil.which("fuser"):
        raise ValueError("Install psmisc for serial ownership checks")
    occupied = subprocess.run(["fuser", str(device.resolve())], capture_output=True)
    if occupied.returncode == 0:
        raise ValueError("Stop the bench monitor before deploying; serial port is busy")
    if occupied.returncode != 1:
        raise ValueError("Cannot check serial ownership")
    with serial.Serial(str(device), 115200, timeout=2, write_timeout=2) as port:
        time.sleep(2)
        port.reset_input_buffer()
        exchange(port, "OFF", "OK OFF")
        exchange(port, "STATUS", "STATUS DISARMED OFF")


def first_upload_preflight(device):
    # A blank board cannot answer the old HELLO protocol. Never bypass USB identity.
    if not device.exists() or not shutil.which("fuser"):
        raise ValueError("Mega device or serial ownership checker missing")
    occupied = subprocess.run(["fuser", str(device.resolve())], capture_output=True)
    if occupied.returncode != 1:
        raise ValueError("Mega serial port is busy or cannot be checked")
    listing = json.loads(subprocess.check_output(["arduino-cli", "board", "list", "--format", "json"], text=True))
    matches = [p for p in listing.get("detected_ports", []) if p.get("port", {}).get("address") == str(device.resolve())]
    if len(matches) != 1 or not any(b.get("fqbn") == "arduino:avr:mega" for b in matches[0].get("matching_boards", [])):
        raise ValueError("First upload requires a positively identified Mega 2560")


def deploy(args, portal, state):
    device = Path(args.port)
    if not str(device).startswith("/dev/serial/by-id/"):
        raise ValueError("Use the stable /dev/serial/by-id/ Arduino path")
    fqbn = BOARDS[getattr(args, "board", "minima")]
    stage_only = getattr(args, "stage_only", False)
    if getattr(args, "first_upload", False):
        if fqbn != BOARDS["mega"] or not stage_only:
            raise ValueError("First upload must target the Mega and use --stage-only")
        first_upload_preflight(device)
    else:
        preflight(device)
    release = state / "releases" / args.version
    manifest = build(Path(args.source).expanduser(), release, args.version, args.notes, fqbn=fqbn)
    print("Release built and retained locally. Archiving to portal before upload.", flush=True)
    portal.archive(release)
    reports = state / "pending"
    sync_reports(portal, reports)
    deployment_id = str(uuid.uuid4())
    save_report(reports, deployment_id, args.version, "started")
    sync_reports(portal, reports)  # Do not flash without server acknowledgment.
    stage = "upload"
    try:
        run("arduino-cli", "upload", "--port", device.resolve(), "--fqbn", fqbn,
            "--input-dir", release / "compiled", release / "source/arduino/BenchController")
        stage = "firmware_verification"
        verify_firmware(device, manifest["firmware_version"])
        stage = "python_verification"
        installed = subprocess.check_output([sys.executable,
            str(release / "source/pi/beam_monitor.py"), "--version"], text=True).strip()
        if installed != manifest["python_version"]:
            raise RuntimeError("Installed Python version mismatch")
        game_installed = subprocess.check_output([sys.executable,
            str(release / "source/pi/game_test.py"), "--version"], text=True).strip()
        if game_installed != installed:
            raise RuntimeError("Installed game runner version mismatch")
        panel_installed = subprocess.check_output([sys.executable,
            str(release / "source/pi/panel_test.py"), "--version"], text=True).strip()
        if panel_installed != installed:
            raise RuntimeError("Installed panel diagnostic version mismatch")
        panel_game_installed = subprocess.check_output([sys.executable,
            str(release / "source/pi/panel_game.py"), "--version"], text=True).strip()
        if panel_game_installed != installed:
            raise RuntimeError("Installed physical-panel game version mismatch")
        target = dict(version=args.version, firmware_version=manifest["firmware_version"],
            python_version=installed, deployment_id=deployment_id, fqbn=fqbn, port=str(device))
        if stage_only:
            stage = "staging"
            write_json(state / "staged-controller.json", target)
        else:
            stage = "activation"
            temporary_link = state / ".current-next"
            if temporary_link.is_symlink(): temporary_link.unlink()
            temporary_link.symlink_to(release / "source/pi", target_is_directory=True)
            os.replace(temporary_link, state / "current")
            write_json(state / "installed.json", target)
        save_report(reports, deployment_id, args.version, "verified",
            firmware_version=manifest["firmware_version"], python_version=installed)
        print("Mega firmware verified and disarmed; service migration pending." if stage_only else "Versions verified; Arduino is disarmed. Python current link updated.", flush=True)
    except BaseException:
        write_json(state / ("staged-controller.json" if stage_only else "installed.json"), dict(version=None, state="unconfirmed",
            deployment_id=deployment_id, reason=stage))
        save_report(reports, deployment_id, args.version, "failed", reason=stage)
        try:
            sync_reports(portal, reports)
        except Exception:
            print("Failure report retained locally; run sync when online.", flush=True)
        raise
    try:
        sync_reports(portal, reports)
    except Exception:
        print("Deployment verified locally; portal report pending. Run sync when online.", flush=True)


def main():
    os.umask(0o077)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", default="~/zoco-monitor/device-config.json")
    parser.add_argument("--state", default="~/laser-maze/deployments")
    sub = parser.add_subparsers(dest="command", required=True)
    deployment = sub.add_parser("deploy")
    deployment.add_argument("--source", required=True, help="Folder containing arduino/ and pi/")
    deployment.add_argument("--version", required=True)
    deployment.add_argument("--notes", required=True)
    deployment.add_argument("--port", required=True)
    deployment.add_argument("--board", choices=BOARDS, default="mega")
    deployment.add_argument("--first-upload", action="store_true", help="Identified blank Mega only; requires --stage-only")
    deployment.add_argument("--stage-only", action="store_true", help="Verify target board without changing current Python/service")
    sub.add_parser("sync", help="Retry durable deployment reports; never flashes firmware")
    args = parser.parse_args()
    state = Path(args.state).expanduser().resolve()
    state.mkdir(parents=True, exist_ok=True, mode=0o700)
    try:
        portal = Portal(args.config)
        if args.command == "sync":
            # Delivery does not own the serial port or interrupt gameplay.
            with (state / "reports.lock").open("a") as lock:
                fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
                sync_reports(portal, state / "pending")
            print("Pending deployment reports synchronized.")
        else:
            if not VERSION.fullmatch(args.version):
                raise ValueError("Invalid release version")
            with managed_game(state):
                with (state / "deploy.lock").open("a") as controller, (state / "reports.lock").open("a") as reports:
                    fcntl.flock(controller, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    fcntl.flock(reports, fcntl.LOCK_EX | fcntl.LOCK_NB)
                    deploy(args, portal, state)
    except KeyboardInterrupt:
        parser.exit(1, "Interrupted; check deployment history before assuming installation state.\n")
    except Exception as exc:
        # Never print HTTP bodies/configuration containing private information.
        detail = f": {exc}" if isinstance(exc, (ValueError, RuntimeError)) else ""
        http = f" HTTP {exc.code}" if hasattr(exc, "code") else ""
        parser.exit(1, f"Deployment incomplete ({type(exc).__name__}{http}){detail}. Local releases/reports retained.\n")


if __name__ == "__main__":
    main()
