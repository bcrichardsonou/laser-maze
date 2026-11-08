import importlib.util
from pathlib import Path
import unittest

root = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("panel_test", root / "panel_test.py")
panel = importlib.util.module_from_spec(spec)
spec.loader.exec_module(panel)


class PanelTests(unittest.TestCase):
    def test_three_inputs_and_snapshot(self):
        self.assertIn("A0", panel.describe("INPUT 0 1"))
        self.assertIn("D3", panel.describe("INPUT 1 0"))
        self.assertIn("D4", panel.describe("INPUT 2 1"))
        self.assertEqual(panel.describe("INPUTS 0 1 0").count("ACTIVE"), 1)

    def test_every_printed_key_and_release(self):
        for key in "0123456789ABCD*#":
            self.assertEqual(panel.describe("KEY " + key), "Key pressed: " + key)
        self.assertEqual(panel.describe("KEY UP"), "Key released")
        self.assertIn("one key", panel.describe("KEY INVALID"))

    def test_reject_unknown_messages(self):
        for line in ("INPUT 3 1", "INPUT 1 9", "INPUTS 0 1", "KEY XX", "FAULT WATCHDOG"):
            with self.assertRaises(RuntimeError):
                panel.describe(line)


if __name__ == "__main__":
    unittest.main()
