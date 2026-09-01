#!/usr/bin/env python3
import copy, json, pathlib

ROOT = pathlib.Path(__file__).resolve().parents[1]
DATA = ROOT / 'data'
DATE = '2026-09-02'
EDITION = '014'
NOW = '2026-09-02T08:00:00+08:00'
FLOORS = {'world':8,'asia':8,'hong-kong':6,'japan':8,'market-economy':8,'ai-tech':6,'manga-anime':4,'manchester-united':4,'football':10}
META = {
 'world':('世界','歐洲 · 北美洲 · 南美洲 · 非洲 · 大洋洲（亞洲另見亞洲版）'),
 'asia':('亞洲','東亞 · 東南亞 · 南亞 · 中亞 · 西亞／中東 · Caucasus · 全亞洲'),
 'hong-kong':('香港','本地 · 社會 · 法庭 · 公共政策 · 民生'),
 'japan':('日本','社會 · 政治 · 司法 · 交通 · 教育 · 醫療 · 災害 · 勞工 · 文化 · 生活'),
 'market-economy':('📈 財經 / 全球市場','美國 · 歐洲 · 台灣 · 日本 · 香港 · 中國 · 全球'),
 'ai-tech':('AI / 科技','全球 AI · 半導體 · 軟件 · 科技'),
 'manga-anime':('漫畫 / Anime','動畫 · 漫畫 · 出版 · 電影 · 產業'),
 'manchester-united':('Manchester United','Club · Squad · Transfers · Fixtures'),
 'football':('Football','England · Europe · UEFA · International · J-League · Hong Kong · Worldwide'),
}

def load(p): return json.loads(p.read_text(encoding='utf-8'))
def dump(p,o): p.parent.mkdir(parents=True, exist_ok=True); p.write_text(json.dumps(o,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')

desk = load(DATA/'desk-latest.json')
live = load(DATA/'live.json')
archive = load(DATA/'archive.json')

# Normalize and dedupe current reservoir. World must exclude any Asia-tagged story.
clean = {}
for slug, minimum in FLOORS.items():
    seen=set(); rows=[]
    for s in desk.get('desks',{}).get(slug,[]):
        if not isinstance(s,dict) or not s.get('id') or s['id'] in seen: continue
        tags=s.get('deskSlugs') or []
        if slug=='world' and 'asia' in tags: continue
        seen.add(s['id']); rows.append(s)
    if len(rows) < minimum:
        raise SystemExit(f'HARD FLOOR FAIL before publication: {slug}={len(rows)} < {minimum}')
    clean[slug]=rows

# Freeze 07:00 current newspaper reservoir as the 08:00 Daily baseline.
desk['date']=DATE
desk['generatedAt']=NOW
desk['mode']='ROLLING_DESK_LATEST'
desk['editorialStandardVersion']=3
desk['contentVersion']=3
desk['desks']=clean
dump(DATA/'desk-latest.json',desk)

# Homepage: fresh 07:00 Live first, then balanced high-priority current stories.
home=[]; used=set()
def add(story):
    if not isinstance(story,dict): return
    sid=story.get('id')
    if not sid or sid in used: return
    x=copy.deepcopy(story); x['status']='LATEST'; home.append(x); used.add(sid)
for s in live.get('items',[]): add(s)
# Guarantee every newspaper desk appears on homepage at least once.
for slug in FLOORS:
    for s in clean[slug]:
        if s.get('id') not in used:
            add(s); break
# Add breadth until 18 stories, weighted to high-flow desks.
for slug in ['world','asia','japan','hong-kong','market-economy','ai-tech','football','market-economy','asia','world','japan','ai-tech','manchester-united','manga-anime']:
    if len(home)>=18: break
    for s in clean[slug]:
        if s.get('id') not in used:
            add(s); break
if len(home)<12: raise SystemExit(f'Homepage too thin: {len(home)}')

sections=[]
for slug,(title,subtitle) in META.items():
    ids=[]
    for a in home:
        tags=a.get('deskSlugs') or []
        if slug in tags or a.get('desk')==slug: ids.append(a['id'])
    sections.append({'slug':slug,'title':title,'subtitle':subtitle,'articleIds':ids})

# Top Five is editorial selection only, never a topic-page cap.
top=[]
for a in home:
    if a['id'] not in top: top.append(a['id'])
    if len(top)==5: break

daily={
 'editionNumber':EDITION,'date':DATE,'dateLabel':'2026年9月2日 星期三',
 'tagline':'全球更新 · 08:00 verified · v3長文','editorialStandardVersion':3,'contentVersion':3,
 'leadId':top[0],'topFive':top,'articles':home,'sections':sections
}
dump(DATA/'latest.json',daily); dump(DATA/f'{DATE}.json',daily)

# Topic-more contains the full non-homepage current reservoir, globally deduped.
extra_by_id={}
for slug in FLOORS:
    for s in clean[slug]:
        if s['id'] not in used and s['id'] not in extra_by_id: extra_by_id[s['id']]=s
extra=list(extra_by_id.values())
extra_ids=set(extra_by_id)
topic_sections=[]
for slug,(title,subtitle) in META.items():
    ids=[s['id'] for s in clean[slug] if s['id'] in extra_ids]
    topic_sections.append({'slug':slug,'title':title,'subtitle':subtitle,'articleIds':ids})
topic={'date':DATE,'editorialStandardVersion':3,'contentVersion':3,'articles':extra,'sections':topic_sections}
dump(DATA/'topic-more'/f'{DATE}.json',topic)

headline='；'.join(a['title'] for a in home[:3])
entry={'date':DATE,'shortDate':'02 SEP 2026','headline':headline,'topics':[v[0] for v in META.values()],'url':f'editions/{DATE}.html'}
archive['editions']=[entry]+[e for e in archive.get('editions',[]) if e.get('date')!=DATE]
dump(DATA/'archive.json',archive)

# 08:00 is Daily-only: no separate Live stories.
baseline={
 'mode':'DAILY_BASELINE','date':DATE,'editorialStandardVersion':3,'contentVersion':3,
 'lastUpdated':NOW,'lastUpdatedLabel':'2026年9月2日 08:00 HKT','windowLabel':'08:00 Daily Edition baseline',
 'nextUpdateLabel':'下一輪 Live 更新 09:00 HKT','newCount':0,'updatedCount':0,'developingCount':0,
 'coverage':{'status':'DAILY_BASELINE','checkedAt':NOW,'deskLatestStoryCounts':{k:len(v) for k,v in clean.items()},'deskLatestDepthMet':True,'japanCountVerified':len(clean['japan'])},
 'items':[]
}
dump(DATA/'live.json',baseline)

html=f'''<!doctype html><html lang="zh-Hant"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><base href="../"><meta name="theme-color" content="#111111"><title>{DATE}｜每日晨報 Daily Brief</title><link rel="stylesheet" href="assets/css/newspaper.css?v=20260902"><link rel="stylesheet" href="assets/css/extras.css?v=20260902"><link rel="stylesheet" href="assets/css/monitoring.css?v=20260902"></head><body data-edition="{DATE}"><div class="paper"><div class="utility-bar"><span>ARCHIVED EDITION · HONG KONG</span><span>NO. <span data-edition-number>{EDITION}</span></span></div><header class="masthead"><div class="masthead-side">世界 · 亞洲 · 香港 · 日本<br>財經 · Stock News · AI · Anime · Football</div><div class="brand"><div class="brand-kicker">個 人 化 電 子 報</div><h1>每日晨報</h1><div class="brand-en">DAILY BRIEF</div></div><div class="masthead-side right"><span data-edition-tagline>全球更新 · 08:00 verified · v3長文</span><br>ARCHIVED EDITION</div></header><nav class="section-nav" aria-label="新聞分版"><a href="live.html">Live</a><a href="index.html">頭版</a><a href="world.html">世界</a><a href="asia.html">亞洲</a><a href="hong-kong.html">香港</a><a href="japan.html">日本</a><a href="finance.html">📈 財經</a><a href="stocks.html">📊 Stock News</a><a href="technology.html">AI / 科技</a><a href="manga-anime.html">漫畫 / Anime</a><a href="manchester-united.html">Manchester United</a><a href="football.html">Football</a><a href="archive.html">Archive</a></nav><div class="date-strip"><span data-edition-date>{DATE}</span><span>GLOBAL VERIFIED DAILY</span></div><main><section class="lead-grid"><article class="lead-story" id="lead-story"><p>正在載入日報…</p></article><aside><div class="section-heading"><h2>今日必讀 5 則</h2><span>TOP FIVE</span></div><div class="top-five" id="top-five"></div></aside></section><div id="dynamic-sections"></div><section class="study-desk" id="study-desk"></section><p class="notice">此頁保存 {DATE} 版本；來源內容可能於原網站後續更新。</p></main><footer class="footer"><span>每日晨報 Daily Brief · {DATE}</span><span><a href="stocks.html">Stock News</a> · <a href="archive.html">Archive</a> · <a href="index.html">今日頭版</a></span></footer></div><script src="assets/js/newspaper.js?v=20260902" defer></script><script src="assets/js/daily-extras.js?v=20260902" defer></script><script src="assets/js/vocab-copy.js?v=20260902" defer></script><script src="assets/js/system-panel.js?v=20260902" defer></script></body></html>'''
(ROOT/'editions'/f'{DATE}.html').write_text(html,encoding='utf-8')
print('PUBLISHED',DATE,'homepage',len(home),'topic-more',len(extra),'desk-counts',{k:len(v) for k,v in clean.items()})
