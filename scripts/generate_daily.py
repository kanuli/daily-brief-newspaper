from __future__ import annotations

import json
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path
from typing import List
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

from openai import OpenAI
from pydantic import BaseModel, Field, HttpUrl, field_validator

ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
EDITIONS_DIR = ROOT / "editions"
CONFIG_PATH = ROOT / "config" / "news_config.json"
ARCHIVE_PATH = DATA_DIR / "archive.json"
LATEST_PATH = DATA_DIR / "latest.json"

HK = ZoneInfo("Asia/Hong_Kong")


class Story(BaseModel):
    id: str = Field(min_length=3, max_length=64, pattern=r"^[a-z0-9-]+$")
    section: str = Field(min_length=2, max_length=40)
    mediaLabel: str = Field(min_length=2, max_length=24)
    title: str = Field(min_length=8, max_length=90)
    dek: str = Field(min_length=12, max_length=160)
    summary: str = Field(min_length=40, max_length=700)
    why: str = Field(min_length=30, max_length=500)
    sourceName: str = Field(min_length=2, max_length=80)
    sourceUrl: HttpUrl
    timeLabel: str = Field(min_length=4, max_length=32)
    image: str | None = None

    @field_validator("sourceUrl")
    @classmethod
    def source_must_be_http(cls, value: HttpUrl):
        if value.scheme not in {"http", "https"}:
            raise ValueError("sourceUrl must be http(s)")
        return value


class Section(BaseModel):
    slug: str = Field(pattern=r"^[a-z0-9-]+$")
    title: str = Field(min_length=2, max_length=40)
    subtitle: str = Field(default="", max_length=80)
    articleIds: List[str]


class StudyDesk(BaseModel):
    label: str
    targetDate: str
    title: str
    summary: str
    action: str
    sourceUrl: HttpUrl


class EditionDraft(BaseModel):
    tagline: str = "只留下值得你知道的事"
    leadId: str
    topFive: List[str] = Field(min_length=5, max_length=5)
    articles: List[Story] = Field(min_length=5, max_length=24)
    sections: List[Section] = Field(min_length=1, max_length=12)
    studyDesk: StudyDesk | None = None


def load_json(path: Path, default):
    if not path.exists():
        return default
    return json.loads(path.read_text(encoding="utf-8"))


def dump_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, default=str) + "\n",
        encoding="utf-8",
    )


def recent_context(limit: int = 3) -> str:
    archive = load_json(ARCHIVE_PATH, {"editions": []})
    entries = archive.get("editions", [])[:limit]
    chunks = []
    for entry in entries:
        date = entry.get("date")
        if not date:
            continue
        edition_path = DATA_DIR / f"{date}.json"
        if not edition_path.exists():
            continue
        edition = load_json(edition_path, {})
        titles = [a.get("title", "") for a in edition.get("articles", []) if a.get("title")]
        chunks.append(f"{date}: " + " | ".join(titles))
    return "\n".join(chunks) or "No previous editions available."


def build_prompt(config: dict, date_hk: datetime) -> str:
    topic_lines = "\n".join(f"- {x}" for x in config["priority_topics"])
    source_lines = "\n".join(f"- {x}" for x in config["source_preferences"])
    return f"""
Today in Hong Kong is {date_hk:%Y-%m-%d}. Create the daily edition of a personal newspaper.

LANGUAGE
- All explanatory copy must be Traditional Chinese (Hong Kong usage).
- Keep proper nouns, company names, player names, official product/model names in their original language when clearer.

EDITORIAL PRIORITIES
{topic_lines}

SELECTION RULES
- Find the most decision-useful and current developments, normally from the last 24 hours.
- Include breaking/emerging news, important developments with useful context, and genuinely market-moving news.
- Do not force equal representation by topic.
- Do not force a fixed number of sections. Create only sections that have worthwhile stories today.
- Publish between {config["min_articles"]} and {config["max_articles"]} stories total.
- Exactly five article IDs must appear in topFive.
- leadId must identify the single strongest story.
- Avoid filler, celebrity trivia, weak rumours, duplicate angles, and stories already covered recently unless there is a material new development.
- Rumours must be explicitly labelled as reports/rumours and must not be written as confirmed facts.
- Prefer primary/official sources or high-quality reporting.
- Every article must have one direct, clickable original source URL that supports the summary.
- Do not invent a URL. If a reliable source URL cannot be established, omit the story.
- image must be null. This site does not use AI-generated news images and image licensing is handled separately.

SOURCE PREFERENCES
{source_lines}

RECENT EDITIONS TO AVOID REPEATING WITHOUT MATERIAL NEW INFORMATION
{recent_context()}

PERSONAL DECISION USEFULNESS
- Japan: emphasize policy, JPY, travel-relevant developments, economy, practical Japan/JLPT developments.
- AI/technology: emphasize material product launches, major platform/model changes, chips/infrastructure, regulation/security, decisions that affect practical technology use.
- Hong Kong/Asia: emphasize policy, economy, transport/travel, jobs/business, public services, markets, regional developments.
- Manchester United: prioritize official club updates, fixtures, injuries, confirmed transfers, and well-sourced material transfer developments.
- Market content should be included only when it is genuinely important, not as a quota.

STRUCTURE
- section is a short display label such as "日本｜政策" or "AI｜科技".
- mediaLabel is a short uppercase display tag, e.g. JAPAN, AI, HONG KONG, UNITED.
- section.slug must be lowercase ASCII with hyphens.
- articleIds in sections must refer to articles in this edition.
- Every article should appear in exactly one section.
- topFive and leadId must refer to valid article IDs.
- title should read like a newspaper headline but remain factual.
- dek is a one-sentence subheadline.
- summary explains what happened with key facts/numbers.
- why explains why it matters or how it could affect a practical decision.

JLPT STUDY DESK
- If there is material current JLPT/Japanese-learning news, it may appear as a normal article.
- Also populate studyDesk only when there is a useful, verified official study/date/action item.
- If studyDesk is used, its sourceUrl should preferably be official JLPT/Japan Foundation material.

Return only the structured edition.
""".strip()


def request_edition(config: dict, date_hk: datetime) -> EditionDraft:
    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError(
            "OPENAI_API_KEY is missing. Add it as a GitHub Actions repository secret."
        )

    client = OpenAI()
    model = os.getenv("OPENAI_MODEL", config.get("openai_model", "gpt-5.6-terra"))

    response = client.responses.parse(
        model=model,
        reasoning={"effort": "low"},
        tools=[
            {
                "type": "web_search",
                "search_context_size": config.get("search_context_size", "medium"),
            }
        ],
        input=[
            {
                "role": "system",
                "content": (
                    "You are the editor of a compact Hong Kong Traditional Chinese "
                    "personal newspaper. Search the live web, verify material claims, "
                    "prefer reliable sources, and output only the requested structure."
                ),
            },
            {"role": "user", "content": build_prompt(config, date_hk)},
        ],
        text_format=EditionDraft,
    )

    if response.output_parsed is None:
        raise RuntimeError("OpenAI returned no parsed edition.")
    return response.output_parsed


def validate_relations(draft: EditionDraft) -> None:
    ids = [a.id for a in draft.articles]
    id_set = set(ids)
    if len(ids) != len(id_set):
        raise ValueError("Duplicate article IDs in edition.")
    if draft.leadId not in id_set:
        raise ValueError("leadId does not match an article.")
    if len(set(draft.topFive)) != 5 or not set(draft.topFive).issubset(id_set):
        raise ValueError("topFive must contain five unique valid article IDs.")

    seen = []
    for section in draft.sections:
        for article_id in section.articleIds:
            if article_id not in id_set:
                raise ValueError(f"Unknown article ID in section: {article_id}")
            seen.append(article_id)
    if sorted(seen) != sorted(ids):
        raise ValueError("Every article must appear exactly once across sections.")


def edition_number() -> str:
    archive = load_json(ARCHIVE_PATH, {"editions": []})
    return f"{len(archive.get('editions', [])) + 1:03d}"


def zh_date_label(dt: datetime) -> str:
    weekdays = "一二三四五六日"
    return f"{dt.year}年{dt.month}月{dt.day}日 星期{weekdays[dt.weekday()]}"


def normalize_url(value) -> str:
    text = str(value)
    parsed = urlparse(text)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ValueError(f"Invalid source URL: {text}")
    return text


def make_payload(draft: EditionDraft, dt: datetime) -> dict:
    payload = draft.model_dump(mode="json")
    for article in payload["articles"]:
        article["sourceUrl"] = normalize_url(article["sourceUrl"])
        article["image"] = None
    if payload.get("studyDesk"):
        payload["studyDesk"]["sourceUrl"] = normalize_url(payload["studyDesk"]["sourceUrl"])
    payload.update(
        {
            "editionNumber": edition_number(),
            "date": dt.strftime("%Y-%m-%d"),
            "dateLabel": zh_date_label(dt),
        }
    )
    return {
        "editionNumber": payload["editionNumber"],
        "date": payload["date"],
        "dateLabel": payload["dateLabel"],
        "tagline": payload["tagline"],
        "leadId": payload["leadId"],
        "topFive": payload["topFive"],
        "articles": payload["articles"],
        "sections": payload["sections"],
        "studyDesk": payload.get("studyDesk"),
    }


def edition_html(payload: dict) -> str:
    date = payload["date"]
    num = payload["editionNumber"]
    date_label = payload["dateLabel"]
    tagline = payload["tagline"]
    nav = "".join(
        f'<a href="#{s["slug"]}">{s["title"]}</a>' for s in payload["sections"]
    )
    if payload.get("studyDesk"):
        nav += '<a href="#study-desk">日語學習</a>'
    nav += '<a href="archive.html">Archive</a>'
    return f"""<!doctype html>
<html lang="zh-Hant">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <base href="../">
  <meta name="theme-color" content="#111111">
  <title>{date}｜每日晨報 Daily Brief</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Noto+Sans+TC:wght@400;700;900&family=Noto+Serif+TC:wght@600;800;900&display=swap" rel="stylesheet">
  <link rel="stylesheet" href="assets/css/newspaper.css">
</head>
<body data-edition="{date}">
  <div class="paper">
    <div class="utility-bar"><span>ARCHIVED EDITION · HONG KONG</span><span>NO. <span data-edition-number>{num}</span></span></div>
    <header class="masthead">
      <div class="masthead-side">日本 · AI · 香港亞洲<br>Manchester United</div>
      <div class="brand"><div class="brand-kicker">個 人 化 電 子 報</div><h1>每日晨報</h1><div class="brand-en">DAILY BRIEF</div></div>
      <div class="masthead-side right"><span data-edition-tagline>{tagline}</span><br>ARCHIVED EDITION</div>
    </header>
    <nav class="section-nav" aria-label="主要分類">{nav}</nav>
    <div class="date-strip"><span data-edition-date>{date_label}</span><span>ARCHIVED · 當日內容固定保存</span></div>
    <main>
      <section class="lead-grid">
        <article class="lead-story" id="lead-story"><p>正在載入日報…</p></article>
        <aside><div class="section-heading"><h2>今日必讀 5 則</h2><span>TOP FIVE</span></div><div class="top-five" id="top-five"></div></aside>
      </section>
      <div id="dynamic-sections"></div>
      <section class="study-desk" id="study-desk"></section>
      <p class="notice">此頁保存 {date} edition。來源內容可能於原網站後續更新；此處摘要保留發刊時版本。</p>
    </main>
    <footer class="footer"><span>每日晨報 Daily Brief · {date}</span><span><a href="archive.html">Archive</a> · <a href="index.html">今日頭版</a></span></footer>
  </div>
  <script src="assets/js/newspaper.js" defer></script>
</body>
</html>
"""


def update_archive(payload: dict) -> None:
    archive = load_json(ARCHIVE_PATH, {"editions": []})
    editions = [e for e in archive.get("editions", []) if e.get("date") != payload["date"]]
    lead = next(a for a in payload["articles"] if a["id"] == payload["leadId"])
    topic_names = [s["title"] for s in payload["sections"]]
    if payload.get("studyDesk"):
        topic_names.append("日語學習")
    entry = {
        "date": payload["date"],
        "shortDate": datetime.strptime(payload["date"], "%Y-%m-%d").strftime("%d %b %Y").upper(),
        "headline": lead["title"],
        "topics": topic_names,
        "url": f'editions/{payload["date"]}.html',
    }
    editions.insert(0, entry)
    archive["editions"] = editions
    dump_json(ARCHIVE_PATH, archive)


def main() -> None:
    config = load_json(CONFIG_PATH, {})
    if not config:
        raise RuntimeError("Missing config/news_config.json")

    now_hk = datetime.now(timezone.utc).astimezone(HK)
    forced_date = os.getenv("EDITION_DATE")
    if forced_date:
        parsed = datetime.strptime(forced_date, "%Y-%m-%d")
        now_hk = parsed.replace(tzinfo=HK)

    draft = request_edition(config, now_hk)
    validate_relations(draft)
    payload = make_payload(draft, now_hk)

    date = payload["date"]
    dated_json = DATA_DIR / f"{date}.json"
    dated_html = EDITIONS_DIR / f"{date}.html"

    dump_json(dated_json, payload)
    shutil.copyfile(dated_json, LATEST_PATH)
    dated_html.parent.mkdir(parents=True, exist_ok=True)
    dated_html.write_text(edition_html(payload), encoding="utf-8")
    update_archive(payload)

    print(
        f"Generated Daily Brief {date}: "
        f"{len(payload['articles'])} stories, {len(payload['sections'])} sections."
    )


if __name__ == "__main__":
    main()
