"""Build an unsigned Today-first candidate from independently verified inputs.

The upstream writer submits copy and its primary URL. The existing verifier
supplies an independently pinned evidence manifest. This stage grants no EIC
approval, writes no shared state, and never touches historical Live items.
"""
import hashlib
import re
from urllib.parse import urlsplit, urlunsplit

from desk_freshness_policy import EXPECTED_DESKS, routed_slugs
from scheduled_publication_contract import stamp, time_label, web_source
from today_first_live import CONTRACT, HKT, candidate_live, canonical, require
from verified_draft_pending import locator_only_url

STORY_FIELDS = ("id", "title", "dek", "summary", "body", "context", "why", "watchNext", "status")
SOURCE_FIELDS = {"name", "url", "publishedAt", "verifiedAt", "documentSha256"}
HEX = re.compile(r"[0-9a-f]{64}\Z")


def publisher_reference(value):
    """Compare only equivalent HTTPS spellings; retain the original evidence URL."""
    require(isinstance(value, str) and value.isascii() and all(ord(ch)>32 and ord(ch)!=127 for ch in value)
            and "\\" not in value, "invalid original publisher URL")
    parsed = urlsplit(value)
    require(parsed.scheme == "https" and bool(parsed.hostname) and parsed.username is None
            and parsed.password is None and parsed.port in (None, 443)
            and re.fullmatch(r"[a-z0-9.-]+", parsed.hostname)
            and "?" not in value.partition("#")[0][-1:]
            and bool(parsed.path) and parsed.path.startswith("/")
            and web_source(value) and not locator_only_url(value),
            "invalid original publisher URL")
    # Do not rewrite the path, query, publisher protocol or redirect target.
    return urlunsplit(("https", parsed.hostname, parsed.path, parsed.query, ""))


def draft_from_evidence(copy, *, primary_url, verified_sources, evidence_sha256, editorial_desk, now, labels):
    """Serialize one article, preserving the verifier's original timestamps."""
    require(now.utcoffset() is not None, "offset-aware edition time required")
    require(isinstance(verified_sources, list) and 0 < len(verified_sources) <= 16,
            "verified evidence manifest required")
    require(hashlib.sha256(canonical(verified_sources)).hexdigest() == evidence_sha256,
            "verified evidence manifest hash mismatch")
    source_map = {}
    for source in verified_sources:
        require(isinstance(source, dict) and set(source) == SOURCE_FIELDS
                and isinstance(source["name"], str) and bool(source["name"].strip())
                and web_source(source["url"]) and not locator_only_url(source["url"])
                and isinstance(source["documentSha256"], str) and HEX.fullmatch(source["documentSha256"]),
                "malformed original publisher evidence")
        published, verified = stamp(source["publishedAt"]), stamp(source["verifiedAt"])
        require(published <= verified <= now, "publisher or verification time out of order")
        reference = publisher_reference(source["url"])
        require(reference not in source_map, "ambiguous original publisher evidence")
        source_map[reference] = source
    reference = publisher_reference(primary_url)
    require(reference in source_map, "primary source not linked to verified evidence")
    primary = source_map[reference]

    require(editorial_desk in EXPECTED_DESKS, "unknown editorial desk")
    item = {field: copy[field] for field in STORY_FIELDS}
    require(all(isinstance(item[field], str) and bool(item[field].strip())
                for field in STORY_FIELDS if field != "body"), "incomplete editorial copy")
    routes = routed_slugs({**item, "deskSlugs": [editorial_desk]})
    require(routes and routes[0] == editorial_desk, "verified copy contradicts proposed editorial desk")
    item.update(desk=routes[0], deskSlugs=routes, section=labels[editorial_desk],
                sectionLabel=labels[editorial_desk], sourceName=primary["name"], sourceUrl=primary["url"],
                publishedAt=primary["publishedAt"], verifiedAt=primary["verifiedAt"],
                timeLabel=time_label(primary["verifiedAt"]),
                sources=[dict(name=s["name"], url=s["url"], date=s["publishedAt"]) for s in source_map.values()])
    status = item["status"]
    local = now.astimezone(HKT)
    raw = canonical(dict(publicationContract=CONTRACT, date=local.date().isoformat(), mode="LIVE",
                         lastUpdated=now.isoformat(), lastUpdatedLabel=local.strftime("%H:%M HKT"),
                         nextUpdateLabel="下次更新視乎核實進度", windowLabel="即時更新",
                         newCount=int(status != "UPDATED"), updatedCount=int(status == "UPDATED"),
                         developingCount=int(status == "DEVELOPING"), leadId=item["id"], items=[item]))
    candidate_live(raw, now=now)
    return raw
