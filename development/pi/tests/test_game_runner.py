import contextlib
import importlib.util
import io
import os
from pathlib import Path
import sys
import tempfile
import types
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
spec = importlib.util.spec_from_file_location("game_test", ROOT / "game_test.py")
runner = importlib.util.module_from_spec(spec)
spec.loader.exec_module(runner)


class FakeClock:
    now = 0

    def monotonic(self):
        return self.now

    def sleep(self, duration):
        self.now += duration


class FakePort:
    def __init__(self, clock, fail=False):
        self.clock = clock
        self.fail = fail
        self.silent = False
        self.pending = bytearray()
        self.commands = []
        self.timeout = 0.02

    def __enter__(self): return self
    def __exit__(self, *args): pass
    def reset_input_buffer(self): self.pending.clear()
    def flush(self): pass

    @property
    def in_waiting(self): return len(self.pending)

    def write(self, value):
        command = value.decode().strip()
        self.commands.append(command)
        responses = {"HELLO": "HELLO 1 bench-0.26.3", "BEAM": "BEAM CLEAR",
            "ARM": "OK ARM", "HB": "OK HB", "ON": "OK ON", "OFF": "OK OFF", "PAUSE": "OK PAUSE"}
        if self.fail and command == "HB":
            self.silent = True
        if self.silent:
            return len(value)
        if command.startswith("TIME "):
            self.pending.extend(b"OK TIME\n")
            return len(value)
        self.pending.extend((responses[command] + "\n").encode())
        return len(value)

    def readline(self):
        line, _, self.pending = self.pending.partition(b"\n")
        return bytes(line) + b"\n"

    def read(self, count):
        self.clock.now += 0.02
        data = self.pending[:count]
        del self.pending[:count]
        return bytes(data)


class RunnerTests(unittest.TestCase):
    def run_game(self, fail=False):
        clock = FakeClock()
        port = FakePort(clock, fail)
        serial = types.SimpleNamespace(Serial=lambda *a, **kw: port, SerialException=OSError)
        output = io.StringIO()
        with tempfile.TemporaryDirectory() as home, patch.dict(os.environ, HOME=home), \
             patch.dict(sys.modules, serial=serial), patch.object(sys, "argv", ["game_test.py", "/dev/fake", "--fast"]), \
             patch.object(runner.time, "monotonic", clock.monotonic), patch.object(runner.time, "sleep", clock.sleep), \
             patch.object(runner.select, "select", return_value=([], [], [])), \
             contextlib.redirect_stdout(output), contextlib.redirect_stderr(output):
            if fail:
                with self.assertRaises(SystemExit) as error:
                    runner.main()
                self.assertEqual(error.exception.code, 1)
            else:
                runner.main()
        return port, output.getvalue()

    def test_timeout_runs_heartbeats_then_disarms(self):
        port, output = self.run_game()
        self.assertIn("RESULT: timeout", output)
        self.assertGreater(port.commands.count("HB"), 50)
        self.assertIn("ON", port.commands)
        self.assertEqual(port.commands[-1], "OFF")

    def test_missing_ack_faults_and_disarms(self):
        port, output = self.run_game(True)
        self.assertIn("acknowledgment timed out", output)
        self.assertEqual(port.commands[-1], "OFF")


if __name__ == "__main__":
    unittest.main()
