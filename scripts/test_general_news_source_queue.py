#!/usr/bin/env python3
"""Regression for bounded fallback source queues; stdlib-only PR CI.

Exercise the deployed queue and direct-rank function AST exactly as written.
Mock *only* upstream trust classification and optional model dependencies.
No network, model, source timestamp fabrication, or publication permissions.
"""
from __future__ import annotations

import ast
import html
from pathlib import Path
import re
import urllib.parse
from typing import Any


SOURCE = Path(__file__).with_name("general_news_local_fallback.py")


def source_queue():
    tree = ast.parse(SOURCE.read_text(encoding="utf-8"), filename=str(SOURCE))
    names = {"direct_source_rank", "bounded_source_queue"}
    selected = [node for node in tree.body if isinstance(node, ast.FunctionDef)
                and node.name in names]
    assert {node.name for node in selected} == names
    max_assign = next(node for node in tree.body
                      if isinstance(node, ast.Assign)
                      and any(isinstance(t, ast.Name) and t.id == "MAX_CANDIDATES_PER_DESK"
                              for t in node.targets))
    max_per_desk = ast.literal_eval(max_assign.value)
    assert max_per_desk == 4, max_per_desk

    def clean(value):
        return re.sub(r"\s+", " ", html.unescape(str(value or ""))).strip()

    def locator_only_url(url):
        host = (urllib.parse.urlparse(str(url or "")).hostname or "").lower().rstrip(".")
        return host == "newspicks.com" or host.endswith(".newspicks.com")

    namespace = {
        "Any": Any, "re": re, "urllib": urllib,
        "clean": clean, "trusted": lambda row: bool(row.get("title") and row.get("source")),
        "locator_only_url": locator_only_url,
        "MAX_CANDIDATES_PER_DESK": max_per_desk,
    }
    exec(compile(ast.Module(body=selected, type_ignores=[]), str(SOURCE), "exec"), namespace)
    return namespace["bounded_source_queue"]


def row(identity, host, when, desk="asia", source="Reuters"):
    return {
        "id": identity, "desk": desk, "source": source,
        "title": "Confirmed original publisher story " + identity,
        "url": "https://" + host + "/news/" + identity,
        "publishedAt": when,
    }


queue = source_queue()
base = "2026-11-17T10:00:00+08:00"
candidates = [
    row("same-1", "www.reuters.com", "2026-11-17T10:04:00+08:00"),
    row("same-2", "www.reuters.com", "2026-11-17T10:03:00+08:00"),
    row("same-3", "www.reuters.com", "2026-11-17T10:02:00+08:00"),
    row("same-4", "www.reuters.com", "2026-11-17T10:01:00+08:00"),
    row("different-1", "www.cna.com.tw", base, source="中央通訊社"),
]
# Previously the fourth same-host candidate consumed the cap before the
# distinct original publisher in fifth place could be reached.
picked = queue({"staleDesks": ["asia"], "candidates": candidates})
ids = [r["id"] for r in picked]
assert ids == ["same-1", "different-1", "same-2", "same-3"], ids
assert len(ids) == 4 and len(set(ids)) == 4, ids

# Maintain the existing direct original Jiji preference for Japan.
jiji = row("jiji", "www.jiji.com", "2026-11-17T09:00:00+08:00",
           desk="japan", source="時事通信")
jiji["provider"] = "Jiji Official RSS"
jiji["url"] = "https://www.jiji.com/jc/article?k=2026111701234&g=pol&m=rss"
mixed = queue({"staleDesks": ["japan", "asia"],
               "candidates": [*candidates, row("jp-other", "www.reuters.com", base, desk="japan"), jiji]})
assert mixed[0]["id"] == "jiji", [r["id"] for r in mixed]
assert len({r["id"] for r in mixed}) == len(mixed)
assert len([r for r in mixed if r["desk"] == "asia"]) <= 4
assert len([r for r in mixed if r["desk"] == "japan"]) <= 4

# A locator cannot be treated as a first-party publisher link.
locator = row("locator", "news.google.com", "2026-11-17T11:00:00+08:00")
assert queue({"staleDesks": ["asia"],
              "candidates": [locator, row("direct", "www.reuters.com", base)]})[0]["id"] == "direct"
assert queue({"staleDesks": [], "candidates": candidates}) == []

print("GENERAL_NEWS_SOURCE_QUEUE_REGRESSION_OK")
