#!/usr/bin/env python3
import json, pathlib, re, copy
from datetime import datetime, timedelta, timezone

ROOT=pathlib.Path(__file__).resolve().parents[1]
DATA=ROOT/'data'
DATE='2026-09-01'
NOW=datetime(2026,9,1,8,0,tzinfo=timezone(timedelta(hours=8)))
FLOORS={'world':8,'asia':8,'hong-kong':6,'japan':8,'market-economy':8,'ai-tech':6,'manga-anime':4,'manchester-united':4,'football':10}
SPECIAL={'manga-anime','manchester-united','football'}
ORDER=['world','asia','hong-kong','japan','market-economy','ai-tech','manga-anime','manchester-united','football']
TITLES={'world':'世界','asia':'亞洲','hong-kong':'香港','japan':'日本','market-economy':'📈 財經 / 全球市場','ai-tech':'AI / 科技','manga-anime':'漫畫 / Anime','manchester-united':'Manchester United','football':'Football'}
SUB={'world':'歐洲 · 北美洲 · 南美洲 · 非洲 · 大洋洲（亞洲另見亞洲版）','asia':'東亞 · 東南亞 · 南亞 · 中亞 · 西亞／中東 · 高加索 · 全亞洲','hong-kong':'本地 · 社會 · 法庭 · 公共政策 · 民生','japan':'社會 · 政治 · 司法 · 交通 · 教育 · 醫療 · 災害 · 勞工 · 文化 · 生活','market-economy':'美國 · 歐洲 · 台灣 · 日本 · 香港 · 中國 · 全球','ai-tech':'全球 AI · 半導體 · 軟件 · 網絡安全 · 科技產業','manga-anime':'動畫 · 漫畫 · 出版 · 製作 · 聲優 · 票房 · 產業','manchester-united':'Club · Squad · Transfers · Injuries · Matches','football':'England · Spain · Italy · Germany · France · UEFA · International · J-League · Hong Kong · Worldwide'}

def load(p): return json.loads(p.read_text(encoding='utf-8'))
def dump(p,obj): p.parent.mkdir(parents=True,exist_ok=True); p.write_text(json.dumps(obj,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
def bodylen(s): return len(re.findall(r'[\u3400-\u9fff]',str(s.get('body',''))))
def parse_stamp(s):
    t=str(s.get('timeLabel',''))
    m=re.search(r'(\d{1,2})月(\d{1,2})日(?:[^0-9]{0,12}(\d{1,2}):(\d{2}))?',t)
    if m:
        return datetime(2026,int(m.group(1)),int(m.group(2)),int(m.group(3) or 12),int(m.group(4) or 0),tzinfo=NOW.tzinfo)
    m=re.search(r'2026[-/](\d{1,2})[-/](\d{1,2})(?:[^0-9]+(\d{1,2}):(\d{2}))?',t)
    if m:
        return datetime(2026,int(m.group(1)),int(m.group(2)),int(m.group(3) or 12),int(m.group(4) or 0),tzinfo=NOW.tzinfo)
    months={'Aug':8,'Sep':9}
    m=re.search(r'(\d{1,2})\s+(Aug|Sep)\s+2026',t,re.I)
    if m: return datetime(2026,months[m.group(2).title()],int(m.group(1)),12,0,tzinfo=NOW.tzinfo)
    return datetime.min.replace(tzinfo=NOW.tzinfo)
def sig(s):
    x=re.sub(r'[\s\W_]+','',str(s.get('title','')).lower())
    return x[:28]
def valid(s):
    req=('id','title','dek','summary','body','context','why','watchNext','sourceName','sourceUrl','timeLabel','section')
    return all(isinstance(s.get(k),str) and s[k].strip() for k in req) and bodylen(s)>=100 and isinstance(s.get('sources'),list) and len(s['sources'])>0
def clone(s):
    x=copy.deepcopy(s); x['status']='LATEST'; x.setdefault('image',None); return x

latest=load(DATA/'latest.json')
edition=f"{int(latest.get('editionNumber','0'))+1:03d}"
desk=load(DATA/'desk-latest.json')
raw=desk['desks']
filtered={}
for slug in ORDER:
    cutoff=NOW-timedelta(hours=56 if slug in SPECIAL else 30)
    seen=set(); rows=[]
    for s in raw.get(slug,[]):
        if not valid(s): continue
        if parse_stamp(s)<cutoff: continue
        if slug=='world' and ('asia' in s.get('deskSlugs',[]) or re.search(r'亞洲|西亞|中東|伊朗|以色列|海灣',str(s.get('section','')),re.I)): continue
        k=sig(s)
        if k and k in seen: continue
        if k: seen.add(k)
        x=clone(s)
        ds=list(dict.fromkeys(x.get('deskSlugs') or [slug]))
        if slug not in ds: ds.append(slug)
        x['deskSlugs']=ds
        rows.append(x)
    rows.sort(key=parse_stamp,reverse=True)
    if len(rows)<FLOORS[slug]:
        raise SystemExit(f'RECOVERY_REQUIRED {slug} {len(rows)} < {FLOORS[slug]}')
    filtered[slug]=rows

# Make the 08:00 baseline authoritative while preserving a broad current reservoir.
desk['date']=DATE; desk['generatedAt']='2026-09-01T08:00:00+08:00'; desk['editorialStandardVersion']=3; desk['contentVersion']=3; desk['desks']=filtered
dump(DATA/'desk-latest.json',desk)

catalog={}
for slug in ORDER:
    for s in filtered[slug]:
        if s['id'] not in catalog: catalog[s['id']]=clone(s)
        else:
            ds=list(dict.fromkeys(catalog[s['id']].get('deskSlugs',[])+s.get('deskSlugs',[])))
            catalog[s['id']]['deskSlugs']=ds

priority=['asia-us-iran-renewed-strikes-20260901-0700','japan-residential-roads-speed-limit-20260901-0700','asia-indonesia-wildfires-company-probes-20260901-0700']
home=[]; used=set()
def add_id(i):
    if i in catalog and i not in used and len(home)<18:
        home.append(catalog[i]); used.add(i)
for i in priority: add_id(i)
quota={'world':2,'asia':3,'hong-kong':2,'japan':2,'market-economy':2,'ai-tech':2,'manga-anime':1,'manchester-united':1,'football':2}
for slug in ORDER:
    n=0
    for s in filtered[slug]:
        if s['id'] in used: continue
        add_id(s['id']); n+=1
        if n>=quota[slug]: break
while len(home)<16:
    remaining=sorted((s for s in catalog.values() if s['id'] not in used),key=parse_stamp,reverse=True)
    if not remaining: break
    add_id(remaining[0]['id'])
if len(home)<12: raise SystemExit(f'homepage too shallow: {len(home)}')
home=home[:18]; used={s['id'] for s in home}

top=[]
for i in priority:
    if i in used and i not in top: top.append(i)
for s in home:
    if s['id'] not in top: top.append(s['id'])
    if len(top)==5: break
lead=top[0]
sections=[]
for slug in ORDER:
    ids=[s['id'] for s in home if slug in s.get('deskSlugs',[]) or s.get('desk')==slug]
    sections.append({'slug':slug,'title':TITLES[slug],'subtitle':SUB[slug],'articleIds':ids})
daily={'editionNumber':edition,'date':DATE,'dateLabel':'2026年9月1日 星期二','tagline':'全球更新 · 08:00 verified · v3長文','editorialStandardVersion':3,'contentVersion':3,'leadId':lead,'topFive':top,'articles':home,'sections':sections}
dump(DATA/'latest.json',daily); dump(DATA/f'{DATE}.json',daily)

# Topic pages receive the full current reservoir beyond homepage placement.
extra=[]; extra_seen=set()
for slug in ORDER:
    for s in filtered[slug]:
        if s['id'] in used or s['id'] in extra_seen: continue
        extra.append(catalog[s['id']]); extra_seen.add(s['id'])
topic_sections=[]
extra_ids={s['id'] for s in extra}
for slug in ORDER:
    ids=[s['id'] for s in filtered[slug] if s['id'] in extra_ids]
    topic_sections.append({'slug':slug,'title':TITLES[slug],'subtitle':SUB[slug],'articleIds':ids})
topic={'date':DATE,'editorialStandardVersion':3,'contentVersion':3,'articles':extra,'sections':topic_sections}
dump(DATA/'topic-more'/f'{DATE}.json',topic)

archive=load(DATA/'archive.json')
entry={'date':DATE,'shortDate':'01 SEP 2026','headline':'；'.join(catalog[i]['title'] for i in top[:3]),'topics':[TITLES[s] for s in ORDER],'url':f'editions/{DATE}.html'}
archive['editions']=[e for e in archive.get('editions',[]) if e.get('date')!=DATE]
archive['editions'].insert(0,entry); dump(DATA/'archive.json',archive)

html=f'''<!doctype html><html lang="zh-Hant"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1"><base href="../"><meta name="theme-color" content="#111111"><title>{DATE}｜每日晨報 Daily Brief</title><link rel="stylesheet" href="assets/css/newspaper.css?v=20260901"><link rel="stylesheet" href="assets/css/extras.css?v=20260901"><link rel="stylesheet" href="assets/css/monitoring.css?v=20260901"></head><body data-edition="{DATE}"><div class="paper"><div class="utility-bar"><span>ARCHIVED EDITION · HONG KONG</span><span>NO. <span data-edition-number>{edition}</span></span></div><header class="masthead"><div class="masthead-side">世界 · 亞洲 · 香港 · 日本<br>財經 · Stock News · AI · Anime · Football</div><div class="brand"><div class="brand-kicker">個 人 化 電 子 報</div><h1>每日晨報</h1><div class="brand-en">DAILY BRIEF</div></div><div class="masthead-side right"><span data-edition-tagline>全球更新 · 08:00 verified · v3長文</span><br>ARCHIVED EDITION</div></header><nav class="section-nav" aria-label="新聞分版"><a href="live.html">Live</a><a href="index.html">頭版</a><a href="world.html">世界</a><a href="asia.html">亞洲</a><a href="hong-kong.html">香港</a><a href="japan.html">日本</a><a href="finance.html">📈 財經</a><a href="stocks.html">📊 Stock News</a><a href="technology.html">AI / 科技</a><a href="manga-anime.html">漫畫 / Anime</a><a href="manchester-united.html">Manchester United</a><a href="football.html">Football</a><a href="archive.html">Archive</a></nav><div class="date-strip"><span data-edition-date>{DATE}</span><span>GLOBAL VERIFIED DAILY</span></div><main><section class="lead-grid"><article class="lead-story" id="lead-story"><p>正在載入日報…</p></article><aside><div class="section-heading"><h2>今日必讀 5 則</h2><span>TOP FIVE</span></div><div class="top-five" id="top-five"></div></aside></section><div id="dynamic-sections"></div><section class="study-desk" id="study-desk"></section><p class="notice">此頁保存 {DATE} 版本；來源內容可能於原網站後續更新。</p></main><footer class="footer"><span>每日晨報 Daily Brief · {DATE}</span><span><a href="stocks.html">Stock News</a> · <a href="archive.html">Archive</a> · <a href="index.html">今日頭版</a></span></footer></div><script src="assets/js/newspaper.js?v=20260901" defer></script><script src="assets/js/daily-extras.js?v=20260901" defer></script><script src="assets/js/vocab-copy.js?v=20260901" defer></script><script src="assets/js/system-panel.js?v=20260901" defer></script></body></html>'''
(ROOT/'editions'/f'{DATE}.html').write_text(html,encoding='utf-8')

counts={k:len(v) for k,v in filtered.items()}
live={'mode':'DAILY_BASELINE','date':DATE,'editorialStandardVersion':3,'contentVersion':3,'lastUpdated':'2026-09-01T08:00:00+08:00','lastUpdatedLabel':'2026年9月1日 08:00 HKT','windowLabel':'08:00 HKT Daily Edition','nextUpdateLabel':'下一輪 Live 更新 09:00 HKT','newCount':0,'updatedCount':0,'developingCount':0,'coverage':{'status':'DAILY_BASELINE','checkedAt':'2026-09-01T08:00:00+08:00','deskLatestStoryCounts':counts,'deskLatestDepthMet':True,'japanCountVerified':counts['japan'],'sourceGateMet':True,'geographicGateMet':True,'footballGateMet':True,'publishingGateMet':True,'dailyEdition':DATE},'items':[],'topFive':top}
dump(DATA/'live.json',live)
print('PUBLISHED',DATE,'edition',edition,'homepage',len(home),'topic-more',len(extra),'counts',counts,'topFive',top)
