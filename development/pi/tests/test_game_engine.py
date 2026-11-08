import sys
from pathlib import Path
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from game_engine import Game, Settings


class GameTests(unittest.TestCase):
    def running(self, mode="usb", count=1):
        g = Game(mode, Settings(beam_count=count))
        g.start(0)
        g.tick(5)
        self.assertEqual(g.state, "running")
        return g

    def test_exclusion_all_modes_is_fixed_and_not_counted(self):
        for mode in ('usb','usb-break-all','keys','keys-break-all'):
            g=Game(mode,Settings(beam_count=2));g.broken=[True,False];g.start(0);g.tick(5)
            self.assertEqual(g.enabled,[False,True]);self.assertEqual(g.outputs(5),(False,True))
            g.beam(0,False,6);g.beam(0,True,7);self.assertEqual(g.breaks,0)
            self.assertFalse(g.outputs(7)[0])
            if mode.startswith('usb'):g.objective_usb(8)
            else:
                for key in (1,3,2,4):g.key(key,8)
            if g.break_all:
                self.assertEqual(g.state,'running');g.beam(1,True,9)
            self.assertEqual(g.outcome,'win')

    def test_preparation_can_exclude_more_beams_but_not_reinclude(self):
        g=Game(settings=Settings(beam_count=3));g.broken=[True,False,False];g.start(0)
        g.broken=[False,True,False];g.tick(5)
        self.assertEqual(g.enabled,[False,False,True]);self.assertEqual(g.breaks,0)

    def test_no_available_beams_rejects_empty_game(self):
        g=Game(settings=Settings(beam_count=2));g.broken=[True,True];g.start(0)
        self.assertEqual(g.outcome,'no_beams_available');self.assertEqual(g.outputs(0),(False,False))

    def test_third_break_and_output_recovery(self):
        g = self.running()
        g.beam(0, True, 6)
        self.assertEqual(g.breaks, 1)
        self.assertEqual(g.outputs(6), (False,))
        g.beam(0, False, 7)
        g.beam(0, True, 8)  # Presses during cooldown cannot count.
        g.beam(0, False, 9)
        g.tick(13)
        self.assertEqual(g.outputs(13), (True,))
        self.assertEqual(g.breaks, 1)
        g.beam(0, True, 14)  # Warmup obstruction isn't counted yet.
        self.assertEqual(g.breaks, 1)
        g.tick(18)
        self.assertEqual(g.breaks, 2)
        g.beam(0, False, 19)
        g.tick(30)
        g.beam(0, True, 31)
        self.assertEqual(g.outcome, "beam_limit")
        self.assertEqual(g.outputs(31), (False,))

    def test_held_input_counts_again_after_recovery(self):
        g = self.running()
        g.beam(0, True, 6)
        g.tick(7)
        self.assertEqual(g.breaks, 1)
        g.tick(18)
        self.assertEqual(g.breaks, 2)
        g.tick(30)
        self.assertEqual(g.outcome, "beam_limit")

    def test_timeout_boundary_and_late_objective(self):
        g = self.running()
        g.tick(154.99)
        self.assertEqual(g.state, "running")
        g.objective_usb(155)
        self.assertEqual(g.outcome, "timeout")

    def test_blocked_startup_fault(self):
        g = Game()
        g.start(0)
        g.beam(0, True, 4)
        g.tick(5)
        self.assertEqual(g.state, "fault")
        self.assertEqual(g.outcome, "no_beams_available")
        self.assertEqual(g.outputs(5), (False,))

    def test_break_all_both_objective_orders(self):
        for objective_first in (True, False):
            with self.subTest(objective_first=objective_first):
                g = self.running("usb-break-all", 3)
                if objective_first:
                    g.objective_usb(5.5)
                for i in range(3):
                    g.beam(i, True, 6 + i)
                    g.beam(i, False, 6.5 + i)
                self.assertEqual(g.breaks, 3)
                self.assertEqual(g.outputs(9), (False, False, False))
                if not objective_first:
                    self.assertEqual(g.state, "running")
                    g.objective_usb(10)
                self.assertEqual(g.outcome, "win")

    def test_wrong_key_and_order(self):
        g = self.running("keys")
        g.key(2, 6)
        self.assertEqual(g.key_progress, 0)
        for key in (1, 3, 2):
            g.key(key, 7)
        self.assertFalse(g.objective)
        g.key(4, 8)
        self.assertEqual(g.outcome, "win")

    def test_key_break_all_needs_both_conditions(self):
        g = self.running("keys-break-all")
        for key in (1, 3, 2, 4):
            g.key(key, 6)
        self.assertEqual(g.state, "running")
        g.beam(0, True, 7)
        self.assertEqual(g.outcome, "win")

    def test_simultaneous_breaks_and_terminal_stop(self):
        g = self.running("usb", 3)
        g.broken = [True] * 3
        g.tick(6)
        self.assertEqual(g.breaks, 3)
        self.assertEqual(g.outcome, "beam_limit")
        g.beam(0, False, 7)
        g.objective_usb(8)
        self.assertEqual(g.outcome, "beam_limit")

    def test_objective_before_running_ignored(self):
        g = Game()
        g.start(0)
        g.objective_usb(1)
        self.assertFalse(g.objective)
        g.objective_usb(5)
        self.assertEqual(g.outcome, "win")

    def test_invalid_configuration(self):
        for kwargs in ({"beam_count": 0}, {"duration": float("nan")}, {"cooldown": 0}):
            with self.assertRaises(ValueError):
                Settings(**kwargs)


if __name__ == "__main__":
    unittest.main()
