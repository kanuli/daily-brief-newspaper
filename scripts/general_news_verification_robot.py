#!/usr/bin/env python3
"""Bridge rolling discovery into source-verified Cantonese general-news drafts.

The collector remains discovery-only. This helper prepares a bounded candidate
set for an isolated verification model, validates/merges its evidence and copy,
and invokes the existing verified producer with the same hour-based freshness
policy used by the Editor-in-Chief.
"""
from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import general_news_verified_producer as producer
from desk_freshness_policy import PUBLIC_DESK_FRESHNESS_HOURS, editorial_story_time

HKT = timezone(timedelta(hours=8))
SOFT_TARGET_HOURS = {
    "world": 3,
    "asia": 3,
    "hong-kong": 6,
    "japan": 6,
    "finance": 4,
    "ai-tech": 4,
    "manga-anime": 24,
    "manchester-united": 12,
    "football": 8,
}
PUBLIC_DESK = {
    "world": "world",
    "asia": "asia",
    "hong-kong": "hong-kong",
    "japan": "japan",
    "finance": "market-economy",
    "ai-tech": "ai-tech",
    "manga-anime": "manga-anime",
    "manchester-united": "manchester-united",
    "football": "football",
}
MAX_CANDIDATES_PER_DESK = 4
MAX_CANDIDATE_AGE_HOURS = 30


def load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def load_model_json(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8").strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text, flags=re.I)
        text = re.sub(r"\s*```$", "", text)
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end < start:
        raise ValueError(f"{path} does not contain a JSON object")
    value = json.loads(text[start : end + 1])
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def parse_iso(value: Any) -> datetime | None:
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if dt.tzinfo is None:
            return None
        return dt.astimezone(timezone.utc)
    except Exception:
        return None


def clean(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def story_time(story: dict[str, Any]) -> datetime | None:
    for key in ("publishedAt", "eventPublishedAt", "updatedAt", "verifiedAt"):
        dt = parse_iso(story.get(key))
        if dt:
            return dt
    return None


def soft_stale_desks(desk_data: dict[str, Any], now: datetime) -> list[str]:
    desks = desk_data.get("desks") if isinstance(desk_data.get("desks"), dict) else {}
    stale: list[str] = []
    for name, limit in SOFT_TARGET_HOURS.items():
        rows = desks.get(PUBLIC_DESK[name]) if isinstance(desks.get(PUBLIC_DESK[name]), list) else []
        stamps = [story_time(row) for row in rows if isinstance(row, dict)]
        newest = max((dt for dt in stamps if dt is not None), default=None)
        if newest is None or (now - newest).total_seconds() / 3600.0 > limit:
            stale.append(name)
    return stale


def existing_identity(desk_data: dict[str, Any], live_data: dict[str, Any]) -> tuple[set[str], set[str]]:
    return producer.existing_identity(desk_data, live_data)


def normalized_title(value: Any) -> str:
    return producer.normalized_title(value)


def raw_candidate_ok(candidate: Any, desk: str, now: datetime, urls: set[str], titles: set[str]) -> bool:
    if not isinstance(candidate, dict) or clean(candidate.get("desk")) != desk:
        return False
    title = clean(candidate.get("title"))
    url = clean(candidate.get("url"))
    source = clean(candidate.get("source"))
    published = parse_iso(candidate.get("publishedAt"))
    if not title or len(title) < 12 or not source or not url.startswith(("http://", "https://")) or not published:
        return False
    if producer.BAD_TEXT.search(title) or producer.LOW_VALUE.search(title):
        return False
    age_hours = (now - published).total_seconds() / 3600.0
    if age_hours < -0.17 or age_hours > MAX_CANDIDATE_AGE_HOURS:
        return False
    if desk == "hong-kong" and not re.search(
        r"香港|港聞|港股|港元|港府|港人|訪港|來港|在港|赴港|港交所|證監會|會財局|金管局|立法會|特區|陳茂波|陳翊庭|\bHong Kong\b|\bHK\b",
        title,
        re.I,
    ):
        return False
    if desk == "manchester-united" and not producer.MAN_UTD_NEWS.search(title):
        return False
    if desk == "football" and not producer.FOOTBALL_EVENT.search(title):
        return False
    key = normalized_title(producer.TITLE_SUFFIX.sub("", title))
    return url not in urls and key not in titles


def candidate_score(row: dict[str, Any]) -> tuple[int, float]:
    title = clean(row.get("title"))
    source = clean(row.get("source"))
    points = 0
    if producer.TRUSTED_SOURCE.search(source):
        points += 4
    if (source == "時事通信" and row.get("provider") == "Jiji Official RSS"
        and row.get("desk") == "japan"
        and re.fullmatch(r"https://www\.jiji\.com/jc/article\?k=[0-9]{13}&g=(?:pol|soc)&m=rss", clean(row.get("url")))):
        points += 4
    if (source == "中央通訊社" and row.get("provider") in {"CNA Official RSS", "CNA Official Japan Topic"}
        and row.get("desk") in {"asia", "japan"}
        and (row.get("provider") != "CNA Official Japan Topic" or row.get("desk") == "japan")
        and re.fullmatch(r"https://www\.cna\.com\.tw/news/aopl/[0-9]{12}\.aspx", clean(row.get("url")))):
        points += 8
    if re.search(r"official|government|gov\.|ministry|police|court|commission|Reuters|AP|BBC|NHK|共同|政府|警方|法院|官方", f"{source} {title}", re.I):
        points += 3
    # A bounded, official direct-feed route is a better source-access candidate
    # than an opaque search redirect. This ranks discovery only: every existing
    # date/dedup/relevance, actual publisher-text and copy gate still runs.
    if (row.get("provider") == "RTHK Official RSS" and source == "香港電台"
        and row.get("desk") in {"world", "asia", "hong-kong", "japan", "finance", "ai-tech"}
        and re.fullmatch(r"https://news\.rthk\.hk/rthk/ch/component/k2/\d+-\d{8}\.htm", clean(row.get("url")))):
        points += 4
    stamp = parse_iso(row.get("publishedAt")) or datetime.min.replace(tzinfo=timezone.utc)
    return points, stamp.timestamp()


def public_freshness_priority(desk_data: dict[str, Any], desk: str, now: datetime) -> int:
    """Schedule hard-breached desks first; do not alter any freshness verdict.

    Three independent workers retain the same four probes/one model call each.
    A merely soft-stale World desk must not consume Finance's worker before its
    third direct candidate when Finance has breached the real public SLA.
    """
    slug = PUBLIC_DESK[desk]
    desks = desk_data.get("desks") if isinstance(desk_data.get("desks"), dict) else {}
    rows = desks.get(slug) if isinstance(desks.get(slug), list) else []
    stamps = [editorial_story_time(row, now=now) for row in rows if isinstance(row, dict)]
    newest = max((stamp for stamp in stamps if stamp is not None), default=None)
    hard_breach = (newest is None or newest > now
                   or (now - newest).total_seconds() > PUBLIC_DESK_FRESHNESS_HOURS[slug] * 3600)
    return 0 if hard_breach else 1


def prepare_request(staging: dict[str, Any], desk_data: dict[str, Any], live_data: dict[str, Any], now: datetime) -> dict[str, Any]:
    stale = soft_stale_desks(desk_data, now)
    stale.sort(key=lambda desk: public_freshness_priority(desk_data, desk, now))
    urls, titles = existing_identity(desk_data, live_data)
    selected: list[dict[str, Any]] = []
    desks = staging.get("desks") if isinstance(staging.get("desks"), dict) else {}
    for desk in stale:
        rows = [row for row in (desks.get(desk) or []) if raw_candidate_ok(row, desk, now, urls, titles)]
        rows.sort(key=candidate_score, reverse=True)
        seen_urls: set[str] = set()
        seen_titles: set[str] = set()
        count = 0
        for row in rows:
            url = clean(row.get("url"))
            title_key = normalized_title(producer.TITLE_SUFFIX.sub("", clean(row.get("title"))))
            if url in seen_urls or title_key in seen_titles:
                continue
            selected.append({
                "id": clean(row.get("id")),
                "desk": desk,
                "title": clean(row.get("title")),
                "url": url,
                "source": clean(row.get("source")),
                "provider": clean(row.get("provider")),
                "query": clean(row.get("query")),
                "publishedAt": clean(row.get("publishedAt")),
            })
            seen_urls.add(url)
            seen_titles.add(title_key)
            count += 1
            if count >= MAX_CANDIDATES_PER_DESK:
                break
    return {
        "schemaVersion": 1,
        "createdAt": now.isoformat().replace("+00:00", "Z"),
        "candidateSnapshotAt": staging.get("lastSearchAt") or staging.get("lastSearchStartedAt"),
        "staleDesks": stale,
        "candidateCount": len(selected),
        "candidates": selected,
    }


def valid_evidence(row: Any) -> bool:
    if not isinstance(row, dict):
        return False
    url = clean(row.get("url"))
    facts = row.get("facts")
    return url.startswith(("http://", "https://")) and isinstance(facts, list) and len([clean(x) for x in facts if clean(x)]) >= 2


def valid_copy(copy: Any) -> bool:
    if not isinstance(copy, dict):
        return False
    if any(not clean(copy.get(field)) for field in producer.COPY_FIELDS):
        return False
    body = str(copy.get("body") or "")
    public = " ".join(clean(copy.get(field)) for field in producer.COPY_FIELDS)
    return "\n\n" in body and len(re.findall(r"[\u3400-\u9fff]", public)) >= 120


def merge_verified(staging: dict[str, Any], request: dict[str, Any], facts: dict[str, Any], copies: dict[str, Any]) -> tuple[dict[str, Any], dict[str, Any]]:
    allowed = {
        clean(row.get("id")): row
        for row in request.get("candidates") or []
        if isinstance(row, dict) and clean(row.get("id"))
    }
    fact_map: dict[str, dict[str, Any]] = {}
    for row in facts.get("verified") or []:
        if not isinstance(row, dict):
            continue
        cid = clean(row.get("candidateId"))
        evidence = [e for e in (row.get("sourceEvidence") or []) if valid_evidence(e)]
        if cid in allowed and clean(row.get("desk")) == clean(allowed[cid].get("desk")) and evidence:
            fact_map[cid] = {"sourceEvidence": evidence, "verificationSummary": clean(row.get("verificationSummary"))}
    copy_map: dict[str, dict[str, Any]] = {}
    for row in copies.get("articles") or []:
        if not isinstance(row, dict):
            continue
        cid = clean(row.get("candidateId"))
        copy = row.get("verifiedCopy")
        if cid in allowed and cid in fact_map and valid_copy(copy):
            copy_map[cid] = copy

    enriched = json.loads(json.dumps(staging, ensure_ascii=False))
    merged: list[str] = []
    for rows in (enriched.get("desks") or {}).values():
        if not isinstance(rows, list):
            continue
        for row in rows:
            if not isinstance(row, dict):
                continue
            cid = clean(row.get("id"))
            if cid not in copy_map:
                continue
            row["sourceEvidence"] = fact_map[cid]["sourceEvidence"]
            row["verifiedCopy"] = copy_map[cid]
            row["verificationSummary"] = fact_map[cid]["verificationSummary"]
            merged.append(cid)
    outcome = {
        "requestedCandidates": len(allowed),
        "factVerifiedCandidates": len(fact_map),
        "copyVerifiedCandidates": len(copy_map),
        "mergedCandidateIds": merged,
    }
    return enriched, outcome


def candidate_ok_soft(candidate: Any, desk: str, now: datetime, urls: set[str], titles: set[str]) -> bool:
    if not raw_candidate_ok(candidate, desk, now, urls, titles):
        return False
    return producer.cantonese_copy(candidate) is not None


def produce_with_soft_policy(staging: dict[str, Any], desk_data: dict[str, Any], live_data: dict[str, Any], now: datetime) -> dict[str, Any]:
    old_stale = producer.stale_desks
    old_candidate_ok = producer.candidate_ok
    try:
        producer.stale_desks = soft_stale_desks
        producer.candidate_ok = candidate_ok_soft
        return producer.produce(staging, desk_data, live_data, now)
    finally:
        producer.stale_desks = old_stale
        producer.candidate_ok = old_candidate_ok


def write_json(path: Path, value: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)

    prep = sub.add_parser("prepare")
    prep.add_argument("staging", type=Path)
    prep.add_argument("--desk", type=Path, default=Path("data/desk-latest.json"))
    prep.add_argument("--live", type=Path, default=Path("data/live.json"))
    prep.add_argument("--output", type=Path, required=True)
    prep.add_argument("--now", default="")

    merge = sub.add_parser("merge")
    merge.add_argument("staging", type=Path)
    merge.add_argument("--request", type=Path, required=True)
    merge.add_argument("--facts", type=Path, required=True)
    merge.add_argument("--copies", type=Path, required=True)
    merge.add_argument("--output", type=Path, required=True)
    merge.add_argument("--report", type=Path, required=True)

    prod = sub.add_parser("produce")
    prod.add_argument("staging", type=Path)
    prod.add_argument("--desk", type=Path, default=Path("data/desk-latest.json"))
    prod.add_argument("--live", type=Path, default=Path("data/live.json"))
    prod.add_argument("--output", type=Path, required=True)
    prod.add_argument("--now", default="")

    args = parser.parse_args()
    if args.command == "prepare":
        now = parse_iso(args.now) if args.now else datetime.now(timezone.utc)
        if now is None:
            raise SystemExit("--now must be timezone-aware ISO")
        result = prepare_request(load(args.staging), load(args.desk), load(args.live), now)
        write_json(args.output, result)
        print(f"GENERAL_NEWS_VERIFY_PREP stale={len(result['staleDesks'])} candidates={result['candidateCount']}")
        return 0

    if args.command == "merge":
        enriched, report = merge_verified(
            load(args.staging),
            load(args.request),
            load_model_json(args.facts),
            load_model_json(args.copies),
        )
        write_json(args.output, enriched)
        write_json(args.report, report)
        print(f"GENERAL_NEWS_VERIFY_MERGE verified={report['copyVerifiedCandidates']} merged={len(report['mergedCandidateIds'])}")
        return 0

    now = parse_iso(args.now) if args.now else datetime.now(timezone.utc)
    if now is None:
        raise SystemExit("--now must be timezone-aware ISO")
    result = produce_with_soft_policy(load(args.staging), load(args.desk), load(args.live), now)
    write_json(args.output, result)
    print(
        "GENERAL_NEWS_OUTCOME_" + ("PASS" if result.get("articles") else "UNRESOLVED"),
        f"stale={len((result.get('coverage') or {}).get('staleDesks') or [])}",
        f"produced={len(result.get('articles') or [])}",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
