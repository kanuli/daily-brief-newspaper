"""Deterministic contract for the existing Scheduled Newsroom Publisher."""
import argparse
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
import hashlib
import json
from pathlib import Path
import re
from urllib.parse import urlsplit

from desk_freshness_policy import HKT, PUBLIC_DESK_FRESHNESS_HOURS, current_daily_dates, routed_slugs
from validate_daily_v3 import validate_sections, validate_story

LIVE_MODES = {"LIVE", "HOURLY_LIVE", "LIVE_INCREMENTAL", "LIVE_UPDATE"}
STORY_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,159}")
CONTRACT = "SCHEDULED_PUBLISHER_LIVE_V1"


def daily_payload_error(daily):
    """Validate a current Daily v3 edition with the existing public-copy rules."""
    try:
        if int(daily.get("contentVersion", 0) or 0) < 3 or int(daily.get("editorialStandardVersion", 0) or 0) < 3:
            return "current Daily requires v3 content and editorial evidence"
        validate_sections(daily, "Daily")
        for index, article in enumerate(daily["articles"]):
            validate_story(article, f"Daily articles[{index}]")
        ids = {article["id"] for article in daily["articles"]}
        top = daily.get("topFive")
        if daily.get("leadId") not in ids or not isinstance(top, list) or any(item not in ids for item in top):
            return "current Daily requires a valid leadId and topFive"
    except (KeyError, OverflowError, TypeError, ValueError) as exc:
        return str(exc)
    return None


def is_scheduled(live):
    items = live.get("items")
    return live.get("publicationContract") == CONTRACT or (isinstance(items, list) and any(
        isinstance(item, dict) and str(item.get("id", "")).startswith("publisher-") for item in items))


def stamp(value):
    if not isinstance(value, str):
        raise ValueError("timezone-aware timestamp required")
    result = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if result.utcoffset() is None:
        raise ValueError("timezone-aware timestamp required")
    return result


def time_label(verified_at):
    """Format the instant at which the publisher actually verified the source."""
    return stamp(verified_at).astimezone(ZoneInfo("Asia/Hong_Kong")).strftime("%m月%d日 %H:%M HKT核實")


def web_source(url):
    if not isinstance(url, str) or any(c.isspace() for c in url):
        return False
    try:
        parts = urlsplit(url)
        return (parts.scheme == "https" and bool(parts.hostname)
                and parts.username is None and parts.password is None
                and parts.path not in {"", "/"})
    except ValueError:
        return False


def article_error(item, edition_at):
    if not isinstance(item, dict) or not isinstance(item.get("id"), str) or not STORY_ID.fullmatch(item["id"]):
        return "invalid article id"
    routes = routed_slugs(item)
    if not routes or item.get("desk") != routes[0] or item.get("deskSlugs") != routes:
        return "invalid editorial route"
    if not all(isinstance(item.get(k), str) and item[k].strip() for k in ("section", "sectionLabel")):
        return "missing section labels"
    if item.get("status") not in {"NEW", "UPDATED", "DEVELOPING"}:
        return "invalid story status"
    sources = item.get("sources")
    if not web_source(item.get("sourceUrl")) or not isinstance(sources, list) or not sources:
        return "missing direct source evidence"
    if not any(isinstance(s, dict) and s.get("name") == item.get("sourceName")
               and s.get("url") == item["sourceUrl"] and web_source(s.get("url")) for s in sources):
        return "primary source not linked to evidence"
    try:
        published, verified = stamp(item.get("publishedAt")), stamp(item.get("verifiedAt"))
    except ValueError:
        return "invalid source or verification timestamp"
    if not published <= verified <= edition_at:
        return "source/verification/edition timestamps out of order"
    limit = min(PUBLIC_DESK_FRESHNESS_HOURS[slug] for slug in routes)
    if edition_at - published > timedelta(hours=limit):
        return "source older than the routed Desk freshness limit"
    if item.get("timeLabel") and item["timeLabel"] != time_label(item["verifiedAt"]):
        return "timeLabel does not match verifiedAt in HKT"
    return ""


def publisher_errors(live, *, now=None):
    """Validate raw Live before it is eligible for merge or a Publisher commit."""
    from merge_live_into_desk import live_item_rejection_reason
    now = now or datetime.now(timezone.utc)
    if not isinstance(live, dict):
        return ["Live snapshot must be an object"]
    try:
        edition = stamp(live.get("lastUpdated"))
    except ValueError:
        return ["invalid Live lastUpdated"]
    if edition > now:
        return ["future Live lastUpdated"]
    local = edition.astimezone(HKT)
    dates = {local.date().isoformat()}
    if local.hour == 0:
        dates.add((local.date() - timedelta(days=1)).isoformat())
    if live.get("date") not in dates or str(live.get("mode", "")).upper() not in LIVE_MODES:
        return ["invalid Live mode or HKT edition date"]
    for key in ("lastUpdatedLabel", "nextUpdateLabel", "windowLabel"):
        if not isinstance(live.get(key), str) or not live[key].strip():
            return [f"missing {key}"]
    items = live.get("items")
    if not isinstance(items, list) or not items:
        return ["Live items must be a non-empty array"]
    errors = []
    ids = set()
    for index, item in enumerate(items):
        label_missing = isinstance(item, dict) and (
            not isinstance(item.get("timeLabel"), str) or not item["timeLabel"].strip())
        if label_missing:
            errors.append(f"items[{index}]: missing timeLabel")
        error = article_error(item, edition) or live_item_rejection_reason(item)
        if error == "missing timeLabel" and label_missing:
            continue
        if error:
            errors.append(f"items[{index}]: {error}")
        elif item["id"] in ids:
            errors.append(f"items[{index}]: duplicate id")
        else:
            ids.add(item["id"])
    if errors:
        return errors
    counts = [live.get(k) for k in ("newCount", "updatedCount", "developingCount")]
    if (any(type(n) is not int or n < 0 for n in counts) or sum(counts[:2]) != len(items)
            or counts[0] < sum(i["status"] == "NEW" for i in items)
            or counts[1] < sum(i["status"] == "UPDATED" for i in items)
            or counts[2] != sum(i["status"] == "DEVELOPING" for i in items)):
        errors.append("Live counters contradict items")
    if not isinstance(live.get("leadId"), str) or live["leadId"] not in ids:
        errors.append("leadId must identify an accepted article")
    return errors


def require_publisher_live(live, *, now=None):
    errors = publisher_errors(live, now=now)
    if errors:
        raise SystemExit("SCHEDULED_LIVE_CONTRACT_HOLD " + "; ".join(errors))


def desk_freshness_errors(desks, *, now=None):
    """Require real, non-future newsroom evidence for each Desk freshness gate."""
    now = now or datetime.now(timezone.utc)
    errors = []
    for slug, maximum in PUBLIC_DESK_FRESHNESS_HOURS.items():
        stamps = []
        for row in desks.get(slug, []):
            if not isinstance(row, dict) or not web_source(row.get("sourceUrl")):
                continue
            # A date encoded in a legacy identifier can guide retention, but
            # it does not substantiate a source timestamp for readiness.
            try:
                stamps.append(stamp(row["publishedAt"]))
            except (KeyError, ValueError):
                continue
        if any(stamp is not None and stamp > now for stamp in stamps):
            errors.append(f"Desk {slug} contains a future article timestamp")
        eligible = [stamp for stamp in stamps if stamp is not None and stamp <= now]
        if not eligible or now - max(eligible) > timedelta(hours=maximum):
            errors.append(f"Desk {slug} is stale")
    return errors


def desk_checkpoint_errors(live, desk, *, now=None):
    """Check the generated checkpoint against the accepted Live articles."""
    from merge_live_into_desk import FLOORS, routing_integrity
    coverage = live.get("coverage")
    desks = desk.get("desks")
    if not isinstance(coverage, dict) or not isinstance(desks, dict):
        return ["missing coverage or Rolling Desk"]
    if desk.get("generatedAt") != live.get("lastUpdated") or desk.get("date") != live.get("date"):
        return ["Rolling Desk checkpoint does not match Live"]
    counts = coverage.get("deskLatestStoryCounts")
    if not isinstance(counts, dict) or set(counts) != set(FLOORS):
        return ["missing or unexpected Desk coverage counts"]
    for slug, floor in FLOORS.items():
        rows = desks.get(slug)
        if (not isinstance(rows, list) or len(rows) < floor
                or type(counts[slug]) is not int or counts[slug] != len(rows)
                or any(not isinstance(row, dict) or not isinstance(row.get("id"), str) for row in rows)
                or len({row["id"] for row in rows}) != len(rows)):
            return [f"Desk count, depth or identity mismatch: {slug}"]
    if not routing_integrity(desks):
        return ["Rolling Desk routing contradiction"]
    for item in live["items"]:
        for slug in routed_slugs(item):
            matching = next((row for row in desks[slug] if row["id"] == item["id"]), {})
            # Merge deliberately changes the per-Desk status to LATEST.
            if not matching or any(matching.get(key) != value for key, value in item.items() if key != "status"):
                return [f"Rolling Desk does not contain the accepted article {item['id']} in {slug}"]
    gates = ("publishingGateMet", "deskLatestDepthMet", "sourceGateMet", "copyGateMet",
             "routingGateMet", "geographicGateMet", "footballGateMet", "deskFreshnessMet")
    if (coverage.get("status") != "COMPLETE" or any(coverage.get(key) is not True for key in gates)
            or coverage.get("japanCountVerified") != counts["japan"]):
        return ["coverage hard gates contradict the acceptance contract"]
    return desk_freshness_errors(desks, now=now)


def merge_preflight(raw, commit, *, now=None):
    """Bind a non-mutating decision to the exact Live file read by Merge."""
    now = now or datetime.now(timezone.utc)
    receipt = {"schema": "ROLLING_DESK_LIVE_PREFLIGHT_V1", "sourceCommit": commit,
               "checkedAt": now.isoformat(), "liveSha256": hashlib.sha256(raw).hexdigest()}
    try:
        live = json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError):
        live = None
    errors = []
    if not isinstance(live, dict) or not isinstance(live.get("items"), list):
        errors.append("Live snapshot must be a JSON object with an items array")
    elif not is_scheduled(live):
        return dict(receipt, status="LEGACY_EXISTING_GATES", errors=[])
    else:
        errors.extend(publisher_errors(live, now=now))
        if not errors and live.get("date") not in current_daily_dates(now=now):
            errors.append("Live edition is outside the current HKT date window")
        if "coverage" in live and not isinstance(live["coverage"], dict):
            errors.append("coverage must be an object")
    return dict(receipt, status="HOLD" if errors else "PASS", errors=errors)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("candidate", type=Path)
    parser.add_argument("--merge-commit", metavar="SHA",
                        help="Check the current checkout before Rolling Desk changes")
    args = parser.parse_args()
    raw = args.candidate.read_bytes()
    if args.merge_commit is not None:
        if not re.fullmatch(r"[0-9a-f]{40}", args.merge_commit):
            parser.error("expected the exact GitHub checkout commit")
        receipt = merge_preflight(raw, args.merge_commit)
        print(json.dumps(receipt, ensure_ascii=True))
        return 1 if receipt["status"] == "HOLD" else 0
    live = json.loads(raw)
    if not isinstance(live, dict) or live.get("publicationContract") != CONTRACT:
        raise SystemExit("SCHEDULED_LIVE_CONTRACT_HOLD publicationContract must be " + CONTRACT)
    require_publisher_live(live)
    coverage = live.get("coverage", {})
    if not isinstance(coverage, dict) or coverage.get("status") == "COMPLETE" or any(
            coverage.get(key) for key in ("publishingGateMet", "deskLatestStoryCounts",
                                         "deskLatestDepthMet", "footballGateMet")):
        raise SystemExit("SCHEDULED_LIVE_CONTRACT_HOLD coverage must be calculated by Rolling Desk")
    print("SCHEDULED_LIVE_PRECHECK_PASS")


if __name__ == "__main__":
    raise SystemExit(main())
