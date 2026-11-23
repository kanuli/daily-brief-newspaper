"""Serialize a reviewed single-story Live draft without credentials or remote writes."""
import argparse
from datetime import datetime, timezone
import hashlib
from pathlib import Path
import re
import sys

from editorial_draft import draft_from_evidence, publisher_reference
from today_first_live import DESK_LABELS, MAX_DRAFT, canonical, require, strict_json


def intake(raw, expected_envelope):
    require(0 < len(raw) <= MAX_DRAFT, "editorial input outside bounds")
    require(bool(re.fullmatch(r"[a-f0-9]{64}", expected_envelope)) and
            hashlib.sha256(raw).hexdigest() == expected_envelope,
            "editorial input does not match the independently supplied digest")
    envelope = strict_json(raw)
    require(isinstance(envelope, dict) and set(envelope) == {
        "copy", "primaryUrl", "verifiedSources", "verifiedSourcesSha256", "editorialDesk"
    }, "invalid editorial intake envelope")
    return envelope


def _draft(envelope, now):
    return draft_from_evidence(envelope["copy"], primary_url=envelope["primaryUrl"],
                               verified_sources=envelope["verifiedSources"],
                               evidence_sha256=envelope["verifiedSourcesSha256"],
                               editorial_desk=envelope["editorialDesk"], now=now, labels=DESK_LABELS)


def emit(raw, expected_envelope, *, now):
    return _draft(intake(raw, expected_envelope),now)


def emit_bundle(raw, expected_envelope, *, now):
    """Produce matching Live bytes and the precise EIC/Core Publisher evidence input."""
    envelope = intake(raw, expected_envelope)
    draft = _draft(envelope,now)
    item, = strict_json(draft)["items"]
    primary, = (source for source in envelope["verifiedSources"]
                if publisher_reference(source["url"]) == publisher_reference(envelope["primaryUrl"]))
    require((item["sourceName"],item["sourceUrl"],item["publishedAt"],item["verifiedAt"]) ==
            (primary["name"],primary["url"],primary["publishedAt"],primary["verifiedAt"]),
            "serialized primary source does not match the verified source")
    return draft, canonical([dict(primary,articleId=item["id"])])


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("editorial_evidence",type=Path)
    p.add_argument("--expected-editorial-sha256",required=True)
    p.add_argument("--publisher-evidence-output",type=Path,
                   help="write exact upstream evidence bytes to a new file; the draft stays on stdout")
    args=p.parse_args()
    with args.editorial_evidence.open("rb") as reader:
        raw=reader.read(MAX_DRAFT+1)
    now=datetime.now(timezone.utc)
    if args.publisher_evidence_output is None:
        draft=emit(raw,args.expected_editorial_sha256,now=now)
    else:
        draft,evidence=emit_bundle(raw,args.expected_editorial_sha256,now=now)
        with args.publisher_evidence_output.open("xb") as target:
            target.write(evidence)
    sys.stdout.buffer.write(draft)


if __name__ == "__main__":
    main()
