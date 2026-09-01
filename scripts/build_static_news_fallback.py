#!/usr/bin/env python3
"""Build same-URL static fallbacks for the public newspaper.

The browser JavaScript remains the enhancement/freshness layer.  This script
pre-renders the current verified publication into the existing HTML so a
GitHub Pages visitor does not see blank shells when JavaScript or a JSON fetch
is slow/blocked.
"""
from __future__ import annotations

import html
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
MARKER = '<meta name="daily-brief-prerender" content="current-publication">'

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
    pattern = re.compile(
        rf'(<{tag}\b(?=[^>]*\bid=["\']{re.escape(element_id)}["\'])[^>]*>)(.*?)(</{tag}>)',
        re.S | re.I,
    )
    new, count = pattern.subn(lambda m: m.group(1) + inner + m.group(3), text, count=1)
    if count != 1:
        raise RuntimeError(f"missing or duplicate {tag}#{element_id}")
    return new


def replace_text(text: str, tag: str, element_id: str, value) -> str:
    return replace_element(text, tag, element_id, esc(value))


def source_link(story: dict) -> str:
    url = story.get("sourceUrl") or story.get("url") or "#"
    name = story.get("sourceName") or "原文"
    return f'<a class="source-link" href="{esc(url)}" target="_blank" rel="noopener noreferrer">{esc(name)} ↗</a>'


def render_story_card(story: dict, feature: bool = False) -> str:
    cls = "story-card feature" if feature else "story-card"
    return (
        f'<article class="{cls}">'
        f'<div class="tag">{esc(story.get("deskLabel") or story.get("label") or story.get("desk"))}</div>'
        f'<h3>{esc(story.get("title"))}</h3>'
        f'<p>{esc(story.get("summary") or story.get("dek") or story.get("body"))}</p>'
        f'<p class="why-mini"><strong>為何重要：</strong>{esc(story.get("why") or story.get("whyItMatters"))}</p>'
        f'{source_link(story)}</article>'
    )


def render_index(latest: dict, live: dict, desk: dict) -> str:
    lead = latest.get("lead") if isinstance(latest.get("lead"), dict) else {}
    top = latest.get("topFive") if isinstance(latest.get("topFive"), list) else []
    cards = []
    if lead:
        cards.append(render_story_card(lead, True))
    for story in top:
        if isinstance(story, dict) and story.get("id") != lead.get("id"):
            cards.append(render_story_card(story))
    return "".join(cards)


def render_live(live: dict) -> str:
    items = live.get("items") if isinstance(live.get("items"), list) else []
    return "".join(render_story_card(x, i == 0) for i, x in enumerate(items) if isinstance(x, dict))


def render_topic(slug: str, title: str, desk: dict) -> tuple[str, str]:
    stories = ((desk.get("desks") or {}).get(slug) or []) if isinstance(desk, dict) else []
    cards = "".join(render_story_card(x, i == 0) for i, x in enumerate(stories) if isinstance(x, dict))
    return str(len(stories)), cards


def stock_freshness(stocks: dict) -> str:
    status = esc(stocks.get("collectionStatus") or "N/V")
    checked = esc(stocks.get("lastCheckedAt") or stocks.get("generatedAt") or "N/V")
    return f'<strong>{status}</strong><span>最後檢查：{checked}</span>'


def render_stocks(stocks: dict) -> tuple[str, str]:
    tickers = stocks.get("tickers") if isinstance(stocks.get("tickers"), list) else []
    nav = []
    sections = []
    for ticker in tickers:
        if not isinstance(ticker, dict):
            continue
        symbol = esc(ticker.get("symbol") or ticker.get("ticker"))
        if not symbol:
            continue
        nav.append(f'<a href="#stock-{symbol}">{symbol}</a>')
        stories = ticker.get("stories") if isinstance(ticker.get("stories"), list) else []
        body = "".join(render_story_card(s) for s in stories if isinstance(s, dict))
        sections.append(f'<section id="stock-{symbol}" class="stock-section"><h2>{symbol}</h2>{body}</section>')
    return "".join(nav), "".join(sections)


def render_archive(archive: dict) -> str:
    rows = archive.get("issues") if isinstance(archive.get("issues"), list) else archive.get("items")
    if not isinstance(rows, list):
        rows = []
    output = []
    for row in rows:
        if not isinstance(row, dict):
            continue
        date = esc(row.get("date") or row.get("dateLabel"))
        title = esc(row.get("title") or row.get("label") or date)
        href = esc(row.get("href") or row.get("url") or "#")
        output.append(f'<article class="archive-item"><h3><a href="{href}">{title}</a></h3><p>{date}</p></article>')
    return "".join(output)


def build_index(latest: dict, live: dict, desk: dict) -> None:
    path = ROOT / "index.html"
    text = ensure_marker(path.read_text(encoding="utf-8"), "index")
    content = render_index(latest, live, desk)
    # Existing site templates have evolved over time.  Prefer the stable
    # prerender target if present; otherwise leave the JS-enhanced page intact.
    for candidate in ("daily-news-list", "daily-edition-items", "daily-edition"):
        if re.search(rf'<div\b(?=[^>]*\bid=["\']{candidate}["\'])', text, flags=re.I):
            text = replace_element(text, "div", candidate, content)
            break
    path.write_text(text, encoding="utf-8")


def build_live(live: dict) -> None:
    path = ROOT / "live.html"
    text = ensure_marker(path.read_text(encoding="utf-8"), "live")
    content = render_live(live)
    for candidate in ("live-items", "live-list"):
        if re.search(rf'<div\b(?=[^>]*\bid=["\']{candidate}["\'])', text, flags=re.I):
            text = replace_element(text, "div", candidate, content)
            break
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
    for slug, title, page in DESKS:
        path = ROOT / page
        text = ensure_marker(path.read_text(encoding="utf-8"), f"topic:{slug}")
        count, content = render_topic(slug, title, desk)
        text = replace_text(text, "span", "topic-date", generated)
        text = replace_text(text, "span", "topic-count", count)
        text = replace_element(text, "div", "topic-sections", content)
        path.write_text(text, encoding="utf-8")


def build_archive(archive: dict) -> None:
    path = ROOT / "archive.html"
    text = ensure_marker(path.read_text(encoding="utf-8"), "archive")
    rendered = render_archive(archive)
    # archive-list now wraps archive-items.  Replacing the outer div with a
    # non-nesting regex was brittle and could consume the inner closing tag.
    # Target the leaf container first; keep compatibility with older templates.
    if re.search(r'<div\b(?=[^>]*\bid=["\']archive-items["\'])', text, flags=re.I):
        text = replace_element(text, "div", "archive-items", rendered)
    elif re.search(r'<div\b(?=[^>]*\bid=["\']archive-list["\'])', text, flags=re.I):
        text = replace_element(text, "div", "archive-list", rendered)
    else:
        raise RuntimeError("archive page has no supported prerender target")
    path.write_text(text, encoding="utf-8")


def main() -> int:
    latest = load("latest.json")
    live = load("live.json")
    desk = load("desk-latest.json")
    stocks = load("stocks-latest.json")
    archive = load("archive.json")
    build_index(latest, live, desk)
    build_live(live)
    build_topics(desk)
    build_stock_page(stocks)
    build_archive(archive)
    print("STATIC NEWS FALLBACK BUILD OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
