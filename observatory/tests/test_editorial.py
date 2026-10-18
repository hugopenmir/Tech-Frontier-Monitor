import json,sys,unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from shutil import copyfile
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'engine'))
from apply_reviews import merge
ROOT=Path(__file__).resolve().parents[1]
class ReviewTests(unittest.TestCase):
 def test_apply_review_no_maturity_mutation_and_idempotent(self):
  with TemporaryDirectory() as temp:
   t=Path(temp)
   for name in ('projects.json','intelligence.json'):copyfile(ROOT/'docs'/name,t/name)
   cand=json.loads((t/'intelligence.json').read_text())['items'][0]['id']
   export=t/'export.json';export.write_text(json.dumps({'reviews':[{'id':cand,'review':'revisada','project':'orbital'}]}))
   changed=merge(export,t);self.assertEqual(len(changed),1)
   self.assertFalse(changed[0]['maturity_changed'])
   self.assertEqual(len(merge(export,t)),0)
   self.assertEqual(len(json.loads((t/'review_log.json').read_text())['events']),1)
   data=json.loads((t/'projects.json').read_text())
   self.assertEqual(len(data['projects']),26)
   export.write_text(json.dumps({'reviews':[{'id':cand,'review':'aprobada','project':None}]}))
   with self.assertRaises(ValueError):merge(export,t)
if __name__=='__main__':unittest.main()
