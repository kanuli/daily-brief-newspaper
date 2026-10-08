#!/usr/bin/env python3
"""Offline compatibility check for the existing General News fallback.

This checks imports and parser behavior only. It performs no news discovery,
model generation, draft writes, publication, or remote calls.
"""
from __future__ import annotations

import argparse
import importlib
import importlib.metadata
import inspect
import json
import sys

EXPECTED_VERSIONS = {
    "googlenewsdecoder": "0.2.1",
    "selectolax": "0.4.12",
}
OFFLINE_HTML = (
    '<c-wiz><div jscontroller="offline-check" '
    'data-n-a-sg="offline-signature" data-n-a-ts="123"></div></c-wiz>'
)


def check_dependencies() -> dict[str, str]:
    versions = {
        name: importlib.metadata.version(name)
        for name in EXPECTED_VERSIONS
    }
    for name, expected in EXPECTED_VERSIONS.items():
        if versions[name] != expected:
            raise RuntimeError(
                f"{name}={versions[name]} is not the verified compatibility version {expected}"
            )

    # Reproduce the exact parser API used by googlenewsdecoder 0.2.1.
    parser = importlib.import_module("selectolax.parser")
    node = parser.HTMLParser(OFFLINE_HTML).css_first("c-wiz > div[jscontroller]")
    if node is None or node.attributes.get("data-n-a-sg") != "offline-signature":
        raise RuntimeError("selectolax legacy parser selector/attributes contract failed")
    if node.attributes.get("data-n-a-ts") != "123":
        raise RuntimeError("selectolax legacy parser timestamp attribute contract failed")

    decoder = importlib.import_module("googlenewsdecoder")
    if not callable(decoder.gnewsdecoder):
        raise RuntimeError("googlenewsdecoder.gnewsdecoder is not callable")
    # Bind only: never decode or fetch this synthetic URL.
    inspect.signature(decoder.gnewsdecoder).bind(
        "https://news.google.com/rss/articles/offline-check",
        interval=None,
        timeout=15.0,
    )

    opencc = importlib.import_module("opencc")
    if opencc.OpenCC("s2hk").convert("新闻") != "新聞":
        raise RuntimeError("OpenCC s2hk conversion contract failed")
    return versions


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--json-only", action="store_true",
        help="Emit only the exact verified version object on success; errors go to stderr.",
    )
    args = parser.parse_args(argv)
    try:
        versions = check_dependencies()
    except Exception as exc:
        if args.json_only:
            # A machine caller must never mistake diagnostics for readiness.
            print(json.dumps({"error": type(exc).__name__}), file=sys.stderr)
            return 1
        print(
            "GENERAL_NEWS_FALLBACK_DEPENDENCIES_FAILED",
            json.dumps({"error": type(exc).__name__, "detail": str(exc)}, ensure_ascii=False),
        )
        return 1
    if args.json_only:
        print(json.dumps(versions, sort_keys=True))
        return 0
    print("GENERAL_NEWS_FALLBACK_DEPENDENCIES_OK", json.dumps(versions, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
