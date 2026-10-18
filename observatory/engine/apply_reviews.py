#!/usr/bin/env python3
"""Import an editorial review export into the versioned site data.

This only updates review status/project cross-reference and an audit log.
It does NOT change technological maturity, dossier evidence, or policy goals.
"""
from __future__ import annotations
import argparse
import datetime as dt
import json
from pathlib import Path

ROOT=Path(__file__).resolve().parents[1]
DOCS=ROOT/'docs'
ALLOWED={'pendiente','revisada','descartada'}

def load(p, default):
 try:return json.loads(Path(p).read_text(encoding='utf8'))
 except FileNotFoundError:return default

def merge(infile, docdir=DOCS):
 docdir=Path(docdir)
 submission=load(infile,{})
 if not isinstance(submission.get('reviews'),list):raise ValueError('Expected JSON containing reviews[] from Observatory')
 candidates=load(docdir/'intelligence.json',{'items':[]}).get('items',[])
 projectdb=load(docdir/'projects.json',{'projects':[]}).get('projects',[])
 valid_candidates={i['id'] for i in candidates}
 valid_projects={i['id'] for i in projectdb}
 reviewfile=docdir/'editorial_reviews.json'
 current=load(reviewfile,{'reviews':{}})
 previous=current.get('reviews',{})
 changelogfile=docdir/'review_log.json'
 log=load(changelogfile,{'events':[]})
 now=dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace('+00:00','Z')
 changed=[]
 for entry in submission['reviews']:
  cid=entry.get('id')
  if cid not in valid_candidates:raise ValueError(f'Unknown candidate id: {cid}')
  review=entry.get('review','pendiente')
  project=entry.get('project') or None
  if review not in ALLOWED:raise ValueError(f'Invalid review state for {cid}: {review}')
  if project and project not in valid_projects:raise ValueError(f'Unknown project id: {project}')
  newer={'review':review,'project':project,'updated_at':now}
  old=previous.get(cid)
  if old and old.get('review')==review and old.get('project')==project:continue
  previous[cid]=newer
  changed.append({'candidate_id':cid,'previous':{'review':old.get('review'),'project':old.get('project')} if old else None,'next':{'review':review,'project':project},'recorded_at':now,'type':'editorial_triage','maturity_changed':False})
 current={'schema':1,'reviews':previous}
 log['events']=(log.get('events',[])+changed)[-3000:]
 reviewfile.write_text(json.dumps(current,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
 changelogfile.write_text(json.dumps(log,ensure_ascii=False,indent=2)+'\n',encoding='utf8')
 return changed

if __name__=='__main__':
 parser=argparse.ArgumentParser()
 parser.add_argument('exported_reviews',help='The JSON downloaded with “Exportar revisión”')
 parser.add_argument('--docdir',default=str(DOCS))
 args=parser.parse_args()
 diffs=merge(args.exported_reviews,args.docdir)
 print(f'{len(diffs)} editorial changes persisted. No maturity updates performed.')
