#!/usr/bin/env python3
"""Remove internal verification/process copy from published Stock News.

Verification policy belongs at page/system level, never as the news value of a
company story. Whole pseudo-news cards whose public copy merely says that Stock
News verified an item are removed so the publication pipeline must replace them
with actual developments.
"""
from __future__ import annotations

import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PATH = ROOT / "data" / "stocks-latest.json"

DEK_SUFFIXES = (
    "；自動核實器只在官方／監管來源出現後才升格為已核實新聞。",
    ";自動核實器只在官方／監管來源出現後才升格為已核實新聞。",
)
BODY_SENTENCES = (
    "Stock News的自動核實器不會因搜尋結果、社交平台貼文或預測文章出現相似標題，就把未正式發布的消息當作公司事實。",
    "Stock News 的自動核實器不會因搜尋結果、社交平台貼文或預測文章出現相似標題，就把未正式發布的消息當作公司事實。",
)
BANNED_STORY_FRAGMENTS = (
    "第一手資料已通過Stock News核實",
    "已通過Stock News核實",
    "Stock News核實",
    "Stock News 核實",
)
PUBLIC_COPY_FIELDS = ("title", "dek", "summary", "body", "context", "why", "watchNext")


def is_process_story(story: dict) -> bool:
    public_copy = " ".join(str(story.get(field) or "") for field in PUBLIC_COPY_FIELDS)
    return any(fragment in public_copy for fragment in BANNED_STORY_FRAGMENTS)


def clean_story(story: dict) -> bool:
    if story.get("verificationMode") != "PRIMARY_SOURCE_AUTO":
        return False
    changed = False

    dek = str(story.get("dek") or "")
    for suffix in DEK_SUFFIXES:
        if suffix in dek:
            dek = dek.replace(suffix, "。")
            changed = True
    dek = dek.replace("。。", "。").strip()
    if changed:
        story["dek"] = dek

    body = str(story.get("body") or "")
    original = body
    for sentence in BODY_SENTENCES:
        body = body.replace(sentence, "")
    body = body.replace("。。", "。").strip()
    if body != original:
        story["body"] = body
        changed = True

    return changed


def main() -> None:
    data = json.loads(PATH.read_text(encoding="utf-8"))
    cleaned_count = 0
    removed_count = 0
    for block in (data.get("tickers") or {}).values():
        if not isinstance(block, dict):
            continue
        stories = block.get("stories") or []
        kept = []
        for story in stories:
            if not isinstance(story, dict):
                continue
            if is_process_story(story):
                removed_count += 1
                continue
            if clean_story(story):
                cleaned_count += 1
            kept.append(story)
        block["stories"] = kept[:3]

    if cleaned_count or removed_count:
        PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("STOCK_BOILERPLATE_CLEAN_OK", "cleaned", cleaned_count, "removed_pseudo_stories", removed_count)


if __name__ == "__main__":
    main()
