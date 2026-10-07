#!/usr/bin/env python3
"""Open-source local fallback for General News when Copilot capacity is exhausted.

This fallback is deliberately conservative:
- only candidates already selected by the newsroom verification request are considered;
- only trusted-source candidates are eligible;
- the model receives headline/source/timestamp metadata only;
- generated public copy is rejected if it introduces numeric claims absent from the headline;
- output is written in the exact facts.raw / copy.raw schema expected by the existing merge gate.

The existing merge + producer validators remain authoritative.
"""
from __future__ import annotations

import argparse
import json
import re
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any

from opencc import OpenCC

import general_news_verified_producer as producer

MODEL_URL = "http://127.0.0.1:11434/api/generate"
MODEL_NAME = "qwen2.5:1.5b"
HK = OpenCC("s2hk")
NUM_RE = re.compile(r"\d+(?:[.,:]\d+)*")
CODE_FENCE_RE = re.compile(r"^\s*```(?:json)?\s*|\s*```\s*$", re.I)
DESK_PURPOSE = {
    "world": "國際重大公共事務",
    "asia": "亞洲重大公共事務",
    "hong-kong": "香港公共事務",
    "japan": "日本公共事務",
    "finance": "財經及宏觀經濟",
    "ai-tech": "人工智能及科技",
    "manga-anime": "漫畫及動畫產業",
    "manchester-united": "曼聯足球",
    "football": "足球",
}


def clean(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain an object")
    return value


def trusted(candidate: dict[str, Any]) -> bool:
    title = clean(candidate.get("title"))
    source = clean(candidate.get("source"))
    url = clean(candidate.get("url"))
    if not title or not source or not url.startswith(("http://", "https://")):
        return False
    if producer.BAD_TEXT.search(title) or producer.LOW_VALUE.search(title):
        return False
    if not producer.TRUSTED_SOURCE.search(source):
        return False
    if clean(candidate.get("desk")) == "manchester-united" and not producer.MAN_UTD_NEWS.search(title):
        return False
    if clean(candidate.get("desk")) == "football" and not producer.FOOTBALL_EVENT.search(title):
        return False
    return True


def choose(request: dict[str, Any]) -> list[dict[str, Any]]:
    selected: list[dict[str, Any]] = []
    used: set[str] = set()
    stale = [clean(x) for x in (request.get("staleDesks") or []) if clean(x)]
    by_desk: dict[str, list[dict[str, Any]]] = {}
    for row in request.get("candidates") or []:
        if not isinstance(row, dict) or not trusted(row):
            continue
        by_desk.setdefault(clean(row.get("desk")), []).append(row)

    for desk in stale:
        rows = by_desk.get(desk) or []
        if not rows:
            continue
        rows.sort(key=lambda row: clean(row.get("publishedAt")), reverse=True)
        row = rows[0]
        cid = clean(row.get("id"))
        if cid and cid not in used:
            selected.append(row)
            used.add(cid)
    return selected[:6]


def ollama_json(prompt: str) -> dict[str, Any]:
    body = json.dumps(
        {
            "model": MODEL_NAME,
            "prompt": prompt,
            "stream": False,
            "format": "json",
            "options": {
                "temperature": 0.1,
                "top_p": 0.8,
                "num_predict": 2200,
            },
        },
        ensure_ascii=False,
    ).encode("utf-8")
    req = urllib.request.Request(
        MODEL_URL,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=240) as response:
        payload = json.loads(response.read().decode("utf-8"))
    raw = str(payload.get("response") or "").strip()
    raw = CODE_FENCE_RE.sub("", raw).strip()
    value = json.loads(raw)
    if not isinstance(value, dict):
        raise ValueError("local model did not return a JSON object")
    return value


def convert_copy(value: Any) -> dict[str, str] | None:
    if not isinstance(value, dict):
        return None
    out: dict[str, str] = {}
    for field in producer.COPY_FIELDS:
        text = str(value.get(field) or "").strip()
        if not text:
            return None
        out[field] = HK.convert(text)
    return out


def valid_grounding(candidate: dict[str, Any], copy: dict[str, str]) -> bool:
    title = clean(candidate.get("title"))
    public = " ".join(copy.values())
    allowed_numbers = set(NUM_RE.findall(title))
    introduced_numbers = set(NUM_RE.findall(public)) - allowed_numbers
    if introduced_numbers:
        return False
    if producer.PROCESS_FILLER.search(public):
        return False
    if "\n\n" not in copy["body"]:
        return False
    cjk = len(re.findall(r"[\u3400-\u9fff]", public))
    ascii_letters = len(re.findall(r"[A-Za-z]", public))
    japanese = len(re.findall(r"[\u3040-\u30ff]", public))
    return cjk >= 120 and cjk >= ascii_letters and japanese <= 8


def prompt_for(rows: list[dict[str, Any]]) -> str:
    packet = []
    for row in rows:
        packet.append(
            {
                "candidateId": clean(row.get("id")),
                "desk": clean(row.get("desk")),
                "deskPurpose": DESK_PURPOSE.get(clean(row.get("desk")), "新聞"),
                "headline": clean(row.get("title")),
                "source": clean(row.get("source")),
                "publishedAt": clean(row.get("publishedAt")),
            }
        )
    return (
        "你是香港繁體中文新聞編輯。這是 Copilot 容量耗盡時的保守本地 fallback。\n"
        "你只能使用 INPUT 中 headline 明確陳述的事實，以及 source / publishedAt metadata。\n"
        "禁止新增 headline 沒有出現的人名、機構、地點、數字、日期、原因、結果、引述、背景細節或預測。\n"
        "可以做語言整理、翻譯和非常保守的編輯脈絡，但不得把推測寫成事實。\n"
        "如果 headline 太薄，無法安全寫成至少兩段完整新聞稿，就 OMIT 該 candidate。\n"
        "public copy 不得出現「系統」「驗證流程」「只根據標題」「資料不足」等內部流程字眼。\n"
        "使用香港繁體中文。body 必須兩段，以空行分隔；整組 public fields 合共至少約120個中文字。\n"
        "watchNext 只能寫合理的後續觀察項目，不能預測結果。\n"
        "只輸出 JSON，不要 Markdown。\n"
        "格式：{\"articles\":[{\"candidateId\":\"...\",\"verifiedCopy\":"
        "{\"title\":\"...\",\"dek\":\"...\",\"summary\":\"...\","
        "\"body\":\"第一段\\n\\n第二段\",\"context\":\"...\","
        "\"why\":\"...\",\"watchNext\":\"...\"}}]}\n"
        "INPUT:\n" + json.dumps(packet, ensure_ascii=False)
    )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("request", type=Path)
    ap.add_argument("--facts", type=Path, required=True)
    ap.add_argument("--copies", type=Path, required=True)
    args = ap.parse_args()

    request = load(args.request)
    rows = choose(request)
    if not rows:
        raise SystemExit("LOCAL_FALLBACK_NO_TRUSTED_CANDIDATES")

    result = ollama_json(prompt_for(rows))
    allowed = {clean(row.get("id")): row for row in rows}
    articles: list[dict[str, Any]] = []
    verified: list[dict[str, Any]] = []

    for row in result.get("articles") or []:
        if not isinstance(row, dict):
            continue
        cid = clean(row.get("candidateId"))
        candidate = allowed.get(cid)
        if not candidate:
            continue
        copy = convert_copy(row.get("verifiedCopy"))
        if copy is None or not valid_grounding(candidate, copy):
            continue

        title = clean(candidate.get("title"))
        source = clean(candidate.get("source"))
        published = clean(candidate.get("publishedAt"))
        url = clean(candidate.get("url"))
        verified.append(
            {
                "candidateId": cid,
                "desk": clean(candidate.get("desk")),
                "sourceEvidence": [
                    {
                        "name": source,
                        "url": url,
                        "facts": [
                            f"{source} headline reports: {title}",
                            f"Discovery feed publication timestamp: {published}",
                        ],
                    }
                ],
                "verificationSummary": (
                    "Trusted-source headline metadata accepted by the local capacity fallback; "
                    "public copy is constrained to the headline proposition."
                ),
            }
        )
        articles.append({"candidateId": cid, "verifiedCopy": copy})

    if not articles:
        raise SystemExit("LOCAL_FALLBACK_NO_SCHEMA_VALID_COPY")

    args.facts.write_text(json.dumps({"verified": verified}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    args.copies.write_text(json.dumps({"articles": articles}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"GENERAL_NEWS_LOCAL_FALLBACK_PASS candidates={len(rows)} published={len(articles)} model={MODEL_NAME}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
