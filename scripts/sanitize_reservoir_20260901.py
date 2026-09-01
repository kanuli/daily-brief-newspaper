#!/usr/bin/env python3
import json, pathlib, re
ROOT=pathlib.Path(__file__).resolve().parents[1]
p=ROOT/'data'/'desk-latest.json'
d=json.loads(p.read_text(encoding='utf-8'))
patterns=[r'今日未找到',r'採全產業掃描',r'本輪',r'本報',r'incremental',r'duplicate',r'重複刊登',r'coverage (?:check|test)',r'collection (?:design|test)',r'這次重新檢查',r'之後每一輪',r'每一輪Football',r'不應由全球搜尋排名決定']
removed=[]
for slug,rows in d.get('desks',{}).items():
    keep=[]
    for s in rows:
        combined=' '.join(str(s.get(k,'')) for k in ('title','dek','summary','body','context','why','watchNext'))
        hit=next((pat for pat in patterns if re.search(pat,combined,re.I)),None)
        if hit:
            removed.append((slug,s.get('id'),hit))
        else:
            keep.append(s)
    d['desks'][slug]=keep
p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print('SANITIZED',len(removed),'stories',removed)
