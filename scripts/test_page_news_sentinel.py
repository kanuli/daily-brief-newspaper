#!/usr/bin/env python3
from datetime import datetime, timezone

from page_news_sentinel import audit_public_site, page_contract, topic_slugs

NOW = datetime(2026, 8, 28, 15, 20, tzinfo=timezone.utc)  # 23:20 HKT


def story(slug, ident, stamp="2026-08-28T14:30:00+00:00"):
    return {
        "id": ident,
        "desk": slug,
        "title": f"{slug} test",
        "publishedAt": stamp,
        "body": "x" * 100,
        "summary": "summary long enough for testing",
        "sourceUrl": "https://example.com/news",
    }


LATEST = {"date": "2026-08-28", "articles": []}
LIVE = {"lastUpdated": "2026-08-28T14:30:00+00:00", "items": [{"id": "live-1"}]}
DESK = {
    "generatedAt": "2026-08-28T14:30:00+00:00",
    "desks": {
        slug: [story(slug, slug + "-1")]
        for slug in (
            "world", "asia", "hong-kong", "japan", "market-economy",
            "ai-tech", "manga-anime", "manchester-united", "football",
        )
    },
}
STOCKS = {
    "generatedAt": "2026-08-28T14:00:00+00:00",
    "lastCheckedAt": "2026-08-28T15:00:00+00:00",
    "collectionStatus": "COMPLETE",
}

PAGES = {
    "index.html": '<html><body></body></html>',
    "live.html": '<html><body></body></html>',
    "stocks.html": '<html><body></body></html>',
    "world.html": '<html><body data-page="topic" data-topic-slugs="world"></body></html>',
    "manga-anime.html": '<html><body data-page="topic" data-topic-slugs="manga-anime"></body></html>',
    "archive.html": '<html><body></body></html>',
}


def make_request(*, stale_manga=False, broken_page=None):
    desk = {"generatedAt": DESK["generatedAt"], "desks": {k: [dict(x) for x in v] for k, v in DESK["desks"].items()}}
    if stale_manga:
        desk["desks"]["manga-anime"][0]["publishedAt"] = "2026-08-26T00:00:00+00:00"

    def request(url):
        import json
        path = url.split("?")[0]
        filename = path.rsplit("/", 1)[-1]
        if filename == "latest.json":
            return 200, "application/json", json.dumps(LATEST).encode()
        if filename == "live.json":
            return 200, "application/json", json.dumps(LIVE).encode()
        if filename == "desk-latest.json":
            return 200, "application/json", json.dumps(desk).encode()
        if filename == "stocks-latest.json":
            return 200, "application/json", json.dumps(STOCKS).encode()
        page = filename
        if page == broken_page:
            return 500, "text/html", b"Error 500 (Server Error)"
        return 200, "text/html", PAGES[page].encode()

    return request


assert topic_slugs(PAGES["world.html"]) == ["world"]
assert page_contract("archive.html", PAGES["archive.html"])["kind"] == "utility"

result = audit_public_site(
    public_base="https://example.com/site/",
    pages=list(PAGES),
    local_html=PAGES,
    now=NOW,
    request=make_request(),
)
assert result["status"] == "HEALTHY", result
assert result["failedPageCount"] == 0, result

result = audit_public_site(
    public_base="https://example.com/site/",
    pages=list(PAGES),
    local_html=PAGES,
    now=NOW,
    request=make_request(stale_manga=True),
)
assert result["status"] == "AUTO_REPAIRING", result
manga = next(row for row in result["pageResults"] if row["page"] == "manga-anime.html")
assert not manga["ok"], manga
assert "rolling-news-search.yml" in result["repairWorkflows"], result
assert "merge-live-into-desk.yml" in result["repairWorkflows"], result

previous = result
result = audit_public_site(
    public_base="https://example.com/site/",
    pages=list(PAGES),
    local_html=PAGES,
    now=NOW,
    previous=previous,
    request=make_request(stale_manga=True),
)
assert result["status"] == "EDITORIAL_ATTENTION_REQUIRED", result
assert "manga-anime.html" in result["persistentFailedPages"], result

result = audit_public_site(
    public_base="https://example.com/site/",
    pages=list(PAGES),
    local_html=PAGES,
    now=NOW,
    request=make_request(broken_page="world.html"),
)
assert "pages.yml" in result["repairWorkflows"], result

print("PAGE_NEWS_SENTINEL_TESTS_OK")
