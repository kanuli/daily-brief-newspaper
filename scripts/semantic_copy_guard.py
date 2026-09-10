#!/usr/bin/env python3
"""Deterministic semantic/copyediting guard for published newsroom copy.

This module is deliberately conservative: it catches high-confidence entity-type
and headline/body inconsistencies that structural validators cannot see.  It is
shared by the Editor-in-Chief audit and the editorial validator so both gates
apply the same rules.
"""
from __future__ import annotations

import re
from typing import Any


def _text(story: dict[str, Any], *keys: str) -> str:
    return " ".join(str(story.get(k) or "").strip() for k in keys if story.get(k))


def semantic_copy_errors(story: dict[str, Any]) -> list[str]:
    """Return high-confidence semantic/copyediting defects for one story.

    The guard does not attempt open-ended fact checking.  It rejects deterministic
    corruption signatures and entity-type contradictions evidenced inside the
    story/source metadata itself.
    """
    title = str(story.get("title") or "").strip()
    if not title:
        return []

    body_context = _text(
        story, "dek", "summary", "body", "context", "why", "watchNext",
        "sourceName",
    )
    combined = f"{title} {body_context}"
    errors: list[str] = []

    # High-confidence token-splice corruption.  This exact family produced the
    # bad public headline "道瓊斯指數 鍾斯阻鄭嘉如...".
    if re.search(r"道瓊斯指數\s*鍾斯", title):
        errors.append("headline contains corrupted entity splice '道瓊斯指數 鍾斯'")

    # Dow Jones is ambiguous between the publishing company and the market index.
    # When the same story is plainly about WSJ/Dow Jones as employer/publisher or
    # a legal/employment case, translating the entity as an index is a semantic
    # type error rather than a stylistic choice.
    dow_jones_index = bool(re.search(r"(?:道瓊斯(?:工業平均)?指數|Dow\s+Jones\s+(?:Industrial\s+Average|index))", title, re.I))
    publisher_context = bool(re.search(
        r"華爾街日報|Wall\s+Street\s+Journal|Dow\s+Jones\s+Publishing|"
        r"出版(?:公司|商)?|出版社|僱主|僱員|僱傭|解僱|勞資|勞工處|記協|記者協會|記者",
        combined,
        re.I,
    ))
    if dow_jones_index and publisher_context:
        errors.append("Dow Jones is typed as a market index in a publisher/employment/legal context")

    # Generic index/entity sanity check: a financial index cannot itself be an
    # employer, candidate, defendant, person or other actor in employment/legal
    # actions.  Limit this to unmistakable actor verbs to avoid flagging normal
    # market headlines such as '道指受訴訟消息拖累'.
    index_actor = re.search(
        r"(?:道瓊斯(?:工業平均)?指數|恒生指數|標普(?:500)?指數|納斯達克(?:綜合)?指數|"
        r"Nikkei\s*225|日經225指數)\s*(?:公司)?\s*"
        r"(?:解僱|僱用|阻止|禁止|控告|被控|被告|罪成|辭退|聘請|參選|任命|拘捕)",
        title,
        re.I,
    )
    if index_actor:
        errors.append("financial index is used as a human/company legal or employment actor")

    # Obvious duplicated entity fragments caused by translation/concatenation.
    if re.search(r"\b(Dow\s+Jones)\b.{0,8}\b\1\b", title, re.I):
        errors.append("headline contains duplicated Dow Jones entity fragment")

    return errors


def semantic_copy_ok(story: dict[str, Any]) -> bool:
    return not semantic_copy_errors(story)
