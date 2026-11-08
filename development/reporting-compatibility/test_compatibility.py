import importlib.util,json,sqlite3,tempfile,unittest
from pathlib import Path
spec=importlib.util.spec_from_file_location('agent',Path(__file__).with_name('zoco_agent.py'));agent=importlib.util.module_from_spec(spec);spec.loader.exec_module(agent)
class Tests(unittest.TestCase):
 def test_oversized_heartbeat_keeps_game_machine_data_and_original(self):
  for count in (42,43):
   metrics={f'metric_{i}':i for i in range(count-3)};metrics.update(rfid_scan_count=2,entry_state='idle',rfid_reader_available=True)
   original=dict(state='ready',metrics=metrics);encoded=json.dumps(original)
   sent=agent.transport_payload('heartbeat',original)
   self.assertEqual(len(sent['metrics']),40);self.assertEqual(json.dumps(original),encoded)
   for key in list(metrics)[:-3]:self.assertEqual(sent['metrics'][key],metrics[key])
 def test_valid_status_and_result_unchanged(self):
  value=dict(state='ready',metrics={f'm_{i}':i for i in range(40)})
  self.assertIs(agent.transport_payload('status',value),value)
  self.assertIs(agent.transport_payload('bench_game_result',value),value)
 def test_unrelated_oversize_is_rejected_not_dropped(self):
  with self.assertRaises(ValueError):agent.transport_payload('heartbeat',dict(metrics={f'm_{i}':i for i in range(41)}))
 def test_batch_retains_event_identity_and_original_queue_payload(self):
  with tempfile.TemporaryDirectory() as d:
   instance=agent.Agent.__new__(agent.Agent);instance.config={'device_id':'test'};instance.db=sqlite3.connect(Path(d)/'queue.sqlite3')
   instance.db.execute('CREATE TABLE events(event_id TEXT,occurred_at TEXT,kind TEXT,payload TEXT,sent INTEGER)')
   payload=dict(state='ready',metrics={f'm_{i}':i for i in range(40)});payload['metrics'].update(rfid_scan_count=2,entry_state='idle',rfid_reader_available=True)
   raw=json.dumps(payload);instance.db.execute('INSERT INTO events VALUES(?,?,?,?,0)',('same-id','2026-10-27T00:00:00.000000Z','heartbeat',raw));instance.db.commit()
   batch=instance.make_batch();self.assertEqual(batch['events'][0]['event_id'],'same-id');self.assertEqual(len(batch['events'][0]['payload']['metrics']),40)
   self.assertEqual(instance.db.execute('SELECT payload,sent FROM events').fetchone(),(raw,0));instance.close()
if __name__=='__main__':unittest.main()
