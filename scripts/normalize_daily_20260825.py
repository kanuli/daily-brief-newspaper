#!/usr/bin/env python3
import json, pathlib
p=pathlib.Path(__file__).resolve().parents[1]/'data'/'desk-latest.json'
d=json.loads(p.read_text(encoding='utf-8'))
labels={'world':'世界','asia':'亞洲','hong-kong':'香港','japan':'日本','market-economy':'財經／全球市場','ai-tech':'AI／科技','manga-anime':'漫畫／Anime','manchester-united':'Manchester United','football':'Football'}
required=['id','title','dek','summary','body','context','why','watchNext','sourceName','sourceUrl','timeLabel']
for slug,items in d.get('desks',{}).items():
    cleaned=[]
    for x in items:
        if not isinstance(x,dict) or any(not str(x.get(k,'')).strip() for k in required):
            continue
        x.setdefault('desk',slug); x.setdefault('deskSlugs',[slug]); x.setdefault('section',labels.get(slug,slug)); x.setdefault('status','LATEST')
        if not isinstance(x.get('sources'),list) or not x['sources']:
            x['sources']=[{'name':x['sourceName'],'url':x['sourceUrl']}]
        cleaned.append(x)
    d['desks'][slug]=cleaned
p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print('NORMALIZED', {k:len(v) for k,v in d['desks'].items()})
