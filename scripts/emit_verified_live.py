"""Serialize a reviewed single-story Live draft without credentials or remote writes."""
import argparse
from datetime import datetime, timezone
import hashlib
from pathlib import Path
import re
import sys

from editorial_draft import draft_from_evidence
from today_first_live import DESK_LABELS, MAX_DRAFT, require, strict_json


def emit(raw, expected_envelope, *, now):
    require(0 < len(raw) <= MAX_DRAFT, "editorial input outside bounds")
    require(bool(re.fullmatch(r"[a-f0-9]{64}", expected_envelope)) and
            hashlib.sha256(raw).hexdigest() == expected_envelope,
            "editorial input does not match the independently supplied digest")
    envelope = strict_json(raw)
    require(isinstance(envelope, dict) and set(envelope) == {
        "copy", "primaryUrl", "verifiedSources", "verifiedSourcesSha256", "editorialDesk"
    }, "invalid editorial intake envelope")
    return draft_from_evidence(envelope["copy"], primary_url=envelope["primaryUrl"],
                               verified_sources=envelope["verifiedSources"],
                               evidence_sha256=envelope["verifiedSourcesSha256"],
                               editorial_desk=envelope["editorialDesk"],now=now,labels=DESK_LABELS)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("editorial_evidence",type=Path)
    p.add_argument("--expected-editorial-sha256",required=True)
    args=p.parse_args()
    with args.editorial_evidence.open("rb") as reader:
        raw=reader.read(MAX_DRAFT+1)
    sys.stdout.buffer.write(emit(raw,args.expected_editorial_sha256,now=datetime.now(timezone.utc)))


if __name__ == "__main__":
    main()
