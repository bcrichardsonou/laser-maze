import sys,unittest
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from entry_authorization import Entry,CODES
from panel_game import Controls,reader_reply
from game_engine import MODES

class EntryTests(unittest.TestCase):
    def code(self,e,code,now=1,gap=.1,allowed=MODES):
        result=None
        for i,key in enumerate(code):result=e.key(key,now+i*gap,allowed)
        return result

    def test_exact_codes_scan_first_and_code_first(self):
        for code,mode in CODES.items():
            e=Entry();self.assertIsNone(e.swipe(0,MODES));self.assertEqual(self.code(e,code),mode)
            self.assertFalse(e.scanned);self.assertEqual(e.code,'')
            e=Entry();self.assertIsNone(self.code(e,code));self.assertEqual(e.swipe(2,MODES),mode)

    def test_scan_without_code_and_code_without_scan_never_start(self):
        e=Entry();self.assertIsNone(e.swipe(0,MODES));e.tick(5);self.assertFalse(e.scanned)
        self.code(e,'77004#',6);e.tick(12);self.assertEqual(e.code,'')

    def test_complementary_action_begins_in_five_seconds_then_each_character_window(self):
        e=Entry();e.swipe(0,MODES)
        self.assertEqual(self.code(e,'77004#',4.9,gap=4.9),'keys')
        e=Entry();e.swipe(0,MODES);self.assertIsNone(self.code(e,'77004#',5))
        self.assertFalse(e.scanned)

    def test_timeout_between_characters_discards_old_scan_and_buffer(self):
        e=Entry();e.swipe(0,MODES);e.key('7',1,MODES)
        self.assertIsNone(self.code(e,'7004#',6));self.assertFalse(e.scanned)

    def test_invalid_code_early_terminator_clear_and_disabled_mode(self):
        for code in ['12345#','77004*','77#','770041']:
            e=Entry();e.swipe(0,MODES);self.assertIsNone(self.code(e,code));self.assertFalse(e.scanned)
        e=Entry();e.swipe(0,MODES);self.assertIsNone(self.code(e,'77004#',allowed=['usb']))
        self.assertEqual(e.reason,'mode_disabled')

    def test_six_character_buffer_is_frozen_until_scan_or_timeout(self):
        e=Entry();self.code(e,'77004#');deadline=e.deadline
        self.assertIsNone(e.key('1',2,MODES));self.assertEqual(e.code,'77004#');self.assertEqual(e.deadline,deadline)
        self.assertEqual(e.swipe(3,MODES),'keys')

    def test_controls_require_reader_scan_and_code_no_A_bypass(self):
        c=Controls(rfid_entry=True)
        for key in '1A77004#':c.key(key,0)
        self.assertIsNone(c.game)
        c.reader_ready=True;c.key('A',1);self.assertIsNone(c.game)
        c.swipe(2)
        for i,key in enumerate('77004#'):c.key(key,2.1+i*.1)
        self.assertEqual(c.mode,'keys');self.assertEqual(c.game.state,'starting')
        original=c.game;c.swipe(3)
        for key in '16646#A':c.key(key,3)
        self.assertIs(c.game,original);self.assertEqual(c.mode,'keys')
        c.tick(5);self.assertEqual(c.game.key_progress,0)
        c.tick(12.6)
        for key in '1324':c.key(key,13)
        c.tick(13);self.assertEqual(c.result[0],'win')

    def test_scan_turns_entrance_purple_until_code_timeout_or_cancel(self):
        c=Controls(rfid_entry=True);c.reader_ready=True
        self.assertEqual(c.display(0)[3],'RED');c.swipe(1)
        self.assertEqual(c.display(1)[3],'PURPLE')
        c.key('7',5);self.assertEqual(c.display(7)[3],'PURPLE')
        c.tick(10);self.assertEqual(c.display(10)[3],'RED')
        c.swipe(11);c.key('*',12);self.assertEqual(c.display(12)[3],'RED')
        c.swipe(13)
        for key in '77004#':c.key(key,14)
        self.assertEqual(c.display(14)[3],'YELLOW')
        c.swipe(15);self.assertEqual(c.display(15)[3],'YELLOW')

    def test_combined_reader_health_and_diagnostic_reply(self):
        ready,d=reader_reply('RFID READY 18 2 3 0 112')
        self.assertTrue(ready);self.assertEqual(d['tag_responses'],18);self.assertEqual(d['receive_gain_register'],112)
        self.assertFalse(reader_reply('RFID MISSING 0 0 3 3 0')[0])
        for bad in ['RFID READY','RFID READY -1 0 3 3 112','RFID READY 0 0 256 3 112','RFID BAD 0 0 3 3 0']:
            with self.assertRaises(RuntimeError):reader_reply(bad)

    def test_D_and_play_lock_invalidate_pending_entry(self):
        c=Controls(rfid_entry=True);c.reader_ready=True;c.swipe(0);c.key('7',1);c.key('D',2)
        self.assertFalse(c.entry.scanned);self.assertEqual(c.entry.code,'')
        c.swipe(3);c.play_locked=True
        for key in '77004#':c.key(key,4)
        self.assertIsNone(c.game);self.assertFalse(c.entry.scanned)

if __name__=='__main__':unittest.main()
