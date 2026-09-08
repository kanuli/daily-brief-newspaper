#!/usr/bin/env python3
"""Build same-URL static fallbacks for the public newspaper.

The browser JavaScript remains the enhancement/freshness layer. This script
pre-renders the current verified publication into the existing HTML so a
GitHub Pages visitor does not see blank shells when JavaScript or a JSON fetch
is slow/blocked. Retail Promotions is intentionally built from the same
promotion-only JSON as its browser renderer so the no-JS page is also current.
"""
from __future__ import annotations

import html
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"

DESKS = [
    ("world", "世界", "world.html"),
    ("asia", "亞洲", "asia.html"),
    ("hong-kong", "香港", "hong-kong.html"),
    ("japan", "日本", "japan.html"),
    ("market-economy", "財經", "finance.html"),
    ("ai-tech", "AI / 科技", "technology.html"),
    ("manga-anime", "漫畫 / Anime", "manga-anime.html"),
    ("manchester-united", "Manchester United", "manchester-united.html"),
    ("football", "Football", "football.html"),
]


def load(name: str):
    return json.loads((DATA / name).read_text(encoding="utf-8"))


def esc(value) -> str:
    return html.escape(str(value or ""), quote=True)


def ensure_marker(text: str, label: str) -> str:
    marker = f'<meta name="daily-brief-prerender" content="current-publication" data-page="{esc(label)}">'
    if re.search(r'<meta\s+name=["\']daily-brief-prerender["\'][^>]*>', text, flags=re.I):
        return re.sub(r'<meta\s+name=["\']daily-brief-prerender["\'][^>]*>', marker, text, count=1, flags=re.I)
    return re.sub(r'</head>', marker + '\n</head>', text, count=1, flags=re.I)


def replace_element(text: str, tag: str, element_id: str, inner: str) -> str:
    opener = re.compile(rf'<{tag}\b(?=[^>]*\bid=["\']{re.escape(element_id)}["\'])[^>]*>', re.I)
    matches = list(opener.finditer(text))
    if len(matches) != 1:
        raise RuntimeError(f"missing or duplicate {tag}#{element_id}")
    opening = matches[0]
    token_re = re.compile(rf'</?{tag}\b[^>]*>', re.I)
    depth = 1
    closing = None
    for token in token_re.finditer(text, opening.end()):
        raw = token.group(0).lstrip()
        if raw.startswith("</"):
            depth -= 1
            if depth == 0:
                closing = token
                break
        elif not raw.rstrip().endswith("/>"):
            depth += 1
    if closing is None:
        raise RuntimeError(f"unclosed {tag}#{element_id}")
    return text[:opening.end()] + inner + text[closing.start():]


def replace_text(text: str, tag: str, element_id: str, value) -> str:
    return replace_element(text, tag, element_id, esc(value))


def source_link(story: dict) -> str:
    url = story.get("sourceUrl") or story.get("url") or "#"
    name = story.get("sourceName") or "原文"
    return f'<a class="source-link" href="{esc(url)}" target="_blank" rel="noopener noreferrer">{esc(name)} ↗</a>'


def render_story_card(story: dict, feature: bool = False) -> str:
    cls = "story-card feature" if feature else "story-card"
    return (
        f'<article class="{cls}"><div class="tag">{esc(story.get("deskLabel") or story.get("label") or story.get("desk"))}</div>'
        f'<h3>{esc(story.get("title"))}</h3><p>{esc(story.get("summary") or story.get("dek") or story.get("body"))}</p>'
        f'<p class="why-mini"><strong>為何重要：</strong>{esc(story.get("why") or story.get("whyItMatters"))}</p>'
        f'{source_link(story)}</article>'
    )


def render_lead(latest: dict) -> str:
    articles = {a.get("id"): a for a in latest.get("articles", []) if isinstance(a, dict)}
    story = articles.get(latest.get("leadId")) or next(iter(articles.values()), {})
    if not story:
        return '<p>今日頭條暫時未能顯示。</p>'
    return (
        f'<div class="eyebrow">{esc(story.get("deskLabel") or story.get("desk"))}</div>'
        f'<h2>{esc(story.get("title"))}</h2><p class="lead-deck">{esc(story.get("summary") or story.get("dek"))}</p>'
        f'<p class="story-meta">{esc(story.get("timeLabel") or story.get("publishedAt"))}</p>'
        f'<div class="story-body"><p>{esc(story.get("body"))}</p></div>'
        f'<div class="why-box"><strong>為何重要：</strong> {esc(story.get("why") or story.get("whyItMatters"))}</div>{source_link(story)}'
    )


def render_top_five(latest: dict) -> str:
    articles = {a.get("id"): a for a in latest.get("articles", []) if isinstance(a, dict)}
    ids = latest.get("topFiveIds") or latest.get("topFive") or []
    rows = []
    for story_id in ids[:5]:
        story = articles.get(story_id)
        if story:
            rows.append('<article class="top-card"><div>' + f'<h3>{esc(story.get("title"))}</h3><p>{esc(story.get("summary") or story.get("dek"))}</p>{source_link(story)}</div></article>')
    return "".join(rows)


def render_live_summary(live: dict) -> str:
    items = live.get("items") or []
    if not items:
        return '<div class="live-loading">目前沒有新增 Live 卡片；08:00 Daily Edition 仍然有效。</div>'
    cards = "".join(
        f'<article class="live-summary-card"><div class="tag">{esc(item.get("deskLabel") or item.get("desk"))}</div>'
        f'<h3>{esc(item.get("title"))}</h3><p>{esc(item.get("summary") or item.get("dek"))}</p>{source_link(item)}</article>'
        for item in items[:6]
    )
    return f'<div class="section-heading"><h2>Live Update</h2><span>{esc(live.get("windowLabel") or live.get("lastUpdatedLabel"))}</span></div><div class="story-grid">{cards}</div>'


def render_desk_latest(desk: dict) -> str:
    rows = []
    for slug, title, _ in DESKS:
        stories = (desk.get("desks") or {}).get(slug) or []
        if stories:
            story = stories[0]
            rows.append(f'<article class="story-card"><div class="tag">{esc(title)}</div><h3>{esc(story.get("title"))}</h3><p>{esc(story.get("summary") or story.get("dek"))}</p>{source_link(story)}</article>')
    return '<div class="section-heading"><h2>各版最新</h2><span>DESK LATEST</span></div><div class="story-grid">' + "".join(rows) + '</div>'


def render_daily_sections(latest: dict) -> str:
    articles = {a.get("id"): a for a in latest.get("articles", []) if isinstance(a, dict)}
    groups = []
    for section in latest.get("sections", []):
        if not isinstance(section, dict):
            continue
        stories = [articles.get(i) for i in section.get("articleIds", [])]
        stories = [s for s in stories if s]
        if stories:
            groups.append('<section class="section-block">' + f'<div class="section-heading"><h2>{esc(section.get("title"))}</h2><span>{esc(section.get("label") or section.get("subtitle"))}</span></div><div class="story-grid">' + "".join(render_story_card(s, i == 0 and len(stories) > 3) for i, s in enumerate(stories)) + '</div></section>')
    return "".join(groups)


def render_live_page(live: dict):
    items = live.get("items") or []
    stats = f'<div><strong>{len(items)}</strong><span>本輪 Live</span></div><div><strong>{esc(live.get("windowLabel") or live.get("lastUpdatedLabel"))}</strong><span>更新時段</span></div><div><strong>{esc(live.get("nextUpdateLabel"))}</strong><span>下一輪</span></div>'
    audit = f'<p><strong>Publication mode：</strong>{esc(live.get("mode"))} · 最後更新 {esc(live.get("lastUpdatedLabel") or live.get("lastUpdated"))}</p>'
    stories = '<p class="notice">目前沒有新增 Live 卡片；Daily Edition / 各版最新仍然保留。</p>' if not items else "".join(f'<article class="live-card"><div class="tag">{esc(item.get("deskLabel") or item.get("desk"))}</div><h2>{esc(item.get("title"))}</h2><p>{esc(item.get("summary") or item.get("dek"))}</p>{source_link(item)}</article>' for item in items)
    return stats, audit, stories


def stock_freshness(data: dict) -> str:
    status = str(data.get("collectionStatus") or "").upper()
    discovered = int(data.get("discoveredThisCheck") or 0)
    reservoir = int(data.get("discoveryCandidateCount") or 0)
    if status == "COLLECTION_FAILURE":
        return '<p class="notice"><strong>⚠️ Stock News 搜集失敗：</strong>最近一次檢查沒有取得 fresh candidate。現有稿件仍保留為最近已核實內容。</p>'
    if status == "INCOMPLETE":
        return f'<p class="notice"><strong>⚠️ Stock News 搜集未達完整度：</strong>本輪找到 {discovered} 則 fresh discovery candidate，但未達 breadth floor。</p>'
    depth = f'；rolling candidate reservoir {reservoir} 則' if reservoir else ''
    return f'<p class="notice"><strong>Newsroom freshness：</strong>本輪已完成搜集{esc(depth)}。頁頂「最後檢查」代表掃描時間；「最近已核實內容更新」只有在真正有新材料通過核實時才會改變。</p>'


def render_stock_source(story: dict) -> str:
    sources = story.get("sources") or []
    if not sources and story.get("sourceUrl"):
        sources = [{"name": story.get("sourceName") or "原文", "url": story.get("sourceUrl")}]
    links = " · ".join(f'<a href="{esc(s.get("url"))}" target="_blank" rel="noopener noreferrer">{esc(s.get("name") or "原文")} ↗</a>' for s in sources if isinstance(s, dict) and s.get("url"))
    return f'<div class="stock-sources"><strong>核實來源：</strong> {links}</div>' if links else ""


def render_stock_story(story: dict, index: int) -> str:
    paras = [p.strip() for p in re.split(r'\n\s*\n', str(story.get("body") or "")) if p.strip()]
    impact = story.get("impact") or "↔"
    cls = "stock-impact-up" if impact == "↑" else "stock-impact-down" if impact == "↓" else "stock-impact-neutral"
    return (
        f'<article class="stock-story {"featured" if index == 0 else ""}"><div class="tag"><span class="stock-impact {cls}">{esc(impact)} {esc(story.get("impactLabel") or "READ-THROUGH")}</span>{esc(story.get("storyType") or "LATEST")}</div>'
        f'<h2>{esc(story.get("title"))}</h2>' + (f'<p class="stock-story-dek">{esc(story.get("dek"))}</p>' if story.get("dek") else "") + (f'<p class="stock-summary"><strong>摘要：</strong>{esc(story.get("summary"))}</p>' if story.get("summary") else "")
        + '<div class="stock-story-body">' + "".join(f'<p>{esc(p)}</p>' for p in paras) + '</div><div class="stock-info-grid stock-info-grid-three">'
        + f'<div class="stock-info-card"><strong>背景</strong><p>{esc(story.get("context"))}</p></div><div class="stock-info-card"><strong>為何重要</strong><p>{esc(story.get("why"))}</p></div><div class="stock-info-card"><strong>下一步</strong><p>{esc(story.get("watchNext"))}</p></div></div>'
        + f'<div class="stock-story-meta">{esc(story.get("timeLabel"))}{(" · " + esc(story.get("sourceName"))) if story.get("sourceName") else ""}</div>' + render_stock_source(story) + '</article>'
    )


def render_stocks(data: dict):
    order = data.get("tracked") or []
    nav = "".join(f'<a href="#stock-{esc(t.lower())}">{esc(t)}</a>' for t in order)
    sections = []
    for ticker in order:
        block = (data.get("tickers") or {}).get(ticker) or {}
        stories = block.get("stories") or []
        body = "".join(render_stock_story(s, i) for i, s in enumerate(stories)) if stories else '<div class="stock-empty">暫未有已核實的新稿；本節會保留最近有效新聞並在下一輪繼續檢查。</div>'
        sections.append(f'<section class="stock-section" id="stock-{esc(ticker.lower())}"><div class="stock-section-head"><div><div class="stock-symbol">{esc(ticker)}</div><div class="stock-name">{esc(block.get("name"))}</div></div><div class="stock-asset-type">{esc(block.get("assetType") or "SECURITY")}</div></div>{body}</section>')
    return nav, "".join(sections)


def render_topic(slug: str, desk: dict):
    stories = (desk.get("desks") or {}).get(slug) or []
    cards = "".join(render_story_card(s, i == 0) for i, s in enumerate(stories))
    return len(stories), cards or '<p class="notice">暫時未有可顯示內容。</p>'


def render_archive(data: dict) -> str:
    return "".join(f'<a class="archive-item" href="{esc(item.get("url") or item.get("href") or "#")}"><div class="archive-date">{esc(item.get("shortDate"))}</div><div><div class="archive-title">{esc(item.get("headline"))}</div><div class="archive-topics">{esc(" · ".join(item.get("topics") or []))}</div></div><div>閱讀 →</div></a>' for item in data.get("editions", []) if isinstance(item, dict))


def retail_promotions(data: dict) -> list[dict]:
    rows = []
    for item in data.get("promotions") or []:
        if not isinstance(item, dict) or item.get("active") is False:
            continue
        kind = str(item.get("sourceType") or "").lower()
        if not ("official" in kind or "social" in kind or "facebook" in kind):
            continue
        if not item.get("id") or not item.get("retailer") or not item.get("title"):
            continue
        row = dict(item)
        row["_timestamp"] = item.get("publishedAt") or item.get("discoveredAt") or item.get("checkedAt") or data.get("generatedAt") or ""
        rows.append(row)
    rows.sort(key=lambda x: str(x.get("_timestamp") or ""), reverse=True)
    return rows


def retail_source_label(kind: str) -> str:
    kind = str(kind or "").lower()
    if "official" in kind: return "OFFICIAL"
    if "facebook" in kind: return "FACEBOOK"
    if "social" in kind: return "SOCIAL"
    return "SOURCE"


def render_retail_promotions(data: dict) -> str:
    rows = retail_promotions(data)
    if not rows:
        return '<p class="empty-retail">目前沒有已核實、仍有效的最新推廣。</p>'
    cards = []
    for p in rows:
        dates = f'活動日期：{esc(p.get("startDate") or "未註明")} – {esc(p.get("endDate") or "未註明")}' if (p.get("startDate") or p.get("endDate")) else f'發布／核實：{esc(p.get("_timestamp"))}'
        cards.append(
            '<article class="promo-card">'
            f'<div class="promo-top"><div class="promo-retailer">{esc(p.get("retailer"))}</div></div>'
            f'<div><span class="source-badge official">{esc(retail_source_label(p.get("sourceType")))}</span> <span class="source-badge official">PROMOTION</span></div>'
            f'<h3>{esc(p.get("title"))}</h3>'
            + (f'<p>{esc(p.get("summary"))}</p>' if p.get("summary") else "")
            + f'<div class="promo-validity">{dates}</div>'
            + (f'<div class="promo-restriction">條件／備註：{esc(p.get("restriction"))}</div>' if p.get("restriction") else "")
            + f'<div class="promo-source">{esc(p.get("sourceName"))}'
            + (f'<br><a class="source-link-retail" href="{esc(p.get("sourceUrl"))}" target="_blank" rel="noopener noreferrer">查看推廣來源 ↗</a>' if p.get("sourceUrl") else "")
            + '</div></article>'
        )
    return "".join(cards)


def render_retail_sources(data: dict) -> str:
    rows = data.get("sources") or []
    if not rows:
        return '<p class="empty-retail">未有來源健康資料。</p>'
    return "".join(
        f'<article class="source-health-card status-{esc(s.get("status") or "limited")}"><div class="status-line"><span class="status-dot"></span>{esc(str(s.get("status") or "limited").upper())} · {esc(s.get("retailer"))}</div><h3>{esc(s.get("label"))}</h3><p>{esc(s.get("detail"))}</p><p>最後檢查：{esc(s.get("checkedAt"))}</p>'
        + (f'<a class="source-link-retail" href="{esc(s.get("url"))}" target="_blank" rel="noopener noreferrer">來源 ↗</a>' if s.get("url") else "") + '</article>'
        for s in rows if isinstance(s, dict)
    )


def build_index(latest: dict, live: dict, desk: dict) -> None:
    path = ROOT / "index.html"
    text = ensure_marker(path.read_text(encoding="utf-8"), "index")
    text = re.sub(r'(<span\s+data-edition-date>).*?(</span>)', lambda m: m.group(1) + esc(latest.get("dateLabel") or latest.get("date")) + m.group(2), text, count=1, flags=re.S)
    text = re.sub(r'(<span\s+data-edition-number>).*?(</span>)', lambda m: m.group(1) + esc(latest.get("editionNumber") or "001") + m.group(2), text, count=1, flags=re.S)
    text = replace_element(text, "article", "lead-story", render_lead(latest))
    text = replace_element(text, "div", "top-five", render_top_five(latest))
    text = replace_element(text, "section", "live-summary", render_live_summary(live))
    text = replace_element(text, "section", "desk-latest-summary", render_desk_latest(desk))
    text = replace_element(text, "div", "dynamic-sections", render_daily_sections(latest))
    path.write_text(text, encoding="utf-8")


def build_live(live: dict) -> None:
    path = ROOT / "live.html"
    text = ensure_marker(path.read_text(encoding="utf-8"), "live")
    stats, audit, stories = render_live_page(live)
    text = replace_text(text, "span", "live-header-time", live.get("lastUpdatedLabel") or live.get("windowLabel") or "Live")
    text = replace_element(text, "div", "live-page-stats", stats)
    text = replace_element(text, "div", "live-audit", audit)
    text = replace_element(text, "section", "live-page-items", stories)
    path.write_text(text, encoding="utf-8")


def build_stock_page(stocks: dict) -> None:
    path = ROOT / "stocks.html"
    text = ensure_marker(path.read_text(encoding="utf-8"), "stocks")
    nav, sections = render_stocks(stocks)
    text = replace_element(text, "div", "stock-ticker-nav", nav)
    text = replace_text(text, "strong", "stock-updated", stocks.get("lastUpdatedLabel") or stocks.get("generatedAt") or "N/V")
    text = replace_element(text, "div", "stock-freshness", stock_freshness(stocks))
    text = replace_element(text, "div", "stock-sections", sections)
    path.write_text(text, encoding="utf-8")


def build_topics(desk: dict) -> None:
    generated = desk.get("generatedAt") or desk.get("date") or ""
    for slug, _, page in DESKS:
        path = ROOT / page
        text = ensure_marker(path.read_text(encoding="utf-8"), f"topic:{slug}")
        count, content = render_topic(slug, desk)
        text = replace_text(text, "span", "topic-date", generated)
        text = replace_text(text, "span", "topic-count", count)
        text = replace_element(text, "div", "topic-sections", content)
        path.write_text(text, encoding="utf-8")


def build_archive(archive: dict) -> None:
    path = ROOT / "archive.html"
    text = ensure_marker(path.read_text(encoding="utf-8"), "archive")
    rendered = render_archive(archive)
    if re.search(r'<div\b(?=[^>]*\bid=["\']archive-items["\'])', text, flags=re.I):
        text = replace_element(text, "div", "archive-items", rendered)
    else:
        text = replace_element(text, "div", "archive-list", rendered)
    path.write_text(text, encoding="utf-8")


def build_retail(retail: dict) -> None:
    path = ROOT / "retail-deals.html"
    text = ensure_marker(path.read_text(encoding="utf-8"), "retail-deals")
    rows = retail_promotions(retail)
    sources = retail.get("sources") or []
    retailers = {p.get("retailer") for p in rows if p.get("retailer")}
    healthy = sum(1 for s in sources if isinstance(s, dict) and s.get("status") == "ok")
    summary = (
        f'<div class="retail-stat"><strong>{len(rows)}</strong><span>已核實推廣</span></div>'
        f'<div class="retail-stat"><strong>{len(retailers)}</strong><span>涵蓋商店</span></div>'
        f'<div class="retail-stat"><strong>{healthy}/{len(sources)}</strong><span>來源正常</span></div>'
        f'<div class="retail-stat"><strong>2小時</strong><span>更新頻率</span></div>'
    )
    text = replace_text(text, "span", "retail-checked", f'最後資料更新：{retail.get("generatedAtHkt") or retail.get("generatedAt") or "未註明"}')
    text = replace_text(text, "span", "retail-generated", "資料範圍：已核實推廣活動（PROMOTION ONLY）")
    text = replace_element(text, "section", "retail-summary", summary)
    text = replace_text(text, "span", "promo-count", f'{len(rows)} VERIFIED PROMOTIONS')
    text = replace_element(text, "div", "promotion-list", render_retail_promotions(retail))
    text = replace_element(text, "div", "source-health", render_retail_sources(retail))
    path.write_text(text, encoding="utf-8")


def main() -> int:
    latest = load("latest.json")
    live = load("live.json")
    desk = load("desk-latest.json")
    stocks = load("stocks-latest.json")
    retail = load("retail-deals.json")
    archive = load("archive.json")
    build_index(latest, live, desk)
    build_live(live)
    build_topics(desk)
    build_stock_page(stocks)
    build_retail(retail)
    build_archive(archive)
    print("STATIC NEWS FALLBACK BUILD OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
