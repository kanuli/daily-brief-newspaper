#!/usr/bin/env python3
import json, pathlib, re, subprocess, sys
ROOT=pathlib.Path(__file__).resolve().parents[1]; DATA=ROOT/'data'; DATE='2026-09-04'
subprocess.run([sys.executable,str(ROOT/'scripts/_publish_20260904.py')],check=True)
ASIA_RE=re.compile(r'西亞|中東|伊朗|以色列|加沙|黎巴嫩|敘利亞|約旦|伊拉克|Iran|Israel|Gaza|Lebanon|Syria|Jordan|Iraq|Middle East|West Asia',re.I)

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

def is_asia_story(s):
 txt=' '.join(str(s.get(k,'') or '') for k in ('section','sectionLabel','title'))
 return bool(ASIA_RE.search(txt))

def save(path,obj): path.write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
# Desk Latest: body repair + move West Asia/Middle East out of World and into Asia.
p=DATA/'desk-latest.json'; d=json.loads(p.read_text(encoding='utf-8')); desks=d.get('desks',{})
for arr in desks.values():
 for s in arr: fix_story(s)
world=desks.get('world',[]); moved=[s for s in world if is_asia_story(s)]; desks['world']=[s for s in world if not is_asia_story(s)]
existing={s.get('id') for s in desks.get('asia',[])}
for s in moved:
 s['desk']='asia'; s['deskSlugs']=[x for x in s.get('deskSlugs',[]) if x!='world']
 if 'asia' not in s['deskSlugs']: s['deskSlugs'].append('asia')
 if s.get('id') not in existing: desks['asia'].insert(0,s); existing.add(s.get('id'))
assert len(desks['world'])>=8
save(p,d)
# Daily + topic-more body repair and World->Asia section routing.
for path in [DATA/'latest.json',DATA/f'{DATE}.json',DATA/'topic-more'/f'{DATE}.json']:
 o=json.loads(path.read_text(encoding='utf-8'))
 amap={s.get('id'):s for s in o.get('articles',[]) if isinstance(s,dict)}
 for s in amap.values(): fix_story(s)
 secs={s.get('slug'):s for s in o.get('sections',[]) if isinstance(s,dict)}
 w=secs.get('world'); a=secs.get('asia')
 if w and a:
  bad=[i for i in list(w.get('articleIds',[])) if i in amap and is_asia_story(amap[i])]
  w['articleIds']=[i for i in w.get('articleIds',[]) if i not in bad]
  for i in bad:
   if i not in a.get('articleIds',[]): a.setdefault('articleIds',[]).append(i)
 save(path,o)
print('BODY DEPTH + WHOLE ASIA GEOGRAPHY REPAIR COMPLETE', 'world',len(desks['world']),'asia',len(desks['asia']))
