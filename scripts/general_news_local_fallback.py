#!/usr/bin/env python3
"""Conservative open-source local fallback for General News.

The local model has one narrow job only: translate/normalise a trusted-source
headline into Hong Kong Traditional Chinese. All other public fields are built
by deterministic templates from that translated headline plus source metadata.
No extra concrete fact may be introduced by the fallback.
"""
from __future__ import annotations

import argparse
import json
import re
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from opencc import OpenCC

import general_news_verified_producer as producer

MODEL_URL = "http://127.0.0.1:11434/api/generate"
MODEL_NAME = "qwen2.5:1.5b"
HK = OpenCC("s2hk")
NUM_RE = re.compile(r"\d+(?:[.,:]\d+)*")
KANA_RE = re.compile(r"[\u3040-\u30ff]")
CJK_RE = re.compile(r"[\u3400-\u9fff]")
CODE_FENCE_RE = re.compile(r"^\s*```(?:json)?\s*|\s*```\s*$", re.I)

DESK_PURPOSE = {
    "world": "國際公共事務",
    "asia": "亞洲公共事務",
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
    desk = clean(candidate.get("desk"))
    if desk == "manchester-united" and not producer.MAN_UTD_NEWS.search(title):
        return False
    if desk == "football" and not producer.FOOTBALL_EVENT.search(title):
        return False
    return True


def choose(request: dict[str, Any]) -> list[dict[str, Any]]:
    stale = [clean(x) for x in (request.get("staleDesks") or []) if clean(x)]
    by_desk: dict[str, list[dict[str, Any]]] = {}
    for row in request.get("candidates") or []:
        if isinstance(row, dict) and trusted(row):
            by_desk.setdefault(clean(row.get("desk")), []).append(row)

    selected: list[dict[str, Any]] = []
    for desk in stale:
        rows = by_desk.get(desk) or []
        if not rows:
            continue
        rows.sort(key=lambda row: clean(row.get("publishedAt")), reverse=True)
        selected.append(rows[0])
    return selected[:6]


def ollama_json(prompt: str) -> dict[str, Any]:
    body = json.dumps(
        {
            "model": MODEL_NAME,
            "prompt": prompt,
            "stream": False,
            "format": "json",
            "options": {"temperature": 0.0, "top_p": 0.6, "num_predict": 700},
        },
        ensure_ascii=False,
    ).encode("utf-8")
    req = urllib.request.Request(
        MODEL_URL,
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=180) as response:
        payload = json.loads(response.read().decode("utf-8"))
    raw = str(payload.get("response") or "").strip()
    raw = CODE_FENCE_RE.sub("", raw).strip()
    value = json.loads(raw)
    if not isinstance(value, dict):
        raise ValueError("local model did not return a JSON object")
    return value


def prompt_for(rows: list[dict[str, Any]]) -> str:
    packet = [
        {
            "candidateId": clean(row.get("id")),
            "headline": clean(row.get("title")),
            "source": clean(row.get("source")),
        }
        for row in rows
    ]
    return (
        "你只做新聞標題翻譯，不寫新聞內容。\n"
        "將每個 headline 忠實翻譯／整理成香港繁體中文。\n"
        "禁止新增原 headline 沒有的人名、機構、地點、數字、日期、原因、結果、引述或背景。\n"
        "保留原有專有名詞與數字。不要評論，不要解釋。\n"
        "只輸出 JSON：{\"titles\":[{\"candidateId\":\"...\",\"titleZh\":\"...\"}]}\n"
        "INPUT:\n" + json.dumps(packet, ensure_ascii=False)
    )


def safe_title(original: str, translated: str) -> str | None:
    translated = HK.convert(clean(translated))
    if not translated:
        return None
    if set(NUM_RE.findall(translated)) - set(NUM_RE.findall(original)):
        return None
    if len(KANA_RE.findall(translated)) > 8:
        return None
    if len(CJK_RE.findall(translated)) < 6:
        return None
    return translated


def hkt_label(value: Any) -> str:
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00")).astimezone(
            timezone.utc
        )
        hkt = dt.astimezone(timezone(timedelta(hours=8)))
        return hkt.strftime("%m月%d日 %H:%M HKT")
    except Exception:
        return "今日"


def build_copy(candidate: dict[str, Any], title_zh: str) -> dict[str, str]:
    source = HK.convert(clean(candidate.get("source")))
    desk = clean(candidate.get("desk"))
    purpose = DESK_PURPOSE.get(desk, "公共事務")
    time_label = hkt_label(candidate.get("publishedAt"))

    dek = f"{source}報道，{title_zh}。"
    summary = f"{source}最新報道指出，{title_zh}。"
    body = (
        f"{source}報道，{title_zh}。消息於{time_label}前後刊出，屬於{purpose}的最新發展。"
        "現階段公開消息的核心重點就是上述進展，相關內容仍會隨正式公布而更新。"
        "\n\n"
        f"這項發展與{purpose}直接相關。後續可留意相關機構、當事方或官方渠道公布的新安排與進一步資料；"
        "在出現新的具體資料前，本報不延伸未獲來源支持的細節。"
    )
    context = f"這是{purpose}方面的最新發展，原始消息由{source}發布。"
    why = f"事件涉及{purpose}，其後的正式安排及新增資料可能影響後續理解。"
    watch = "留意相關機構、當事方或官方渠道其後公布的正式資料與安排。"
    return {
        "title": title_zh,
        "dek": dek,
        "summary": summary,
        "body": body,
        "context": context,
        "why": why,
        "watchNext": watch,
    }


def valid_copy(candidate: dict[str, Any], copy: dict[str, str]) -> bool:
    public = " ".join(copy.values())
    original = clean(candidate.get("title"))
    if set(NUM_RE.findall(public)) - set(NUM_RE.findall(original)):
        return False
    if producer.PROCESS_FILLER.search(public):
        return False
    if "\n\n" not in copy["body"]:
        return False
    cjk = len(CJK_RE.findall(public))
    ascii_letters = len(re.findall(r"[A-Za-z]", public))
    japanese = len(KANA_RE.findall(public))
    return cjk >= 120 and cjk >= ascii_letters and japanese <= 8


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
    translated = {
        clean(row.get("candidateId")): clean(row.get("titleZh"))
        for row in (result.get("titles") or [])
        if isinstance(row, dict)
    }

    verified: list[dict[str, Any]] = []
    articles: list[dict[str, Any]] = []
    rejected: list[str] = []

    for cid, candidate in allowed.items():
        title_zh = safe_title(clean(candidate.get("title")), translated.get(cid, ""))
        if not title_zh:
            rejected.append(f"{cid}:unsafe-title")
            continue
        copy = build_copy(candidate, title_zh)
        if not valid_copy(candidate, copy):
            rejected.append(f"{cid}:copy-gate")
            continue

        source = clean(candidate.get("source"))
        title = clean(candidate.get("title"))
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
                    "Trusted-source headline accepted by the local capacity fallback; "
                    "public copy is deterministically constrained to the headline proposition."
                ),
            }
        )
        articles.append({"candidateId": cid, "verifiedCopy": copy})

    print(
        "LOCAL_FALLBACK_DIAGNOSTIC",
        json.dumps(
            {
                "selected": list(allowed),
                "translated": sorted(translated),
                "rejected": rejected,
                "accepted": [row["candidateId"] for row in articles],
            },
            ensure_ascii=False,
        ),
    )

    if not articles:
        raise SystemExit("LOCAL_FALLBACK_NO_SCHEMA_VALID_COPY")

    args.facts.write_text(
        json.dumps({"verified": verified}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    args.copies.write_text(
        json.dumps({"articles": articles}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        f"GENERAL_NEWS_LOCAL_FALLBACK_PASS candidates={len(rows)} "
        f"published={len(articles)} model={MODEL_NAME}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
