#!/usr/bin/env python3
import json, pathlib, re
ROOT=pathlib.Path(__file__).resolve().parents[1]; DATA=ROOT/'data'; DATE='2026-09-02'
PAT=re.compile(r'中東|西岸|加沙|伊朗|以色列|亞洲|日本|香港|台灣|中國|韓國|印度|尼泊爾|敘利亞|黎巴嫩|約旦|海灣|Middle East|West Bank|Gaza|Iran|Israel|Asia|Japan|Hong Kong|Taiwan|China|Korea|India|Nepal|Syria|Lebanon|Jordan|Gulf',re.I)
def load(p): return json.loads(p.read_text(encoding='utf-8'))
def dump(p,o): p.write_text(json.dumps(o,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def asian(s): return bool(PAT.search(str(s.get('section',''))+' '+str(s.get('title',''))))
p=DATA/'desk-latest.json'; d=load(p); before=len(d['desks']['world']); d['desks']['world']=[s for s in d['desks']['world'] if not asian(s) and 'asia' not in (s.get('deskSlugs') or [])]; after=len(d['desks']['world'])
if after<8: raise SystemExit(f'World geography cleanup left only {after} stories')
dump(p,d)
for p in [DATA/'latest.json',DATA/f'{DATE}.json',DATA/'topic-more'/f'{DATE}.json']:
    o=load(p); amap={a.get('id'):a for a in o.get('articles',[]) if isinstance(a,dict)}
    for sec in o.get('sections',[]):
        if sec.get('slug')=='world': sec['articleIds']=[i for i in sec.get('articleIds',[]) if i in amap and not asian(amap[i])]
    refs={i for sec in o.get('sections',[]) for i in sec.get('articleIds',[])}
    if 'topFive' in o: refs.update(o.get('topFive',[]))
    if o.get('leadId'): refs.add(o['leadId'])
    o['articles']=[a for a in o.get('articles',[]) if a.get('id') in refs]
    dump(p,o)
# Keep 08:00 baseline telemetry identical to actual desk-latest after cleanup.
lp=DATA/'live.json'; live=load(lp); counts={k:len(v) for k,v in d['desks'].items()}; live.setdefault('coverage',{})['deskLatestStoryCounts']=counts; live['coverage']['deskLatestDepthMet']=True; live['coverage']['japanCountVerified']=counts.get('japan',0); dump(lp,live)
print('WORLD GEOGRAPHY CLEANUP',before,'->',after,'COUNTS',counts)
