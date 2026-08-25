#!/usr/bin/env python3
import json, pathlib
ROOT=pathlib.Path(__file__).resolve().parents[1]; D=ROOT/'data'
labels={'world':'世界','asia':'亞洲','hong-kong':'香港','japan':'日本','market-economy':'財經／全球市場','ai-tech':'AI／科技','manga-anime':'漫畫／Anime','manchester-united':'Manchester United','football':'Football'}
required=['id','title','dek','summary','body','context','why','watchNext','sourceName','sourceUrl','timeLabel']
public_fields=['title','dek','summary','body','context','why','watchNext']
replacements={'本輪':'開幕輪','本報':'新聞版','incremental':'新增','duplicate':'重複內容'}

def sanitize_story(x):
    for k in public_fields:
        if isinstance(x.get(k),str):
            for a,b in replacements.items(): x[k]=x[k].replace(a,b)
    return x

p=D/'desk-latest.json'; d=json.loads(p.read_text(encoding='utf-8'))
for slug,items in d.get('desks',{}).items():
    cleaned=[]
    for x in items:
        if not isinstance(x,dict) or any(not str(x.get(k,'')).strip() for k in required): continue
        sanitize_story(x)
        x.setdefault('desk',slug); x.setdefault('deskSlugs',[slug]); x.setdefault('section',labels.get(slug,slug)); x.setdefault('status','LATEST')
        if not isinstance(x.get('sources'),list) or not x['sources']: x['sources']=[{'name':x['sourceName'],'url':x['sourceUrl']}]
        cleaned.append(x)
    d['desks'][slug]=cleaned
p.write_text(json.dumps(d,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
for path in [D/'latest.json',D/'2026-08-25.json',D/'topic-more'/'2026-08-25.json']:
    obj=json.loads(path.read_text(encoding='utf-8'))
    for x in obj.get('articles',[]): sanitize_story(x)
    path.write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
print('NORMALIZED', {k:len(v) for k,v in d['desks'].items()})
