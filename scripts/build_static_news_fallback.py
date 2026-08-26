#!/usr/bin/env python3
"""Pre-render public news HTML so the newspaper is readable before JS runs.

JSON remains the source of truth. This script is executed only in the GitHub
Pages deployment workspace. Client-side scripts may refresh the same containers
after first paint, while crawlers, previews and no-JS readers get real content.
"""
from __future__ import annotations

import html
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
VERSION = "20260827-v1"
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


def load(name: str) -> dict:
    return json.loads((DATA / name).read_text(encoding="utf-8"))


def esc(value="") -> str:
    return html.escape(str(value or ""), quote=True)


def ensure_marker(text: str, page: str) -> str:
    if 'name="daily-brief-prerender"' in text:
        return text
    meta = (
        f'<meta name="daily-brief-prerender" content="{VERSION}">\n'
        f'  <meta name="daily-brief-prerender-page" content="{esc(page)}">'
    )
    return text.replace("</head>", f"  {meta}\n</head>", 1)


def replace_element(text: str, tag: str, element_id: str, inner: str) -> str:
    pattern = re.compile(
        rf'(<{tag}\b[^>]*\bid=["\']{re.escape(element_id)}["\'][^>]*>).*?(</{tag}>)',
        re.I | re.S,
    )
    result, count = pattern.subn(lambda m: m.group(1) + inner + m.group(2), text, count=1)
    if count != 1:
        raise RuntimeError(f"missing or duplicate {tag}#{element_id}")
    return result


def replace_text(text: str, tag: str, element_id: str, value="") -> str:
    return replace_element(text, tag, element_id, esc(value))


def story_sources(story: dict) -> list[dict]:
    items = story.get("sources")
    if isinstance(items, list) and items:
        return [item for item in items if isinstance(item, dict) and item.get("url")]
    if story.get("sourceUrl"):
        return [{"name": story.get("sourceName") or "原文", "url": story.get("sourceUrl")}]
    return []


def source_markup(story: dict) -> str:
    items = story_sources(story)
    if not items:
        return ""
    links = " · ".join(
        f'<a class="source-link" href="{esc(item.get("url"))}" target="_blank" rel="noopener noreferrer">'
        f'{esc(item.get("name") or "原文")} ↗</a>'
        for item in items
    )
    return f'<div class="article-sources"><strong>核實來源：</strong> {links}</div>'


def body_markup(value="") -> str:
    parts = [p.strip() for p in re.split(r"\n\s*\n", str(value or "")) if p.strip()]
    return "".join(f"<p>{esc(p)}</p>" for p in parts)


def articles_by_id(data: dict) -> dict[str, dict]:
    return {
        str(item.get("id")): item
        for item in data.get("articles", [])
        if isinstance(item, dict) and item.get("id")
    }


def badge(status="UPDATED") -> str:
    safe = str(status or "UPDATED").upper()
    return f'<span class="live-badge live-{esc(safe.lower())}">{esc(safe)}</span>'


def render_lead(latest: dict) -> str:
    by_id = articles_by_id(latest)
    story = by_id.get(str(latest.get("leadId"))) or (next(iter(by_id.values())) if by_id else None)
    if not story:
        return '<p class="notice">今日頭條資料暫不可用。</p>'
    return (
        f'<span class="eyebrow">{esc(story.get("section"))}｜今日頭條</span>'
        f'<h2>{esc(story.get("title"))}</h2>'
        f'<p class="lead-deck">{esc(story.get("dek"))}</p>'
        f'<div class="story-meta">{esc(story.get("timeLabel") or latest.get("dateLabel"))} · {esc(story.get("sourceName"))}</div>'
        f'<div class="story-body"><p>{esc(story.get("summary"))}</p></div>'
        f'<div class="why-box"><strong>為何重要：</strong> {esc(story.get("why"))}</div>'
        f'{source_markup(story)}'
    )


def render_top_five(latest: dict) -> str:
    by_id = articles_by_id(latest)
    ids = list(latest.get("topFive") or list(by_id))[:5]
    return "".join(
        '<article class="top-card"><div>'
        f'<h3>{esc(by_id[story_id].get("title"))}</h3>'
        f'<p>{esc(by_id[story_id].get("dek"))}</p>'
        '</div></article>'
        for story_id in ids if story_id in by_id
    )


def render_daily_sections(latest: dict) -> str:
    by_id = articles_by_id(latest)
    output = []
    for section in latest.get("sections", []) if isinstance(latest.get("sections"), list) else []:
        if not isinstance(section, dict):
            continue
        stories = [by_id.get(str(story_id)) for story_id in section.get("articleIds", [])]
        stories = [story for story in stories if story]
        if not stories:
            continue
        cards = []
        for index, story in enumerate(stories):
            feature = "feature" if index == 0 and len(stories) > 1 else ""
            cards.append(
                f'<article class="story-card {feature}">'
                f'<div class="tag">{esc(story.get("section"))}</div>'
                f'<h3>{esc(story.get("title"))}</h3>'
                f'<p>{esc(story.get("summary"))}</p>'
                f'<p class="why-mini"><strong>為何重要：</strong> {esc(story.get("why"))}</p>'
                f'{source_markup(story)}</article>'
            )
        output.append(
            f'<section class="section-block" id="{esc(section.get("slug"))}">'
            '<div class="section-heading">'
            f'<h2>{esc(section.get("title"))}</h2>'
            f'<span>{esc(section.get("subtitle") or f"{len(stories)} 則")}</span>'
            '</div><div class="story-grid">' + "".join(cards) + '</div></section>'
        )
    return "".join(output)


def render_live_summary(live: dict) -> str:
    items = [item for item in live.get("items", []) if isinstance(item, dict)][:4]
    cards = "".join(
        '<article class="live-mini-card">'
        f'<div>{badge(item.get("status"))} <span class="live-time">{esc(item.get("timeLabel"))}</span></div>'
        f'<h3>{esc(item.get("title"))}</h3><p>{esc(item.get("summary"))}</p>'
        '</article>'
        for item in items
    ) or '<p class="notice">本輪沒有需要新增的重大新聞；各版最新內容仍在下方保留。</p>'
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
    source = desk.get("desks") if isinstance(desk.get("desks"), dict) else {}
    cards = []
    for slug, title, page in DESKS:
        stories = source.get(slug) if isinstance(source.get(slug), list) else []
        story = next((item for item in stories if isinstance(item, dict)), None)
        if not story:
            continue
        cards.append(
            '<article class="story-card desk-latest-card">'
            f'<div class="tag">{esc(title)} · LATEST</div>'
            f'<h3><a href="{esc(page)}">{esc(story.get("title"))}</a></h3>'
            f'<p>{esc(story.get("summary"))}</p>'
            f'<div class="story-meta">{esc(story.get("timeLabel"))}</div>'
            f'{source_markup(story)}</article>'
        )
    return (
        '<div class="section-heading"><h2>各版最新</h2>'
        f'<span>DESK LATEST · {esc(desk.get("generatedAt"))}</span></div>'
        '<p class="notice">Live 只顯示今小時真正有變化的新聞；這裡保留各新聞 Desk 目前最新的重要內容，避免把「沒有新增卡片」誤解成「沒有新聞」。</p>'
        '<div class="story-grid">' + "".join(cards) + '</div>'
    )


def render_live_page(live: dict) -> tuple[str, str, str]:
    items = [item for item in live.get("items", []) if isinstance(item, dict)]
    counts = {"NEW": 0, "UPDATED": 0, "DEVELOPING": 0}
    for item in items:
        status = str(item.get("status") or "").upper()
        if status in counts:
            counts[status] += 1
    stats = (
        f'<div><strong>{counts["NEW"]}</strong><span>NEW</span></div>'
        f'<div><strong>{counts["UPDATED"]}</strong><span>UPDATED</span></div>'
        f'<div><strong>{counts["DEVELOPING"]}</strong><span>DEVELOPING</span></div>'
        f'<p>{esc(live.get("nextUpdateLabel"))}</p>'
    )
    coverage = live.get("coverage") if isinstance(live.get("coverage"), dict) else {}
    if any(key in coverage for key in ("rawFreshCandidateCount", "verifiedCandidateCount", "incrementalCandidateCount")):
        audit = (
            '<strong>最新搜集：</strong>'
            f'raw {esc(coverage.get("rawFreshCandidateCount", "N/V"))} · '
            f'verified {esc(coverage.get("verifiedCandidateCount", "N/V"))} · '
            f'incremental {esc(coverage.get("incrementalCandidateCount", "N/V"))}'
        )
    else:
        audit = f'<strong>最新出版：</strong>{esc(live.get("lastUpdatedLabel") or live.get("windowLabel") or "已更新")}'
    stories = []
    for item in items:
        label = item.get("sectionLabel") or item.get("section") or item.get("desk") or "Live"
        stories.append(
            '<article class="live-story live-story-rich">'
            f'<div class="live-story-meta">{badge(item.get("status"))} <span>{esc(label)}</span> <span>{esc(item.get("timeLabel"))}</span></div>'
            f'<h2>{esc(item.get("title"))}</h2><p class="live-article-dek">{esc(item.get("dek"))}</p>'
            '<div class="live-article-body">'
            f'<p class="live-article-summary"><strong>摘要：</strong>{esc(item.get("summary"))}</p>'
            f'<div class="live-body-main">{body_markup(item.get("body"))}</div>'
            f'<p class="live-article-context"><strong>背景：</strong>{esc(item.get("context") or item.get("background"))}</p>'
            f'<p class="live-article-why"><strong>為何重要：</strong>{esc(item.get("why") or item.get("whyImportant"))}</p>'
            f'<p class="live-article-next"><strong>下一步：</strong>{esc(item.get("watchNext") or item.get("nextStep"))}</p>'
            f'</div>{source_markup(item)}</article>'
        )
    return stats, audit, "".join(stories) or '<p class="notice">本輪沒有新增 Live 卡片；各分版仍保留最近已核實內容。</p>'


def render_topic_story(story: dict, featured: bool) -> str:
    feature = "topic-feature" if featured else ""
    label = story.get("section") or story.get("sectionLabel") or story.get("desk") or "NEWS"
    return (
        f'<article class="topic-story {feature}">'
        f'<div class="tag"><span class="topic-latest-badge">LATEST</span>{esc(label)}</div>'
        f'<h2>{esc(story.get("title"))}</h2><p class="topic-dek">{esc(story.get("dek"))}</p>'
        '<div class="topic-article-body">'
        f'<p class="topic-summary"><strong>最新：</strong>{esc(story.get("summary"))}</p>'
        f'<div class="topic-full-body">{body_markup(story.get("body"))}</div>'
        f'<p class="topic-context"><strong>背景：</strong>{esc(story.get("context") or story.get("background"))}</p>'
        f'<p class="why-mini"><strong>為何重要：</strong>{esc(story.get("why") or story.get("whyImportant"))}</p>'
        f'<p class="topic-next"><strong>下一步：</strong>{esc(story.get("watchNext") or story.get("nextStep"))}</p>'
        '</div>'
        f'<div class="story-meta">{esc(story.get("timeLabel"))} · {esc(story.get("sourceName"))}</div>'
        f'{source_markup(story)}</article>'
    )


def render_topic(slug: str, title: str, desk: dict) -> tuple[str, str]:
    stories = ((desk.get("desks") or {}).get(slug) or [])
    stories = [story for story in stories if isinstance(story, dict)]
    if not stories:
        return "0 stories", '<p class="notice">本版目前未有可核實內容。</p>'
    body = (
        f'<section class="topic-section" id="{esc(slug)}">'
        f'<div class="section-heading"><h2>{esc(title)}</h2><span>{len(stories)} 則 · Rolling Desk</span></div>'
        '<div class="topic-story-grid">'
        + "".join(render_topic_story(story, index == 0) for index, story in enumerate(stories))
        + '</div></section>'
    )
    return f'{len(stories)} stories · prerendered Rolling Desk', body


def render_stock_story(story: dict, index: int) -> str:
    impact = str(story.get("impact") or "↔")
    css = "stock-impact-up" if impact == "↑" else "stock-impact-down" if impact == "↓" else "stock-impact-neutral"
    return (
        f'<article class="stock-story {"featured" if index == 0 else ""}">'
        f'<div class="tag"><span class="stock-impact {css}">{esc(impact)} {esc(story.get("impactLabel") or "READ-THROUGH")}</span>{esc(story.get("storyType") or "LATEST")}</div>'
        f'<h2>{esc(story.get("title"))}</h2><p class="stock-story-dek">{esc(story.get("dek"))}</p>'
        f'<p class="stock-summary"><strong>摘要：</strong>{esc(story.get("summary"))}</p>'
        f'<div class="stock-story-body">{body_markup(story.get("body"))}</div>'
        '<div class="stock-info-grid stock-info-grid-three">'
        f'<div class="stock-info-card"><strong>背景</strong><p>{esc(story.get("context"))}</p></div>'
        f'<div class="stock-info-card"><strong>為何重要</strong><p>{esc(story.get("why"))}</p></div>'
        f'<div class="stock-info-card"><strong>下一步</strong><p>{esc(story.get("watchNext"))}</p></div>'
        '</div>'
        f'<div class="stock-story-meta">{esc(story.get("timeLabel"))} · {esc(story.get("sourceName"))}</div>'
        f'{source_markup(story)}</article>'
    )


def render_stocks(data: dict) -> tuple[str, str]:
    order = data.get("tracked") if isinstance(data.get("tracked"), list) else []
    tickers = data.get("tickers") if isinstance(data.get("tickers"), dict) else {}
    nav = "".join(f'<a href="#stock-{esc(ticker.lower())}">{esc(ticker)}</a>' for ticker in order)
    output = []
    for ticker in order:
        block = tickers.get(ticker) if isinstance(tickers.get(ticker), dict) else {}
        stories = block.get("stories") if isinstance(block.get("stories"), list) else []
        story_html = "".join(render_stock_story(story, index) for index, story in enumerate(stories))
        output.append(
            f'<section class="stock-section" id="stock-{esc(ticker.lower())}">'
            '<div class="stock-section-head"><div>'
            f'<div class="stock-symbol">{esc(ticker)}</div><div class="stock-name">{esc(block.get("name"))}</div>'
            f'</div><div class="stock-asset-type">{esc(block.get("assetType") or "SECURITY")}</div></div>'
            + (story_html or '<div class="stock-empty">暫未有已核實的新稿。</div>')
            + '</section>'
        )
    return nav, "".join(output)


def stock_freshness(data: dict) -> str:
    status = str(data.get("collectionStatus") or "").upper()
    found = int(data.get("discoveredThisCheck") or 0)
    reservoir = int(data.get("discoveryCandidateCount") or 0)
    if status == "COLLECTION_FAILURE":
        message = "⚠️ 最近一次搜集失敗；這不是『市場沒有新聞』。"
    elif status == "INCOMPLETE":
        message = f"⚠️ 本輪找到 {found} 則 fresh candidates，但未達 breadth floor。"
    else:
        message = f"本輪找到 {found} 則 fresh candidates；rolling reservoir {reservoir} 則。沒有新稿通過核實時，舊稿不會重新標示成新新聞。"
    return f'<p class="notice"><strong>Newsroom freshness：</strong>{esc(message)}</p>'


def render_archive(data: dict) -> str:
    return "".join(
        f'<a class="archive-item" href="{esc(item.get("url"))}">'
        f'<div class="archive-date">{esc(item.get("shortDate"))}</div><div>'
        f'<div class="archive-title">{esc(item.get("headline"))}</div>'
        f'<div class="archive-topics">{esc(" · ".join(item.get("topics") or []))}</div>'
        '</div><div>閱讀 →</div></a>'
        for item in data.get("editions", []) if isinstance(item, dict)
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
    text = replace_text(text, "strong", "stock-checked", stocks.get("lastCheckedLabel") or stocks.get("lastCheckedAt") or "尚未建立")
    text = replace_text(text, "strong", "stock-updated", stocks.get("lastUpdatedLabel") or stocks.get("generatedAt") or "N/V")
    text = replace_element(text, "div", "stock-freshness", stock_freshness(stocks))
    text = replace_element(text, "div", "stock-sections", sections)
    path.write_text(text, encoding="utf-8")


def build_topics(desk: dict) -> None:
    generated = desk.get("generatedAt") or desk.get("date") or ""
    for slug, title, page in DESKS:
        path = ROOT / page
        text = ensure_marker(path.read_text(encoding="utf-8"), f"topic:{slug}")
        count, content = render_topic(slug, title, desk)
        text = replace_text(text, "span", "topic-date", generated)
        text = replace_text(text, "span", "topic-count", count)
        text = replace_element(text, "div", "topic-sections", content)
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
    print("STATIC_NEWS_FALLBACK_OK", VERSION, "pages", 13)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
