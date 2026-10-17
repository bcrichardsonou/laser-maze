"""Bounded operator settings, shared by controller and maintenance validation."""
from game_engine import MODES
DEFAULT_SETTINGS=dict(duration=150,startup=5,cooldown=7,warmup=5,max_breaks=3,enabled_beams=[True,True],available_modes=list(MODES))
RANGES=dict(duration=(10,3600),startup=(1,30),cooldown=(1,60),warmup=(1,30),max_breaks=(1,20))

def validate_settings(value):
    if not isinstance(value,dict) or set(value)!=set(DEFAULT_SETTINGS):raise ValueError('invalid_game_settings')
    for key,(low,high) in RANGES.items():
        if type(value[key]) is not int or not low<=value[key]<=high:raise ValueError('invalid_'+key)
    beams=value['enabled_beams'];modes=value['available_modes']
    if not isinstance(beams,list) or len(beams)!=2 or any(type(v) is not bool for v in beams) or not any(beams):raise ValueError('enable_at_least_one_beam')
    if not isinstance(modes,list) or not modes or len(set(modes))!=len(modes) or any(not isinstance(v,str) or v not in MODES for v in modes):raise ValueError('invalid_available_modes')
    return dict(value)


def validate_thresholds(value):
    if not isinstance(value,dict) or set(value)!= {'break_below','clear_above'}:raise ValueError('invalid_thresholds')
    if any(type(v) is not int for v in value.values()) or not 0<value['break_below']<value['clear_above']<1023:raise ValueError('invalid_thresholds')
    return dict(value)
