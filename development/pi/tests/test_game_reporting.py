import importlib.util
import json
from pathlib import Path
import sqlite3
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from game_reporting import Reporting, transfer_outbox
from panel_game import Controls


class ReportTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.folder = Path(self.tmp.name) / "reports"

    def tearDown(self): self.tmp.cleanup()

    def events(self):
        return [json.loads(p.read_text()) for p in (self.folder / "outbox").glob("*.json")]

    def test_result_and_live_status_are_durable_without_network(self):
        r = Reporting(self.folder, "bench-test", True)
        c = Controls(True, r)
        c.key("A", 0); c.tick(2)
        r.status(c, c.display(2), 2)
        status = json.loads((self.folder / "game-status.json").read_text())
        self.assertEqual(status["state"], "running")
        self.assertTrue(status["metrics"]["bench_prototype"])
        c.usb_update(False,2.5);c.usb_update(True,3); c.tick(3)
        rows = self.events()
        final = [v for v in rows if v["kind"] == "bench_game_result"]
        self.assertEqual(len(final), 1)
        self.assertEqual(final[0]["payload"]["outcome"], "win")
        self.assertEqual(final[0]["payload"]["elapsed_seconds"], 1)
        self.assertFalse(r.active.exists())
        self.assertEqual((self.folder / "game-status.json").stat().st_mode & 0o777, 0o600)

    def test_excluded_selection_reported_and_saved_in_final(self):
        r=Reporting(self.folder,"bench-test",True);c=Controls(True,r)
        c.inputs([True,False,False],0);c.key("A",0);c.tick(2)
        r.status(c,c.display(2),2,audio={"audio_"+str(i):False for i in range(8)},maintenance=dict(maintenance_protocol=1,maintenance_enabled=False,maintenance_pending=False,maintenance_local_enabled=False,maintenance_test_active=False))
        status=json.loads((self.folder/"game-status.json").read_text())
        self.assertEqual(status['metrics']['active_beams'],1)
        self.assertEqual(status['metrics']['excluded_beams'],'1')
        self.assertLessEqual(len(status['metrics']),40)
        c.usb_update(False,2.5);c.usb_update(True,3);c.tick(3)
        final=[e for e in self.events() if e['kind']=='bench_game_result'][0]['payload']
        self.assertEqual(final['excluded_beams'],[1]);self.assertEqual(final['enabled_beams'],[2])

    def test_restart_recovers_interrupted_session_once(self):
        r = Reporting(self.folder, "bench-test", True)
        c = Controls(True, r); c.key("A", 0)
        Reporting(self.folder, "bench-test", True)
        Reporting(self.folder, "bench-test", True)
        final = [v for v in self.events() if v["kind"] == "bench_game_result"]
        self.assertEqual(len(final), 1)
        self.assertEqual(final[0]["payload"]["outcome"], "interrupted")
        self.assertIsNone(final[0]["payload"]["break_count"])

    def test_countdown_does_not_generate_event_each_second(self):
        r = Reporting(self.folder, "bench-test", True)
        c = Controls(True, r); c.key("A", 0); c.tick(2)
        r.status(c, c.display(2), 2)
        count = len(self.events())
        for now in range(3, 10): r.status(c, c.display(now), now)
        self.assertEqual(len(self.events()), count)

    def test_transfer_commit_then_retry_does_not_duplicate(self):
        r = Reporting(self.folder, "bench-test", True)
        c = Controls(True, r); c.key("A", 0)
        fake = Path(self.tmp.name) / "agent.py"
        fake.write_text('''import sqlite3
class Agent:
 def __init__(self,config):
  self.db=sqlite3.connect(config)
  self.db.execute("CREATE TABLE IF NOT EXISTS events(event_id TEXT PRIMARY KEY,occurred_at TEXT,kind TEXT,payload TEXT,sent INTEGER DEFAULT 0)")
 def close(self): self.db.close()
''')
        database = Path(self.tmp.name) / "events.sqlite"
        file = next((self.folder / "outbox").glob("*.json"))
        with patch.object(Path, "unlink", side_effect=OSError("crash after commit")):
            with self.assertRaises(OSError): transfer_outbox(self.folder, database, fake)
        transfer_outbox(self.folder, database, fake)
        with sqlite3.connect(database) as db:
            self.assertEqual(db.execute("SELECT COUNT(*) FROM events").fetchone()[0], 1)
        self.assertFalse(list((self.folder / "outbox").glob("*.json")))

    def test_stopped_status_is_unknown_fault_is_faulted(self):
        r = Reporting(self.folder, "bench-test", True); c = Controls(True, r)
        r.status(c, (False, False, 0, "OFF"), 0, stopped=True)
        self.assertEqual(json.loads((self.folder / "game-status.json").read_text())["state"], "unknown")
        r.status(c, (False, False, 0, "OFF"), 1, connected=False, fault="controller_communication_fault")
        self.assertEqual(json.loads((self.folder / "game-status.json").read_text())["state"], "faulted")


if __name__ == "__main__": unittest.main()
