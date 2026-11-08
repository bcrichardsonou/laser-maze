import sys
from pathlib import Path
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from panel_game import Controls


class PanelGameTests(unittest.TestCase):
    def test_module_is_powered_during_preparation_then_follows_beam_one(self):
        c=Controls();c.key("A",0)
        for now in (0,1,4.999):
            c.tick(now);self.assertEqual(c.display(now)[:2],(True,True))
        c.tick(5);self.assertEqual(c.display(5)[:2],(True,True))
        c.inputs([True,False,False],11)
        self.assertEqual(c.display(11)[:2],(False,True))
        c.inputs([False,False,False],12);c.tick(18)
        self.assertEqual(c.display(18)[:2],(True,True))
        c.key("D",19);c.tick(19)
        self.assertEqual(c.display(19)[:2],(False,False))

    def test_dark_receiver_can_clear_during_powered_preparation(self):
        c=Controls();c.inputs([True,True,False],0);c.key("A",0)
        self.assertEqual(c.display(0)[:2],(True,True))
        c.inputs([False,True,False],1);c.tick(5)
        self.assertEqual(c.game.enabled,[True,False]);self.assertEqual(c.game.breaks,0)
        c.inputs([True,True,False],6)
        self.assertEqual(c.game.breaks,0)
        c.inputs([False,True,False],9);c.tick(10);c.inputs([True,True,False],11)
        self.assertEqual(c.game.breaks,1)

    def test_entrance_sequence_is_independent_of_beam_feedback(self):
        c=Controls();self.assertEqual(c.display(0)[3],"RED")
        c.key("A",0);self.assertEqual(c.display(0)[2:],(0,"YELLOW"))
        c.tick(5);self.assertEqual(c.display(5)[2:],(0,"GREEN"))
        c.inputs([False,False,True],6);self.assertFalse(c.game.objective)
        c.tick(10);self.assertEqual(c.display(10)[2:],(150,"BLUE"))
        c.inputs([True,False,True],11);self.assertEqual(c.display(11)[3],"BLUE")
        self.assertEqual(c.game.breaks,1);self.assertFalse(c.display(11)[0])
        c.inputs([False,False,True],12);c.tick(18);self.assertEqual(c.display(18)[3],"BLUE")
        c.key("D",19);c.tick(19);self.assertEqual(c.display(19)[3],"BLUE")

    def test_excluded_beam_does_not_make_entrance_yellow_during_play(self):
        c=Controls();c.inputs([True,False,False],0);c.key("A",0);c.tick(10)
        self.assertEqual(c.game.enabled,[False,True]);self.assertEqual(c.display(10)[3],"BLUE")

    def test_finish_holds_occupied_light_then_returns_red(self):
        for outcome,hold in [("win",10),("beam_limit",10),("timeout",10),("stopped",10)]:
            c=Controls();c.key("A",0);c.tick(10);c.game.finish(outcome);c.tick(11)
            self.assertEqual(c.display(11)[3],"BLUE" if hold else "RED")
            self.assertEqual(c.display(11+hold)[3],"RED")
            self.assertEqual(c.display(11)[:2],(False,False))

    def test_preexisting_usb_does_not_win(self):
        c = Controls(True)
        c.usb_update(True, 0)
        c.key("A", 0); c.tick(2)
        c.usb_update(True, 3)
        self.assertFalse(c.game.objective)
        c.usb_update(False, 4)
        c.usb_update(True, 5); c.tick(5)
        self.assertEqual(c.result, ("win", 0))

    def test_startup_usb_activation_requires_new_edge(self):
        c = Controls(True); c.key("A", 0)
        c.usb_update(True, 1); c.tick(2)
        c.usb_update(True, 3)
        self.assertFalse(c.game.objective)

    def test_two_beam_break_all_and_repeat_start(self):
        c = Controls(True); c.key("2", 0); c.key("A", 0); c.tick(2)
        c.inputs([True, True, False], 3)
        self.assertEqual(c.game.breaks, 2)
        self.assertEqual(c.display(3)[:2], (False, False))
        c.usb_update(False,3.5);c.usb_update(True,4); c.tick(4)
        self.assertEqual(c.result, ("win", 2))
        c.inputs([False,False,False],4.5);c.key("A", 5); c.tick(7)
        self.assertEqual(c.game.state, "running")
        self.assertFalse(c.game.objective)

    def test_keys_mode_selection_and_stop(self):
        c = Controls(True); c.key("3", 0); c.key("A", 0); c.tick(2)
        for key in "1324": c.key(key, 3)
        c.tick(3); self.assertEqual(c.result[0], "win")
        c.key("A", 4); c.key("D", 5); c.tick(5)
        self.assertEqual(c.result[0], "stopped")
        self.assertEqual(c.display(5)[:3], (False, False, 0))

    def test_blocked_beam_is_excluded_and_rechecked_next_game(self):
        c = Controls(True); c.inputs([True, False, False], 0)
        c.key("A", 1); c.tick(1)
        self.assertIsNone(c.result);c.tick(3)
        self.assertEqual(c.game.enabled,[False,True]);self.assertEqual(c.display(3)[:2],(False,True))
        c.inputs([False,False,False],4);self.assertEqual(c.game.enabled,[False,True])
        c.key("D",5);c.tick(5);c.key("A",6);c.tick(8)
        self.assertEqual(c.game.enabled,[True,True])


if __name__ == "__main__": unittest.main()
