"""Approved one-time ACS scan-beep configuration; restore original driver bytes."""
import os
from pathlib import Path
import re
import subprocess
import sys
import time

DRIVER=Path('/usr/lib/pcsc/drivers/ifd-ccid.bundle/Contents/Info.plist')
CLIENT=r'''
import json
from pathlib import Path
from smartcard import scard as s
rc,ctx=s.SCardEstablishContext(s.SCARD_SCOPE_USER)
assert rc==s.SCARD_S_SUCCESS, 'PCSC context unavailable'
try:
 rc,names=s.SCardListReaders(ctx,[])
 names=[n for n in names if 'ACR1552' in n and 'PICC' in n and 'SAM' not in n]
 assert rc==s.SCARD_S_SUCCESS and len(names)==1, 'Expected one ACR1552 PICC interface'
 rc,handle,protocol=s.SCardConnect(ctx,names[0],s.SCARD_SHARE_DIRECT,0)
 assert rc==s.SCARD_S_SUCCESS, 'Reader direct connection unavailable'
 try:
  rc,features=s.SCardControl(handle,s.SCARD_CTL_CODE(3400),[])
  assert rc==s.SCARD_S_SUCCESS and len(features)%6==0, 'Cannot discover driver features'
  escapes=[int.from_bytes(bytes(features[i+2:i+6]),'big') for i in range(0,len(features),6) if features[i]==0x13 and features[i+1]==4]
  assert len(escapes)==1, 'Driver escape feature unavailable'
  def control(command):
   rc,data=s.SCardControl(handle,escapes[0],command)
   print('UI control reply',hex(rc),list(data),flush=True)
   assert rc==s.SCARD_S_SUCCESS and len(data)==6 and data[0] in (0xe0,0xe1) and data[1:5]==[0,0,0,1], 'Vendor command not acknowledged'
   return data[5]
  old=control([0xe0,0,0,0x21,0]);new=old&~0x18
  if old!=new:assert control([0xe0,0,0,0x21,1,new])==new
  assert control([0xe0,0,0,0x21,0])==new
  record=dict(model='ACS ACR1552U',scan_beep_disabled=True,removal_beep_disabled=True,previous_ui=old,configured_ui=new)
  p=Path.home()/'zoco-monitor/laser-maze/control/reader-settings.json'
  p.write_text(json.dumps(record)+'\n');p.chmod(0o600)
  print(json.dumps(record))
 finally:s.SCardDisconnect(handle,s.SCARD_LEAVE_CARD)
finally:s.SCardReleaseContext(ctx)
'''
assert os.geteuid()==0, 'Run through sudo on the Pi'
original=DRIVER.read_bytes()
updated,count=re.subn(rb'(<key>ifdDriverOptions</key>\s*<string>)0x0000(</string>)',rb'\g<1>0x0001\2',original)
assert count==1, 'Unexpected driver configuration; no change made'
try:
 DRIVER.write_bytes(updated)
 subprocess.run(['systemctl','restart','pcscd.service'],check=True)
 time.sleep(1)
 subprocess.run(['runuser','-u','brent','--','python3','-c',CLIENT],check=True)
finally:
 DRIVER.write_bytes(original)
 subprocess.run(['systemctl','restart','pcscd.service'],check=True)
 assert DRIVER.read_bytes()==original
 print('Original driver restriction restored.')
