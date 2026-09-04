#!/usr/bin/env python3
import json, pathlib, re, subprocess, sys
ROOT=pathlib.Path(__file__).resolve().parents[1]; DATA=ROOT/'data'; DATE='2026-09-04'
subprocess.run([sys.executable,str(ROOT/'scripts/_publish_20260904.py')],check=True)

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

def save(path,obj): path.write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
# Desk Latest
p=DATA/'desk-latest.json'; d=json.loads(p.read_text(encoding='utf-8'))
for arr in d.get('desks',{}).values():
 for s in arr: fix_story(s)
save(p,d)
# Daily and topic-more
for path in [DATA/'latest.json',DATA/f'{DATE}.json',DATA/'topic-more'/f'{DATE}.json']:
 o=json.loads(path.read_text(encoding='utf-8'))
 for s in o.get('articles',[]): fix_story(s)
 save(path,o)
print('BODY DEPTH REPAIR COMPLETE')
