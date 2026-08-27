#!/usr/bin/env python3
"""Editor-in-Chief supervisory audit for Daily Brief.

This module never fabricates or promotes news. It classifies newsroom health and
emits a targeted repair plan that can only invoke already-gated maintenance
workflows.
"""
from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from desk_retention import expired_cross_desk_football, story_time

HKT = timezone(timedelta(hours=8))
EXPECTED_DESKS = (
    "world", "asia", "hong-kong", "japan", "market-economy",
    "ai-tech", "manga-anime", "manchester-united", "football",
)
REPAIR_WORKFLOWS = {
    "collection": "rolling-news-search.yml",
    "live": "live-publication-maintenance.yml",
    "desk": "merge-live-into-desk.yml",
    "stock": "stock-publication-maintenance.yml",
    "pages": "pages.yml",
    "voice": "canto-nano-production.yml",
}

@dataclass
class Finding:
    code: str
    severity: str
    area: str
    message: str
    repair: str | None = None


def load_json(path: str | Path | None, *, optional: bool = False) -> dict[str, Any] | None:
    if not path:
        return None
    p = Path(path)
    if not p.is_file():
        if optional:
            return None
        raise FileNotFoundError(p)
    data = json.loads(p.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{p}: expected JSON object")
    return data


def parse_iso(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except Exception:
        return None
    if dt.tzinfo is None:
        return None
    return dt.astimezone(timezone.utc)


def age_minutes(value: Any, now: datetime) -> float | None:
    dt = parse_iso(value)
    if dt is None:
        return None
    return max(0.0, (now - dt).total_seconds() / 60.0)


def add(findings: list[Finding], code: str, severity: str, area: str, message: str, repair: str | None = None) -> None:
    findings.append(Finding(code, severity, area, message, repair))


def audit(
    latest: dict[str, Any], live: dict[str, Any], desk: dict[str, Any], stocks: dict[str, Any],
    tts: dict[str, Any], pages: dict[str, Any] | None, staging: dict[str, Any] | None,
    now: datetime, previous: dict[str, Any] | None = None,
) -> dict[str, Any]:
    findings: list[Finding] = []
    now_hkt = now.astimezone(HKT)
    hour, minute = now_hkt.hour, now_hkt.minute

    # Collector progress: 15-minute collection gets a 25-minute supervisor tolerance.
    if staging is None:
        add(findings, "COLLECTION_STATUS_MISSING", "warning", "collection",
            "news-staging snapshot is unavailable to the supervisor")
    else:
        search_age = age_minutes(staging.get("lastSearchAt") or staging.get("lastSearchStartedAt"), now)
        if search_age is None or search_age > 25:
            add(findings, "COLLECTION_STALE", "critical", "collection",
                f"rolling discovery is stale ({search_age if search_age is not None else 'unknown'} min)", "collection")

    # Daily and Live freshness. Preserve overnight windows; never fake timestamps.
    daily_required = hour > 8 or (hour == 8 and minute >= 15)
    if daily_required and latest.get("date") != now_hkt.date().isoformat():
        add(findings, "DAILY_STALE", "critical", "daily",
            f"daily edition date is {latest.get('date')}, expected {now_hkt.date().isoformat()}")

    live_age = age_minutes(live.get("lastUpdated"), now)
    live_active = hour == 0 or 6 <= hour <= 7 or 9 <= hour <= 23
    live_limit = 155 if hour == 9 and minute < 20 else 95
    if hour == 6 and minute < 20:
        live_active = False
    if live_active and (live_age is None or live_age > live_limit):
        add(findings, "LIVE_STALE", "critical", "live",
            f"Live publication age is {live_age if live_age is not None else 'unknown'} min", "live")

    # Desk coverage, retention and article quality.
    desks = desk.get("desks") if isinstance(desk.get("desks"), dict) else {}
    all_ids: dict[str, str] = {}
    all_titles: dict[str, str] = {}
    desk_summary: dict[str, Any] = {}
    for slug in EXPECTED_DESKS:
        stories = desks.get(slug) if isinstance(desks.get(slug), list) else []
        newest = None
        quality_errors = 0
        stale_cross_desk_football = 0
        for story in stories:
            if not isinstance(story, dict):
                quality_errors += 1
                continue
            sid = str(story.get("id") or "").strip()
            title = str(story.get("title") or "").strip()
            body = str(story.get("body") or "").strip()
            summary = str(story.get("summary") or "").strip()
            source_url = str(story.get("sourceUrl") or "").strip()
            routes = {
                str(x) for x in (story.get("deskSlugs") or [])
                if isinstance(story.get("deskSlugs"), list) and str(x)
            }
            if not sid or not title or len(body) < 80 or len(summary) < 20 or not source_url.startswith("http"):
                quality_errors += 1

            # Intentional multi-desk routing is not itself a duplicate defect.  What
            # matters is whether a cross-post is still appropriate for the target desk.
            if expired_cross_desk_football(story, slug, now=now):
                stale_cross_desk_football += 1
                add(findings, "STALE_CROSS_DESK_FOOTBALL", "critical", slug,
                    f"football cross-post {sid or title} exceeded the 36-hour regional-desk retention window",
                    "desk")

            if sid:
                prior = all_ids.get(sid)
                intentional = bool(prior and prior in routes and slug in routes)
                if prior and prior != slug and not intentional:
                    add(findings, "DUPLICATE_ARTICLE_ID", "warning", "editorial",
                        f"article id {sid} appears in both {prior} and {slug} without an explicit multi-desk route")
                all_ids[sid] = slug
            norm_title = re.sub(r"\s+", "", title).lower()
            if norm_title:
                prior = all_titles.get(norm_title)
                intentional = bool(prior and prior in routes and slug in routes)
                if prior and prior != slug and not intentional:
                    add(findings, "DUPLICATE_HEADLINE", "warning", "editorial",
                        f"same headline appears in both {prior} and {slug} without an explicit multi-desk route")
                all_titles[norm_title] = slug
            st = story_time(story, now=now)
            if st and (newest is None or st > newest):
                newest = st
        newest_age = max(0.0, (now - newest).total_seconds() / 60.0) if newest else None
        desk_summary[slug] = {
            "storyCount": len(stories),
            "newestAgeMinutes": newest_age,
            "qualityErrorCount": quality_errors,
            "staleCrossDeskFootballCount": stale_cross_desk_football,
        }
        if not stories:
            add(findings, "DESK_EMPTY", "critical", slug,
                f"{slug} has no Rolling Desk stories", "collection")
        elif quality_errors:
            add(findings, "ARTICLE_SHAPE_INVALID", "warning", slug,
                f"{quality_errors} story/stories fail basic article-shape checks")
        # A desk going two days without any parseable/new material is suspicious, but
        # not a licence to manufacture a story. Trigger discovery once, then escalate.
        if newest_age is not None and newest_age > 48 * 60:
            add(findings, "DESK_EDITORIAL_GAP", "critical", slug,
                f"newest parseable story is {newest_age/60:.1f} hours old", "collection")

    # Stock: hourly checks should be fresh; verified content staleness triggers the
    # gated primary-source producer, never timestamp rewriting.
    stock_check_age = age_minutes(stocks.get("lastCheckedAt") or stocks.get("generatedAt"), now)
    stock_content_age = age_minutes(stocks.get("generatedAt"), now)
    stock_active = hour == 0 or 6 <= hour <= 23
    if hour == 6 and minute < 15:
        stock_active = False
    if stock_active and (stock_check_age is None or stock_check_age > 95 or str(stocks.get("collectionStatus", "")).upper() != "COMPLETE"):
        add(findings, "STOCK_CHECK_STALE", "critical", "stock",
            f"Stock check age/status is {stock_check_age}/{stocks.get('collectionStatus')}", "stock")
    if stock_content_age is None or stock_content_age > 36 * 60:
        add(findings, "STOCK_VERIFIED_POOL_STALE", "critical", "stock",
            f"verified Stock content age is {stock_content_age/60:.1f} hours" if stock_content_age is not None else "verified Stock content timestamp is invalid",
            "stock")

    # Public propagation is authoritative evidence. Equal-but-stale is already red in pages probe.
    pages_age = age_minutes((pages or {}).get("checkedAt"), now) if pages else None
    if pages is None or pages_age is None or pages_age > 30:
        add(findings, "PUBLIC_PROBE_STALE", "critical", "pages",
            "public Pages probe is missing or older than 30 minutes", "pages")
    else:
        if not bool(pages.get("infrastructureMatch")):
            add(findings, "PUBLIC_INFRASTRUCTURE_MISMATCH", "critical", "pages",
                "public site differs from repository or a core page/runtime check failed", "pages")
        if not bool(pages.get("editorialFreshnessMatch")):
            add(findings, "PUBLIC_EDITORIAL_STALE", "warning", "pages",
                "public probe reports editorial freshness failure; root-cause freshness checks are evaluated separately")

    # Voice: do not chase routine partial coverage. Repair only if the public manifest
    # is mismatched or if voice has clearly fallen behind changing Live content.
    if tts.get("engine") != "typangaa/canto-tts-nano" or int(tts.get("availableArticleCount") or 0) <= 0:
        add(findings, "VOICE_ENGINE_INVALID", "critical", "voice",
            "Canto Nano manifest is missing/invalid", "voice")
    voice_age = age_minutes(tts.get("lastVoicePublishedAt") or tts.get("generatedAt"), now)
    live_dt = parse_iso(live.get("lastUpdated"))
    voice_dt = parse_iso(tts.get("generatedAt"))
    if live_dt and voice_dt and live_dt - voice_dt > timedelta(hours=2) and (voice_age is None or voice_age > 120):
        add(findings, "VOICE_BEHIND_CONTENT", "critical", "voice",
            "voice manifest is more than two hours behind current Live content", "voice")
    elif int(tts.get("pendingArticleCount") or 0) > 0:
        add(findings, "VOICE_PENDING", "info", "voice",
            f"{int(tts.get('pendingArticleCount') or 0)} article(s) remain pending; scheduled voice production owns the backlog")

    # Discord is audited conservatively here. Delivery-level evidence is not persisted
    # in the repository, so the supervisor must not claim success it cannot prove.
    add(findings, "DISCORD_DELIVERY_OBSERVABILITY", "info", "discord",
        "Discord workflow delivery cannot be proven from newsroom JSON alone; workflow-run health remains the delivery evidence")

    # If the same critical repairable failure survives a previous supervisory cycle,
    # escalate it rather than endlessly restarting workflows.
    if previous:
        previous_codes = {
            str(f.get("code")) for f in (previous.get("findings") or [])
            if isinstance(f, dict) and f.get("severity") == "critical"
        }
        persistent = [f for f in findings if f.severity == "critical" and f.repair and f.code in previous_codes]
        for f in persistent:
            add(findings, "PERSISTENT_" + f.code, "critical", f.area,
                f"{f.code} remains unresolved after the previous Editor-in-Chief cycle; automatic repair alone is no longer sufficient")

    repair_keys = []
    for f in findings:
        if f.repair and f.repair not in repair_keys:
            repair_keys.append(f.repair)
    workflows = [REPAIR_WORKFLOWS[k] for k in repair_keys]

    critical = [f for f in findings if f.severity == "critical"]
    unresolved = [f for f in critical if not f.repair]
    warnings = [f for f in findings if f.severity == "warning"]
    if unresolved:
        status = "EDITORIAL_ATTENTION_REQUIRED"
    elif workflows:
        status = "AUTO_REPAIRING"
    elif warnings:
        status = "HEALTHY_WITH_WARNINGS"
    else:
        status = "HEALTHY"

    return {
        "schemaVersion": 1,
        "role": "Editor-in-Chief",
        "checkedAt": now.isoformat(),
        "checkedAtHKT": now_hkt.isoformat(),
        "status": status,
        "policy": {
            "fabricateNews": False,
            "fakeFreshness": False,
            "weakenVerificationGates": False,
            "autoRepairDeterministicInfrastructure": True,
            "escalateUnverifiableEditorialGaps": True,
        },
        "summary": {
            "criticalCount": len(critical),
            "warningCount": len(warnings),
            "findingCount": len(findings),
            "repairWorkflowCount": len(workflows),
            "unresolvedCriticalCount": len(unresolved),
        },
        "deskAudit": desk_summary,
        "freshness": {
            "liveAgeMinutes": live_age,
            "stockCheckAgeMinutes": stock_check_age,
            "stockContentAgeMinutes": stock_content_age,
            "pagesProbeAgeMinutes": pages_age,
            "voiceAgeMinutes": voice_age,
        },
        "repairPlan": [{"area": key, "workflow": REPAIR_WORKFLOWS[key]} for key in repair_keys],
        "findings": [asdict(f) for f in findings],
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--latest", default="data/latest.json")
    ap.add_argument("--live", default="data/live.json")
    ap.add_argument("--desk", default="data/desk-latest.json")
    ap.add_argument("--stocks", default="data/stocks-latest.json")
    ap.add_argument("--tts", default="data/tts-manifest.json")
    ap.add_argument("--pages-status")
    ap.add_argument("--staging")
    ap.add_argument("--previous-status")
    ap.add_argument("--output", default="/tmp/editor-in-chief-status.json")
    ap.add_argument("--now", help="ISO timestamp, test-only")
    args = ap.parse_args()
    now = parse_iso(args.now) if args.now else datetime.now(timezone.utc)
    if now is None:
        raise SystemExit("invalid --now")
    result = audit(
        load_json(args.latest) or {}, load_json(args.live) or {}, load_json(args.desk) or {},
        load_json(args.stocks) or {}, load_json(args.tts) or {},
        load_json(args.pages_status, optional=True), load_json(args.staging, optional=True), now,
        load_json(args.previous_status, optional=True),
    )
    Path(args.output).write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False))
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
