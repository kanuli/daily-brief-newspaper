#!/usr/bin/env python3
import json, pathlib, re, subprocess, sys
ROOT=pathlib.Path(__file__).resolve().parents[1]; DATA=ROOT/'data'; DATE='2026-09-04'
FLOORS={'world':8,'asia':8,'hong-kong':6,'japan':8,'market-economy':8,'ai-tech':6,'manga-anime':4,'manchester-united':4,'football':10}
subprocess.run([sys.executable,str(ROOT/'scripts/_publish_20260904.py')],check=True)
ASIA_RE=re.compile(r'西亞|中東|伊朗|以色列|加沙|黎巴嫩|敘利亞|約旦|伊拉克|Iran|Israel|Gaza|Lebanon|Syria|Jordan|Iraq|Middle East|West Asia',re.I)
PROCESS_RE=re.compile(r'今日未找到|採全產業掃描|本輪|本報|incremental|duplicate|重複刊登|coverage\s*(?:check|test)|collection\s*(?:design|test)|這次重新檢查|之後每一輪|每一輪Football|固定檢查HKFA|不應由全球搜尋排名決定|讀者應該看到的核心新聞',re.I)
PUBLIC_FIELDS=('title','dek','summary','body','context','why','watchNext')

def measure(t):
 c=len(re.findall(r'[\u3400-\u9fff]',str(t or '')))
 return c if c>=50 else len(re.sub(r'\s+','',str(t or '')))

def fix_story(s):
 body=str(s.get('body') or '').strip()
 if '\n\n' not in body:
  body=body+'\n\n'+str(s.get('context') or s.get('summary') or '')
 while measure(body)<100:
  add=' '.join(x for x in [str(s.get('context') or ''),str(s.get('why') or ''),str(s.get('watchNext') or '')] if x).strip()
  if not add: break
  body=body+'\n\n'+add
 s['body']=body
 return s

def is_process(s):
 return bool(PROCESS_RE.search(' '.join(str(s.get(k,'') or '') for k in PUBLIC_FIELDS)))

def is_asia_story(s):
 txt=' '.join(str(s.get(k,'') or '') for k in ('section','sectionLabel','title'))
 return bool(ASIA_RE.search(txt))

def save(path,obj): path.write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
# Desk Latest: repair body, remove internal-process copy, then enforce geography.
p=DATA/'desk-latest.json'; d=json.loads(p.read_text(encoding='utf-8')); desks=d.get('desks',{})
for slug,arr in list(desks.items()):
 cleaned=[]
 for s in arr:
  fix_story(s)
  if not is_process(s): cleaned.append(s)
 desks[slug]=cleaned
world=desks.get('world',[]); moved=[s for s in world if is_asia_story(s)]; desks['world']=[s for s in world if not is_asia_story(s)]
existing={s.get('id') for s in desks.get('asia',[])}
for s in moved:
 s['desk']='asia'; s['deskSlugs']=[x for x in s.get('deskSlugs',[]) if x!='world']
 if 'asia' not in s['deskSlugs']: s['deskSlugs'].append('asia')
 if s.get('id') not in existing: desks['asia'].insert(0,s); existing.add(s.get('id'))
for slug,minimum in FLOORS.items():
 assert len(desks.get(slug,[]))>=minimum, f'{slug} {len(desks.get(slug,[]))}<{minimum}'
save(p,d)
# Daily + topic-more: repair body, remove process stories/references, and route West Asia out of World.
for path in [DATA/'latest.json',DATA/f'{DATE}.json',DATA/'topic-more'/f'{DATE}.json']:
 o=json.loads(path.read_text(encoding='utf-8'))
 raw=o.get('articles',[])
 for s in raw: fix_story(s)
 removed={s.get('id') for s in raw if is_process(s)}
 o['articles']=[s for s in raw if s.get('id') not in removed]
 amap={s.get('id'):s for s in o.get('articles',[]) if isinstance(s,dict)}
 for sec in o.get('sections',[]):
  if isinstance(sec,dict): sec['articleIds']=[i for i in sec.get('articleIds',[]) if i in amap]
 secs={s.get('slug'):s for s in o.get('sections',[]) if isinstance(s,dict)}
 w=secs.get('world'); a=secs.get('asia')
 if w and a:
  bad=[i for i in list(w.get('articleIds',[])) if i in amap and is_asia_story(amap[i])]
  w['articleIds']=[i for i in w.get('articleIds',[]) if i not in bad]
  for i in bad:
   if i not in a.get('articleIds',[]): a.setdefault('articleIds',[]).append(i)
 if 'leadId' in o and o.get('leadId') not in amap:
  o['leadId']=next(iter(amap),None)
 if 'topFive' in o:
  o['topFive']=[i for i in o.get('topFive',[]) if i in amap]
 save(path,o)
print('PUBLIC COPY + BODY + WHOLE ASIA REPAIR COMPLETE')
for slug in FLOORS: print(slug,len(desks[slug]))
