#!/usr/bin/env python3
import json
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
DATA = ROOT / 'data'
MANDATORY_FOOTBALL = ['A','B','C','D','E','F','G','H','I','J']
SOURCE_MIN = {'world':12,'asia':10,'hong-kong':8,'japan':8,'market-economy':10,'ai-tech':10,'manga-anime':4,'manchester-united':4,'football':12}


def load(path):
    return json.loads(path.read_text(encoding='utf-8'))


def fail(msg):
    raise ValueError(msg)


def cjk_len(value):
    return len(re.findall(r'[\u3400-\u9fff]', str(value or '')))


def validate_story(story, label, strict=False):
    required = ['title','dek','summary','context','why','watchNext','sourceName','sourceUrl','timeLabel']
    if strict:
        required.append('body')
    for key in required:
        if not isinstance(story.get(key), str) or not story.get(key).strip():
            fail(f'{label}: missing {key}')
    if strict:
        body = story.get('body','')
        paras = [p.strip() for p in re.split(r'\n\s*\n', body) if p.strip()]
        if len(paras) < 2:
            fail(f'{label}: body must contain at least 2 paragraphs')
        if cjk_len(body) < 180:
            fail(f'{label}: body too short ({cjk_len(body)} CJK chars; need >=180)')
        if cjk_len(story.get('summary')) < 100:
            fail(f'{label}: summary too short for newspaper mode ({cjk_len(story.get("summary"))} CJK chars; need >=100)')


def main():
    try:
        desk_path = DATA / 'desk-latest.json'
        if desk_path.exists():
            desk = load(desk_path)
            strict = int(desk.get('contentVersion', 1) or 1) >= 2
            desks = desk.get('desks')
            if not isinstance(desks, dict): fail('data/desk-latest.json: desks must be object')
            for slug in SOURCE_MIN:
                stories = desks.get(slug)
                if not isinstance(stories, list): fail(f'desk-latest: missing desk {slug}')
                for i, story in enumerate(stories): validate_story(story, f'desk-latest {slug}[{i}]', strict)
            if strict:
                if len(desks.get('hong-kong', [])) < 3: fail('desk-latest v2: Hong Kong needs >=3 stories')
                if len(desks.get('japan', [])) < 3: fail('desk-latest v2: Japan needs >=3 stories')

        live_path = DATA / 'live.json'
        if live_path.exists():
            live = load(live_path)
            strict = int(live.get('editorialStandardVersion', 1) or 1) >= 2
            for i, story in enumerate(live.get('items', [])): validate_story(story, f'live[{i}]', strict)
            cov = live.get('coverage', {})
            if strict and str(cov.get('status','')).upper() == 'COMPLETE':
                if cov.get('sourceOrganizationCount',0) < 45: fail('live v2 COMPLETE needs >=45 organizations')
                if cov.get('freshSearchCount',0) < 40: fail('live v2 COMPLETE needs >=40 searches')
                source_counts = cov.get('deskSourceCounts',{})
                for slug, minimum in SOURCE_MIN.items():
                    if source_counts.get(slug,0) < minimum:
                        fail(f'live v2 COMPLETE: {slug} sources {source_counts.get(slug,0)} < {minimum}')
                fc = cov.get('footballCoverage')
                if not isinstance(fc, dict): fail('live v2 COMPLETE requires footballCoverage object')
                for key in MANDATORY_FOOTBALL:
                    row = fc.get(key)
                    if not isinstance(row, dict) or row.get('searched') is not True:
                        fail(f'live v2 COMPLETE: footballCoverage {key} not searched')
                    if not isinstance(row.get('sourcesChecked'), list):
                        fail(f'live v2 COMPLETE: footballCoverage {key} sourcesChecked missing')
                    if not isinstance(row.get('candidateCount'), int):
                        fail(f'live v2 COMPLETE: footballCoverage {key} candidateCount missing')
        print('EDITORIAL V2 VALIDATION OK')
        return 0
    except Exception as exc:
        print('EDITORIAL V2 VALIDATION FAILED', file=sys.stderr)
        print(f'- {exc}', file=sys.stderr)
        return 1

if __name__ == '__main__':
    raise SystemExit(main())
