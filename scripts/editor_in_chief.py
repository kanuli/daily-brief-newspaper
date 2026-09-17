#!/usr/bin/env python3
"""Editor-in-Chief supervisory audit for Daily Brief.

The supervisor never fabricates or promotes news. It classifies newsroom
health, enforces structural/routing/freshness rules, performs deterministic
semantic copyediting checks, and models recovery ownership before declaring
production healthy.
"""
from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass, asdict
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from desk_retention import expired_cross_desk_football
from desk_freshness_policy import editorial_story_time, routed_slugs
from semantic_copy_guard import semantic_copy_errors

HKT = timezone(timedelta(hours=8))
EXPECTED_DESKS = (
    "world", "asia", "hong-kong", "japan", "market-economy",
    "ai-tech", "manga-anime", "manchester-united", "football",
)
DESK_FRESHNESS_SLA_HOURS = {
    "world": 24,
    "asia": 24,
    "hong-kong": 24,
    "japan": 24,
    "market-economy": 24,
    "ai-tech": 24,
    "manga-anime": 48,
    "manchester-united": 48,
    "football": 48,
}
REPAIR_WORKFLOWS = {
    "collection": "rolling-news-search.yml",
    "live": "live-publication-maintenance.yml",
    "desk": "merge-live-into-desk.yml",
    "stock": "stock-publication-maintenance.yml",
    "pages": "pages.yml",
    "voice": "canto-nano-production.yml",
}
# Some recovery owners are not GitHub workflows. The Daily publisher is an
# external scheduled production owner supervised by the ChatGPT watchdog.
RECOVERY_OWNERS = {
    "daily": "automation:Daily Priority Briefing",
    **{key: f"workflow:{value}" for key, value in REPAIR_WORKFLOWS.items()},
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


def add(findings: list[Finding], code: str, severity: str, area: str, message: str,
        repair: str | None = None) -> None:
    findings.append(Finding(code, severity, area, message, repair))


def audit(
    latest: dict[str, Any], live: dict[str, Any], desk: dict[str, Any], stocks: dict[str, Any],
    tts: dict[str, Any], pages: dict[str, Any] | None, staging: dict[str, Any] | None,
    now: datetime, previous: dict[str, Any] | None = None,
) -> dict[str, Any]:
    findings: list[Finding] = []
    now_hkt = now.astimezone(HKT)
    hour, minute = now_hkt.hour, now_hkt.minute
    today = now_hkt.date().isoformat()

    # Collector progress: 15-minute collection gets a 25-minute supervisor tolerance.
    if staging is None:
        add(findings, "COLLECTION_STATUS_MISSING", "warning", "collection",
            "news-staging snapshot is unavailable to the supervisor")
    else:
        search_age = age_minutes(staging.get("lastSearchAt") or staging.get("lastSearchStartedAt"), now)
        if search_age is None or search_age > 25:
            add(findings, "COLLECTION_STALE", "critical", "collection",
                f"rolling discovery is stale ({search_age if search_age is not None else 'unknown'} min)", "collection")

    # TODAY-FIRST: a missed historical edition is never rebuilt before today's edition.
    # Daily recovery is owned by the existing Daily Priority Briefing publisher, not by
    # a deterministic GitHub workflow that cannot author verified current journalism.
    daily_required = hour > 8 or (hour == 8 and minute >= 15)
    current_daily = latest.get("date") == today
    if daily_required and not current_daily:
        add(findings, "DAILY_STALE", "critical", "daily",
            f"daily edition date is {latest.get('date')}, expected {today}; publish TODAY directly without historical backfill",
            "daily")

    live_age = age_minutes(live.get("lastUpdated"), now)
    live_active = hour == 0 or 6 <= hour <= 7 or 9 <= hour <= 23
    live_limit = 155 if hour == 9 and minute < 20 else 95
    if hour == 6 and minute < 20:
        live_active = False
    if live_active and (live_age is None or live_age > live_limit):
        add(findings, "LIVE_STALE", "critical", "live",
            f"Live publication age is {live_age if live_age is not None else 'unknown'} min", "live")

    desks = desk.get("desks") if isinstance(desk.get("desks"), dict) else {}
    all_ids: dict[str, str] = {}
    all_titles: dict[str, str] = {}
    desk_summary: dict[str, Any] = {}
    for slug in EXPECTED_DESKS:
        stories = desks.get(slug) if isinstance(desks.get(slug), list) else []
        newest = None
        quality_errors = 0
        semantic_errors = 0
        stale_cross_desk_football = 0
        routing_errors = 0
        newest_first_errors = 0
        previous_stamp = None
        for story in stories:
            if not isinstance(story, dict):
                quality_errors += 1
                continue
            sid = str(story.get("id") or "").strip()
            title = str(story.get("title") or "").strip()
            body = str(story.get("body") or "").strip()
            summary = str(story.get("summary") or "").strip()
            source_url = str(story.get("sourceUrl") or "").strip()
            routes = set(routed_slugs(story))
            if not sid or not title or len(body) < 80 or len(summary) < 20 or not source_url.startswith("http"):
                quality_errors += 1

            semantic = semantic_copy_errors(story)
            if semantic:
                quality_errors += 1
                semantic_errors += 1
                for reason in semantic:
                    add(findings, "SEMANTIC_COPY_CORRUPTION", "critical", slug,
                        f"story {sid or title}: {reason}", None)

            if routes and slug not in routes:
                routing_errors += 1
                add(findings, "HARD_ROUTING_VIOLATION", "critical", slug,
                    f"story {sid or title} belongs to {sorted(routes)} but is still present on {slug}", "desk")

            stamp = editorial_story_time(story, now=now)
            if stamp is not None:
                if previous_stamp is not None and stamp > previous_stamp:
                    newest_first_errors += 1
                previous_stamp = stamp
                if newest is None or stamp > newest:
                    newest = stamp

            if expired_cross_desk_football(story, slug, now=now):
                stale_cross_desk_football += 1
                add(findings, "STALE_CROSS_DESK_FOOTBALL", "critical", slug,
                    f"football cross-post {sid or title} exceeded the 36-hour regional-desk retention window", "desk")

            if sid:
                prior = all_ids.get(sid)
                intentional = bool(prior and prior in routes and slug in routes)
                if prior and prior != slug and not intentional:
                    add(findings, "DUPLICATE_ARTICLE_ID", "warning", "editorial",
                        f"article id {sid} appears in both {prior} and {slug} without an explicit valid route")
                all_ids[sid] = slug
            norm_title = re.sub(r"\s+", "", title).lower()
            if norm_title:
                prior = all_titles.get(norm_title)
                intentional = bool(prior and prior in routes and slug in routes)
                if prior and prior != slug and not intentional:
                    add(findings, "DUPLICATE_HEADLINE", "warning", "editorial",
                        f"same headline appears in both {prior} and {slug} without an explicit valid route")
                all_titles[norm_title] = slug

        if newest_first_errors:
            add(findings, "DESK_NOT_NEWEST_FIRST", "critical", slug,
                f"{slug} has {newest_first_errors} timestamp inversion(s); newest verified story is not at the top", "desk")

        newest_age = max(0.0, (now - newest).total_seconds() / 60.0) if newest else None
        sla_hours = DESK_FRESHNESS_SLA_HOURS[slug]
        desk_summary[slug] = {
            "storyCount": len(stories),
            "newestAgeMinutes": newest_age,
            "freshnessSlaHours": sla_hours,
            "fresh": newest_age is not None and newest_age <= sla_hours * 60,
            "qualityErrorCount": quality_errors,
            "semanticCopyErrorCount": semantic_errors,
            "staleCrossDeskFootballCount": stale_cross_desk_football,
            "hardRoutingErrorCount": routing_errors,
            "newestFirstErrorCount": newest_first_errors,
        }
        if not stories:
            add(findings, "DESK_EMPTY", "critical", slug, f"{slug} has no Rolling Desk stories", "collection")
        elif quality_errors and not semantic_errors:
            add(findings, "ARTICLE_SHAPE_INVALID", "warning", slug,
                f"{quality_errors} story/stories fail basic article-shape checks")
        if newest_age is not None and newest_age > sla_hours * 60:
            add(findings, "DESK_EDITORIAL_GAP", "critical", slug,
                f"newest parseable story is {newest_age/60:.1f} hours old (SLA {sla_hours}h); repair with a genuine current story, not timestamp refresh",
                "collection")

    live_semantic_errors = 0
    for story in live.get("items") or []:
        if not isinstance(story, dict):
            continue
        semantic = semantic_copy_errors(story)
        if semantic:
            live_semantic_errors += 1
            sid = str(story.get("id") or story.get("title") or "live-story")
            for reason in semantic:
                add(findings, "SEMANTIC_COPY_CORRUPTION", "critical", "live",
                    f"story {sid}: {reason}", None)

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

    # Public rendered outcome is authoritative. Repository updates, Discord alerts,
    # or started workflows do not equal publication success.
    pages_age = age_minutes((pages or {}).get("checkedAt"), now) if pages else None
    if pages is None or pages_age is None or pages_age > 30:
        add(findings, "PUBLIC_PROBE_STALE", "critical", "pages",
            "public Pages probe is missing or older than 30 minutes", "pages")
    else:
        if not bool(pages.get("infrastructureMatch", pages.get("runtimeMatch", pages.get("match")))):
            add(findings, "PUBLIC_INFRASTRUCTURE_MISMATCH", "critical", "pages",
                "public site differs from repository or a core page/runtime check failed", "pages")
        for field, code, label in (
            ("liveMatch", "PUBLIC_LIVE_NOT_PROPAGATED", "Live"),
            ("deskMatch", "PUBLIC_DESK_NOT_PROPAGATED", "Rolling Desk"),
            ("stockMatch", "PUBLIC_STOCK_NOT_PROPAGATED", "Stock"),
            ("voiceManifestMatch", "PUBLIC_VOICE_NOT_PROPAGATED", "Voice manifest"),
        ):
            if pages.get(field) is False:
                add(findings, code, "critical", "pages",
                    f"{label} repository state has not propagated to the public rendered site", "pages")
        if pages.get("editorialFreshnessMatch") is False:
            add(findings, "PUBLIC_EDITORIAL_STALE", "warning", "pages",
                "public probe reports editorial freshness failure; root-cause freshness checks are evaluated separately")

    if tts.get("engine") != "typangaa/canto-tts-nano" or int(tts.get("availableArticleCount") or 0) <= 0:
        add(findings, "VOICE_ENGINE_INVALID", "critical", "voice", "Canto Nano manifest is missing/invalid", "voice")
    voice_age = age_minutes(tts.get("lastVoicePublishedAt") or tts.get("generatedAt"), now)
    live_dt = parse_iso(live.get("lastUpdated"))
    voice_dt = parse_iso(tts.get("generatedAt"))
    if live_dt and voice_dt and live_dt - voice_dt > timedelta(hours=2) and (voice_age is None or voice_age > 120):
        add(findings, "VOICE_BEHIND_CONTENT", "critical", "voice",
            "voice manifest is more than two hours behind current Live content", "voice")
    elif int(tts.get("pendingArticleCount") or 0) > 0:
        add(findings, "VOICE_PENDING", "info", "voice",
            f"{int(tts.get('pendingArticleCount') or 0)} article(s) remain pending; scheduled voice production owns the backlog")

    add(findings, "DISCORD_DELIVERY_OBSERVABILITY", "info", "discord",
        "Discord proves newsroom data changed, not that GitHub Pages deployed; public probe is the publication authority")
    if pages and pages.get("liveMatch") is False and live_age is not None and live_age <= 95:
        add(findings, "DISCORD_PUBLICATION_TRUTH_GAP", "warning", "discord",
            "new newsroom headlines may reach Discord before Pages; label them publication-pending until public probe confirms propagation")

    previous_codes: set[str] = set()
    if previous:
        previous_codes = {
            str(f.get("code")) for f in (previous.get("findings") or [])
            if isinstance(f, dict) and f.get("severity") == "critical"
        }
        persistent = [f for f in findings if f.severity == "critical" and f.repair and f.code in previous_codes]
        for f in persistent:
            add(findings, "PERSISTENT_" + f.code, "critical", f.area,
                f"{f.code} remains unresolved after the previous cycle; verify actual progress and treat an over-age active repair as STUCK",
                f.repair)

    repair_keys: list[str] = []
    for f in findings:
        if f.repair and f.repair not in repair_keys:
            repair_keys.append(f.repair)

    repair_plan = []
    for key in repair_keys:
        repair_plan.append({
            "area": key,
            "owner": RECOVERY_OWNERS.get(key),
            "workflow": REPAIR_WORKFLOWS.get(key),
            "todayFirst": key in {"daily", "collection", "live", "desk", "stock"},
        })

    critical = [f for f in findings if f.severity == "critical"]
    unresolved = [f for f in critical if not f.repair]
    warnings = [f for f in findings if f.severity == "warning"]
    persistent_count = sum(1 for f in critical if f.code.startswith("PERSISTENT_"))
    if unresolved:
        status = "EDITORIAL_ATTENTION_REQUIRED"
    elif persistent_count:
        status = "RECOVERY_ESCALATION_REQUIRED"
    elif repair_plan:
        status = "AUTO_REPAIRING"
    elif warnings:
        status = "HEALTHY_WITH_WARNINGS"
    else:
        status = "HEALTHY"

    return {
        "schemaVersion": 3,
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
            "semanticCopyeditingGate": True,
            "todayFirstRecovery": True,
            "historicalBacklogNonBlocking": True,
            "antiSnowball": True,
            "outcomeBasedRecovery": True,
            "publicRenderedOutcomeIsAuthority": True,
            "publisherOwnershipGuard": True,
            "stuckActiveRunEscalation": True,
            "discordAlertIsNotPublicationProof": True,
            "stockFailureMustNotMasqueradeAsWholeSiteSuccess": True,
        },
        "currentDay": {
            "expectedDate": today,
            "dailyCurrent": current_daily,
            "recoveryMode": "TODAY_FIRST_NO_BACKFILL",
        },
        "summary": {
            "criticalCount": len(critical),
            "warningCount": len(warnings),
            "findingCount": len(findings),
            "repairActionCount": len(repair_plan),
            "repairWorkflowCount": sum(1 for x in repair_plan if x.get("workflow")),
            "unresolvedCriticalCount": len(unresolved),
            "persistentCriticalCount": persistent_count,
            "liveSemanticCopyErrorCount": live_semantic_errors,
        },
        "deskAudit": desk_summary,
        "freshness": {
            "liveAgeMinutes": live_age,
            "stockCheckAgeMinutes": stock_check_age,
            "stockContentAgeMinutes": stock_content_age,
            "pagesProbeAgeMinutes": pages_age,
            "voiceAgeMinutes": voice_age,
        },
        "repairPlan": repair_plan,
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