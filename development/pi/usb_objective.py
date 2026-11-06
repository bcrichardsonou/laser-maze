"""Observe USB storage at a designated physical socket using sysfs metadata only."""
import json
from pathlib import Path
import re


def usb_location(device):
    device=Path(device).resolve()
    root=next(p for p in device.parents if re.fullmatch(r'usb\d+',p.name))
    family=int((root/'version').read_text().strip().split('.')[0])
    return dict(controller=str(root.parent),family=family,route=(device/'devpath').read_text().strip())


class USBObjective:
    def __init__(self,config,sys_root='/sys'):
        self.sys=Path(sys_root);self.locations=[];self.error='usb_port_not_configured'
        self.present=None;self.next_poll=0;self.observations=0;self.insertions=0;self.removals=0
        try:
            data=json.loads(Path(config).read_text());locations=data['locations']
            if not isinstance(locations,list) or not 1<=len(locations)<=4:raise ValueError()
            for loc in locations:
                if set(loc)!= {'controller','family','route'} or not str(loc['controller']).startswith('/') or loc['family'] not in (2,3) or not re.fullmatch(r'\d+(\.\d+)*',loc['route']):raise ValueError()
            self.locations=[dict(loc,controller=str(Path(loc['controller']).resolve())) for loc in locations];self.error=''
        except (OSError,ValueError,KeyError,TypeError):pass
    def poll(self,now):
        if now<self.next_poll:return False
        self.next_poll=now+.1
        if not self.locations:self.present=None;return True
        previous=self.present
        try:
            roots=list((self.sys/'bus/usb/devices').glob('usb*'))
            available=any(str(root.resolve().parent)==loc['controller'] and int((root/'version').read_text().strip().split('.')[0])==loc['family'] for root in roots for loc in self.locations)
            if not available:raise OSError('configured_usb_controller_missing')
            found=set()
            for node in (self.sys/'class/block').iterdir():
                if (node/'partition').exists():continue
                try:
                    device=next((p for p in node.resolve().parents if (p/'idVendor').exists()),None)
                    if device is not None and usb_location(device) in self.locations:found.add(str(device))
                except FileNotFoundError:continue  # Normal removal during enumeration.
            self.present=bool(found);self.error='';self.observations+=1
            if previous is False and self.present:self.insertions+=1
            if previous is True and not self.present:self.removals+=1
        except (OSError,ValueError,StopIteration):
            self.present=None;self.error='usb_input_unconfirmed'
        return True
    def status(self):
        return dict(configured=bool(self.locations),present=self.present,error=self.error,
                    insertions_this_run=self.insertions,removals_this_run=self.removals,
                    source='designated_pi_usb_port',files_read=False)
