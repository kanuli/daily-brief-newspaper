#!/usr/bin/env python3
"""Collect public Hong Kong retail prices and promotions for Daily Brief.

The collector is deliberately isolated from the newsroom pipelines. It uses only
public web pages / RSS discovery, preserves historical observations, and records
source health. Advertised reference-price discounts are NOT treated as observed
historical price changes.
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
from typing import Any, Iterable

HKT = timezone(timedelta(hours=8))
USER_AGENT = "DailyBriefRetailTracker/1.1 (+https://github.com/kanuli/daily-brief-newspaper)"
HISTORY_DAYS = 180
MAX_PRODUCTS = 180
MAX_DISCOVERY_PROMOS = 24
DISCOVERY_PER_RETAILER = 6

WELLCOME_HOME = "https://www.wellcome.com.hk/en"
WELLCOME_FRESH = "https://www.wellcome.com.hk/en/d/pH7gxW1LTK04bz.html"
WELLCOME_PROMOS = "https://www.wellcome.com.hk/d/KWlzJQUAj0kd.html"
WELLCOME_WEEKLY = "https://www.wellcome.com.hk/en/d/UYotKNFg7BGJ.html"
AEON_PROMOS = "https://aeonstores.com.hk/promotion"
AEON_DAISO = "https://www.aeon.com.hk/en/privilege/promotion_purplepremium.html"
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
SEED_ALIASES = {
    "wellcome-cherry-blossom-rice-8kg": ["櫻城牌日本品種珍珠米 8KG"],
    "wellcome-norway-salmon-480g": ["挪威 急凍三文魚柳4件裝 480GM"],
    "wellcome-meadows-mackerel-2pc": ["Meadows 挪威急凍鯖魚柳 2PC"],
    "wellcome-deqingyuan-white-eggs-10pc": ["DQY 德青源日本白蛋10隻裝 10PC"],
}


class TextCollector(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.jsonld: list[str] = []
        self._in_jsonld = False
        self._script_parts: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag.lower() == "script":
            attr = {k.lower(): (v or "") for k, v in attrs}
            if "ld+json" in attr.get("type", "").lower():
                self._in_jsonld = True
                self._script_parts = []

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() == "script" and self._in_jsonld:
            self.jsonld.append("".join(self._script_parts))
            self._script_parts = []
            self._in_jsonld = False

    def handle_data(self, data: str) -> None:
        if self._in_jsonld:
            self._script_parts.append(data)
        else:
            text = re.sub(r"\s+", " ", data).strip()
            if text:
                self.parts.append(text)

    def text(self) -> str:
        return "\n".join(self.parts)


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


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


def clean(value: Any) -> str:
    return re.sub(r"\s+", " ", html.unescape(str(value or ""))).strip()


def normalized_name(value: str) -> str:
    text = clean(value).lower()
    text = re.sub(r"[^a-z0-9\u3400-\u9fff]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def slug(value: str) -> str:
    text = normalized_name(value).replace(" ", "-")
    if text:
        return text[:100]
    return hashlib.sha1(value.encode("utf-8")).hexdigest()[:16]


def price_number(value: Any) -> float | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return round(float(value), 2)
    match = re.search(r"(?:HK\$|\$)?\s*([0-9]+(?:\.[0-9]{1,2})?)", clean(value).replace(",", ""))
    return round(float(match.group(1)), 2) if match else None


def walk_json(value: Any) -> Iterable[dict[str, Any]]:
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from walk_json(child)
    elif isinstance(value, list):
        for child in value:
            yield from walk_json(child)


def jsonld_products(markup: str, source_url: str, observed: datetime) -> list[dict[str, Any]]:
    parser = TextCollector()
    parser.feed(markup)
    products: list[dict[str, Any]] = []
    seen: set[str] = set()
    for block in parser.jsonld:
        try:
            root = json.loads(block)
        except Exception:
            continue
        for node in walk_json(root):
            node_type = node.get("@type")
            types = {str(x).lower() for x in (node_type if isinstance(node_type, list) else [node_type]) if x}
            if "product" not in types:
                continue
            name = clean(node.get("name"))
            if not name or len(name) < 3 or RESTRICTED_PRODUCT_RE.search(name):
                continue
            offers = node.get("offers")
            offer_nodes: list[dict[str, Any]] = []
            if isinstance(offers, dict):
                offer_nodes = [offers]
            elif isinstance(offers, list):
                offer_nodes = [x for x in offers if isinstance(x, dict)]
            price = None
            currency = "HKD"
            for offer in offer_nodes:
                price = price_number(offer.get("price") or offer.get("lowPrice") or offer.get("highPrice"))
                currency = clean(offer.get("priceCurrency")) or currency
                if price is not None:
                    break
            if price is None or price <= 0 or price > 50000:
                continue
            key = normalized_name(name)
            if key in seen:
                continue
            seen.add(key)
            products.append(
                {
                    "id": "wellcome-" + slug(name),
                    "retailer": "Wellcome 惠康",
                    "name": name,
                    "size": clean(node.get("size") or node.get("weight") or node.get("sku") or ""),
                    "currency": currency.upper() if len(currency) <= 5 else "HKD",
                    "currentPrice": price,
                    "regularPrice": None,
                    "promoLabel": "公開網店價格",
                    "sourceType": "official-products",
                    "sourceUrl": source_url,
                    "observedAt": iso(observed),
                }
            )
            if len(products) >= 100:
                return products
    return products


def visible_products(markup: str, source_url: str, observed: datetime) -> list[dict[str, Any]]:
    """Parse visible Wellcome product/price text when JSON-LD is unavailable.

    Wellcome commonly renders a product text node followed by one or two price
    nodes, with cents sometimes split into a separate `.90` text node. We only
    accept candidate names that contain a retail size/unit token and whose next
    few text nodes contain a dollar price. This intentionally favors precision.
    """
    parser = TextCollector()
    parser.feed(markup)
    parts = parser.parts
    products: list[dict[str, Any]] = []
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
            elif re.search(r"新人價|頭\s*\d+\s*件|優惠|特價|原箱", token, re.I):
                hints.append(token[:60])
            j += 1
        if prices:
            current = prices[-1]
            regular = prices[0] if len(prices) >= 2 and prices[0] > current else None
            key = normalized_name(name)
            if key not in seen:
                seen.add(key)
                size_matches = list(PRODUCT_UNIT_RE.finditer(name))
                size = size_matches[-1].group(0).replace(" ", "") if size_matches else ""
                promo = " / ".join(dict.fromkeys(hints)) if hints else ("網站優惠價" if regular else ("Fresh Deal" if source_url == WELLCOME_FRESH else "公開網店價格"))
                products.append(
                    {
                        "id": "wellcome-" + slug(name),
                        "retailer": "Wellcome 惠康",
                        "name": name,
                        "size": size,
                        "currency": "HKD",
                        "currentPrice": current,
                        "regularPrice": regular,
                        "promoLabel": promo,
                        "sourceType": "official-products",
                        "sourceUrl": source_url,
                        "observedAt": iso(observed),
                    }
                )
        i += 1
        if len(products) >= 120:
            break
    return products


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


def dedupe_observations(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    unique: dict[tuple[str, str], dict[str, Any]] = {}
    for row in rows:
        key = (clean(row.get("retailer")), normalized_name(str(row.get("name") or "")))
        if not key[1]:
            continue
        old = unique.get(key)
        if old is None or (old.get("regularPrice") is None and row.get("regularPrice") is not None):
            unique[key] = row
    return list(unique.values())


def collect_official(now: datetime) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    observed: list[dict[str, Any]] = []
    sources: list[dict[str, Any]] = []
    wellcome_errors: list[str] = []

    for url in (WELLCOME_HOME, WELLCOME_FRESH):
        try:
            markup = fetch_text(url)
            rows = jsonld_products(markup, url, now)
            if not rows:
                rows = visible_products(markup, url, now)
            observed.extend(rows)
        except Exception as exc:
            wellcome_errors.append(f"{url}: {exc}")
    observed = dedupe_observations(observed)
    if observed:
        sources.append(source_record("wellcome-products", "Wellcome 惠康", "官方網店價格", WELLCOME_HOME, "official-products", "ok", now, f"本輪直接從官方公開頁讀取 {len(observed)} 個商品價格。"))
    elif wellcome_errors:
        sources.append(source_record("wellcome-products", "Wellcome 惠康", "官方網店價格", WELLCOME_HOME, "official-products", "limited", now, "官方頁可用性／結構本輪未能抽取價格；保留上一輪資料，不會清空歷史。"))
    else:
        sources.append(source_record("wellcome-products", "Wellcome 惠康", "官方網店價格", WELLCOME_HOME, "official-products", "limited", now, "官方頁本輪未提供可辨識商品價格；保留上一輪資料。"))

    for source_id, retailer, label, url, mode in [
        ("wellcome-promotions", "Wellcome 惠康", "官方推廣及每週廣告", WELLCOME_WEEKLY, "official-promotions"),
        ("aeon-promotions", "AEON / DAISO Japan", "AEON 官方推廣", AEON_PROMOS, "official-promotions"),
        ("kaibo-official", "Kai Bo 佳寶", "佳寶官方網站／會員 App", KAIBO, "official-site"),
    ]:
        try:
            body = fetch_text(url)
            text_len = len(re.sub(r"<[^>]+>", " ", body))
            status = "ok" if text_len > 300 else "limited"
            detail = "官方公開頁可正常讀取。" if status == "ok" else "官方頁可讀取，但可抽取的公開文字／價格有限。"
            if source_id == "kaibo-official":
                status = "limited"
                detail = "官方網站可連線，但暫未提供與大型網店相同的結構化逐項價格；優惠會配合公開搜尋發現。"
            sources.append(source_record(source_id, retailer, label, url, mode, status, now, detail))
        except Exception as exc:
            sources.append(source_record(source_id, retailer, label, url, mode, "error", now, f"本輪讀取失敗：{clean(exc)}；保留舊資料。"))

    try:
        fetch_text(AEON_DAISO)
    except Exception:
        pass

    return observed[:MAX_PRODUCTS], sources


def google_news_url(query: str) -> str:
    return "https://news.google.com/rss/search?" + urllib.parse.urlencode({"q": query, "hl": "zh-HK", "gl": "HK", "ceid": "HK:zh-Hant"})


def discovery_promotions(now: datetime) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    failures = 0
    for retailer, query in DISCOVERY_QUERIES:
        per_retailer = 0
        try:
            payload = fetch_text(google_news_url(query))
            root = ET.fromstring(payload)
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
            rows.append(
                {
                    "id": pid,
                    "retailer": retailer,
                    "title": re.sub(r"\s+-\s+[^-]{2,80}$", "", title).strip(),
                    "summary": "公開新聞／優惠搜尋新發現；屬發現線索，優惠細節請以原發布者及零售商最新公布為準。",
                    "startDate": None,
                    "endDate": None,
                    "active": True,
                    "restriction": "尚未由結構化官方商品頁核實的細節不會當作實測價格。",
                    "sourceType": "secondary-discovery",
                    "sourceName": source_name,
                    "sourceUrl": link,
                    "discoveredAt": iso(now),
                    "publishedAt": iso(published) if published else None,
                }
            )
            per_retailer += 1
            if per_retailer >= DISCOVERY_PER_RETAILER:
                break
    dedup: dict[str, dict[str, Any]] = {row["id"]: row for row in rows}
    status = "ok" if failures == 0 else "limited" if failures < len(DISCOVERY_QUERIES) else "error"
    detail = f"本輪保留 {len(dedup)} 個近期優惠發現線索；{failures} 個搜尋查詢失敗。"
    health = source_record("retail-social-discovery", "多個零售商", "Facebook／網上優惠發現", "https://news.google.com/", "social-reference", status, now, detail)
    return list(dedup.values())[:MAX_DISCOVERY_PROMOS], health


def load_existing(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def aliases_for(row: dict[str, Any]) -> set[str]:
    values = {normalized_name(str(row.get("name") or ""))}
    for alias in SEED_ALIASES.get(str(row.get("id") or ""), []):
        values.add(normalized_name(alias))
    return {x for x in values if x}


def same_product(a: dict[str, Any], b: dict[str, Any]) -> bool:
    if clean(a.get("retailer")) != clean(b.get("retailer")):
        return False
    aa = aliases_for(a)
    bb = aliases_for(b)
    for an in aa:
        for bn in bb:
            if an == bn or (len(an) >= 8 and an in bn) or (len(bn) >= 8 and bn in an):
                return True
    return False


def history_values(history: list[dict[str, Any]]) -> list[float]:
    out: list[float] = []
    for item in history:
        value = price_number(item.get("price"))
        if value is not None:
            out.append(value)
    return out


def merge_products(existing: list[dict[str, Any]], observations: list[dict[str, Any]], now: datetime) -> list[dict[str, Any]]:
    existing = [dict(x) for x in existing if isinstance(x, dict)]
    matched: set[int] = set()
    result: list[dict[str, Any]] = []
    cutoff = now - timedelta(days=HISTORY_DAYS)

    for new in observations:
        old_index = next((i for i, old in enumerate(existing) if i not in matched and (old.get("id") == new.get("id") or same_product(old, new))), None)
        old = existing[old_index] if old_index is not None else {}
        if old_index is not None:
            matched.add(old_index)
        row = dict(old)
        row.update({k: v for k, v in new.items() if v is not None or k not in row})
        row["id"] = old.get("id") or new.get("id")
        row["firstSeenAt"] = old.get("firstSeenAt") or new.get("observedAt") or iso(now)
        row["lastSeenAt"] = new.get("observedAt") or iso(now)
        row["observedAt"] = new.get("observedAt") or iso(now)
        row["stale"] = False
        if new.get("regularPrice") is None and old.get("regularPrice") is not None and price_number(old.get("currentPrice")) == price_number(new.get("currentPrice")):
            row["regularPrice"] = old.get("regularPrice")
        if (not new.get("promoLabel") or new.get("promoLabel") == "公開網店價格") and old.get("promoLabel") and price_number(old.get("currentPrice")) == price_number(new.get("currentPrice")):
            row["promoLabel"] = old.get("promoLabel")

        history = [dict(x) for x in old.get("priceHistory", []) if isinstance(x, dict) and (parse_dt(x.get("observedAt")) or now) >= cutoff]
        current = price_number(row.get("currentPrice"))
        if current is not None:
            latest = history[-1] if history else None
            latest_time = parse_dt(latest.get("observedAt")) if latest else None
            latest_price = price_number(latest.get("price")) if latest else None
            should_append = latest is None or latest_price != current or (latest_time and latest_time.astimezone(HKT).date() != now.astimezone(HKT).date())
            if should_append:
                history.append({"observedAt": row["observedAt"], "price": current, "regularPrice": price_number(row.get("regularPrice"))})
        history = history[-HISTORY_DAYS:]
        row["priceHistory"] = history
        vals = history_values(history)
        row["historicalLow"] = min(vals) if vals else current
        row["historicalHigh"] = max(vals) if vals else current
        if len(vals) >= 2:
            previous = vals[-2]
            row["previousObservedPrice"] = previous
            row["changePct"] = round(((vals[-1] - previous) / previous) * 100, 2) if previous else None
        else:
            row["previousObservedPrice"] = None
            row["changePct"] = None
        result.append(row)

    for i, old in enumerate(existing):
        if i in matched:
            continue
        row = dict(old)
        row["stale"] = True
        result.append(row)

    result.sort(key=lambda x: (bool(x.get("stale")), clean(x.get("retailer")), clean(x.get("name"))))
    return result[:MAX_PRODUCTS]


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


def merge_promotions(existing: list[dict[str, Any]], discovered: list[dict[str, Any]], now: datetime) -> list[dict[str, Any]]:
    fresh_discovery_ids = {str(x.get("id")) for x in discovered if x.get("id")}
    rows: dict[str, dict[str, Any]] = {}
    for item in existing:
        if not isinstance(item, dict) or not item.get("id"):
            continue
        if item.get("sourceType") == "secondary-discovery" and str(item.get("id")) not in fresh_discovery_ids:
            continue
        rows[str(item["id"])] = dict(item)
    for item in discovered:
        if item.get("id"):
            old = rows.get(str(item["id"]), {})
            merged = dict(old)
            merged.update(item)
            merged["discoveredAt"] = old.get("discoveredAt") or item.get("discoveredAt") or iso(now)
            rows[str(item["id"])] = merged
    today = now.astimezone(HKT).date()
    out: list[dict[str, Any]] = []
    for row in rows.values():
        row["active"] = promotion_active(row, today, now)
        if row.get("sourceType") == "secondary-discovery" and row["active"] is False:
            continue
        out.append(row)
    out.sort(key=lambda x: (not bool(x.get("active")), str(x.get("endDate") or "9999-12-31"), str(x.get("title") or "")))
    return out[:50]


def merge_sources(existing: list[dict[str, Any]], fresh: list[dict[str, Any]]) -> list[dict[str, Any]]:
    rows = {str(x.get("id")): dict(x) for x in existing if isinstance(x, dict) and x.get("id")}
    for item in fresh:
        rows[str(item["id"])] = item
    return list(rows.values())


def build(output: Path) -> dict[str, Any]:
    now = utcnow()
    existing = load_existing(output)
    observed, official_sources = collect_official(now)
    discovered, discovery_health = discovery_promotions(now)
    products = merge_products(existing.get("products", []), observed, now)
    promotions = merge_promotions(existing.get("promotions", []), discovered, now)
    sources = merge_sources(existing.get("sources", []), official_sources + [discovery_health])
    data = {
        "schemaVersion": 1,
        "collectorVersion": "1.1.0",
        "generatedAt": iso(now),
        "generatedAtHkt": now.astimezone(HKT).strftime("%Y-%m-%d %H:%M HKT"),
        "products": products,
        "promotions": promotions,
        "sources": sources,
        "stats": {
            "trackedProducts": len(products),
            "activePromotions": sum(1 for x in promotions if x.get("active") is not False),
            "observedPriceDrops": sum(1 for x in products if isinstance(x.get("changePct"), (int, float)) and x.get("changePct") < 0),
            "healthySources": sum(1 for x in sources if x.get("status") == "ok"),
            "sourceCount": len(sources),
        },
    }
    return data


def validate(data: dict[str, Any]) -> None:
    if data.get("schemaVersion") != 1:
        raise SystemExit("retail schemaVersion must be 1")
    for key in ("products", "promotions", "sources"):
        if not isinstance(data.get(key), list):
            raise SystemExit(f"retail {key} must be an array")
    for p in data["products"]:
        if not p.get("id") or not p.get("retailer") or not p.get("name"):
            raise SystemExit("retail product identity missing")
        if price_number(p.get("currentPrice")) is None:
            raise SystemExit(f"retail product price missing: {p.get('id')}")
        if not p.get("sourceUrl"):
            raise SystemExit(f"retail product source missing: {p.get('id')}")
    for p in data["promotions"]:
        if not p.get("id") or not p.get("retailer") or not p.get("title") or not p.get("sourceUrl"):
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
        "RETAIL_TRACKER_OK",
        "products", len(data["products"]),
        "active_promotions", data["stats"]["activePromotions"],
        "sources_ok", data["stats"]["healthySources"],
        "generated", data["generatedAt"],
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
