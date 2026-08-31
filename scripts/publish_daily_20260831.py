#!/usr/bin/env python3
import copy, json, pathlib
from datetime import datetime

ROOT = pathlib.Path(__file__).resolve().parents[1]
DATA = ROOT / 'data'
DATE = '2026-08-31'
EDITION = '012'

SLUG_META = {
    'world': ('世界','歐洲 · 北美洲 · 南美洲 · 非洲 · 大洋洲（亞洲另見亞洲版）'),
    'asia': ('亞洲','東亞 · 東南亞 · 南亞 · 中亞 · 西亞／中東 · Caucasus · 全亞洲'),
    'hong-kong': ('香港','本地 · 社會 · 法庭 · 公共政策 · 民生'),
    'japan': ('日本','社會 · 政治 · 司法 · 交通 · 教育 · 醫療 · 災害 · 勞工 · 文化 · 生活'),
    'market-economy': ('📈 財經 / 全球市場','美國 · 歐洲 · 台灣 · 日本 · 香港 · 中國 · 全球'),
    'ai-tech': ('AI / 科技','全球 AI · 半導體 · 軟件 · 科技'),
    'manga-anime': ('漫畫 / Anime','動畫 · 漫畫 · 出版 · 製作 · 平台 · 產業'),
    'manchester-united': ('Manchester United','Club · Squad · Transfers · Fixtures'),
    'football': ('Football','England · Europe · UEFA · International · J-League · Hong Kong · Worldwide'),
}
FLOORS = {'world':8,'asia':8,'hong-kong':6,'japan':8,'market-economy':8,'ai-tech':6,'manga-anime':4,'manchester-united':4,'football':10}


def load(path): return json.loads(path.read_text(encoding='utf-8'))
def dump(path, obj):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(obj, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


desk = load(DATA/'desk-latest.json')
assert desk.get('date') == DATE, f"desk-latest date is {desk.get('date')}"
assert int(desk.get('editorialStandardVersion',0)) >= 3 and int(desk.get('contentVersion',0)) >= 3

# 07:45+ discovery recovery: independently reverified against Reuters + AP.
iran = {
  'id':'asia-us-iran-larak-strike-20260831-0745',
  'desk':'asia','status':'LATEST',
  'title':'美軍再空襲伊朗 Larak Island 火箭發射器　近一個月軍事停頓結束、霍爾木茲風險再升',
  'dek':'美方稱伊朗革命衛隊正準備把帶水雷的火箭系統部署到海峽；伊朗其後向駐約旦美軍發射彈道導彈並誓言報復。',
  'summary':'Reuters 與 AP 均確認，美軍8月30日打擊伊朗 Larak Island 兩個火箭發射器，是7月以來首次公開披露的美軍對伊朗攻擊；事件重新提高霍爾木茲航運及能源供應風險。',
  'body':'美國官員向 Reuters 及 Associated Press 證實，美軍8月30日對伊朗 Larak Island 的兩個火箭發射器發動攻擊，是近一個月來首次公開披露的美軍對伊朗軍事行動。美方表示，相關設施由伊朗革命衛隊操作，當時正準備把海雷相關武器部署到霍爾木茲海峽附近；伊朗媒體其後報告有人員傷亡，革命衛隊亦公開表示會作出回應。\n\n伊朗其後向駐約旦美軍方向發射彈道導彈，約旦方面表示攔截多枚來襲目標。霍爾木茲海峽在正常情況下承載全球約五分之一石油運輸，今次軍事行動打破此前短暫降溫，市場會重新評估海上布雷、船舶改道、保險費及原油風險溢價。',
  'context':'美伊衝突在2026年持續反覆升降溫；美國近月一度把重心轉向經濟及金融制裁，但仍警告伊朗若在霍爾木茲布雷將面臨軍事回應。',
  'why':'霍爾木茲是全球最重要能源咽喉之一。美軍重新動武及伊朗報復訊號會直接影響油價、航運、保險、亞洲進口能源成本及區域安全判斷。',
  'watchNext':'留意伊朗是否再向美軍基地或航運目標報復、美國會否擴大打擊、霍爾木茲船流與海雷清除情況，以及油價和航運保費反應。',
  'sourceName':'Reuters／Associated Press',
  'sourceUrl':'https://www.reuters.com/world/middle-east/us-forces-strike-two-iranian-launchers-irans-larak-island-us-official-says-2026-08-30/',
  'timeLabel':'8月31日07:45 HKT前重新核實',
  'sources':[
    {'name':'Reuters','url':'https://www.reuters.com/world/middle-east/us-forces-strike-two-iranian-launchers-irans-larak-island-us-official-says-2026-08-30/'},
    {'name':'Associated Press','url':'https://apnews.com/article/6b098da673ac3161a266ee459d5eff44'}
  ],
  'deskSlugs':['asia','market-economy'],
  'section':'亞洲｜西亞／伊朗／霍爾木茲'
}
for slug in ('asia','market-economy'):
    rows = [s for s in desk['desks'][slug] if s.get('id') != iran['id'] and 'Larak' not in s.get('title','')]
    desk['desks'][slug] = [copy.deepcopy(iran)] + rows

desk['date'] = DATE
desk['generatedAt'] = '2026-08-31T08:00:00+08:00'
desk['editorialStandardVersion'] = 3
desk['contentVersion'] = 3
for slug, floor in FLOORS.items():
    ids = [s.get('id') for s in desk['desks'].get(slug,[])]
    assert len(ids) == len(set(ids)), f'duplicate ids in {slug}'
    assert len(ids) >= floor, f'{slug} {len(ids)} < {floor}'
assert len(desk['desks']['japan']) >= 8

dump(DATA/'desk-latest.json', desk)

# Build homepage: 16 unique highest-priority stories, while topic pages retain the full reservoir.
selected=[]; selected_ids=set(); chosen_slug={}
def take(slug, n):
    for story in desk['desks'][slug]:
        sid=story.get('id')
        if not sid or sid in selected_ids: continue
        selected.append(copy.deepcopy(story)); selected_ids.add(sid); chosen_slug[sid]=slug
        if sum(1 for x in selected if chosen_slug.get(x['id'])==slug) >= n: break

# Lead is the newly verified Iran escalation, followed by broad desk coverage.
selected.append(copy.deepcopy(iran)); selected_ids.add(iran['id']); chosen_slug[iran['id']]='asia'
for slug,n in [('world',3),('asia',2),('hong-kong',2),('japan',2),('market-economy',2),('ai-tech',1),('manga-anime',1),('manchester-united',1),('football',1)]: take(slug,n)
# Fill to 16 if cross-desk dedupe reduced the count.
for slug in SLUG_META:
    if len(selected)>=16: break
    take(slug,16)
selected=selected[:16]

# Top Five: Iran escalation + leading World, Japan, Finance and Football stories.
def first_id(slug):
    return next((s['id'] for s in selected if chosen_slug.get(s['id'])==slug), None)
top=[iran['id'], first_id('world'), first_id('japan'), first_id('market-economy'), first_id('football')]
top=[x for x in top if x]
for s in selected:
    if len(top)>=5: break
    if s['id'] not in top: top.append(s['id'])

sections=[]
for slug,(title,subtitle) in SLUG_META.items():
    ids=[s['id'] for s in selected if chosen_slug.get(s['id'])==slug]
    if ids: sections.append({'slug':slug,'title':title,'subtitle':subtitle,'articleIds':ids})

latest={
 'editionNumber':EDITION,'date':DATE,'dateLabel':'2026年8月31日 星期一',
 'tagline':'全球更新 · 08:00 verified · v3長文',
 'editorialStandardVersion':3,'contentVersion':3,
 'leadId':iran['id'],'topFive':top,'articles':selected,'sections':sections
}
dump(DATA/'latest.json', latest); dump(DATA/f'{DATE}.json', latest)

# Topic-more: every current reservoir story not already on homepage, deduped globally.
extras=[]; seen=set(selected_ids)
for slug in SLUG_META:
    for story in desk['desks'][slug]:
        sid=story.get('id')
        if not sid or sid in seen: continue
        extras.append(copy.deepcopy(story)); seen.add(sid)
extra_sections=[]
for slug,(title,subtitle) in SLUG_META.items():
    ids=[]
    pool_ids={s['id'] for s in desk['desks'][slug]}
    for s in extras:
        if s['id'] in pool_ids: ids.append(s['id'])
    if ids: extra_sections.append({'slug':slug,'title':title,'subtitle':subtitle,'articleIds':ids})
topic={'date':DATE,'editorialStandardVersion':3,'contentVersion':3,'articles':extras,'sections':extra_sections}
dump(DATA/'topic-more'/f'{DATE}.json', topic)

# 08:00 is Daily-exclusive; Live becomes a clean Daily baseline.
counts={slug:len(desk['desks'][slug]) for slug in FLOORS}
live={
 'mode':'DAILY_BASELINE','date':DATE,'editorialStandardVersion':3,'contentVersion':3,
 'lastUpdated':'2026-08-31T08:00:00+08:00','lastUpdatedLabel':'2026年8月31日 08:00 HKT',
 'windowLabel':'08:00 HKT Daily Edition','nextUpdateLabel':'下一輪 Live 更新 09:00 HKT',
 'newCount':0,'updatedCount':0,'developingCount':0,'items':[],
 'coverage':{'status':'DAILY_BASELINE','checkedAt':'2026-08-31T08:00:00+08:00','deskLatestStoryCounts':counts,'deskLatestDepthMet':True,'japanCountVerified':counts['japan'],'dailyEdition':DATE}
}
dump(DATA/'live.json', live)

# Archive.
archive=load(DATA/'archive.json')
entry={'date':DATE,'shortDate':'31 AUG 2026','headline':'；'.join(next(s['title'] for s in selected if s['id']==sid) for sid in top[:3]),
       'topics':[m[0] for m in SLUG_META.values()],'url':f'editions/{DATE}.html'}
archive['editions']=[entry]+[e for e in archive.get('editions',[]) if e.get('date')!=DATE]
dump(DATA/'archive.json', archive)

# Archived shell.
html=f'''<!doctype html><html lang="zh-Hant"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><base href="../"><meta name="theme-color" content="#111111"><title>{DATE}｜每日晨報 Daily Brief</title><link rel="stylesheet" href="assets/css/newspaper.css?v=20260831"><link rel="stylesheet" href="assets/css/extras.css?v=20260831"><link rel="stylesheet" href="assets/css/monitoring.css?v=20260831"></head><body data-edition="{DATE}"><div class="paper"><div class="utility-bar"><span>ARCHIVED EDITION · HONG KONG</span><span>NO. <span data-edition-number>{EDITION}</span></span></div><header class="masthead"><div class="masthead-side">世界 · 亞洲 · 香港 · 日本<br>財經 · Stock News · AI · Anime · Football</div><div class="brand"><div class="brand-kicker">個 人 化 電 子 報</div><h1>每日晨報</h1><div class="brand-en">DAILY BRIEF</div></div><div class="masthead-side right"><span data-edition-tagline>全球更新 · 08:00 verified · v3長文</span><br>ARCHIVED EDITION</div></header><nav class="section-nav" aria-label="新聞分版"><a href="live.html">Live</a><a href="index.html">頭版</a><a href="world.html">世界</a><a href="asia.html">亞洲</a><a href="hong-kong.html">香港</a><a href="japan.html">日本</a><a href="finance.html">📈 財經</a><a href="stocks.html">📊 Stock News</a><a href="technology.html">AI / 科技</a><a href="manga-anime.html">漫畫 / Anime</a><a href="manchester-united.html">Manchester United</a><a href="football.html">Football</a><a href="archive.html">Archive</a></nav><div class="date-strip"><span data-edition-date>{DATE}</span><span>GLOBAL VERIFIED DAILY</span></div><main><section class="lead-grid"><article class="lead-story" id="lead-story"><p>正在載入日報…</p></article><aside><div class="section-heading"><h2>今日必讀 5 則</h2><span>TOP FIVE</span></div><div class="top-five" id="top-five"></div></aside></section><div id="dynamic-sections"></div><section class="study-desk" id="study-desk"></section><p class="notice">此頁保存 {DATE} 版本；來源內容可能於原網站後續更新。</p></main><footer class="footer"><span>每日晨報 Daily Brief · {DATE}</span><span><a href="stocks.html">Stock News</a> · <a href="archive.html">Archive</a> · <a href="index.html">今日頭版</a></span></footer></div><script src="assets/js/newspaper.js?v=20260831" defer></script><script src="assets/js/daily-extras.js?v=20260831" defer></script><script src="assets/js/vocab-copy.js?v=20260831" defer></script><script src="assets/js/system-panel.js?v=20260831" defer></script></body></html>'''
(ROOT/'editions').mkdir(exist_ok=True)
(ROOT/'editions'/f'{DATE}.html').write_text(html, encoding='utf-8')

# Publication assertions.
assert latest['leadId'] in {a['id'] for a in latest['articles']}
assert len(latest['topFive']) == 5 and all(i in {a['id'] for a in latest['articles']} for i in latest['topFive'])
assert 12 <= len(latest['articles']) <= 20
assert counts['japan'] >= 8
print('PUBLISH DAILY 2026-08-31 OK', counts, 'homepage', len(selected), 'topic-more', len(extras))
