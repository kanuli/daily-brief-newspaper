#!/usr/bin/env python3
import copy, json, pathlib
ROOT=pathlib.Path(__file__).resolve().parents[1]; DATA=ROOT/'data'
DATE='2026-09-03'; EDITION='015'
META={'world':('世界','歐洲 · 北美洲 · 南美洲 · 非洲 · 大洋洲（亞洲另見亞洲版）'),'asia':('亞洲','東亞 · 東南亞 · 南亞 · 中亞 · 西亞／中東 · Caucasus · 全亞洲'),'hong-kong':('香港','本地 · 社會 · 法庭 · 公共政策 · 民生'),'japan':('日本','社會 · 政治 · 司法 · 交通 · 教育 · 醫療 · 災害 · 勞工 · 文化 · 生活'),'market-economy':('📈 財經 / 全球市場','美國 · 歐洲 · 台灣 · 日本 · 香港 · 中國 · 全球'),'ai-tech':('AI / 科技','全球 AI · 半導體 · 軟件 · 科技'),'manga-anime':('漫畫 / Anime','動畫 · 漫畫 · 出版 · 製作 · 平台 · 產業'),'manchester-united':('Manchester United','Club · Squad · Transfers · Fixtures'),'football':('Football','England · Europe · UEFA · International · J-League · Hong Kong · Worldwide')}
FLOORS={'world':8,'asia':8,'hong-kong':6,'japan':8,'market-economy':8,'ai-tech':6,'manga-anime':4,'manchester-united':4,'football':10}
def load(p): return json.loads(p.read_text(encoding='utf-8'))
def dump(p,o): p.parent.mkdir(parents=True,exist_ok=True); p.write_text(json.dumps(o,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def validate_story(s,label):
    for k in ('id','title','dek','summary','body','context','why','watchNext','sourceName','sourceUrl','timeLabel'):
        assert isinstance(s.get(k),str) and s[k].strip(),f'{label} missing {k}'
    assert len([x for x in s['body'].split('\n\n') if x.strip()])>=2,f'{label} paragraphs'
    assert len(''.join(s['body'].split()))>=100,f'{label} short body'
    assert isinstance(s.get('sources'),list) and s['sources'],f'{label} sources'
desk=load(DATA/'desk-latest.json')
assert desk.get('date')==DATE,f"desk date {desk.get('date')}"
assert int(desk.get('editorialStandardVersion',0))>=3 and int(desk.get('contentVersion',0))>=3
for slug,floor in FLOORS.items():
    rows=desk.get('desks',{}).get(slug,[]); ids=[x.get('id') for x in rows]
    assert len(ids)==len(set(ids)),f'duplicate ids {slug}'; assert len(rows)>=floor,f'{slug} {len(rows)} < {floor}'
    for i,s in enumerate(rows): validate_story(s,f'{slug}[{i}]')
assert len(desk['desks']['japan'])>=8
# Freeze 08:00 baseline from the already verified 07:00 current reservoir.
desk['generatedAt']='2026-09-03T08:00:00+08:00'; desk['editorialStandardVersion']=3; desk['contentVersion']=3; dump(DATA/'desk-latest.json',desk)
selected=[]; seen=set(); owner={}
def take(slug,n):
    before=sum(1 for s in selected if owner.get(s['id'])==slug)
    for s in desk['desks'][slug]:
        if s['id'] in seen: continue
        selected.append(copy.deepcopy(s)); seen.add(s['id']); owner[s['id']]=slug
        if sum(1 for x in selected if owner.get(x['id'])==slug)>=before+n: break
for slug,n in [('world',3),('asia',3),('hong-kong',2),('japan',3),('market-economy',2),('ai-tech',2),('manga-anime',1),('manchester-united',1),('football',1)]: take(slug,n)
for slug in META:
    if len(selected)>=18: break
    take(slug,18)
selected=selected[:18]
def first(slug): return next((s['id'] for s in selected if owner.get(s['id'])==slug),None)
top=[first('world'),first('asia'),first('hong-kong'),first('japan'),first('market-economy')]; top=[x for x in top if x]
for s in selected:
    if len(top)>=5: break
    if s['id'] not in top: top.append(s['id'])
sections=[]
for slug,(title,subtitle) in META.items():
    ids=[s['id'] for s in selected if owner.get(s['id'])==slug]
    if ids: sections.append({'slug':slug,'title':title,'subtitle':subtitle,'articleIds':ids})
latest={'editionNumber':EDITION,'date':DATE,'dateLabel':'2026年9月3日 星期四','tagline':'全球更新 · 08:00 verified · v3長文','editorialStandardVersion':3,'contentVersion':3,'leadId':top[0],'topFive':top,'articles':selected,'sections':sections}
dump(DATA/'latest.json',latest); dump(DATA/f'{DATE}.json',latest)
extras=[]; exseen=set(seen)
for slug in META:
    for s in desk['desks'][slug]:
        if s['id'] in exseen: continue
        extras.append(copy.deepcopy(s)); exseen.add(s['id'])
exsecs=[]
for slug,(title,subtitle) in META.items():
    pool={s['id'] for s in desk['desks'][slug]}; ids=[s['id'] for s in extras if s['id'] in pool]
    if ids: exsecs.append({'slug':slug,'title':title,'subtitle':subtitle,'articleIds':ids})
dump(DATA/'topic-more'/f'{DATE}.json',{'date':DATE,'editorialStandardVersion':3,'contentVersion':3,'articles':extras,'sections':exsecs})
counts={k:len(desk['desks'][k]) for k in FLOORS}
live={'mode':'DAILY_BASELINE','date':DATE,'editorialStandardVersion':3,'contentVersion':3,'lastUpdated':'2026-09-03T08:00:00+08:00','lastUpdatedLabel':'2026年9月3日 08:00 HKT','windowLabel':'08:00 HKT Daily Edition','nextUpdateLabel':'下一輪 Live 更新 09:00 HKT','newCount':0,'updatedCount':0,'developingCount':0,'items':[],'coverage':{'status':'DAILY_BASELINE','checkedAt':'2026-09-03T08:00:00+08:00','deskLatestStoryCounts':counts,'deskLatestDepthMet':True,'japanCountVerified':counts['japan'],'dailyEdition':DATE}}
dump(DATA/'live.json',live)
archive=load(DATA/'archive.json'); entry={'date':DATE,'shortDate':'03 SEP 2026','headline':'；'.join(next(s['title'] for s in selected if s['id']==sid) for sid in top[:3]),'topics':[v[0] for v in META.values()],'url':f'editions/{DATE}.html'}; archive['editions']=[entry]+[e for e in archive.get('editions',[]) if e.get('date')!=DATE]; dump(DATA/'archive.json',archive)
prev=(ROOT/'editions/2026-09-02.html').read_text(encoding='utf-8'); html=prev.replace('2026-09-02',DATE).replace('20260902','20260903').replace('>014<','>015<'); (ROOT/f'editions/{DATE}.html').write_text(html,encoding='utf-8')
print('PUBLISHED',DATE,'homepage',len(selected),'desk counts',counts)
