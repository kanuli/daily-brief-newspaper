#!/usr/bin/env python3
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
DATA = ROOT / 'data'
MANDATORY_FOOTBALL = ['A','B','C','D','E','F','G','H','I','J','K']
SOURCE_MIN = {'world':12,'asia':10,'hong-kong':8,'japan':8,'market-economy':10,'ai-tech':10,'manga-anime':4,'manchester-united':4,'football':10}
BASE_META_PATTERNS = [
    r'今日未找到', r'沒有新聞', r'沒有headline', r'已完成.*檢查', r'本輪已檢查',
    r'J-?League.*已檢查', r'採全產業掃描', r'coverage check', r'no news found'
]
V3_PROCESS_PATTERNS = [
    r'本輪真正incremental', r'incremental news', r'duplicate', r'重複刊登',
    r'本報.*版', r'對本報', r'搜集規則', r'collection design', r'coverage test',
    r'這次重新檢查', r'之後每一輪', r'每一輪Football', r'固定檢查HKFA',
    r'不應由全球搜尋排名決定', r'讀者應該看到的核心新聞'
]


def load(path):
    return json.loads(path.read_text(encoding='utf-8'))


def fail(msg):
    raise ValueError(msg)


def cjk_len(value):
    return len(re.findall(r'[\u3400-\u9fff]', str(value or '')))


def compact_len(value):
    return len(re.sub(r'\s+', '', str(value or '')))


def validate_story(story, label, strict=False):
    required = ['title','dek','summary','context','why','watchNext','sourceName','sourceUrl','timeLabel']
    if strict:
        required.append('body')
    for key in required:
        if not isinstance(story.get(key), str) or not story.get(key).strip():
            fail(f'{label}: missing {key}')

    combined = ' '.join(str(story.get(k,'')) for k in ('title','dek','summary','body','context','why','watchNext'))
    for pattern in BASE_META_PATTERNS:
        if re.search(pattern, combined, flags=re.I):
            fail(f'{label}: meta/coverage text cannot be published as a news article ({pattern})')
    if strict:
        for pattern in V3_PROCESS_PATTERNS:
            if re.search(pattern, combined, flags=re.I):
                fail(f'{label}: editorial/process text cannot be published as news copy ({pattern})')

        body = story.get('body','')
        paras = [p.strip() for p in re.split(r'\n\s*\n', body) if p.strip()]
        if len(paras) < 2:
            fail(f'{label}: body must contain at least 2 paragraphs')
        measure = cjk_len(body) if cjk_len(body) >= 50 else compact_len(body)
        if measure < 100:
            fail(f'{label}: body too short ({measure}; need >=100)')
        if measure > 1800:
            fail(f'{label}: body too long ({measure}; newspaper article should stay near the 100-500 word range)')


def main():
    try:
        desk_path = DATA / 'desk-latest.json'
        if desk_path.exists():
            desk = load(desk_path)
            strict = int(desk.get('contentVersion', 1) or 1) >= 3
            desks = desk.get('desks')
            if not isinstance(desks, dict): fail('data/desk-latest.json: desks must be object')
            for slug in SOURCE_MIN:
                stories = desks.get(slug)
                if not isinstance(stories, list): fail(f'desk-latest: missing desk {slug}')
                for i, story in enumerate(stories): validate_story(story, f'desk-latest {slug}[{i}]', strict)
            if int(desk.get('contentVersion', 1) or 1) >= 2:
                if len(desks.get('hong-kong', [])) < 3: fail('desk-latest v2+: Hong Kong needs >=3 stories')
                if len(desks.get('japan', [])) < 3: fail('desk-latest v2+: Japan needs >=3 stories')
                if len(desks.get('football', [])) < 2: fail('desk-latest v2+: Football needs current real stories, not coverage meta')

        live_path = DATA / 'live.json'
        if live_path.exists():
            live = load(live_path)
            strict = int(live.get('contentVersion', 1) or 1) >= 3
            for i, story in enumerate(live.get('items', [])): validate_story(story, f'live[{i}]', strict)
            cov = live.get('coverage', {})
            if int(live.get('editorialStandardVersion', 1) or 1) >= 2 and str(cov.get('status','')).upper() == 'COMPLETE':
                if cov.get('sourceOrganizationCount',0) < 40: fail('live v2+ COMPLETE needs >=40 organizations')
                if cov.get('freshSearchCount',0) < 36: fail('live v2+ COMPLETE needs >=36 searches')
                source_counts = cov.get('deskSourceCounts',{})
                for slug, minimum in SOURCE_MIN.items():
                    if source_counts.get(slug,0) < minimum:
                        fail(f'live v2+ COMPLETE: {slug} sources {source_counts.get(slug,0)} < {minimum}')
                fc = cov.get('footballCoverage')
                if not isinstance(fc, dict): fail('live v2+ COMPLETE requires footballCoverage object')
                for key in MANDATORY_FOOTBALL:
                    row = next((v for k,v in fc.items() if str(k).startswith(key)), None)
                    if not isinstance(row, dict) or row.get('searched') is not True:
                        fail(f'live v2+ COMPLETE: footballCoverage {key} not searched')
                    if not isinstance(row.get('sourcesChecked'), list) or not row.get('sourcesChecked'):
                        fail(f'live v2+ COMPLETE: footballCoverage {key} sourcesChecked missing')
                    if not isinstance(row.get('candidateCount'), int):
                        fail(f'live v2+ COMPLETE: footballCoverage {key} candidateCount missing')

                asia = cov.get('asiaCoverage', {})
                if not isinstance(asia, dict): fail('live v2+ COMPLETE requires asiaCoverage')
                regions = set(asia.get('regionsChecked', []))
                for region in ('East Asia','Southeast Asia','South Asia','Central Asia','West Asia / Middle East'):
                    if region not in regions: fail(f'live v2+ COMPLETE: Asia missing region {region}')
                if asia.get('securityIntegrated') is not True:
                    fail('live v2+ COMPLETE: regional security must be integrated into geographic Asia coverage')
        print('EDITORIAL VALIDATION OK')
        return 0
    except Exception as exc:
        print('EDITORIAL VALIDATION FAILED', file=sys.stderr)
        print(f'- {exc}', file=sys.stderr)
        return 1

if __name__ == '__main__':
    raise SystemExit(main())