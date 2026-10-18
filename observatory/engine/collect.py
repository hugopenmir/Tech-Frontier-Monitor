#!/usr/bin/env python3
"""CHINA 2035 intelligence-feed collector. No API key required.

The collector only discovers and classifies *candidate signals*; it never
promotes research maturity or edits vetted project dossiers.
"""
from __future__ import annotations
import argparse
import datetime as dt
import hashlib
import html
import json
import re
import sys
import unicodedata
from email.utils import parsedate_to_datetime
from pathlib import Path
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse
from urllib.request import Request, urlopen
import xml.etree.ElementTree as ET
from difflib import SequenceMatcher

ROOT=Path(__file__).resolve().parents[1]
DOCS=ROOT/'docs'
DEFAULT_SOURCES=ROOT/'sources.json'
TRACKING={'utm_source','utm_medium','utm_campaign','utm_content','utm_term','utm_id','fbclid','gclid','mc_cid','mc_eid'}
CHINA_TERMS=('china','chinese','beijing','shanghai','shenzhen','tsinghua','peking university','zhongguo','中国','中国科学院','华为','量子','科技','中科院','嫦娥','天宫','百度','宁德时代','华中科技','清华','华为','深度求索','长征','合肥','小米','字节','深海','杭州')
DOMAINS={
 'IA': ('artificial intelligence','ai model','llm','large language model','deepseek','qwen','agentic','ai for science','foundation model','大模型','人工智能','智能体','科学智能','通义'),
 'Semiconductores': ('semiconductor','lithography','asic','chip','hbm','ascend','microelectronics','晶圆','半导体','光刻','芯片','昇腾'),
 'Robótica': ('humanoid','robotic','embodied intelligence','robot ','robotics','具身智能','人形机器人','机器狗','机器人'),
 'Cuántica': ('quantum','qubit','superconducting quantum','量子','超导量子'),
 'Espacio': ('satellite','rocket','lunar','moon mission','space station','orbital','launch vehicle','chang’e','chang\'e','space solar','航天','太空','卫星','嫦娥','天宫','火箭','空间计算'),
 'Energía': ('fusion','tokamak','nuclear','battery','solar cell','photovoltaic','hydrogen','grid storage','renewable','hydropower','核聚变','新能源','储能','光伏','氢能','电网','电池','钍基'),
 'Transporte': ('maglev','high-speed rail','railway','hyperloop','autonomous driving','vehicle-road','rail transport','transport ai','磁悬浮','高铁','无人驾驶','智能道路','铁路'),
 'Ciudades': ('smart city','green city','urban brain','sponge city','smart highway','digital twin','zero carbon city','智慧城市','绿色城市','海绵城市','数字孪生','雄安'),
 'Conectividad': ('6g','telecommunications','network infrastructure','fiber optics','data center','east data west','6 ghz','算力','数据中心','6g网络','通信网络','东数西算'),
 'Bio': ('biotech','biomedical','gene edit','brain-computer','biomanufactur','drug discovery','bioscience','生物制造','脑机接口','生物医药','基因编辑','生命科学'),
 'Materiales': ('materials science','perovskite','advanced manufacturing','3d printing','rare earth','new materials','增材制造','先进材料','钙钛矿','稀土'),
 'Ciencia': ('scientific facility','research institute','laboratory','basic research','university','experimental station','实验室','科学装置','科学院','大学','研究所'),
}
SIGNALS={
 'regulación': ('draft regulation','export control','rule proposal','restrict export','regulatory','policy proposed','征求意见','出口管制'),
 'retraso': ('delayed','postponed','suspended','cancelled','failure','setback','推迟','延期','取消','失败'),
 'publicación': ('study published','journal','peer-reviewed','research paper','nature communications','preprint','论文','发表研究'),
 'financiamiento': ('investment','funding','fundraising','financing','grant','invests','融资','投资','出资'),
 'prueba': ('prototype','tested','trial','demonstrat','experiment','record','test flight','试验','测试','原型','实验'),
 'despliegue': ('commercial launch','deploy','operational','mass produc','enters service','工厂投产','规模化','投运','商业化'),
 'anuncio': ('announced','unveiled','plans to','roadmap','target','will build','宣称','计划','发布','宣布'),
}
TIER={'paper': 'investigación científica','official': 'institucional','press':'prensa','discovery':'agregador de descubrimiento'}


def nowiso(): return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat().replace('+00:00','Z')
def normalized(s):
 s=unicodedata.normalize('NFKC',s or '').casefold()
 return re.sub(r'[^\w\u3400-\u9fff]+',' ',s).strip()
def canonical(url):
 try:
  v=urlparse(url.strip())
  if v.scheme not in ('http','https'): return ''
  return urlunparse((v.scheme,v.netloc.lower(),re.sub('/+$','',v.path) or '/', '',urlencode(sorted((k,val) for k,val in parse_qsl(v.query) if k.lower() not in TRACKING)),''))
 except Exception: return ''
def digest(url,title): return hashlib.sha256((canonical(url)+'|'+normalized(title)[:160]).encode('utf8')).hexdigest()[:20]
def get_child(elem,key):
 for c in list(elem):
  if c.tag.split('}')[-1].lower()==key.lower(): return c
 return None
def child_text(elem,key):
 c=get_child(elem,key)
 return ''.join(c.itertext()).strip() if c is not None else ''
def entry_link(elem):
 for child in elem:
  if child.tag.split('}')[-1]=='link':
   href=child.attrib.get('href','')
   if href and child.attrib.get('rel','alternate') in ('alternate',''):return href
   if (child.text or '').strip().startswith('http'):return child.text.strip()
 return child_text(elem,'link')
def dateiso(raw):
 if not raw:return ''
 try:
  parsed=dt.datetime.fromisoformat(raw.replace('Z','+00:00'))
  if parsed.tzinfo is None: parsed=parsed.replace(tzinfo=dt.timezone.utc)
  return parsed.date().isoformat()
 except Exception: pass
 try:return parsedate_to_datetime(raw).date().isoformat()
 except Exception:return ''
def parse_feed(raw):
 root=ET.fromstring(raw)
 entries=[e for e in root.iter() if e.tag.split('}')[-1] in ('item','entry')]
 result=[]
 for e in entries:
  title=html.unescape(re.sub(r'<[^>]*>','',child_text(e,'title'))).strip()
  link=canonical(entry_link(e))
  published=dateiso(child_text(e,'pubDate') or child_text(e,'published') or child_text(e,'updated') or child_text(e,'date'))
  description=html.unescape(re.sub(r'<[^>]*>',' ',child_text(e,'description') or child_text(e,'summary'))).strip()
  if title and link: result.append({'title':title[:330], 'url':link,'published':published, 'excerpt':re.sub(r'\s+',' ',description)[:480]})
 return result

def classify(item, source):
 # Search/discovery queries may contain China only in the query but titles still need China/entity relevance.
 content=normalized(item['title']+' '+item.get('excerpt',''))
 if not any(k in content for k in CHINA_TERMS):
  # Many aggregator feeds omit the country; permitted when source curated on a specific project AND title mentions the entity.
  return None
 matches={domain:sum(1 for term in terms if term in content) for domain,terms in DOMAINS.items()}
 domain=max(matches,key=matches.get)
 if matches[domain]==0:return None
 kind=next((typ for typ,terms in SIGNALS.items() if any(term in content for term in terms)),'noticia')
 risk='Requiere fuente original y corroboración antes de actualizar un expediente.'
 if kind=='anuncio': risk='Declaración / plan: NO demuestra operación, rendimiento ni viabilidad comercial.'
 if kind=='publicación': risk='Verificar paper, método, métricas y replicación antes de interpretar el resultado.'
 if kind=='regulación': risk='Confirmar el texto y fase normativa; una propuesta NO es ley vigente.'
 return {'id':digest(item['url'],item['title']),'title':item['title'],'url':item['url'],'published':item.get('published') or '', 'excerpt':item.get('excerpt',''),'domain':domain,'signal_type':kind,'source_id':source['id'],'source_name':source['name'],'source_tier':source.get('tier','discovery'),'source_kind':TIER.get(source.get('tier','discovery'),'fuente sin clasificar'),'verification':'pendiente','maturity_change':False,'risk_note':risk,'detected':nowiso(),'review':'pendiente','project_id':None}

def load_json(path, default):
 try: return json.loads(Path(path).read_text(encoding='utf8'))
 except (FileNotFoundError,json.JSONDecodeError):return default

def write_json(path,data):
 path=Path(path);path.parent.mkdir(parents=True,exist_ok=True)
 path.write_text(json.dumps(data,ensure_ascii=False,indent=2,sort_keys=False)+'\n',encoding='utf8')

def process(sources_path=DEFAULT_SOURCES, outdir=DOCS, fixtures=None,days=21,verbose=False):
 outdir=Path(outdir)
 sources=load_json(sources_path,[])
 prev=load_json(outdir/'intelligence.json',{'items':[]})
 items={i['id']:i for i in prev.get('items',[]) if i.get('id')}
 # Preserve existing editorial review flags if a candidate is encountered again.
 health=[];added=[];now=dt.datetime.now(dt.timezone.utc)
 for source in sources:
  if not source.get('enabled',True):continue
  try:
   if fixtures is not None:
    fname=source['id']+'.xml'
    raw=(Path(fixtures)/fname).read_bytes()
   else:
    req=Request(source['url'],headers={'User-Agent':'China2035-FrontierObservatory/1.1 (+curated scientific discovery; no republishing)','Accept':'application/rss+xml,application/atom+xml,application/xml,text/xml,*/*'})
    with urlopen(req,timeout=18) as res:
     raw=res.read(2_500_000)
   entries=parse_feed(raw)
   new=0
   for rawitem in entries[:45]:
    # Age-gate: old publications are not "new" on initial backfill.
    if rawitem['published']:
     try:
      delta=(now.date()-dt.date.fromisoformat(rawitem['published'])).days
      if delta < -1 or delta > days:continue
     except Exception:pass
    item=classify(rawitem,source)
    if not item or item['id'] in items:continue
    # Near-title dedupe within domain, across mirrored feeds.
    simple=normalized(item['title'])
    dup=next((v for v in items.values() if v.get('domain')==item['domain'] and SequenceMatcher(None,simple,normalized(v.get('title',''))).ratio()>=.93),None)
    if dup:continue
    items[item['id']]=item;added.append(item);new+=1
   health.append({'id':source['id'],'name':source['name'],'status':'ok','checked_at':nowiso(),'fetched':len(entries),'added':new,'tier':source.get('tier','discovery')})
   if verbose:print(f"OK {source['id']}: {len(entries)} entries / +{new}")
  except Exception as e:
   health.append({'id':source['id'],'name':source['name'],'status':'error','checked_at':nowiso(),'fetched':0,'added':0,'error':str(e)[:240],'tier':source.get('tier','discovery')})
   if verbose:print(f"ERR {source['id']}: {e}",file=sys.stderr)
 # Candidate JSON is bounded to 1000 most-recent signals. Never mutate dossier status.
 all_items=sorted(items.values(),key=lambda a:(a.get('published') or '',a.get('detected') or ''),reverse=True)[:1000]
 out={'schema':1,'last_checked':nowiso(),'last_successful_sources':sum(h['status']=='ok' for h in health),'sources_total':len(health),'new_candidates_this_run':len(added),'items':all_items,'source_health':health,'disclaimer':'Machine-found candidates. Links/titles alone never validate milestones or upgrade maturity. Publication date not necessarily event date.'}
 write_json(outdir/'intelligence.json',out)
 history=load_json(outdir/'ingestion_history.json',{'runs':[]})
 previous=history.get('runs',[])
 previous.append({'time':out['last_checked'],'new_candidates':len(added),'successful_sources':out['last_successful_sources'],'failed_sources':len(health)-out['last_successful_sources'],'candidate_total':len(all_items)})
 history['runs']=previous[-90:];write_json(outdir/'ingestion_history.json',history)
 return out

if __name__=='__main__':
 ap=argparse.ArgumentParser(description='Collect candidate deeptech signals; no maturity promotions.')
 ap.add_argument('--sources',default=str(DEFAULT_SOURCES))
 ap.add_argument('--outdir',default=str(DOCS))
 ap.add_argument('--fixtures',default=None)
 ap.add_argument('--days',type=int,default=21)
 args=ap.parse_args()
 result=process(args.sources,args.outdir,args.fixtures,args.days,verbose=True)
 print(f"{len(result['items'])} candidates; +{result['new_candidates_this_run']} new; {result['last_successful_sources']}/{result['sources_total']} sources operational")
 if not result['last_successful_sources']: sys.exit(2)
