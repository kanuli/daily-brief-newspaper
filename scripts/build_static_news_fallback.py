#!/usr/bin/env python3
"""Pre-render public news HTML for resilient first paint and no-JS readers.

The JSON files remain the newsroom source of truth.  This build step runs only
inside the GitHub Pages deployment workspace and fills the existing loading
containers with the exact snapshot being deployed.  Client-side JavaScript can
then refresh/replace the same containers normally.

This gives crawlers, link previews, slow connections and partially broken JS a
real readable newspaper instead of a page made entirely of ``載入中…`` shells.
"""
from __future__ import annotations

import html
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
PRERENDER_VERSION = "20260827-v1"

DESKS = [
    ("world", "世界", "world.html"),
    ("asia", "亞洲", "asia.html"),
    ("hong-kong", "香港", "hong-kong.html"),
    ("japan", "日本", "japan.html"),
    ("market-economy", "財經 / 全球市場", "finance.html"),
    ("ai-tech", "AI / 科技", "technology.html"),
    ("manga-anime", "漫畫 / Anime", "manga-anime.html"),
    ("manchester-united", "Manchester United", "manchester-united.html"),
    ("football", "Football", "football.html"),
]

TOPIC_PAGE_TO_SLUG = {page: slug for slug, _, page in DESKS}


def load(name: str) -> dict:
    return json.loads((DATA / name).read_text(encoding="utf-8"))


def esc(value="") -> str:
    return html.escape(str(value or ""), quote=True)


def marker(page: str) -> str:
    return (
        f'<meta name="daily-brief-prerender" content="{PRERENDER_VERSION}">\n'
        f'<meta name="daily-brief-prerender-page" content="{esc(page)}">'
    )


def ensure_marker(text: str, page: str) -> str:
    if 'name="daily-brief-prerender"' in text:
        return text
    return text.replace("</head>", f"  {marker(page)}\n</head>", 1)


def replace_element(text: str, tag: str, element_id: str, inner: str) -> str:
    pattern = re.compile(
        rf'(<{tag}\b[^>]*\bid=["\']{re.escape(element_id)}["\'][^>]*>).*?(</{tag}>)',
        re.I | re.S,
    )
    new, count = pattern.subn(lambda m: m.group(1) + inner + m.group(2), text, count=1)
    if count != 1:
        raise RuntimeError(f"could not replace <{tag} id={element_id}> exactly once")
    return new


def replace_text_by_id(text: str, tag: str, element_id: str, value: str) -> str:
    return replace_element(text, tag, element_id, esc(value))


def sources(story: dict) -> list[dict]:
    raw = story.get("sources")
    if isinstance(raw, list) and raw:
        return [s for s in raw if isinstance(s, dict) and s.get("url")]
    if story.get("sourceUrl"):
        return [{"name": story.get("sourceName") or "原文", "url": story.get("sourceUrl")}]
    return []


def source_markup(story: dict, label: str = "核實來源：") -> str:
    items = sources(story)
    if not items:
        return ""
    links = " · ".join(
        f'<a class="source-link" href="{esc(item.get("url"))}" target="_blank" rel="noopener noreferrer">'
        f'{esc(item.get("name") or "原文")} ↗</a>'
        for item in items
    )
    return f'<div class="article-sources"><strong>{esc(label)}</strong> {links}</div>'


def paragraphs(value="") -> str:
    parts = [part.strip() for part in re.split(r"\n\s*\n", str(value or "")) if part.strip()]
    return "".join(f"<p>{esc(part)}</p>" for part in parts)


def article_map(data: dict) -> dict[str, dict]:
    return {
        str(article.get("id")): article
        for article in data.get("articles", [])
        if isinstance(article, dict) and article.get("id")
    }


def live_badge(status="UPDATED") -> str:
    safe = str(status or "UPDATED").upper()
    return f'<span class="live-badge live-{esc(safe.lower())}">{esc(safe)}</span>'


def render_lead(latest: dict) -> str:
    by_id = article_map(latest)
    story = by_id.get(str(latest.get("leadId")))
    if not story and by_id:
        story = next(iter(by_id.values()))
    if not story:
        return '<p class="notice">今日頭條資料暫不可用。</p>'
    return (
        f'<span class="eyebrow">{esc(story.get("section"))}｜今日頭條</span>'
        f'<h2>{esc(story.get("title"))}</h2>'
        f'<p class="lead-deck">{esc(story.get("dek"))}</p>'
        f'<div class="story-meta">{esc(story.get("timeLabel") or latest.get("dateLabel"))} · '
        f'{esc(story.get("sourceName"))}</div>'
        f'<div class="story-body"><p>{esc(story.get("summary"))}</p></div>'
        f'<div class="why-box"><strong>為何重要：</strong> {esc(story.get("why"))}</div>'
        f'{source_markup(story)}'
    )


def render_top_five(latest: dict) -> str:
    by_id = article_map(latest)
    ids = list(latest.get("topFive") or [])[:5]
    if not ids:
        ids = list(by_id)[:5]
    out = []
    for story_id in ids:
        story = by_id.get(str(story_id))
        if not story:
            continue
        out.append(
            '<article class="top-card"><div>'
            f'<h3>{esc(story.get("title"))}</h3>'
            f'<p>{esc(story.get("dek"))}</p>'
            '</div></article>'
        )
    return "".join(out)


def render_daily_sections(latest: dict) -> str:
    by_id = article_map(latest)
    sections = latest.get("sections") if isinstance(latest.get("sections"), list) else []
    out = []
    for section in sections:
        if not isinstance(section, dict):
            continue
        stories = [by_id.get(str(story_id)) for story_id in section.get("articleIds", [])]
        stories = [story for story in stories if story]
        if not stories:
            continue
        cards = []
        for index, story in enumerate(stories):
            cards.append(
                f'<article class="story-card {"feature" if index == 0 and len(stories) > 1 else ""}">'
                f'<div class="tag">{esc(story.get("section"))}</div>'
                f'<h3>{esc(story.get("title"))}</h3>'
                f'<p>{esc(story.get("summary"))}</p>'
                f'<p class="why-mini"><strong>為何重要：</strong> {esc(story.get("why"))}</p>'
                f'{source_markup(story)}'</n                '</article>'
            )
        out.append(
            f'<section class="section-block" id="{esc(section.get("slug"))}">'
            '<div class="section-heading">'
            f'<h2>{esc(section.get("title"))}</h2>'
            f'<span>{esc(section.get("subtitle") or f"{len(stories)} 則")}</span>'
            '</div><div class="story-grid">'
            + "".join(cards)
            + '</div></section>'
        )
    return "".join(out)


def render_live_summary(live: dict) -> str:
    items = [item for item in live.get("items", []) if isinstance(item, dict)][:4]
    cards = "".join(
        '<article class="live-mini-card">'
        f'<div>{live_badge(item.get("status"))} <span class="live-time">{esc(item.get("timeLabel"))}</span></div>'
        f'<h3>{esc(item.get("title"))}</h3><p>{esc(item.get("summary"))}</p>'
        '</article>'
        for item in items
    )
    if not cards:
        cards = '<p class="notice">本輪沒有需要新增的重大新聞；各版最新內容仍在下方保留。</p>'
    return (
        '<div class="live-summary-head"><div>'
        '<div class="live-kicker"><span class="live-dot"></span> LIVE UPDATE</div>'
        '<h2>今小時有甚麼變化</h2>'
        f'<p>Last updated {esc(live.get("lastUpdatedLabel") or "—")} · {esc(live.get("nextUpdateLabel"))}</p>'
        '</div><div class="live-counts">'
        f'<span><strong>{int(live.get("newCount") or 0)}</strong> NEW</span>'
        f'<span><strong>{int(live.get("updatedCount") or 0)}</strong> UPDATED</span>'
        f'<span><strong>{int(live.get("developingCount") or 0)}</strong> DEVELOPING</span>'
        '</div></div>'
        f'<div class="live-summary-grid">{cards}</div>'
        '<div class="live-more"><a href="live.html">查看完整 Live Update →</a></div>'
    )


def render_desk_latest(desk: dict) -> str:
    desks = desk.get("desks") if isinstance(desk.get("desks"), dict) else {}
    cards = []
    for slug, title, page in DESKS:
        stories = desks.get(slug) if isinstance(desks.get(slug), list) else []
        story = next((story for story in stories if isinstance(story, dict)), None)
        if not story:
            continue
        cards.append(
            '<article class="story-card desk-latest-card">'
            f'<div class="tag">{esc(title)} · LATEST</div>'
            f'<h3><a href="{esc(page)}">{esc(story.get("title"))}</a></h3>'
            f'<p>{esc(story.get("summary"))}</p>'
            f'<div class="story-meta">{esc(story.get("timeLabel"))}</div>'
            f'{source_markup(story)}'
            '</article>'
        )
    return (
        '<div class="section-heading"><h2>各版最新</h2>'
        f'<span>DESK LATEST · {esc(desk.get("generatedAt") or "")}</span></div>'
        '<p class="notice">Live 只顯示今小時真正有變化的新聞；這裡保留各新聞 Desk 目前最新的重要內容，避免把「沒有新增卡片」誤解成「沒有新聞」。</p>'
        '<div class="story-grid">' + "".join(cards) + '</div>'
    )


def render_live_page(live: dict) -> tuple[str, str, str]:
    items = [item for item in live.get("items", []) if isinstance(item, dict)]
    actual = {"NEW": 0, "UPDATED": 0, "DEVELOPING": 0}
    for item in items:
        status = str(item.get("status") or "").upper()
        if status in actual:
            actual[status] += 1
    stats = (
        f'<div><strong>{actual["NEW"]}</strong><span>NEW</span></div>'
        f'<div><strong>{actual["UPDATED"]}</strong><span>UPDATED</span></div>'
        f'<div><strong>{actual["DEVELOPING"]}</strong><span>DEVELOPING</span></div>'
        f'<p>{esc(live.get("nextUpdateLabel"))}</p>'
    )
    coverage = live.get("coverage") if isinstance(live.get("coverage"), dict) else {}
    raw = coverage.get("rawFreshCandidateCount")
    verified = coverage.get("verifiedCandidateCount")
    incremental = coverage.get("incrementalCandidateCount")
    if any(value is not None for value in (raw, verified, incremental)):
        audit = (
            '<strong>最新搜集：</strong>'
            f'raw {esc(raw if raw is not None else "N/V")} · '
            f'verified {esc(verified if verified is not None else "N/V")} · '
            f'incremental {esc(incremental if incremental is not None else "N/V")}'
        )
    else:
        audit = f'<strong>最新出版：</strong>{esc(live.get("lastUpdatedLabel") or live.get("windowLabel") or "已更新")}'
    stories = []
    for item in items:
        stories.append(
            '<article class="live-story live-story-rich">'
            '<div class="live-story-meta">'
            f'{live_badge(item.get("status"))} '
            f'<span>{esc(item.get("sectionLabel") or item.get("section") or item.get("desk") or "Live")}</span> '
            f'<span>{esc(item.get("timeLabel"))}</span></div>'
            f'<h2>{esc(item.get("title"))}</h2>'
            f'<p class="live-article-dek">{esc(item.get("dek"))}</p>'
            '<div class="live-article-body">'
            f'<p class="live-article-summary"><strong>摘要：</strong>{esc(item.get("summary"))}</p>'
            f'<div class="live-body-main">{paragraphs(item.get("body"))}</div>'
            f'<p class="live-article-context"><strong>背景：</strong>{esc(item.get("context") or item.get("background"))}</p>'
            f'<p class="live-article-why"><strong>為何重要：</strong>{esc(item.get("why") or item.get("whyImportant"))}</p>'
            f'<p class="live-article-next"><strong>下一步：</strong>{esc(item.get("watchNext") or item.get("nextStep"))}</p>'
            '</div>'
            f'{source_markup(item)}'
            '</article>'
        )
    if not stories:
        stories.append('<p class="notice">本輪沒有新增 Live 卡片；各分版仍保留最近已核實內容。</p>')
    return stats, audit, "".join(stories)


def render_topic_story(story: dict, featured: bool = False) -> str:
    return (
        f'<article class="topic-story {"topic-feature" if featured else ""}">'
        f'<div class="tag"><span class="topic-latest-badge">LATEST</span>{esc(story.get("section") or story.get("sectionLabel") or story.get("desk"))}</div>'
        f'<h2>{esc(story.get("title"))}</h2>'
        f'<p class="topic-dek">{esc(story.get("dek"))}</p>'
        '<div class="topic-article-body">'
        f'<p class="topic-summary"><strong>最新：</strong>{esc(story.get("summary"))}</p>'
        f'<div class="topic-full-body">{paragraphs(story.get("body"))}</div>'
        f'<p class="topic-context"><strong>背景：</strong>{esc(story.get("context") or story.get("background"))}</p>'
        f'<p class="why-mini"><strong>為何重要：</strong>{esc(story.get("why") or story.get("whyImportant"))}</p>'
        f'<p class="topic-next"><strong>下一步：</strong>{esc(story.get("watchNext") or story.get("nextStep"))}</p>'
        '</div>'
        f'<div class="story-meta">{esc(story.get("timeLabel"))} · {esc(story.get("sourceName"))}</div>'
        f'{source_markup(story)}'
        '</article>'
    )


def render_topic(slug: str, title: str, desk: dict) -> tuple[str, str]:
    stories = ((desk.get("desks") or {}).get(slug) or [])
    stories = [story for story in stories if isinstance(story, dict)]
    body = (
        f'<section class="topic-section" id="{esc(slug)}">'
        '<div class="section-heading">'
        f'<h2>{esc(title)}</h2><span>{len(stories)} 則 · Rolling Desk</span>'
        '</div><div class="topic-story-grid">'
        + "".join(render_topic_story(story, index == 0) for index, story in enumerate(stories))
        + '</div></section>'
    ) if stories else '<p class="notice">本版目前未有可核實內容。</p>'
    return f'{len(stories)} stories · prerendered Rolling Desk', body


def stock_freshness(data: dict) -> str:
    status = str(data.get("collectionStatus") or "").upper()
    checked = data.get("lastCheckedLabel") or data.get("lastCheckedAt") or "尚未建立獨立檢查時間"
    updated = data.get("lastUpdatedLabel") or data.get("generatedAt") or "N/V"
    if status == "COLLECTION_FAILURE":
        message = "⚠️ 最近一次 Stock News 搜集失敗；現有稿件只代表最近已核實內容。"
    elif status == "INCOMPLETE":
        message = "⚠️ 最近一次 Stock News 搜集未達 breadth floor；系統不會把這一輪標記為完整搜集。"
    else:
        found = int(data.get("discoveredThisCheck") or 0)
        reservoir = int(data.get("discoveryCandidateCount") or 0)
        message = f"最近一次 newsroom check 找到 {found} 則 fresh candidates；rolling reservoir {reservoir} 則。沒有新稿通過核實時，舊稿不會被重新標示成新新聞。"
    return (
        f'<p class="notice"><strong>最後檢查：</strong>{esc(checked)} · '
        f'<strong>最近已核實內容更新：</strong>{esc(updated)}<br>{esc(message)}</p>'
    )


def render_stock_story(story: dict, index: int) -> str:
    impact = str(story.get("impact") or "↔")
    impact_class = "stock-impact-up" if impact == "↑" else "stock-impact-down" if impact == "↓" else "stock-impact-neutral"
    return (
        f'<article class="stock-story {"featured" if index == 0 else ""}">'
        f'<div class="tag"><span class="stock-impact {impact_class}">{esc(impact)} {esc(story.get("impactLabel") or "READ-THROUGH")}</span>'
        f'{esc(story.get("storyType") or "LATEST")}</div>'
        f'<h2>{esc(story.get("title"))}</h2><p class="stock-story-dek">{esc(story.get("dek"))}</p>'
        f'<p class="stock-summary"><strong>摘要：</strong>{esc(story.get("summary"))}</p>'
        f'<div class="stock-story-body">{paragraphs(story.get("body"))}</div>'
        '<div class="stock-info-grid stock-info-grid-three">'
        f'<div class="stock-info-card"><strong>背景</strong><p>{esc(story.get("context"))}</p></div>'
        f'<div class="stock-info-card"><strong>為何重要</strong><p>{esc(story.get("why"))}</p></div>'
        f'<div class="stock-info-card"><strong>下一步</strong><p>{esc(story.get("watchNext"))}</p></div>'
        '</div>'
        f'<div class="stock-story-meta">{esc(story.get("timeLabel"))} · {esc(story.get("sourceName"))}</div>'
        f'{source_markup(story)}'
        '</article>'
    )


def render_stocks(data: dict) -> tuple[str, str]:
    order = data.get("tracked") if isinstance(data.get("tracked"), list) else []
    tickers = data.get("tickers") if isinstance(data.get("tickers"), dict) else {}
    nav = "".join(f'<a href="#stock-{esc(ticker.lower())}">{esc(ticker)}</a>' for ticker in order)
    sections = []
    for ticker in order:
        block = tickers.get(ticker) if isinstance(tickers.get(ticker), dict) else {}
        stories = block.get("stories") if isinstance(block.get("stories"), list) else []
        sections.append(
            f'<section class="stock-section" id="stock-{esc(ticker.lower())}">'
            '<div class="stock-section-head"><div>'
            f'<div class="stock-symbol">{esc(ticker)}</div><div class="stock-name">{esc(block.get("name"))}</div>'
            f'</div><div class="stock-asset-type">{esc(block.get("assetType") or "SECURITY")}</div></div>'
            + ("".join(render_stock_story(story, index) for index, story in enumerate(stories))
               if stories else '<div class="stock-empty">暫未有已核實的新稿。</div>')
            + '</section>'
        )
    return nav, "".join(sections)


def render_archive(data: dict) -> str:
    items = []
    for edition in data.get("editions", []):
        if not isinstance(edition, dict):
            continue
        items.append(
            f'<a class="archive-item" href="{esc(edition.get("url"))}">'
            f'<div class="archive-date">{esc(edition.get("shortDate"))}</div>'
            '<div>'
            f'<div class="archive-title">{esc(edition.get("headline"))}</div>'
            f'<div class="archive-topics">{esc(" · ".join(edition.get("topics") or []))}</div>'
            '</div><div>閱讀 →</div></a>'
        )
    return "".join(items)


def build_index(latest: dict, live: dict, desk: dict) -> None:
    path = ROOT / "index.html"
    text = ensure_marker(path.read_text(encoding="utf-8"), "index")
    text = re.sub(r'(<span\s+data-edition-date>).*?(</span>)', rf'\g<1>{esc(latest.get("dateLabel") or latest.get("date"))}\g<2>', text, count=1, flags=re.S)
    text = re.sub(r'(<span\s+data-edition-number>).*?(</span>)', rf'\g<1>{esc(latest.get("editionNumber") or "001")}\g<2>', text, count=1, flags=re.S)
    text = replace_element(text, "article", "lead-story", render_lead(latest))
    text = replace_element(text, "div", "top-five", render_top_five(latest))
    text = replace_element(text, "section", "live-summary", render_live_summary(live))
    text = replace_element(text, "div", "dynamic-sections", render_daily_sections(latest))
    text = replace_element(text, "section", "desk-latest-summary", render_desk_latest(desk))
    path.write_text(text, encoding="utf-8")


def build_live(live: dict) -> None:
    path = ROOT / "live.html"
    text = ensure_marker(path.read_text(encoding="utf-8"), "live")
    stats, audit, stories = render_live_page(live)
    text = replace_text_by_id(text, "span", "live-header-time", live.get("lastUpdatedLabel") or live.get("windowLabel") or "Live")
    text = replace_element(text, "div", "live-page-stats", stats)
    text = replace_element(text, "div", "live-audit", audit)
    text = replace_element(text, "section", "live-page-items", stories)
    path.write_text(text, encoding="utf-8")


def build_stock_page(stocks: dict) -> None:
    path = ROOT / "stocks.html"
    text = ensure_marker(path.read_text(encoding="utf-8"), "stocks")
    nav, sections = render_stocks(stocks)
    text = replace_element(text, "div", "stock-ticker-nav", nav)
    text = replace_text_by_id(text, "strong", "stock-checked", stocks.get("lastCheckedLabel") or stocks.get("lastCheckedAt") or "尚未建立")
    text = replace_text_by_id(text, "strong", "stock-updated", stocks.get("lastUpdatedLabel") or stocks.get("generatedAt") or "N/V")
    text = replace_element(text, "div", "stock-freshness", stock_freshness(stocks))
    text = replace_element(text, "div", "stock-sections", sections)
    path.write_text(text, encoding="utf-8")


def build_topics(desk: dict) -> None:
    generated = desk.get("generatedAt") or desk.get("date") or ""
    title_by_slug = {slug: title for slug, title, _ in DESKS}
    for page, slug in TOPIC_PAGE_TO_SLUG.items():
        path = ROOT / page
        text = ensure_marker(path.read_text(encoding="utf-8"), f"topic:{slug}")
        count_label, body = render_topic(slug, title_by_slug[slug], desk)
        text = replace_text_by_id(text, "span", "topic-date", generated)
        text = replace_text_by_id(text, "span", "topic-count", count_label)
        text = replace_element(text, "div", "topic-sections", body)
        path.write_text(text, encoding="utf-8")


def build_archive(data: dict) -> None:
    path = ROOT / "archive.html"
    text = ensure_marker(path.read_text(encoding="utf-8"), "archive")
    text = replace_element(text, "div", "archive-items", render_archive(data))
    path.write_text(text, encoding="utf-8")


def main() -> int:
    latest = load("latest.json")
    live = load("live.json")
    desk = load("desk-latest.json")
    stocks = load("stocks-latest.json")
    archive = load("archive.json")
    build_index(latest, live, desk)
    build_live(live)
    build_stock_page(stocks)
    build_topics(desk)
    build_archive(archive)
    pages = ["index.html", "live.html", "stocks.html", "archive.html", *TOPIC_PAGE_TO_SLUG.keys()]
    print("STATIC_NEWS_FALLBACK_OK", PRERENDER_VERSION, "pages", len(pages))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
