import sys,unittest
from pathlib import Path
from collections import deque
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from panel_game import StatusFrames
class Port:
 def __init__(self):self.writes=[]
 def write(self,data):self.writes.append(data)
 def flush(self):pass
class StatusFrameTests(unittest.TestCase):
 def setUp(self):self.port=Port();self.replies=deque();self.now=0;self.link=StatusFrames(self.port,self.replies,clock=lambda:self.now)
 def ack(self):
  _,_,callback=self.replies.popleft()
  if callback:callback()
 def test_frames_never_overlap_other_requests(self):
  self.link.tick(0);self.assertEqual(self.port.writes,[])
  self.link.send('RGB RED','OK RGB RED');self.link.tick(.1);self.assertEqual(len(self.port.writes),1)
  self.ack();self.link.tick(.2);self.assertEqual(self.port.writes[-1],b'FRAME\n');self.assertTrue(self.link.waiting)
  self.link.send('LIGHT','LIGHT A0');self.link.send('HB','OK HB');self.assertEqual(self.port.writes[-1],b'FRAME\n')
  self.ack();self.assertEqual(self.port.writes[-2:],[b'LIGHT\n',b'HB\n']);self.assertFalse(self.link.waiting)
  self.link.tick(.3);self.assertEqual(self.port.writes[-1],b'HB\n')
 def test_frame_timer_finishes_and_off_disables_it(self):
  self.link.send('RGB BLUE','OK RGB BLUE');self.ack();self.link.tick(2);self.assertNotIn(b'FRAME\n',self.port.writes)
  self.link.send('RGB OFF','OK RGB OFF');self.ack();self.link.tick(.1);self.assertNotIn(b'FRAME\n',self.port.writes)
 def test_deferred_callbacks_are_retained(self):
  called=[];self.link.send('RGB GREEN','OK RGB GREEN');self.ack();self.link.tick(.1)
  self.link.send('CAL 20 41','OK CAL 20 41',lambda:called.append(True));self.ack();self.assertFalse(called)
  self.ack();self.assertTrue(called)
if __name__=='__main__':unittest.main()
