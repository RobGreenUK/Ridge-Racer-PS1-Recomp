import csv,importlib.util,tempfile,unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
spec=importlib.util.spec_from_file_location('handoffs',ROOT/'tools/analyze_handoffs.py')
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
class HandoffWindowsTests(unittest.TestCase):
 def test_merge_markers_and_report_incomplete_tail(self):
  with tempfile.TemporaryDirectory() as d:
   p=Path(d)/'frames.csv'
   with p.open('w') as f:
    w=csv.DictWriter(f,fieldnames=['frame','wall_s','present_end_ns','event_marker','handoff_candidate','callback_skipped','marker_ms','telemetry_dropped']);w.writeheader()
    for i in range(30):w.writerow(dict(frame=i,wall_s=i,present_end_ns=i+1,event_marker=int(i>=12)+int(i>=29),handoff_candidate=int(i==15),callback_skipped=int(i==15),marker_ms=20 if i==14 else 0,telemetry_dropped=0))
   result=module.windows(p);self.assertEqual(len(result['windows']),2)
   a,b=result['windows'];self.assertEqual(a['start_s'],2);self.assertEqual(a['end_s'],18)
   self.assertEqual(len(a['events']),2);self.assertEqual(a['callback_skips'],1);self.assertEqual(a['capture_frames'],[14]);self.assertTrue(a['post_window_complete']);self.assertFalse(b['post_window_complete'])
