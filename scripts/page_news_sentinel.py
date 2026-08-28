#!/usr/bin/env python3
"""Public-page news sentinel for Daily Brief.

The sentinel complements the Editor-in-Chief supervisor by proving, page by
page, that a public HTML route is reachable and that the newsroom data feeding
that route is still within its editorial freshness SLA. Root HTML pages are
discovered automatically so a newly-added page cannot silently escape the
monitor.

The sentinel never fabricates news or rewrites timestamps. It emits targeted,
verification-gated repair workflows only.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from desk_freshness_policy import (  # noqa: E402
    EXPECTED_DESKS,
    PUBLIC_DESK_FRESHNESS_HOURS,
    current_daily_dates,
    newest_age_hours,
)

HKT = timezone(timedelta(hours=8))
KNOWN_ERROR_MARKERS = (
    "Error 500 (Server Error)",
    "That’s an error",
    "That's an error",
    "There was an error. Please try again later.",
)

REPAIR_WORKFLOWS = {
    "pages": "pages.yml",
    "collection": "rolling-news-search.yml",
    "desk": "merge-live-into-desk.yml",
    "live": "live-publication-maintenance.yml",
    "stock": "stock-publication-maintenance.yml",
}

NON_NEWS_PAGES = {"archive.html"}


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


def discover_pages(root: Path = ROOT) -> list[str]:
    """Discover all public root HTML routes, excluding edition snapshots."""
    return sorted(p.name for p in root.glob("*.html") if p.is_file())


def topic_slugs(html: str) -> list[str]:
    m = re.search(r'data-topic-slugs=["\']([^"\']+)["\']', html, re.I)
    if not m:
        return []
    raw = re.split(r"[\s,]+", m.group(1).strip())
    return [slug for slug in raw if slug]


def page_contract(page: str, html: str) -> dict[str, Any]:
    if page == "index.html":
        return {"kind": "daily", "slugs": []}
    if page == "live.html":
        return {"kind": "live", "slugs": []}
    if page == "stocks.html":
        return {"kind": "stock", "slugs": []}
    if page in NON_NEWS_PAGES:
        return {"kind": "utility", "slugs": []}
    slugs = topic_slugs(html)
    return {"kind": "topic", "slugs": slugs}


def _request_bytes(url: str, *, timeout: int = 15) -> tuple[int, str, bytes]:
    sep = "&" if "?" in url else "?"
    req = urllib.request.Request(
        url + sep + "sentinel=" + str(int(time.time() * 1000)),
        headers={
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
            "User-Agent": "daily-brief-page-news-sentinel",
        },
    )
    with urllib.request.urlopen(req, timeout=timeout) as response:
        return response.getcode(), response.headers.get_content_type(), response.read()


def _fetch_json(url: str, request: Callable[..., tuple[int, str, bytes]] = _request_bytes) -> dict[str, Any]:
    status, _, body = request(url)
    if status != 200:
        raise RuntimeError(f"{url} HTTP {status}")
    value = json.loads(body.decode("utf-8"))
    if not isinstance(value, dict):
        raise RuntimeError(f"{url} did not return a JSON object")
    return value


def _topic_health(slugs: list[str], desk: dict[str, Any], latest: dict[str, Any], now: datetime) -> tuple[bool, list[str], dict[str, Any]]:
    reasons: list[str] = []
    rows: dict[str, Any] = {}
    desks = desk.get("desks") if isinstance(desk.get("desks"), dict) else {}

    latest_date = str(latest.get("date") or "")
    daily_current = latest_date in current_daily_dates(now=now)
    daily_articles = latest.get("articles") if isinstance(latest.get("articles"), list) else []

    for slug in slugs:
        if slug not in EXPECTED_DESKS:
            reasons.append(f"unknown topic slug: {slug}")
            rows[slug] = {"fresh": False, "reason": "unknown-slug"}
            continue
        stories = desks.get(slug) if isinstance(desks.get(slug), list) else []
        age = newest_age_hours(stories, now=now)
        limit = PUBLIC_DESK_FRESHNESS_HOURS[slug]
        fresh = age is not None and age <= limit

        required_ids: list[str] = []
        if daily_current:
            for article in daily_articles:
                if not isinstance(article, dict):
                    continue
                routes = article.get("deskSlugs")
                if isinstance(routes, list) and slug in {str(x) for x in routes}:
                    aid = str(article.get("id") or "").strip()
                    if aid:
                        required_ids.append(aid)
                elif not routes and str(article.get("desk") or "").strip() == slug:
                    aid = str(article.get("id") or "").strip()
                    if aid:
                        required_ids.append(aid)
        ids = {str(story.get("id") or "").strip() for story in stories if isinstance(story, dict)}
        missing_daily = [aid for aid in required_ids if aid not in ids]
        if not stories:
            reasons.append(f"{slug}: desk empty")
        elif not fresh:
            reasons.append(f"{slug}: newest news age {age!r}h exceeds {limit}h SLA")
        if missing_daily:
            reasons.append(f"{slug}: current Daily article(s) missing from public desk: {', '.join(missing_daily)}")
        rows[slug] = {
            "storyCount": len(stories),
            "newestAgeHours": age,
            "freshnessSlaHours": limit,
            "fresh": fresh,
            "missingCurrentDailyArticleIds": missing_daily,
            "dailySynced": not missing_daily,
        }
    return not reasons, reasons, rows


def _daily_health(latest: dict[str, Any], now: datetime) -> tuple[bool, list[str], dict[str, Any]]:
    current = str(latest.get("date") or "") in current_daily_dates(now=now)
    return current, ([] if current else [f"Daily edition date {latest.get('date')} is outside the current handover window"]), {"date": latest.get("date")}


def _live_health(live: dict[str, Any], now: datetime) -> tuple[bool, list[str], dict[str, Any]]:
    hkt = now.astimezone(HKT)
    hour, minute = hkt.hour, hkt.minute
    age = age_minutes(live.get("lastUpdated"), now)
    active = hour == 0 or 6 <= hour <= 7 or 9 <= hour <= 23
    if hour == 6 and minute < 20:
        return True, [], {"ageMinutes": age, "grace": "06:00-startup"}
    limit = 155 if hour == 9 and minute < 20 else 95
    ok = True if not active else bool(age is not None and age <= limit and (live.get("items") or []))
    reasons = [] if ok else [f"Live publication age/items failed: age={age} min limit={limit} min"]
    return ok, reasons, {"ageMinutes": age, "limitMinutes": limit, "itemCount": len(live.get("items") or [])}


def _stock_health(stocks: dict[str, Any], now: datetime) -> tuple[bool, list[str], dict[str, Any]]:
    hkt = now.astimezone(HKT)
    hour, minute = hkt.hour, hkt.minute
    check_age = age_minutes(stocks.get("lastCheckedAt") or stocks.get("generatedAt"), now)
    content_age = age_minutes(stocks.get("generatedAt"), now)
    active = hour == 0 or 6 <= hour <= 23
    if hour == 6 and minute < 15:
        active = False
    check_ok = True if not active else bool(
        check_age is not None and check_age <= 95 and str(stocks.get("collectionStatus") or "").upper() == "COMPLETE"
    )
    pool_ok = bool(content_age is not None and content_age <= 36 * 60)
    reasons = []
    if not check_ok:
        reasons.append(f"Stock check stale/incomplete: age={check_age} min status={stocks.get('collectionStatus')}")
    if not pool_ok:
        reasons.append(f"Stock verified content pool is stale: age={content_age} min")
    return check_ok and pool_ok, reasons, {
        "checkAgeMinutes": check_age,
        "contentAgeMinutes": content_age,
        "collectionStatus": stocks.get("collectionStatus"),
    }


def audit_public_site(
    *,
    public_base: str,
    pages: list[str],
    local_html: dict[str, str],
    now: datetime,
    previous: dict[str, Any] | None = None,
    request: Callable[..., tuple[int, str, bytes]] = _request_bytes,
) -> dict[str, Any]:
    base = public_base.rstrip("/") + "/"
    data_base = base + "data/"
    remote_latest = _fetch_json(data_base + "latest.json", request)
    remote_live = _fetch_json(data_base + "live.json", request)
    remote_desk = _fetch_json(data_base + "desk-latest.json", request)
    remote_stocks = _fetch_json(data_base + "stocks-latest.json", request)

    prior_failures = set()
    for row in (previous or {}).get("pageResults") or []:
        if isinstance(row, dict) and not row.get("ok"):
            prior_failures.add(str(row.get("page") or ""))

    results: list[dict[str, Any]] = []
    repairs: list[str] = []
    persistent: list[str] = []

    def add_repair(key: str) -> None:
        workflow = REPAIR_WORKFLOWS[key]
        if workflow not in repairs:
            repairs.append(workflow)

    for page in pages:
        reasons: list[str] = []
        http_status = None
        try:
            status, content_type, body = request(base + page)
            http_status = status
            remote_html = body.decode("utf-8", "replace")
            marker = next((m for m in KNOWN_ERROR_MARKERS if m in remote_html), None)
            if status != 200 or "<html" not in remote_html.lower() or marker:
                reasons.append(f"public page failed HTTP/HTML check: status={status} marker={marker}")
                add_repair("pages")
        except Exception as exc:
            content_type = None
            reasons.append(f"public page request failed: {exc}")
            add_repair("pages")

        contract = page_contract(page, local_html.get(page, ""))
        kind = contract["kind"]
        detail: dict[str, Any] = {}
        data_ok = True
        if not reasons:
            if kind == "daily":
                data_ok, data_reasons, detail = _daily_health(remote_latest, now)
                if not data_ok:
                    add_repair("collection")
            elif kind == "live":
                data_ok, data_reasons, detail = _live_health(remote_live, now)
                if not data_ok:
                    add_repair("live")
            elif kind == "stock":
                data_ok, data_reasons, detail = _stock_health(remote_stocks, now)
                if not data_ok:
                    add_repair("stock")
            elif kind == "topic":
                if not contract["slugs"]:
                    data_ok = False
                    data_reasons = ["topic page has no data-topic-slugs contract"]
                    detail = {}
                    add_repair("pages")
                else:
                    data_ok, data_reasons, detail = _topic_health(contract["slugs"], remote_desk, remote_latest, now)
                    if not data_ok:
                        add_repair("collection")
                        add_repair("desk")
            else:
                data_reasons = []
            reasons.extend(data_reasons)

        ok = not reasons and data_ok
        if not ok and page in prior_failures:
            persistent.append(page)
        results.append({
            "page": page,
            "kind": kind,
            "topicSlugs": contract["slugs"],
            "ok": ok,
            "httpStatus": http_status,
            "contentType": content_type,
            "reasons": reasons,
            "detail": detail,
        })

    failed = [r for r in results if not r["ok"]]
    if persistent:
        status = "EDITORIAL_ATTENTION_REQUIRED"
    elif failed:
        status = "AUTO_REPAIRING"
    else:
        status = "HEALTHY"

    return {
        "schemaVersion": 1,
        "role": "Page News Sentinel",
        "checkedAt": now.astimezone(timezone.utc).isoformat(),
        "checkedAtHKT": now.astimezone(HKT).isoformat(),
        "publicBaseUrl": base,
        "status": status,
        "discoveredPageCount": len(pages),
        "healthyPageCount": len(results) - len(failed),
        "failedPageCount": len(failed),
        "persistentFailedPages": persistent,
        "repairWorkflows": repairs,
        "policy": {
            "autoDiscoverRootHtmlPages": True,
            "requireFreshNewsNotOnlyHttp200": True,
            "fabricateNews": False,
            "fakeFreshness": False,
        },
        "pageResults": results,
    }


def load_previous(path: str | None) -> dict[str, Any] | None:
    if not path:
        return None
    p = Path(path)
    if not p.is_file():
        return None
    value = json.loads(p.read_text(encoding="utf-8"))
    return value if isinstance(value, dict) else None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--public-base", required=True)
    ap.add_argument("--previous-status")
    ap.add_argument("--output", default="/tmp/page-news-sentinel-status.json")
    ap.add_argument("--now", help="ISO timestamp, test-only")
    args = ap.parse_args()

    now = parse_iso(args.now) if args.now else datetime.now(timezone.utc)
    if now is None:
        raise SystemExit("invalid --now")
    pages = discover_pages(ROOT)
    local_html = {page: (ROOT / page).read_text(encoding="utf-8") for page in pages}
    result = audit_public_site(
        public_base=args.public_base,
        pages=pages,
        local_html=local_html,
        now=now,
        previous=load_previous(args.previous_status),
    )
    Path(args.output).write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result["status"] != "EDITORIAL_ATTENTION_REQUIRED" else 2


if __name__ == "__main__":
    raise SystemExit(main())
