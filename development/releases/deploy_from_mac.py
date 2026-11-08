#!/usr/bin/env python3
"""Copy allowlisted source to the Pi, deploy it, and retain an archive on the Mac."""
import argparse
from pathlib import Path
import re
import shlex
import subprocess

SOURCE = Path(__file__).resolve().parents[1]
PORT = "/dev/serial/by-id/usb-Arduino__www.arduino.cc__0042_EXAMPLE_MEGA_SERIAL-if00"


def run(*args, **kwargs):
    return subprocess.run(list(args), check=True, **kwargs)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("version")
    parser.add_argument("--notes", required=True)
    parser.add_argument("--host", default="laser-maze", help="Existing Mac SSH shortcut")
    parser.add_argument("--port", default=PORT)
    parser.add_argument("--board", choices=("mega", "minima"), default="mega")
    parser.add_argument("--first-upload", action="store_true")
    parser.add_argument("--stage-only", action="store_true")
    args = parser.parse_args()
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}", args.version):
        parser.error("Use a simple release version without spaces or slashes")
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._-]{0,100}", args.host):
        parser.error("Use a simple SSH shortcut")
    if not args.port.startswith("/dev/serial/by-id/"):
        parser.error("Use a stable Arduino by-id path")
    run("ssh", args.host, "mkdir -p ~/laser-maze/source/arduino ~/laser-maze/source/pi ~/laser-maze/tools")
    # Explicit files only: no private configuration or hidden files copied.
    run("ssh", args.host, "mkdir -p ~/laser-maze/source/arduino/BenchController")
    run("scp", str(SOURCE / "arduino/BenchController/BenchController.ino"),
        args.host + ":~/laser-maze/source/arduino/BenchController/")
    run("scp", str(SOURCE / "arduino/BenchController/InputPanel.h"),
        args.host + ":~/laser-maze/source/arduino/BenchController/")
    run("ssh", args.host, "mkdir -p ~/laser-maze/source/arduino/LaserModuleNano")
    run("scp", str(SOURCE / "arduino/BenchController/ReceiverConfig.h"),
        args.host + ":~/laser-maze/source/arduino/BenchController/")
    for name in ('LaserModuleNano.ino','ModuleState.h','README.md'):
        run("scp", str(SOURCE / "arduino/LaserModuleNano" / name),
            args.host + ":~/laser-maze/source/arduino/LaserModuleNano/")
    run("scp", str(SOURCE / "arduino/BenchController/RfidReader.h"), args.host + ":~/laser-maze/source/arduino/BenchController/")
    for name in ("tank_level.py", "hazer_dmx.py", "usb_rfid.py", "usb_objective.py", "entry_authorization.py", "beam_monitor.py", "bench_test.py", "game_engine.py", "game_test.py", "panel_test.py", "panel_game.py", "game_reporting.py", "game_audio.py", "maintenance.py", "maintenance_bridge.py", "receiver_calibrate.py", "operator_settings.py"):
        run("scp", str(SOURCE / "pi" / name), args.host + ":~/laser-maze/source/pi/")
    run("ssh", args.host, "mkdir -p ~/laser-maze/source/tools")
    for name in ("install-maintenance-reboot.sh","set-reader-silent.py","49-zoco-acr1552.rules"):
        run("scp", str(SOURCE / "tools" / name), args.host + ":~/laser-maze/source/tools/")
    run("scp", str(SOURCE / "releases/deploy.py"), args.host + ":~/laser-maze/tools/")
    run("ssh", args.host, "mkdir -p ~/laser-maze/source/pi/audio")
    for name in ('preparation.wav','entrance.wav','warning90.wav','warning30.wav','warning10.wav','beam.wav','win_keys.wav','win_usb.wav','beam_loss.wav','timeout.wav','provenance.json'):
        run("scp", str(SOURCE / "pi/audio" / name), args.host + ":~/laser-maze/source/pi/audio/")
    remote_args = ["python3", "/home/brent/laser-maze/tools/deploy.py", "deploy",
        "--source", "/home/brent/laser-maze/source", "--version", args.version,
        "--notes", args.notes, "--port", args.port, "--board", args.board]
    if args.first_upload: remote_args.append("--first-upload")
    if args.stage_only: remote_args.append("--stage-only")
    command = shlex.join(remote_args)
    result = subprocess.run(["ssh", args.host, command])
    backup = SOURCE / "release-backups" / args.version
    backup.mkdir(parents=True, exist_ok=True, mode=0o700)
    saved = subprocess.run(["scp", args.host + ":~/laser-maze/deployments/releases/" +
        args.version + "/release.tar.gz", str(backup / "release.tar.gz")])
    if saved.returncode == 0:
        print(f"Release archive also saved on this Mac: {backup / 'release.tar.gz'}")
    else:
        print("Mac backup did not complete. Inspect Pi release storage before retrying.")
    if result.returncode:
        parser.exit(result.returncode, "Deployment did not complete; inspect its result before retrying.\n")
    if saved.returncode:
        parser.exit(saved.returncode, "Pi deployment completed, but the Mac archive copy needs retry.\n")


if __name__ == "__main__":
    main()
