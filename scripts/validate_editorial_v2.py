#!/usr/bin/env python3
import json, pathlib, re, sys
ROOT=pathlib.Path(__file__).resolve().parents[1]
DATA=ROOT/'data'
MANDATORY_FOOTBALL=list('ABCDEFGHIJK')
DEPTH_FLOOR={'world':8,'asia':8,'hong-kong':6,'japan':8,'market-economy':8,'ai-tech':6,'manga-anime':4,'manchester-united':4,'football':10}
SOURCE_MIN={'world':12,'asia':10,'hong-kong':8,'japan':8,'market-economy':10,'ai-tech':10,'manga-anime':4,'manchester-united':4,'football':10}
BASE_META_PATTERNS=[r'今日未找到',r'沒有新聞',r'沒有headline',r'已完成.*檢查',r'本輪已檢查',r'J-?League.*已檢查',r'採全產業掃描',r'coverage check',r'no news found']
V3_PROCESS_PATTERNS=[r'本輪真正incremental',r'incremental news',r'duplicate',r'重複刊登',r'本報.*版',r'對本報',r'搜集規則',r'collection design',r'coverage test',r'這次重新檢查',r'之後每一輪',r'每一輪Football',r'固定檢查HKFA',r'不應由全球搜尋排名決定',r'讀者應該看到的核心新聞']

def load(p): return json.loads(p.read_text(encoding='utf-8'))
def fail(m): raise ValueError(m)
def cjk_len(v): return len(re.findall(r'[\u3400-\u9fff]',str(v or '')))
def compact_len(v): return len(re.sub(r'\s+','',str(v or '')))

def validate_story(story,label,strict=False):
    required=['title','dek','summary','context','why','watchNext','sourceName','sourceUrl','timeLabel']+(['body'] if strict else [])
    for key in required:
        if not isinstance(story.get(key),str) or not story.get(key).strip(): fail(f'{label}: missing {key}')
    combined=' '.join(str(story.get(k,'')) for k in ('title','dek','summary','body','context','why','watchNext'))
    for pattern in BASE_META_PATTERNS:
        if re.search(pattern,combined,re.I): fail(f'{label}: meta/coverage text cannot be published ({pattern})')
    if strict:
        for pattern in V3_PROCESS_PATTERNS:
            if re.search(pattern,combined,re.I): fail(f'{label}: editorial/process text cannot be published ({pattern})')
        body=story.get('body','')
        if len([p for p in re.split(r'\n\s*\n',body) if p.strip()])<2: fail(f'{label}: body must contain >=2 paragraphs')
        measure=cjk_len(body) if cjk_len(body)>=50 else compact_len(body)
        if measure<100: fail(f'{label}: body too short ({measure})')
        if measure>1800: fail(f'{label}: body too long ({measure})')
        sources=story.get('sources')
        if not isinstance(sources,list) or not sources: fail(f'{label}: sources must be non-empty array')

def main():
    try:
        desk_path=DATA/'desk-latest.json'; desk=None
        if desk_path.exists():
            desk=load(desk_path); version=int(desk.get('contentVersion',1) or 1); strict=version>=3
            desks=desk.get('desks')
            if not isinstance(desks,dict): fail('desk-latest: desks must be object')
            for slug,minimum in DEPTH_FLOOR.items():
                stories=desks.get(slug)
                if not isinstance(stories,list): fail(f'desk-latest: missing desk {slug}')
                ids=[s.get('id') for s in stories if isinstance(s,dict)]
                if len(ids)!=len(stories) or len(ids)!=len(set(ids)): fail(f'desk-latest {slug}: story IDs must be unique')
                if version>=3 and len(stories)<minimum: fail(f'desk-latest v3: {slug} story depth {len(stories)} < {minimum}')
                for i,story in enumerate(stories): validate_story(story,f'desk-latest {slug}[{i}]',strict)
            if len(desks.get('japan',[]))<8: fail('desk-latest: Japan must contain >=8 unique verified stories')
        live_path=DATA/'live.json'
        if live_path.exists():
            live=load(live_path); live_version=int(live.get('contentVersion',1) or 1); strict=live_version>=3
            for i,story in enumerate(live.get('items',[])): validate_story(story,f'live[{i}]',strict)
            cov=live.get('coverage',{}); status=str(cov.get('status','')).upper()
            if live_version>=3:
                counts=cov.get('deskLatestStoryCounts')
                if not isinstance(counts,dict): fail('live v3 requires coverage.deskLatestStoryCounts')
                for slug,minimum in DEPTH_FLOOR.items():
                    value=counts.get(slug)
                    if not isinstance(value,int) or value<minimum: fail(f'live v3: deskLatestStoryCounts.{slug}={value} < {minimum}')
                    if desk is not None and value!=len(desk.get('desks',{}).get(slug,[])): fail(f'live v3: reported {slug}={value} but actual={len(desk.get("desks",{}).get(slug,[]))}')
                if counts.get('japan',0)<8 or cov.get('japanCountVerified',counts.get('japan',0))<8: fail('live v3: Japan count must be explicitly >=8')
            if status=='COMPLETE':
                source_counts=cov.get('deskSourceCounts')
                if isinstance(source_counts,dict):
                    for slug,minimum in SOURCE_MIN.items():
                        if source_counts.get(slug,0)<minimum: fail(f'live COMPLETE: {slug} sources below gate')
                elif cov.get('sourceGateMet') is not True: fail('live COMPLETE: source gate not evidenced')
                fc=cov.get('footballCoverage')
                if isinstance(fc,dict):
                    for key in MANDATORY_FOOTBALL:
                        row=next((v for k,v in fc.items() if str(k).startswith(key)),None)
                        if not isinstance(row,dict) or row.get('searched') is not True: fail(f'live COMPLETE: footballCoverage {key} not searched')
                elif cov.get('footballGateMet') is not True: fail('live COMPLETE: football gate not evidenced')
                asia=cov.get('asiaCoverage')
                if isinstance(asia,dict):
                    regions=set(asia.get('regionsChecked',[]))
                    for region in ('East Asia','Southeast Asia','South Asia','Central Asia','West Asia / Middle East'):
                        if region not in regions: fail(f'live COMPLETE: Asia missing {region}')
                    if asia.get('securityIntegrated') is not True: fail('live COMPLETE: Asia security not integrated')
                elif cov.get('geographicGateMet') is not True: fail('live COMPLETE: geographic gate not evidenced')
        print('EDITORIAL VALIDATION OK')
        return 0
    except Exception as exc:
        print('EDITORIAL VALIDATION FAILED',file=sys.stderr); print(f'- {exc}',file=sys.stderr); return 1
if __name__=='__main__': raise SystemExit(main())
