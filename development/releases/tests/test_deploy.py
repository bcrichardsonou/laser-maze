import importlib.util
import json
import os
from pathlib import Path
import tarfile
import tempfile
import types
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
spec = importlib.util.spec_from_file_location("deploy", ROOT / "releases/deploy.py")
deploy = importlib.util.module_from_spec(spec)
spec.loader.exec_module(deploy)


class Portal:
    def __init__(self):
        self.records = []
        self.archives = []
        self.fail_reports = False

    def archive(self, release):
        self.archives.append(release)

    def post(self, body):
        if self.fail_reports and body["status"] == "verified":
            raise OSError("offline")
        self.records.append(body.copy())
        return dict(deployment_id=body["deployment_id"], accepted=body["status"])


class ReleaseTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.work = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def fake_cli(self):
        cli = self.work / "arduino-cli"
        cli.write_text('''#!/usr/bin/env python3
import sys
from pathlib import Path
if sys.argv[1] == 'compile':
 p=Path(sys.argv[sys.argv.index('--output-dir')+1]);(p/('BenchController.ino.hex' if 'arduino:avr:mega:cpu=atmega2560' in sys.argv else 'BenchController.ino.bin')).write_bytes(b'firmware test binary');(p/'temporary.log').write_text('excluded')
elif sys.argv[1] == 'version': print('Arduino CLI fake-test')
elif sys.argv[1:3] == ['core','list']: print('arduino:renesas_uno fake-test')
elif sys.argv[1:3] == ['lib','list']: print('Adafruit NeoPixel fake-test')
else: sys.exit(1)
''')
        cli.chmod(0o700)

    def test_package_allowlist_hashes_and_versions(self):
        self.fake_cli()
        with patch.dict(os.environ, PATH=str(self.work)+os.pathsep+os.environ["PATH"]):
            target = self.work / "releases/test-1"
            manifest = deploy.build(ROOT, target, "test-1", "Test release")
        self.assertEqual(manifest["firmware_version"], "bench-0.26.3")
        self.assertEqual(manifest["python_version"], "bench-0.26.3")
        self.assertEqual(manifest["nano_modules"]["firmware_version"], "nano-module-0.3.0")
        self.assertEqual(manifest["nano_modules"]["installed_version"], "unverified")
        self.assertIn("source/arduino/LaserModuleNano/ModuleState.h", manifest["files"])
        with tarfile.open(target / "release.tar.gz") as archive:
            self.assertEqual(set(archive.getnames()), set(manifest["files"]) | {"manifest.json"})
            for name, checksum in manifest["files"].items():
                self.assertEqual(deploy.digest(archive.extractfile(name).read()), checksum)
            self.assertFalse(any("config" in name or "__pycache__" in name or ".log" in name for name in archive.getnames()))
        # A failed network attempt can reuse exactly the same immutable package.
        with patch.object(deploy, "run") as compile_again:
            self.assertEqual(deploy.build(ROOT, target, "test-1", "Test release"), manifest)
            compile_again.assert_not_called()
        with self.assertRaises(ValueError):
            deploy.build(ROOT, target, "test-1", "Changed notes")

    def test_mega_hex_build_and_target_mismatch(self):
        self.fake_cli()
        with patch.dict(os.environ, PATH=str(self.work)+os.pathsep+os.environ["PATH"]):
            target=self.work / "mega"
            m=deploy.build(ROOT,target,"mega-1","Mega test",fqbn=deploy.BOARDS["mega"])
            self.assertEqual(m["fqbn"],deploy.BOARDS["mega"])
            self.assertIn("compiled/BenchController.ino.hex",m["files"])
            with self.assertRaises(ValueError):deploy.build(ROOT,target,"mega-1","Mega test")

    def test_stage_keeps_installed_controller(self):
        portal=Portal();args=self.args();args.stage_only=True;args.board="mega"
        (self.work / "installed.json").write_text('{"version":"old-minima"}')
        with patch.object(deploy,"preflight"),patch.object(deploy,"build",self.build_stub),patch.object(deploy,"run"),patch.object(deploy,"verify_firmware"),patch.object(deploy.subprocess,"check_output",return_value="bench-0.2.1\n"):
            deploy.deploy(args,portal,self.work)
        self.assertFalse((self.work / "current").exists())
        self.assertEqual(json.loads((self.work / "installed.json").read_text())["version"],"old-minima")
        self.assertEqual(json.loads((self.work / "staged-controller.json").read_text())["fqbn"],deploy.BOARDS["mega"])

    def test_first_upload_rejects_wrong_usb_board(self):
        device=self.work / "device";device.touch()
        listing={"detected_ports":[{"port":{"address":str(device.resolve())},"matching_boards":[{"fqbn":deploy.FQBN}]}]}
        with patch.object(deploy.shutil,"which",return_value="fuser"),patch.object(deploy.subprocess,"run",return_value=types.SimpleNamespace(returncode=1)),patch.object(deploy.subprocess,"check_output",return_value=json.dumps(listing)):
            with self.assertRaises(ValueError):deploy.first_upload_preflight(device)
            listing["detected_ports"][0]["matching_boards"][0]["fqbn"]="arduino:avr:mega"
            with patch.object(deploy.subprocess,"check_output",return_value=json.dumps(listing)):deploy.first_upload_preflight(device)

    def test_reject_existing_version_and_path_escape(self):
        existing = self.work / "already"
        existing.mkdir()
        with self.assertRaises((ValueError, FileNotFoundError)):
            deploy.build(ROOT, existing, "test-1", "test")
        with self.assertRaises(ValueError):
            deploy.build(ROOT, self.work / "new", "../bad", "test")

    def test_reject_symlink_source(self):
        source = self.work / "source"
        path = source / deploy.SOURCES[0]
        path.parent.mkdir(parents=True)
        path.symlink_to(ROOT / deploy.SOURCES[0])
        with self.assertRaises(ValueError):
            deploy.build(source, self.work / "release", "test-1", "test")

    def test_report_persistence_and_retry(self):
        portal = Portal()
        directory = self.work / "pending"
        deploy.save_report(directory, "abc", "test-1", "verified")
        portal.fail_reports = True
        with self.assertRaises(OSError):
            deploy.sync_reports(portal, directory)
        self.assertEqual(len(list(directory.glob("*.json"))), 1)
        portal.fail_reports = False
        deploy.sync_reports(portal, directory)
        self.assertFalse(list(directory.glob("*.json")))

    def args(self):
        return types.SimpleNamespace(port="/dev/serial/by-id/test-board", source=ROOT,
            version="test-1", notes="test")

    def build_stub(self, source, release, version, notes, fqbn=deploy.FQBN):
        (release / "source/pi").mkdir(parents=True)
        return dict(firmware_version="bench-0.2.1", python_version="bench-0.2.1")

    def test_archive_failure_never_flashes(self):
        portal = Portal()
        with patch.object(deploy, "preflight"), patch.object(deploy, "build", self.build_stub), \
             patch.object(portal, "archive", side_effect=OSError("offline")), patch.object(deploy, "run") as run:
            with self.assertRaises(OSError):
                deploy.deploy(self.args(), portal, self.work)
            run.assert_not_called()

    def test_failed_upload_does_not_activate(self):
        portal = Portal()
        with patch.object(deploy, "preflight"), patch.object(deploy, "build", self.build_stub), \
             patch.object(deploy, "run", side_effect=RuntimeError("upload failed")):
            with self.assertRaises(RuntimeError):
                deploy.deploy(self.args(), portal, self.work)
        self.assertFalse((self.work / "current").exists())
        self.assertEqual(json.loads((self.work / "installed.json").read_text())["state"], "unconfirmed")
        self.assertEqual([r["status"] for r in portal.records], ["started", "failed"])

    def test_success_verifies_then_activates_and_queues_final_report(self):
        portal = Portal()
        portal.fail_reports = True
        with patch.object(deploy, "preflight"), patch.object(deploy, "build", self.build_stub), \
             patch.object(deploy, "run"), patch.object(deploy, "verify_firmware") as verify, \
             patch.object(deploy.subprocess, "check_output", return_value="bench-0.2.1\n"):
            deploy.deploy(self.args(), portal, self.work)
        verify.assert_called_once()
        self.assertTrue((self.work / "current").is_symlink())
        self.assertEqual(json.loads((self.work / "installed.json").read_text())["version"], "test-1")
        self.assertEqual(len(list((self.work / "pending").glob("*.json"))), 1)
        portal.fail_reports = False
        deploy.sync_reports(portal, self.work / "pending")
        self.assertEqual(portal.records[-1]["status"], "verified")

    def test_wrong_firmware_never_activates(self):
        portal = Portal()
        with patch.object(deploy, "preflight"), patch.object(deploy, "build", self.build_stub), \
             patch.object(deploy, "run"), patch.object(deploy, "verify_firmware", side_effect=RuntimeError("wrong version")):
            with self.assertRaises(RuntimeError):
                deploy.deploy(self.args(), portal, self.work)
        self.assertFalse((self.work / "current").exists())
        self.assertEqual(portal.records[-1]["reason"], "firmware_verification")


if __name__ == "__main__":
    unittest.main()
