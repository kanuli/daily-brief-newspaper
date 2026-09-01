#!/usr/bin/env python3
"""Remove repeated verification-policy boilerplate from published Stock News.

The verification policy belongs at page level, not repeated inside every
company story. This keeps event-specific copy distinct while preserving all
facts, sources, timestamps, and verification metadata.
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
    body = body.replace("。。", "。").replace("。\n\n", "。\n\n").strip()
    if body != original:
        story["body"] = body
        changed = True

    return changed


def main() -> None:
    data = json.loads(PATH.read_text(encoding="utf-8"))
    changed_count = 0
    for block in (data.get("tickers") or {}).values():
        if not isinstance(block, dict):
            continue
        for story in block.get("stories") or []:
            if isinstance(story, dict) and clean_story(story):
                changed_count += 1

    if changed_count:
        PATH.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("STOCK_BOILERPLATE_CLEAN_OK", "stories", changed_count)


if __name__ == "__main__":
    main()
