import json
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'engine'))
from collect import canonical, parse_feed, classify, process
ROOT=Path(__file__).resolve().parents[1]
class PipelineTests(unittest.TestCase):
 def test_canonical(self):
  self.assertEqual(canonical('https://example.org/a?utm_source=feed&x=1#foo'), 'https://example.org/a?x=1')
 def test_rss_atom(self):
  for f in ('ai-science.xml','quantum.xml'):
   r=parse_feed((ROOT/'fixtures'/f).read_bytes());self.assertGreater(len(r),0)
  self.assertEqual(len(parse_feed((ROOT/'fixtures'/'quantum.xml').read_bytes())),1)
 def test_classify_without_country_discard(self):
  src={'id':'a','name':'A','tier':'press'}
  self.assertIsNone(classify({'title':'Autonomous cars in New York','url':'https://example.org/1'},src))
 def test_idempotence_and_state(self):
  with TemporaryDirectory() as temp:
   t=Path(temp);src=t/'sources.json';source=[{'id':'ai-science','name':'AI','tier':'discovery'},{'id':'quantum','name':'Quantum','tier':'paper'}]
   src.write_text(json.dumps(source));d=t/'docs'
   a=process(src,d,ROOT/'fixtures');self.assertEqual(a['new_candidates_this_run'],2)
   self.assertEqual(len(a['items']),2)
   b=process(src,d,ROOT/'fixtures');self.assertEqual(b['new_candidates_this_run'],0)
   self.assertEqual(len(b['items']),2)
   self.assertEqual(len(json.loads((d/'ingestion_history.json').read_text())['runs']),2)
   self.assertTrue(all(x['verification']=='pendiente' for x in b['items']))
   self.assertTrue(all(x['maturity_change'] is False for x in b['items']))
 def test_failed_sources_reported(self):
  with TemporaryDirectory() as temp:
   t=Path(temp);src=t/'sources.json';src.write_text(json.dumps([{'id':'missing','name':'Missing','tier':'press'}]))
   a=process(src,t/'docs',ROOT/'fixtures')
   self.assertEqual(a['last_successful_sources'],0)
   self.assertEqual(a['source_health'][0]['status'],'error')
if __name__=='__main__':unittest.main()
