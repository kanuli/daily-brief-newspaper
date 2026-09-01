#!/usr/bin/env python3
"""Collect current Hong Kong retail offers and promotions for Daily Brief.

This collector intentionally does not keep price history. It only publishes the
latest offer snapshot, current promotion discoveries, and source-health status.
"""

from __future__ import annotations

import argparse
import email.utils
import hashlib
import html
import json
import re
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import date, datetime, timedelta, timezone
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

HKT = timezone(timedelta(hours=8))
USER_AGENT = "DailyBriefRetailDeals/2.0 (+https://github.com/kanuli/daily-brief-newspaper)"
MAX_OFFERS = 300
MAX_DISCOVERY_PROMOS = 24
DISCOVERY_PER_RETAILER = 6

WELLCOME_HOME = "https://www.wellcome.com.hk/en"
WELLCOME_FRESH = "https://www.wellcome.com.hk/en/d/pH7gxW1LTK04bz.html"
WELLCOME_WEEKLY = "https://www.wellcome.com.hk/en/d/UYotKNFg7BGJ.html"
AEON_PROMOS = "https://aeonstores.com.hk/promotion"
KAIBO = "https://www.kaibo.com.hk/"

DISCOVERY_QUERIES = [
    ("Kai Bo 佳寶", '"佳寶食品超級市場" (優惠 OR 折 OR 減價 OR 推廣) when:7d'),
    ("Wellcome 惠康", '惠康 (優惠 OR 特價 OR 推廣) when:7d'),
    ("DAISO Japan / AEON", '(DAISO OR 大創 OR AEON) 香港 (優惠 OR 推廣 OR 折) when:7d'),
    ("PARKnSHOP 百佳", '(百佳 OR PARKnSHOP) (優惠 OR 特價 OR 推廣) when:7d'),
]
PROMO_TERMS = re.compile(r"優惠|特價|減價|折扣|\d\s*折|買.+送|贈|coupon|promo|promotion|discount|sale|會員|感謝日", re.I)
PRODUCT_UNIT_RE = re.compile(r"(?:\d+(?:\.\d+)?\s*(?:KG|GM|G|ML|LT|L|PC|PCS|PK|RL|EA|LB|OZ|CS))\b", re.I)
PRICE_TOKEN_RE = re.compile(r"^\$\s*([0-9][0-9,]*(?:\.[0-9]{1,2})?)$")
DECIMAL_TOKEN_RE = re.compile(r"^\.([0-9]{2})$")
TITLE_DAY_RE = re.compile(r"(?<!\d)(1[0-2]|[1-9])月([0-3]?\d)日")
RESTRICTED_PRODUCT_RE = re.compile(r"啤酒|紅酒|白酒|香檳|威士忌|清酒|梅酒|wine|beer|champagne|whisky|whiskey|vodka|sake", re.I)


class TextCollector(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        text = re.sub(r"\s+", " ", data).strip()
        if text:
            self.parts.append(text)


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def clean(value: Any) -> str:
    return re.sub(r"\s+", " ", html.unescape(str(value or ""))).strip()


def normalized_name(value: str) -> str:
    text = clean(value).lower()
    text = re.sub(r"[^a-z0-9\u3400-\u9fff]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def slug(value: str) -> str:
    text = normalized_name(value).replace(" ", "-")
    return (text[:100] if text else hashlib.sha1(value.encode("utf-8")).hexdigest()[:16])


def parse_dt(value: Any) -> datetime | None:
    if not value:
        return None
    text = str(value).strip()
    try:
        dt = email.utils.parsedate_to_datetime(text)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        pass
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).astimezone(timezone.utc)
    except Exception:
        return None


def parse_day(value: Any) -> date | None:
    if not value:
        return None
    try:
        return date.fromisoformat(str(value)[:10])
    except Exception:
        return None


def fetch_text(url: str, timeout: int = 20) -> str:
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": USER_AGENT,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.7",
            "Accept-Language": "zh-HK,zh-Hant;q=0.9,en;q=0.7",
        },
    )
    last: Exception | None = None
    for attempt in range(2):
        try:
            with urllib.request.urlopen(req, timeout=timeout) as response:
                raw = response.read()
                charset = response.headers.get_content_charset() or "utf-8"
                return raw.decode(charset, errors="replace")
        except Exception as exc:
            last = exc
            if attempt == 0:
                time.sleep(1.2)
    raise RuntimeError(str(last))


def visible_offers(markup: str, source_url: str, checked: datetime) -> list[dict[str, Any]]:
    parser = TextCollector()
    parser.feed(markup)
    parts = parser.parts
    offers: list[dict[str, Any]] = []
    seen: set[str] = set()

    def candidate(text: str) -> bool:
        if len(text) < 4 or len(text) > 180:
            return False
        if text.startswith(("電話", "電郵", "©", "關於", "條款")):
            return False
        return bool(PRODUCT_UNIT_RE.search(text)) and not bool(RESTRICTED_PRODUCT_RE.search(text))

    i = 0
    while i < len(parts):
        name = clean(parts[i])
        if not candidate(name):
            i += 1
            continue
        prices: list[float] = []
        hints: list[str] = []
        j = i + 1
        while j < len(parts) and j <= i + 8:
            token = clean(parts[j])
            if j > i + 1 and candidate(token):
                break
            match = PRICE_TOKEN_RE.match(token.replace(" ", ""))
            if match:
                value = float(match.group(1).replace(",", ""))
                if j + 1 < len(parts):
                    decimal = DECIMAL_TOKEN_RE.match(clean(parts[j + 1]))
                    if decimal and "." not in match.group(1):
                        value += int(decimal.group(1)) / 100
                        j += 1
                if 0 < value <= 50000:
                    prices.append(round(value, 2))
            elif re.search(r"新人價|頭\s*\d+\s*件|優惠|特價|原箱|Fresh Deal", token, re.I):
                hints.append(token[:60])
            j += 1

        if prices:
            current = prices[-1]
            regular = prices[0] if len(prices) >= 2 and prices[0] > current else None
            promo = " / ".join(dict.fromkeys(hints)) if hints else ("Fresh Deal" if source_url == WELLCOME_FRESH else ("網站優惠價" if regular else ""))
            is_offer = bool(promo) or (regular is not None and regular > current)
            key = normalized_name(name)
            if is_offer and key not in seen:
                seen.add(key)
                size_matches = list(PRODUCT_UNIT_RE.finditer(name))
                size = size_matches[-1].group(0).replace(" ", "") if size_matches else ""
                offers.append(
                    {
                        "id": "wellcome-" + slug(name),
                        "retailer": "Wellcome 惠康",
                        "name": name,
                        "size": size,
                        "currency": "HKD",
                        "currentPrice": current,
                        "regularPrice": regular,
                        "promoLabel": promo or "網站優惠價",
                        "sourceType": "official-products",
                        "sourceName": "Wellcome 惠康官方",
                        "sourceUrl": source_url,
                        "checkedAt": iso(checked),
                        "active": True,
                    }
                )
        i += 1
        if len(offers) >= MAX_OFFERS:
            break
    return offers


def dedupe_offers(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    unique: dict[tuple[str, str], dict[str, Any]] = {}
    for row in rows:
        key = (clean(row.get("retailer")), normalized_name(str(row.get("name") or "")))
        if not key[1]:
            continue
        old = unique.get(key)
        if old is None or (old.get("regularPrice") is None and row.get("regularPrice") is not None):
            unique[key] = row
    return sorted(unique.values(), key=lambda x: (clean(x.get("retailer")), clean(x.get("name"))))[:MAX_OFFERS]


def source_record(source_id: str, retailer: str, label: str, url: str, mode: str, status: str, checked: datetime, detail: str) -> dict[str, Any]:
    return {
        "id": source_id,
        "retailer": retailer,
        "label": label,
        "url": url,
        "mode": mode,
        "status": status,
        "checkedAt": iso(checked),
        "detail": detail,
    }


def collect_official(now: datetime) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    offers: list[dict[str, Any]] = []
    sources: list[dict[str, Any]] = []
    errors: list[str] = []

    for url in (WELLCOME_HOME, WELLCOME_FRESH):
        try:
            offers.extend(visible_offers(fetch_text(url), url, now))
        except Exception as exc:
            errors.append(f"{url}: {exc}")
    offers = dedupe_offers(offers)
    if offers:
        sources.append(source_record("wellcome-offers", "Wellcome 惠康", "官方最新優惠", WELLCOME_HOME, "official-offers", "ok", now, f"本輪從官方公開頁讀取 {len(offers)} 個目前優惠項目。"))
    else:
        detail = "本輪未能抽取優惠；不會以舊價格歷史作替代。" if errors else "官方頁本輪未提供可辨識優惠。"
        sources.append(source_record("wellcome-offers", "Wellcome 惠康", "官方最新優惠", WELLCOME_HOME, "official-offers", "limited", now, detail))

    for source_id, retailer, label, url, mode in [
        ("wellcome-promotions", "Wellcome 惠康", "官方推廣及每週廣告", WELLCOME_WEEKLY, "official-promotions"),
        ("aeon-promotions", "AEON / DAISO Japan", "AEON 官方推廣", AEON_PROMOS, "official-promotions"),
        ("kaibo-official", "Kai Bo 佳寶", "佳寶官方網站／會員 App", KAIBO, "official-site"),
    ]:
        try:
            body = fetch_text(url)
            text_len = len(re.sub(r"<[^>]+>", " ", body))
            status = "ok" if text_len > 300 else "limited"
            detail = "官方公開頁可正常讀取。" if status == "ok" else "官方頁可讀取，但公開優惠文字有限。"
            if source_id == "kaibo-official" and status == "ok":
                status = "limited"
                detail = "官方網站可連線；最新優惠同時配合公開搜尋發現。"
            sources.append(source_record(source_id, retailer, label, url, mode, status, now, detail))
        except Exception as exc:
            sources.append(source_record(source_id, retailer, label, url, mode, "error", now, f"本輪讀取失敗：{clean(exc)}。"))
    return offers, sources


def google_news_url(query: str) -> str:
    return "https://news.google.com/rss/search?" + urllib.parse.urlencode({"q": query, "hl": "zh-HK", "gl": "HK", "ceid": "HK:zh-Hant"})


def title_date_is_current(title: str, today: date) -> bool:
    matches = TITLE_DAY_RE.findall(title or "")
    if not matches:
        return True
    parsed: list[date] = []
    for month_text, day_text in matches:
        try:
            parsed.append(date(today.year, int(month_text), int(day_text)))
        except ValueError:
            pass
    return not parsed or max(parsed) >= today


def promotion_active(row: dict[str, Any], today: date, now: datetime) -> bool:
    start = parse_day(row.get("startDate"))
    end = parse_day(row.get("endDate"))
    if start and today < start:
        return False
    if end and today > end:
        return False
    if row.get("sourceType") == "secondary-discovery" and not start and not end:
        published = parse_dt(row.get("publishedAt")) or parse_dt(row.get("discoveredAt"))
        if published and published < now - timedelta(days=7):
            return False
        if not title_date_is_current(str(row.get("title") or ""), today):
            return False
    return True


def discovery_promotions(now: datetime) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    failures = 0
    for retailer, query in DISCOVERY_QUERIES:
        per_retailer = 0
        try:
            root = ET.fromstring(fetch_text(google_news_url(query)))
        except Exception:
            failures += 1
            continue
        for item in root.findall(".//item")[:20]:
            title = clean(item.findtext("title"))
            link = clean(item.findtext("link"))
            if not title or not link or not PROMO_TERMS.search(title):
                continue
            published = parse_dt(item.findtext("pubDate"))
            if published and published < now - timedelta(days=8):
                continue
            source_node = item.find("source")
            source_name = clean(source_node.text if source_node is not None else "") or "Google News indexed source"
            pid = "discovery-" + hashlib.sha1(f"{retailer}|{normalized_name(title)}".encode("utf-8")).hexdigest()[:16]
            row = {
                "id": pid,
                "retailer": retailer,
                "title": re.sub(r"\s+-\s+[^-]{2,80}$", "", title).strip(),
                "summary": "公開新聞／優惠搜尋新發現；詳情以原發布者及零售商最新公布為準。",
                "startDate": None,
                "endDate": None,
                "active": True,
                "restriction": "屬優惠發現線索；未核實細節不會當作官方條款。",
                "sourceType": "secondary-discovery",
                "sourceName": source_name,
                "sourceUrl": link,
                "discoveredAt": iso(now),
                "publishedAt": iso(published) if published else None,
            }
            if promotion_active(row, now.astimezone(HKT).date(), now):
                rows.append(row)
                per_retailer += 1
            if per_retailer >= DISCOVERY_PER_RETAILER:
                break
    dedup = {row["id"]: row for row in rows}
    status = "ok" if failures == 0 else "limited" if failures < len(DISCOVERY_QUERIES) else "error"
    health = source_record(
        "retail-promotion-discovery",
        "多個零售商",
        "網上最新優惠發現",
        "https://news.google.com/",
        "promotion-discovery",
        status,
        now,
        f"本輪保留 {len(dedup)} 個近期優惠發現線索；{failures} 個搜尋查詢失敗。",
    )
    return list(dedup.values())[:MAX_DISCOVERY_PROMOS], health


def load_existing(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def current_carried_promotions(existing: dict[str, Any], now: datetime) -> list[dict[str, Any]]:
    today = now.astimezone(HKT).date()
    rows: list[dict[str, Any]] = []
    for item in existing.get("promotions", []):
        if not isinstance(item, dict) or not item.get("id"):
            continue
        if item.get("sourceType") == "secondary-discovery":
            continue
        row = dict(item)
        row["active"] = promotion_active(row, today, now)
        if row["active"]:
            rows.append(row)
    return rows


def merge_promotions(carried: list[dict[str, Any]], discovered: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    for item in carried + discovered:
        if item.get("id"):
            rows[str(item["id"])] = item
    out = list(rows.values())
    out.sort(key=lambda x: (str(x.get("endDate") or "9999-12-31"), str(x.get("title") or "")))
    return out[:50]


def merge_sources(existing: dict[str, Any], fresh: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = {str(x.get("id")): dict(x) for x in existing.get("sources", []) if isinstance(x, dict) and x.get("id")}
    for item in fresh:
        rows[str(item["id"])] = item
    return list(rows.values())


def build(output: Path) -> dict[str, Any]:
    now = utcnow()
    existing = load_existing(output)
    offers, official_sources = collect_official(now)
    discovered, discovery_health = discovery_promotions(now)
    promotions = merge_promotions(current_carried_promotions(existing, now), discovered)
    sources = merge_sources(existing, official_sources + [discovery_health])
    active_promotions = [x for x in promotions if x.get("active") is not False]
    return {
        "schemaVersion": 2,
        "collectorVersion": "2.0.0",
        "generatedAt": iso(now),
        "generatedAtHkt": now.astimezone(HKT).strftime("%Y-%m-%d %H:%M HKT"),
        "offers": offers,
        "promotions": promotions,
        "sources": sources,
        "stats": {
            "latestDeals": len(offers) + len(active_promotions),
            "offerItems": len(offers),
            "activePromotions": len(active_promotions),
            "healthySources": sum(1 for x in sources if x.get("status") == "ok"),
            "sourceCount": len(sources),
        },
    }


def validate(data: dict[str, Any]) -> None:
    if data.get("schemaVersion") != 2:
        raise SystemExit("retail schemaVersion must be 2")
    for key in ("offers", "promotions", "sources"):
        if not isinstance(data.get(key), list):
            raise SystemExit(f"retail {key} must be an array")
    for offer in data["offers"]:
        if not offer.get("id") or not offer.get("retailer") or not offer.get("name") or not offer.get("sourceUrl"):
            raise SystemExit("retail offer identity/source missing")
        if not isinstance(offer.get("currentPrice"), (int, float)):
            raise SystemExit(f"retail offer price missing: {offer.get('id')}")
    for promo in data["promotions"]:
        if not promo.get("id") or not promo.get("retailer") or not promo.get("title") or not promo.get("sourceUrl"):
            raise SystemExit("retail promotion identity/source missing")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--output", default="data/retail-deals.json")
    args = ap.parse_args()
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    data = build(output)
    validate(data)
    tmp = output.with_suffix(output.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(output)
    print(
        "RETAIL_DEALS_OK",
        "offers", len(data["offers"]),
        "promotions", data["stats"]["activePromotions"],
        "sources_ok", data["stats"]["healthySources"],
        "generated", data["generatedAt"],
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
