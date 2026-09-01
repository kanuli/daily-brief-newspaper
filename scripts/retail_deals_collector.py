#!/usr/bin/env python3
"""Collect Hong Kong retail promotions only for Daily Brief.

Promotion-only contract:
- no product price catalogue
- no regular/current price fields
- no price history or comparison
- only promotion campaigns/notices plus source health

Source policy:
- DAISO Hong Kong Facebook and Kai Bo Facebook are primary social sources.
- Try Meta's public Page Plugin timeline first.
- If Meta does not expose public post text to the runner, use public web-search
  indexing as a fallback and preserve direct Facebook URLs whenever available.
- Kai Bo's corporate homepage is not treated as a live promotion source.
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
USER_AGENT = "DailyBriefRetailPromotions/3.3 (+https://github.com/kanuli/daily-brief-newspaper)"
MAX_PROMOTIONS = 60
MAX_OFFICIAL_PER_SOURCE = 12
MAX_DISCOVERY_PER_RETAILER = 6
MAX_FACEBOOK_PER_PAGE = 8

WELLCOME_WEEKLY = "https://www.wellcome.com.hk/en/d/UYotKNFg7BGJ.html"
AEON_PROMOS = "https://aeonstores.com.hk/promotion"
DAISO_FB = "https://www.facebook.com/daisohongkong/"
KAIBO_FB = "https://www.facebook.com/Kaibofoodsupermarket/"

OFFICIAL_SOURCES = [
    ("wellcome-promotions", "Wellcome 惠康", "Wellcome 官方推廣／本週廣告", WELLCOME_WEEKLY),
    ("aeon-promotions", "AEON / DAISO Japan", "AEON／DAISO 官方推廣", AEON_PROMOS),
]

FACEBOOK_SOURCES = [
    ("daiso-facebook", "DAISO Hong Kong", "DAISO Hong Kong Facebook", DAISO_FB, "daisohongkong"),
    ("kaibo-facebook", "Kai Bo 佳寶", "佳寶食品超級市場 Facebook", KAIBO_FB, "Kaibofoodsupermarket"),
]

DISCOVERY_QUERIES = [
    ("Wellcome 惠康", '惠康 (優惠 OR 推廣 OR 會員 OR 優惠券 OR 信用卡 OR 抽獎 OR 換購) when:7d'),
    ("DAISO Hong Kong", '(DAISO OR 大創) 香港 (優惠 OR 推廣 OR 會員 OR 感謝日 OR 換購) when:7d'),
    ("Kai Bo 佳寶", '"佳寶食品超級市場" (優惠 OR 推廣 OR 會員 OR 優惠券 OR 全場 OR 抽獎 OR 換購) when:7d'),
    ("PARKnSHOP 百佳", '(百佳 OR PARKnSHOP) (優惠 OR 推廣 OR 會員 OR 優惠券 OR 信用卡 OR 抽獎) when:7d'),
]

PROMO_TERMS = re.compile(
    r"優惠|推廣|本週廣告|折扣|\d\s*折|全場|會員|優惠券|coupon|promotion|campaign|offers?|"
    r"抽獎|幸運大抽獎|換購|贈送|送禮|買.+送|禮遇|信用卡|visa|mastercard|"
    r"感謝日|reward|rewards|開學|中秋|月餅|限時|期間限定|著數",
    re.I,
)
PRICEISH = re.compile(r"\$\s*\d|HK\$\s*\d|原價|優惠價|每件|/件|\d+(?:\.\d+)?\s*(?:KG|GM|G|ML|LT|L|PCS?|PK)\b", re.I)
NAV_JUNK = re.compile(r"^(home|首頁|登入|login|register|註冊|contact|聯絡|about|關於|store|分店|privacy|私隱|terms|條款|search|搜尋)$", re.I)
GENERIC_PROMO_TITLE = re.compile(r"^(推廣資訊|今期推廣|AEON會員卡|租戶優惠|AEON\s*推廣活動|會員尊享優惠|AEON\s*信用卡優惠|AEONCITY網購推廣)$", re.I)
FALSE_POSITIVE = re.compile(r"必逛|推介\s*\d+間|攻略|合集|懶人包|介紹|開箱|新品介紹", re.I)
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
    req = urllib.request.Request(url, headers={
        "User-Agent": USER_AGENT,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.7",
        "Accept-Language": "zh-HK,zh-Hant;q=0.9,en;q=0.7",
    })
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
                time.sleep(1.0)
    raise RuntimeError(str(last))


def source_record(source_id: str, retailer: str, label: str, url: str, status: str, checked: datetime, detail: str, mode: str = "promotion-only") -> dict[str, Any]:
    return {"id": source_id, "retailer": retailer, "label": label, "url": url, "mode": mode, "status": status, "checkedAt": iso(checked), "detail": detail}


def promotion_id(retailer: str, title: str, url: str) -> str:
    digest = hashlib.sha1(f"{retailer}|{normalized(title)}|{url}".encode("utf-8")).hexdigest()[:16]
    return f"promotion-{digest}"


def make_promotion(retailer: str, title: str, source_type: str, source_name: str, source_url: str, now: datetime, published: datetime | None = None, summary: str | None = None, restriction: str | None = None) -> dict[str, Any]:
    return {
        "id": promotion_id(retailer, title, source_url), "retailer": retailer, "title": clean(title),
        "summary": summary or "近期公開 Promotion；詳情以零售商最新公布為準。",
        "startDate": None, "endDate": None, "active": True,
        "restriction": restriction or "以零售商最新條款、指定分店／會員／付款方式要求為準。",
        "sourceType": source_type, "sourceName": source_name, "sourceUrl": source_url,
        "checkedAt": iso(now), "publishedAt": iso(published) if published else None, "discoveredAt": iso(now),
    }


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
        if NAV_JUNK.match(title) or GENERIC_PROMO_TITLE.match(title) or PRICEISH.search(title) or FALSE_POSITIVE.search(title) or not PROMO_TERMS.search(title):
            continue
        href_host = urllib.parse.urlparse(href).netloc.lower().removeprefix("www.")
        if href_host and source_host and not (href_host == source_host or href_host.endswith("." + source_host)):
            continue
        key = normalized(title)
        if not key or key in seen:
            continue
        seen.add(key)
        rows.append(make_promotion(retailer, title, "official-promotion", source_name, href, now, summary="零售商官方公開 Promotion；活動內容及條款請查看官方頁面。"))
        if len(rows) >= MAX_OFFICIAL_PER_SOURCE:
            break
    return rows


def collect_official(now: datetime) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    promotions: list[dict[str, Any]] = []
    sources: list[dict[str, Any]] = []
    for source_id, retailer, label, url in OFFICIAL_SOURCES:
        try:
            rows = official_promotions(retailer, label, url, fetch_text(url), now)
            promotions.extend(rows)
            status = "ok" if rows else "limited"
            detail = f"本輪辨識 {len(rows)} 個實際 Promotion；不收集商品價格。" if rows else "官方頁可讀取，但本輪未辨識到實際 Promotion。"
            sources.append(source_record(source_id, retailer, label, url, status, now, detail))
        except Exception as exc:
            sources.append(source_record(source_id, retailer, label, url, "error", now, f"本輪讀取失敗：{clean(exc)}。"))
    return promotions, sources


def facebook_plugin_url(page_url: str) -> str:
    return "https://www.facebook.com/plugins/page.php?" + urllib.parse.urlencode({
        "href": page_url, "tabs": "timeline", "width": "500", "height": "900",
        "small_header": "false", "adapt_container_width": "true", "hide_cover": "false", "show_facepile": "false",
    })


def facebook_plugin_promotions(retailer: str, label: str, page_url: str, handle: str, now: datetime) -> list[dict[str, Any]]:
    plugin = facebook_plugin_url(page_url)
    parser = PromotionLinkParser(plugin)
    parser.feed(fetch_text(plugin))
    rows: list[dict[str, Any]] = []
    seen: set[str] = set()
    for text, href in parser.rows:
        title = clean(text)
        if len(title) < 8 or len(title) > 300 or not PROMO_TERMS.search(title) or FALSE_POSITIVE.search(title):
            continue
        href = html.unescape(href)
        parsed = urllib.parse.urlparse(href)
        if "facebook.com" not in parsed.netloc.lower():
            continue
        # Plugin redirect links may URL-encode the real Facebook URL.
        qs = urllib.parse.parse_qs(parsed.query)
        for candidate_key in ("u", "href"):
            candidate = qs.get(candidate_key, [None])[0]
            if candidate and "facebook.com" in candidate:
                href = urllib.parse.unquote(candidate)
                parsed = urllib.parse.urlparse(href)
                break
        if handle.lower() not in (parsed.path or "").lower() and "/posts/" not in (parsed.path or "").lower() and "/permalink/" not in (parsed.path or "").lower():
            continue
        key = normalized(title)
        if not key or key in seen:
            continue
        seen.add(key)
        rows.append(make_promotion(
            retailer, title[:220], "facebook", label, href, now,
            summary="Facebook Page 公開 timeline Promotion。",
            restriction="以 Facebook Page 原貼文最新條款為準。",
        ))
        if len(rows) >= MAX_FACEBOOK_PER_PAGE:
            break
    return rows


def bing_rss_url(query: str) -> str:
    return "https://www.bing.com/search?" + urllib.parse.urlencode({"q": query, "format": "rss", "setlang": "zh-hant"})


def facebook_search_promotions(retailer: str, label: str, handle: str, now: datetime) -> list[dict[str, Any]]:
    query = f'site:facebook.com/{handle} (優惠 OR 推廣 OR 折扣 OR 會員 OR 抽獎 OR 換購 OR 感謝日)'
    root = ET.fromstring(fetch_text(bing_rss_url(query)))
    rows: list[dict[str, Any]] = []
    for item in root.findall(".//item")[:30]:
        title = clean(item.findtext("title")); link = clean(item.findtext("link")); description = clean(item.findtext("description"))
        if not title or not link or not PROMO_TERMS.search(f"{title} {description}") or FALSE_POSITIVE.search(title):
            continue
        parsed = urllib.parse.urlparse(link)
        if "facebook.com" not in parsed.netloc.lower() or f"/{handle.lower()}" not in (parsed.path or "").lower():
            continue
        published = parse_dt(item.findtext("pubDate"))
        if published and published < now - timedelta(days=21):
            continue
        rows.append(make_promotion(
            retailer, title, "facebook", label, link, now, published,
            summary="Facebook 公開 Promotion；由公開搜尋索引發現並連回原 Facebook。",
            restriction="以 Facebook Page 原貼文最新條款為準。",
        ))
        if len(rows) >= MAX_FACEBOOK_PER_PAGE:
            break
    return rows


def collect_facebook(now: datetime) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    promotions: list[dict[str, Any]] = []
    sources: list[dict[str, Any]] = []
    for source_id, retailer, label, page_url, handle in FACEBOOK_SOURCES:
        plugin_error = None
        try:
            rows = facebook_plugin_promotions(retailer, label, page_url, handle, now)
        except Exception as exc:
            rows = []; plugin_error = clean(exc)
        mode = "facebook-page-plugin"
        if not rows:
            try:
                rows = facebook_search_promotions(retailer, label, handle, now)
                mode = "facebook-search-fallback"
            except Exception as exc:
                if not plugin_error:
                    plugin_error = clean(exc)
        promotions.extend(rows)
        if rows:
            sources.append(source_record(source_id, retailer, label, page_url, "ok", now, f"Facebook 為主要 Promotion 來源；本輪取得 {len(rows)} 個公開 Promotion。", mode=mode))
        else:
            detail = "Facebook 為主要 Promotion 來源；Meta 本輪沒有向無登入 runner 提供可核實新貼文，搜尋 fallback 亦未找到。佳寶官網不會被當作最新 Promotion 來源。"
            if plugin_error:
                detail += f" 技術狀態：{plugin_error[:120]}"
            sources.append(source_record(source_id, retailer, label, page_url, "limited", now, detail, mode=mode))
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
    rows: list[dict[str, Any]] = []; failures = 0; today = now.astimezone(HKT).date()
    for retailer, query in DISCOVERY_QUERIES:
        kept = 0
        try:
            root = ET.fromstring(fetch_text(google_news_url(query)))
        except Exception:
            failures += 1; continue
        for item in root.findall(".//item")[:25]:
            title = clean(item.findtext("title")); link = clean(item.findtext("link"))
            if not title or not link or not PROMO_TERMS.search(title) or FALSE_POSITIVE.search(title):
                continue
            published = parse_dt(item.findtext("pubDate"))
            if published and published < now - timedelta(days=8):
                continue
            if not title_date_is_current(title, today):
                continue
            source_node = item.find("source")
            source_name = clean(source_node.text if source_node is not None else "") or "公開網上來源"
            clean_title = re.sub(r"\s+-\s+[^-]{2,80}$", "", title).strip()
            rows.append(make_promotion(
                retailer, clean_title, "secondary-discovery", source_name, link, now, published,
                summary="近期公開 Promotion 消息；詳情以零售商最新官方／Facebook 公布為準。",
                restriction="屬公開網上 Promotion 發現；未核實細節不會當作官方條款。",
            ))
            kept += 1
            if kept >= MAX_DISCOVERY_PER_RETAILER:
                break
    status = "ok" if failures == 0 else "limited" if failures < len(DISCOVERY_QUERIES) else "error"
    return rows, source_record("promotion-web-discovery", "多個零售商", "公開網頁／新聞 Promotion 補充", "https://news.google.com/", status, now, f"本輪保留 {len(rows)} 個近期 Promotion 補充線索；{failures} 個搜尋查詢失敗。")


def source_rank(source_type: str) -> int:
    return {"facebook": 3, "official-promotion": 2, "secondary-discovery": 1}.get(source_type, 0)


def dedupe(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    unique: dict[tuple[str, str], dict[str, Any]] = {}
    for row in rows:
        key = (clean(row.get("retailer")), normalized(str(row.get("title") or "")))
        if not key[0] or not key[1]:
            continue
        old = unique.get(key)
        if old is None or source_rank(str(row.get("sourceType"))) > source_rank(str(old.get("sourceType"))):
            unique[key] = row
    out = list(unique.values())
    out.sort(key=lambda x: str(x.get("publishedAt") or x.get("discoveredAt") or ""), reverse=True)
    return out[:MAX_PROMOTIONS]


def walk_forbidden(value: Any, path: str = "root") -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            if key in FORBIDDEN_PRICE_KEYS:
                raise SystemExit(f"FORBIDDEN_PRICE_FIELD {path}.{key}")
            walk_forbidden(child, f"{path}.{key}")
    elif isinstance(value, list):
        for idx, child in enumerate(value):
            walk_forbidden(child, f"{path}[{idx}]")


def build() -> dict[str, Any]:
    now = utcnow()
    official, official_sources = collect_official(now)
    facebook, facebook_sources = collect_facebook(now)
    discovered, discovery_source = discovery_promotions(now)
    promotions = dedupe(facebook + official + discovered)
    sources = facebook_sources + official_sources + [discovery_source]
    data = {
        "schemaVersion": 3, "collectorVersion": "3.3.0",
        "generatedAt": iso(now), "generatedAtHkt": now.astimezone(HKT).strftime("%Y-%m-%d %H:%M HKT"),
        "promotions": promotions, "sources": sources,
        "stats": {
            "activePromotions": len(promotions),
            "retailerCount": len({x.get("retailer") for x in promotions if x.get("retailer")}),
            "facebookPromotions": sum(1 for x in promotions if x.get("sourceType") == "facebook"),
            "healthySources": sum(1 for x in sources if x.get("status") == "ok"),
            "sourceCount": len(sources),
        },
    }
    walk_forbidden(data)
    return data


def validate(data: dict[str, Any]) -> None:
    if data.get("schemaVersion") != 3:
        raise SystemExit("retail promotion schemaVersion must be 3")
    if not isinstance(data.get("promotions"), list):
        raise SystemExit("promotions must be an array")
    if not isinstance(data.get("sources"), list) or not data["sources"]:
        raise SystemExit("sources must be a non-empty array")
    walk_forbidden(data)
    for promo in data["promotions"]:
        for key in ("id", "retailer", "title", "sourceUrl", "sourceType"):
            if not promo.get(key):
                raise SystemExit(f"promotion missing {key}")


def main() -> int:
    ap = argparse.ArgumentParser(); ap.add_argument("--output", default="data/retail-deals.json"); args = ap.parse_args()
    output = Path(args.output); output.parent.mkdir(parents=True, exist_ok=True)
    data = build(); validate(data)
    tmp = output.with_suffix(output.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"); tmp.replace(output)
    print("RETAIL_PROMOTIONS_OK", "promotions", data["stats"]["activePromotions"], "facebook", data["stats"]["facebookPromotions"], "retailers", data["stats"]["retailerCount"], "sources_ok", data["stats"]["healthySources"], "generated", data["generatedAt"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
