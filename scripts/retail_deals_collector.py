#!/usr/bin/env python3
"""Collect Hong Kong retail promotions only for Daily Brief.

Promotion-only contract:
- no product price catalogue
- no regular/current price fields
- no price history or comparison
- only promotion campaigns/notices plus source health
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
USER_AGENT = "DailyBriefRetailPromotions/3.0 (+https://github.com/kanuli/daily-brief-newspaper)"
MAX_PROMOTIONS = 60
MAX_OFFICIAL_PER_SOURCE = 12
MAX_DISCOVERY_PER_RETAILER = 6

WELLCOME_WEEKLY = "https://www.wellcome.com.hk/en/d/UYotKNFg7BGJ.html"
AEON_PROMOS = "https://aeonstores.com.hk/promotion"
KAIBO = "https://www.kaibo.com.hk/"

OFFICIAL_SOURCES = [
    ("wellcome-promotions", "Wellcome 惠康", "Wellcome 官方推廣／本週廣告", WELLCOME_WEEKLY),
    ("aeon-promotions", "AEON / DAISO Japan", "AEON／DAISO 官方推廣", AEON_PROMOS),
    ("kaibo-promotions", "Kai Bo 佳寶", "佳寶官方網站／會員資訊", KAIBO),
]

DISCOVERY_QUERIES = [
    ("Kai Bo 佳寶", '"佳寶食品超級市場" (優惠 OR 推廣 OR 會員 OR 優惠券 OR 全場 OR 抽獎 OR 換購) when:7d'),
    ("Wellcome 惠康", '惠康 (優惠 OR 推廣 OR 會員 OR 優惠券 OR 信用卡 OR 抽獎 OR 換購) when:7d'),
    ("DAISO Japan / AEON", '(DAISO OR 大創 OR AEON) 香港 (優惠 OR 推廣 OR 會員 OR 感謝日 OR 換購) when:7d'),
    ("PARKnSHOP 百佳", '(百佳 OR PARKnSHOP) (優惠 OR 推廣 OR 會員 OR 優惠券 OR 信用卡 OR 抽獎) when:7d'),
]

PROMO_TERMS = re.compile(
    r"優惠|推廣|推介|折扣|\d\s*折|全場|會員|優惠券|coupon|promotion|campaign|"
    r"抽獎|幸運大抽獎|換購|贈送|送禮|買.+送|禮遇|信用卡|visa|mastercard|"
    r"感謝日|reward|rewards|開學|中秋|月餅|限時|期間限定|著數",
    re.I,
)
PRICEISH = re.compile(r"\$\s*\d|HK\$\s*\d|原價|優惠價|每件|/件|\d+(?:\.\d+)?\s*(?:KG|GM|G|ML|LT|L|PCS?|PK)\b", re.I)
NAV_JUNK = re.compile(r"^(home|首頁|登入|login|register|註冊|contact|聯絡|about|關於|store|分店|privacy|私隱|terms|條款|search|搜尋)$", re.I)
TITLE_DAY_RE = re.compile(r"(?<!\d)(1[0-2]|[1-9])月([0-3]?\d)日")
FORBIDDEN_PRICE_KEYS = {"offers", "products", "currentPrice", "regularPrice", "priceHistory", "historicalLow", "historicalHigh", "previousObservedPrice", "changePct"}


class PromotionLinkParser(HTMLParser):
    def __init__(self, base_url: str) -> None:
        super().__init__(convert_charrefs=True)
        self.base_url = base_url
        self.current_href: str | None = None
        self.current_parts: list[str] = []
        self.rows: list[tuple[str, str]] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_map = {k.lower(): (v or "") for k, v in attrs}
        if tag.lower() == "a":
            self.current_href = urllib.parse.urljoin(self.base_url, attrs_map.get("href", ""))
            self.current_parts = []
        elif tag.lower() == "img" and self.current_href:
            alt = clean(attrs_map.get("alt") or attrs_map.get("title"))
            if alt:
                self.current_parts.append(alt)

    def handle_data(self, data: str) -> None:
        if self.current_href:
            text = clean(data)
            if text:
                self.current_parts.append(text)

    def handle_endtag(self, tag: str) -> None:
        if tag.lower() != "a" or not self.current_href:
            return
        text = clean(" ".join(self.current_parts))
        if text:
            self.rows.append((text, self.current_href))
        self.current_href = None
        self.current_parts = []


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def iso(dt: datetime) -> str:
    return dt.astimezone(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def clean(value: Any) -> str:
    return re.sub(r"\s+", " ", html.unescape(str(value or ""))).strip()


def normalized(value: str) -> str:
    text = clean(value).lower()
    text = re.sub(r"[^a-z0-9\u3400-\u9fff]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


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


def source_record(source_id: str, retailer: str, label: str, url: str, status: str, checked: datetime, detail: str) -> dict[str, Any]:
    return {
        "id": source_id,
        "retailer": retailer,
        "label": label,
        "url": url,
        "mode": "promotion-only",
        "status": status,
        "checkedAt": iso(checked),
        "detail": detail,
    }


def promotion_id(retailer: str, title: str, url: str) -> str:
    digest = hashlib.sha1(f"{retailer}|{normalized(title)}|{url}".encode("utf-8")).hexdigest()[:16]
    return f"promotion-{digest}"


def official_promotions(retailer: str, source_name: str, url: str, markup: str, now: datetime) -> list[dict[str, Any]]:
    parser = PromotionLinkParser(url)
    parser.feed(markup)
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    source_host = urllib.parse.urlparse(url).netloc.lower().removeprefix("www.")

    for title, href in parser.rows:
        title = clean(title)
        if len(title) < 4 or len(title) > 140:
            continue
        if NAV_JUNK.match(title) or PRICEISH.search(title) or not PROMO_TERMS.search(title):
            continue
        href_host = urllib.parse.urlparse(href).netloc.lower().removeprefix("www.")
        if href_host and source_host and not (href_host == source_host or href_host.endswith("." + source_host)):
            continue
        key = normalized(title)
        if not key or key in seen:
            continue
        seen.add(key)
        rows.append(
            {
                "id": promotion_id(retailer, title, href),
                "retailer": retailer,
                "title": title,
                "summary": "零售商官方公開推廣；活動內容及條款請查看官方頁面。",
                "startDate": None,
                "endDate": None,
                "active": True,
                "restriction": "以零售商官方最新條款、指定分店／會員／付款方式要求為準。",
                "sourceType": "official-promotion",
                "sourceName": source_name,
                "sourceUrl": href,
                "checkedAt": iso(now),
                "publishedAt": None,
                "discoveredAt": iso(now),
            }
        )
        if len(rows) >= MAX_OFFICIAL_PER_SOURCE:
            break
    return rows


def collect_official(now: datetime) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    promotions: list[dict[str, Any]] = []
    sources: list[dict[str, Any]] = []

    for source_id, retailer, label, url in OFFICIAL_SOURCES:
        try:
            markup = fetch_text(url)
            rows = official_promotions(retailer, label, url, markup, now)
            promotions.extend(rows)
            if rows:
                status = "ok"
                detail = f"本輪從官方公開頁辨識 {len(rows)} 個推廣活動；不收集商品價格。"
            else:
                status = "limited"
                detail = "官方頁可讀取，但本輪未辨識到可結構化的推廣活動；不會以商品價格代替。"
            sources.append(source_record(source_id, retailer, label, url, status, now, detail))
        except Exception as exc:
            sources.append(source_record(source_id, retailer, label, url, "error", now, f"本輪讀取失敗：{clean(exc)}。"))
    return promotions, sources


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


def discovery_promotions(now: datetime) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    failures = 0
    today = now.astimezone(HKT).date()

    for retailer, query in DISCOVERY_QUERIES:
        kept = 0
        try:
            root = ET.fromstring(fetch_text(google_news_url(query)))
        except Exception:
            failures += 1
            continue

        for item in root.findall(".//item")[:25]:
            title = clean(item.findtext("title"))
            link = clean(item.findtext("link"))
            if not title or not link or not PROMO_TERMS.search(title):
                continue
            published = parse_dt(item.findtext("pubDate"))
            if published and published < now - timedelta(days=8):
                continue
            if not title_date_is_current(title, today):
                continue
            source_node = item.find("source")
            source_name = clean(source_node.text if source_node is not None else "") or "公開網上來源"
            clean_title = re.sub(r"\s+-\s+[^-]{2,80}$", "", title).strip()
            rows.append(
                {
                    "id": promotion_id(retailer, clean_title, link),
                    "retailer": retailer,
                    "title": clean_title,
                    "summary": "近期公開優惠／推廣消息；詳情以零售商最新官方公布為準。",
                    "startDate": None,
                    "endDate": None,
                    "active": True,
                    "restriction": "屬公開網上推廣發現；未核實細節不會當作官方條款。",
                    "sourceType": "secondary-discovery",
                    "sourceName": source_name,
                    "sourceUrl": link,
                    "checkedAt": iso(now),
                    "publishedAt": iso(published) if published else None,
                    "discoveredAt": iso(now),
                }
            )
            kept += 1
            if kept >= MAX_DISCOVERY_PER_RETAILER:
                break

    health_status = "ok" if failures == 0 else "limited" if failures < len(DISCOVERY_QUERIES) else "error"
    health = source_record(
        "promotion-web-discovery",
        "多個零售商",
        "公開網頁／新聞／社交推廣發現",
        "https://news.google.com/",
        health_status,
        now,
        f"本輪保留 {len(rows)} 個近期 Promotion 線索；{failures} 個搜尋查詢失敗。",
    )
    return rows, health


def dedupe(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    unique: dict[tuple[str, str], dict[str, Any]] = {}
    for row in rows:
        key = (clean(row.get("retailer")), normalized(str(row.get("title") or "")))
        if not key[0] or not key[1]:
            continue
        old = unique.get(key)
        if old is None:
            unique[key] = row
            continue
        if old.get("sourceType") != "official-promotion" and row.get("sourceType") == "official-promotion":
            unique[key] = row
    out = list(unique.values())
    out.sort(key=lambda x: str(x.get("publishedAt") or x.get("discoveredAt") or x.get("checkedAt") or ""), reverse=True)
    return out[:MAX_PROMOTIONS]


def build() -> dict[str, Any]:
    now = utcnow()
    official, source_rows = collect_official(now)
    discovered, discovery_health = discovery_promotions(now)
    promotions = dedupe(official + discovered)
    sources = source_rows + [discovery_health]
    return {
        "schemaVersion": 3,
        "collectorVersion": "3.0.0",
        "generatedAt": iso(now),
        "generatedAtHkt": now.astimezone(HKT).strftime("%Y-%m-%d %H:%M HKT"),
        "promotions": promotions,
        "sources": sources,
        "stats": {
            "activePromotions": len(promotions),
            "retailerCount": len({str(x.get("retailer")) for x in promotions if x.get("retailer")}),
            "healthySources": sum(1 for x in sources if x.get("status") == "ok"),
            "sourceCount": len(sources),
        },
    }


def walk_forbidden(value: Any, path: str = "root") -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            if key in FORBIDDEN_PRICE_KEYS:
                raise SystemExit(f"promotion-only schema contains forbidden price key: {path}.{key}")
            walk_forbidden(child, f"{path}.{key}")
    elif isinstance(value, list):
        for i, child in enumerate(value):
            walk_forbidden(child, f"{path}[{i}]")


def validate(data: dict[str, Any]) -> None:
    if data.get("schemaVersion") != 3:
        raise SystemExit("retail schemaVersion must be 3")
    if not isinstance(data.get("promotions"), list) or not isinstance(data.get("sources"), list):
        raise SystemExit("promotion-only schema requires promotions and sources arrays")
    walk_forbidden(data)
    for promo in data["promotions"]:
        if not promo.get("id") or not promo.get("retailer") or not promo.get("title") or not promo.get("sourceUrl"):
            raise SystemExit("promotion identity/source missing")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--output", default="data/retail-deals.json")
    args = ap.parse_args()
    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    data = build()
    validate(data)
    tmp = output.with_suffix(output.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(output)
    print(
        "RETAIL_PROMOTIONS_OK",
        "promotions", data["stats"]["activePromotions"],
        "retailers", data["stats"]["retailerCount"],
        "sources_ok", data["stats"]["healthySources"],
        "generated", data["generatedAt"],
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
