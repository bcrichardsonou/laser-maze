import sys
from pathlib import Path
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from receiver_calibrate import propose,summarize

class CalibrationTests(unittest.TestCase):
    def test_separation_hysteresis_and_recheck(self):
        result=propose([10]*100,[110]*100,[20]*100)
        self.assertTrue(result['usable'])
        self.assertEqual(result['proposed_break_threshold'],50)
        self.assertEqual(result['proposed_clear_threshold'],80)
    def test_reject_noise_overlap_reverse_and_saturation(self):
        for values in [([10]*100,[25]*100,[20]*100),([200]*100,[10]*100,[200]*100),([10]*100,[1023]*100,[10]*100)]:
            self.assertFalse(propose(*values)['usable'])
    def test_invalid_adc_and_small_sample(self):
        for values in [[1]*10,[1024]*100,[True]*100]:
            with self.assertRaises(ValueError):summarize(values)

    def test_cancel_releases_port_and_restarts_prior_game(self):
        import json
        import tempfile
        import types
        from unittest.mock import patch
        import receiver_calibrate as tool
        writes=[]
        class Port:
            last=''
            def __enter__(self):return self
            def __exit__(self,*args):writes.append('closed')
            def write(self,b):self.last=b.decode().strip();writes.append(self.last)
            def flush(self):pass
            def reset_input_buffer(self):pass
            def readline(self):
                return ({'HELLO':'HELLO 1 bench-test','STATUS':'STATUS DISARMED OFF'}[self.last]+'\n').encode()
        with tempfile.TemporaryDirectory() as d:
            home=Path(d);state=home/'laser-maze/deployments';state.mkdir(parents=True)
            (state/'installed.json').write_text(json.dumps(dict(fqbn='arduino:avr:mega:cpu=atmega2560',port='/dev/serial/by-id/test',firmware_version='bench-test')))
            with patch.object(tool.Path,'home',return_value=home),patch.object(sys,'argv',['receiver_calibrate.py']),patch.object(tool.signal,'signal'),patch.dict(sys.modules,serial=types.SimpleNamespace(Serial=lambda *a,**k:Port(),SerialException=OSError)),patch.object(tool.time,'sleep'),patch.object(tool.subprocess,'check_output',return_value='active\n'),patch.object(tool.subprocess,'run') as run,patch('builtins.input',side_effect=KeyboardInterrupt),patch('builtins.print'):
                with self.assertRaises(KeyboardInterrupt):tool.main()
                self.assertEqual([c.args[0][-2] for c in run.call_args_list],['stop','start'])
                self.assertEqual(writes[-2:],['OFF','closed'])
