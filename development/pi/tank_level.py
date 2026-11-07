"""Read-only 240–33 ohm sender diagnostics with a 680-ohm high-side resistor."""
import json
from pathlib import Path
from statistics import median
from game_reporting import atomic_json


def ohms(raw):
    if type(raw) not in (int,float) or not 0<=raw<1023:raise ValueError('invalid_sender_reading')
    return 680*raw/(1023-raw)

class TankLevel:
    def __init__(self,path):
        self.path=Path(path);self.raw=None;self.at=-100;self.captures={};self.calibration=None
        try:
            p=json.loads(self.path.read_text())
            e,f=p['empty_raw'],p['full_raw']
            if any(type(v) not in (int,float) or not 5<v<1000 for v in (e,f)) or e-f<30:raise ValueError()
            self.calibration=dict(empty_raw=e,full_raw=f)
        except (OSError,ValueError,KeyError,TypeError):pass
    def receive(self,raw,now):
        if type(raw) is not int or not 0<=raw<=1023:raise ValueError('invalid_sender_reading')
        self.raw=raw;self.at=now
    def capture(self,phase,samples):
        if phase not in ('empty','full') or len(samples)<20 or any(type(v) is not int or not 5<v<1000 for v in samples):raise ValueError('sender_reading_invalid_check_wiring')
        if max(samples)-min(samples)>15:raise ValueError('hold_float_still_and_retry')
        value=median(samples)
        if not 15<=ohms(value)<=350:raise ValueError('sender_resistance_outside_expected_range')
        if phase=='empty':self.captures={}
        elif 'empty' not in self.captures:raise ValueError('capture_empty_first')
        self.captures[phase]=dict(raw=value,minimum=min(samples),maximum=max(samples),samples=len(samples))
        if phase=='full':
            e,f=self.captures['empty']['raw'],value
            if e-f<30:raise ValueError('empty_and_full_not_separated_or_reversed')
            result=dict(empty_raw=e,full_raw=f)
            atomic_json(self.path,result);self.calibration=result
            return 'tank_empty_full_calibration_saved'
        return 'tank_empty_captured_move_float_to_full'
    def status(self,now):
        fresh=self.raw is not None and now-self.at<2
        raw=self.raw if fresh else None;resistance=round(ohms(raw),1) if raw is not None and raw<1023 else None
        state='unconfirmed' if not fresh else 'open_or_connected_to_5v' if raw>=1000 else 'short_or_connected_to_ground' if raw<=5 else 'uncalibrated' if self.calibration is None else 'reading'
        percentage=None
        if state=='reading':
            e,f=(ohms(self.calibration[k]) for k in ('empty_raw','full_raw'))
            percentage=round(max(0,min(100,100*(e-ohms(raw))/(e-f))),1)
        return dict(pin='A1',raw=raw,resistance_ohms=resistance,state=state,float_height_percent=percentage,calibration=self.calibration,captures=self.captures,resistor_ohms=680,alerts_enabled=False,automatic_cutoff=False)
