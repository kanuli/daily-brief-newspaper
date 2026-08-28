#!/usr/bin/env python3
import copy, json, pathlib, re
from datetime import datetime

ROOT=pathlib.Path(__file__).resolve().parents[1]
DATA=ROOT/'data'
DATE='2026-08-28'
NOW='2026-08-28T08:00:00+08:00'
FLOORS={'world':8,'asia':8,'hong-kong':6,'japan':8,'market-economy':8,'ai-tech':6,'manga-anime':4,'manchester-united':4,'football':10}
TITLES={'world':'世界','asia':'亞洲','hong-kong':'香港','japan':'日本','market-economy':'📈 財經 / 全球市場','ai-tech':'AI / 科技','manga-anime':'漫畫 / Anime','manchester-united':'Manchester United','football':'Football'}
SUB={'world':'歐洲 · 北美洲 · 南美洲 · 非洲 · 大洋洲（亞洲另見亞洲版）','asia':'東亞 · 東南亞 · 南亞 · 中亞 · 西亞／中東 · 高加索 · 全亞洲','hong-kong':'本地 · 社會 · 法庭 · 公共政策 · 民生','japan':'社會 · 政治 · 司法 · 交通 · 教育 · 醫療 · 災害 · 生活','market-economy':'美國 · 歐洲 · 台灣 · 日本 · 香港 · 中國 · 全球','ai-tech':'全球 AI · 半導體 · 軟件 · 網絡安全 · 科技','manga-anime':'動畫 · 漫畫 · 出版 · 票房 · 製作 · 產業','manchester-united':'Club · Squad · Transfers · Injuries','football':'England · Europe · UEFA · International · J-League · Hong Kong · Worldwide'}
ASIA_RE=re.compile(r'亞洲|中國|香港|日本|韓國|南韓|北韓|朝鮮|台灣|印度|巴基斯坦|孟加拉|斯里蘭卡|尼泊爾|不丹|緬甸|泰國|越南|柬埔寨|老撾|馬來西亞|新加坡|印尼|菲律賓|哈薩克|烏茲別克|吉爾吉斯|塔吉克|土庫曼|伊朗|伊拉克|以色列|巴勒斯坦|加沙|黎巴嫩|敘利亞|約旦|沙特|阿聯酋|卡塔爾|阿曼|也門|土耳其|格魯吉亞|亞美尼亞|阿塞拜疆|Middle East|West Asia|Nepal|Japan|China|Korea|India|Iran|Israel|Gaza',re.I)
PROCESS_RE=re.compile(r'本輪|本報|incremental|duplicate|重複刊登|coverage test|collection design|這次重新檢查|之後每一輪|每一輪Football|不應由全球搜尋排名決定',re.I)

def load(p): return json.loads(p.read_text(encoding='utf-8'))
def dump(p,o): p.parent.mkdir(parents=True,exist_ok=True); p.write_text(json.dumps(o,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def measure(s):
    s=str(s or '')
    c=len(re.findall(r'[\u3400-\u9fff]',s))
    return c if c>=50 else len(re.sub(r'\s+','',s))
def valid_story(s):
    req=['id','title','dek','summary','body','context','why','watchNext','sourceName','sourceUrl','timeLabel','section']
    if not isinstance(s,dict) or any(not str(s.get(k,'')).strip() for k in req): return False
    if measure(s.get('body'))<100 or len([p for p in re.split(r'\n\s*\n',s['body']) if p.strip()])<2: return False
    pub=' '.join(str(s.get(k,'')) for k in ['title','dek','summary','body','context','why','watchNext'])
    if PROCESS_RE.search(pub): return False
    src=s.get('sources')
    return isinstance(src,list) and len(src)>=1

desk=load(DATA/'desk-latest.json')
assert desk.get('mode')=='ROLLING_DESK_LATEST'
desks=desk.get('desks') or {}
# World must exclude Asia. Remove geographic Asia stories from World only; retain them in their Asia/specialist desks.
clean=[]
for s in desks.get('world',[]):
    blob=' '.join(str(s.get(k,'')) for k in ['title','section','context'])
    if ASIA_RE.search(blob):
        continue
    clean.append(s)
desks['world']=clean
# Filter invalid/public-process rows, dedupe within each desk and normalize memberships/status.
for slug in FLOORS:
    out=[]; seen=set()
    for raw in desks.get(slug,[]):
        s=copy.deepcopy(raw)
        if not valid_story(s) or s.get('id') in seen: continue
        seen.add(s['id'])
        s['status']='LATEST'
        ds=s.get('deskSlugs') if isinstance(s.get('deskSlugs'),list) else []
        if slug not in ds: ds.append(slug)
        if slug=='world': ds=[x for x in ds if x!='asia']
        s['deskSlugs']=ds
        out.append(s)
    desks[slug]=out
# Hard publication gate — minimums are lower bounds, never caps.
counts={slug:len(desks.get(slug,[])) for slug in FLOORS}
for slug,minn in FLOORS.items():
    if counts[slug] < minn:
        raise SystemExit(f'HARD DESK FLOOR FAIL {slug}: {counts[slug]} < {minn}')
if counts['japan'] < 8: raise SystemExit('JAPAN HARD FLOOR FAIL')

desk['date']=DATE; desk['generatedAt']=NOW; desk['editorialStandardVersion']=3; desk['contentVersion']=3; desk['desks']=desks
dump(DATA/'desk-latest.json',desk)

# Homepage: broad 18-story selection. This does not cap topic pages.
quota={'world':3,'asia':2,'hong-kong':2,'japan':2,'market-economy':3,'ai-tech':2,'manga-anime':1,'manchester-united':1,'football':2}
articles=[]; used=set()
for slug,n in quota.items():
    got=0
    for raw in desks[slug]:
        if raw['id'] in used: continue
        s=copy.deepcopy(raw); used.add(s['id']); got+=1
        s['mediaLabel']=TITLES[slug].replace('📈 ','').upper()
        articles.append(s)
        if got>=n: break
# backfill to 18 if cross-desk duplicates reduced quotas
if len(articles)<18:
    for slug in FLOORS:
        for raw in desks[slug]:
            if raw['id'] in used: continue
            s=copy.deepcopy(raw); used.add(s['id']); s['mediaLabel']=TITLES[slug].upper(); articles.append(s)
            if len(articles)>=18: break
        if len(articles)>=18: break
if len(articles)<12: raise SystemExit(f'homepage depth fail: {len(articles)}')

# Re-rank lead/top five by public importance while keeping the full article set.
def score(s):
    t=(s.get('title','')+' '+s.get('section','')).lower(); z=0
    for pat,w in [('洪',7),('死亡',7),('戰',6),('攻擊',6),('制裁',4),('颱風',6),('地震',6),('nvidia',5),('利率',4),('市場',3),('人工智能',4),('ai',3),('曼聯',3),('manchester',3)]:
        if pat in t: z+=w
    if any(x in s.get('deskSlugs',[]) for x in ['world','asia','market-economy','japan']): z+=2
    return z
ranked=sorted(articles,key=score,reverse=True)
lead=ranked[0]['id']; top=[x['id'] for x in ranked[:5]]

sections=[]
for slug in FLOORS:
    ids=[a['id'] for a in articles if slug in (a.get('deskSlugs') or [])]
    if ids:
        sections.append({'slug':slug,'title':TITLES[slug],'subtitle':SUB[slug],'articleIds':ids})

daily={'editionNumber':'009','date':DATE,'dateLabel':'2026年8月28日 星期五','tagline':'全球更新 · 08:00 verified · v3長文','editorialStandardVersion':3,'contentVersion':3,'leadId':lead,'topFive':top,'articles':articles,'sections':sections}
dump(DATA/f'{DATE}.json',daily); dump(DATA/'latest.json',daily)

# Topic-more gets every other current verified story; no homepage cap.
extras=[]; exseen=set()
for slug in FLOORS:
    for raw in desks[slug]:
        if raw['id'] in used or raw['id'] in exseen: continue
        exseen.add(raw['id']); extras.append(copy.deepcopy(raw))
exsections=[]
known={a['id'] for a in extras}
for slug in FLOORS:
    ids=[]
    for s in desks[slug]:
        if s['id'] in known: ids.append(s['id'])
    exsections.append({'slug':slug,'title':TITLES[slug],'subtitle':SUB[slug],'articleIds':ids})
topic={'date':DATE,'editorialStandardVersion':3,'contentVersion':3,'articles':extras,'sections':exsections}
dump(DATA/'topic-more'/f'{DATE}.json',topic)

# Archive prepend without duplication.
archive=load(DATA/'archive.json')
eds=[e for e in archive.get('editions',[]) if e.get('date')!=DATE]
headline='；'.join(re.sub(r'\s+',' ',x.get('title','')).strip()[:26] for x in ranked[:3])
eds.insert(0,{'date':DATE,'shortDate':'28 AUG 2026','headline':headline,'topics':['世界','亞洲','香港','日本','財經 / 全球市場','AI / 科技','漫畫 / Anime','Manchester United','Football'],'url':f'editions/{DATE}.html'})
archive['editions']=eds; dump(DATA/'archive.json',archive)

# 08:00 Daily-only Live baseline; counts report exact desk reservoir.
live={'mode':'DAILY_BASELINE','date':DATE,'editorialStandardVersion':3,'contentVersion':3,'lastUpdated':NOW,'lastUpdatedLabel':'2026年8月28日 08:00 HKT','nextUpdateLabel':'下一輪預定 09:00 HKT','windowLabel':'08:00 Daily Edition baseline','newCount':0,'updatedCount':0,'developingCount':0,'coverage':{'status':'DAILY_BASELINE','checkedAt':NOW,'deskLatestStoryCounts':counts,'deskLatestDepthMet':True,'qaNote':'08:00 Daily baseline; topic pages use the complete current Rolling Desk reservoir.'},'items':[]}
dump(DATA/'live.json',live)

# Archived edition shell loads the dated JSON via the existing renderer.
html=f'''<!doctype html><html lang="zh-Hant"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><base href="../"><meta name="theme-color" content="#111111"><title>{DATE}｜每日晨報 Daily Brief</title><link rel="stylesheet" href="assets/css/newspaper.css?v=20260828"><link rel="stylesheet" href="assets/css/extras.css?v=20260828"><link rel="stylesheet" href="assets/css/monitoring.css?v=20260828"></head><body data-edition="{DATE}"><div class="paper"><div class="utility-bar"><span>ARCHIVED EDITION · HONG KONG</span><span>NO. <span data-edition-number>009</span></span></div><header class="masthead"><div class="masthead-side">世界 · 亞洲 · 香港 · 日本<br>財經 · Stock News · AI · Anime · Football</div><div class="brand"><div class="brand-kicker">個 人 化 電 子 報</div><h1>每日晨報</h1><div class="brand-en">DAILY BRIEF</div></div><div class="masthead-side right"><span data-edition-tagline>全球更新 · 08:00 verified · v3長文</span><br>ARCHIVED EDITION</div></header><nav class="section-nav" aria-label="新聞分版"><a href="live.html">Live</a><a href="index.html">頭版</a><a href="world.html">世界</a><a href="asia.html">亞洲</a><a href="hong-kong.html">香港</a><a href="japan.html">日本</a><a href="finance.html">📈 財經</a><a href="stocks.html">📊 Stock News</a><a href="technology.html">AI / 科技</a><a href="manga-anime.html">漫畫 / Anime</a><a href="manchester-united.html">Manchester United</a><a href="football.html">Football</a><a href="archive.html">Archive</a></nav><div class="date-strip"><span data-edition-date>{DATE}</span><span>GLOBAL VERIFIED DAILY</span></div><main><section class="lead-grid"><article class="lead-story" id="lead-story"><p>正在載入日報…</p></article><aside><div class="section-heading"><h2>今日必讀 5 則</h2><span>TOP FIVE</span></div><div class="top-five" id="top-five"></div></aside></section><div id="dynamic-sections"></div><section class="study-desk" id="study-desk"></section><p class="notice">此頁保存 {DATE} 版本；來源內容可能於原網站後續更新。</p></main><footer class="footer"><span>每日晨報 Daily Brief · {DATE}</span><span><a href="stocks.html">Stock News</a> · <a href="archive.html">Archive</a> · <a href="index.html">今日頭版</a></span></footer></div><script src="assets/js/newspaper.js?v=20260828" defer></script><script src="assets/js/daily-extras.js?v=20260828" defer></script><script src="assets/js/vocab-copy.js?v=20260828" defer></script><script src="assets/js/system-panel.js?v=20260828" defer></script></body></html>'''
p=(ROOT/'editions'/f'{DATE}.html'); p.parent.mkdir(exist_ok=True); p.write_text(html,encoding='utf-8')

print('DAILY_20260828_READY', 'homepage',len(articles),'topic_more',len(extras),'counts',counts,'japan',counts['japan'])
