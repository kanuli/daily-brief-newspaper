"""Validate the existing public source-headline shape without generating editorial copy."""
import re
from urllib.parse import urlsplit

MODE = "AI_GROUP_SOURCE_HEADLINE_V1"
COPY_FIELDS = ("dek", "summary", "body", "context", "why", "watchNext")
PROCESS = re.compile(r"今日未找到|本輪已檢查|重複刊登|coverage (?:check|test)|no news found", re.I)


def validate_source_headline(story, label):
    if story.get("sourceAggregation") is None:
        return False
    if story["sourceAggregation"] != MODE:
        raise ValueError(f"{label}: unsupported source aggregation mode")
    for field in ("id", "title", "sourceName", "sourceUrl", "publishedAt", "verifiedAt", "timeLabel"):
        value = story.get(field)
        if not isinstance(value, str) or not value.strip():
            raise ValueError(f"{label}: missing {field}")
    if any(story.get(field, "") != "" for field in COPY_FIELDS) or PROCESS.search(story["title"]):
        raise ValueError(f"{label}: source headline contains unauthorized narrative or process text")
    from scheduled_publication_contract import stamp, time_label, web_source

    url = story["sourceUrl"]
    parts = urlsplit(url)
    if (not web_source(url) or parts.scheme != "https" or not parts.hostname
            or parts.username or parts.password or parts.path in {"", "/"} or parts.fragment
            or any(ch.isspace() for ch in url)):
        raise ValueError(f"{label}: original HTTPS source URL required")
    sources = story.get("sources")
    if not isinstance(sources, list) or not any(
        isinstance(row, dict) and row.get("name") == story["sourceName"] and row.get("url") == url
        for row in sources
    ):
        raise ValueError(f"{label}: primary source name and URL must match verification evidence")
    published, verified = stamp(story["publishedAt"]), stamp(story["verifiedAt"])
    if published > verified or time_label(story["verifiedAt"]) != story["timeLabel"]:
        raise ValueError(f"{label}: source publication or verification clock invalid")
    return True
