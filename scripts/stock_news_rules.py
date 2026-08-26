#!/usr/bin/env python3
"""Shared Stock News matching, trust and event rules.

The rolling collector is deliberately broad, but Stock News must not confuse
short tickers with unrelated entities (for example VT=Virginia Tech or a bad
publisher tag that labels Navitas Semiconductor as NVDA).  The verified
producer imports the same rules so discovery and publication cannot disagree
about ticker identity.
"""
from __future__ import annotations

import re
from typing import Iterable

TRACKED = ("NVDA", "AAPL", "TSM", "PLTR", "MSFT", "GOOG", "EMXC", "EWY", "VT")
ETF_TICKERS = {"EMXC", "EWY", "VT"}

# Ordered patterns intentionally prefer explicit company names / finance-style
# ticker notation.  VT is never accepted as a naked two-letter token.
_PATTERNS = {
    "NVDA": (
        re.compile(r"\bNVIDIA\b", re.I),
        re.compile(r"(?:NASDAQ\s*[:：]\s*NVDA|NVDA\s*[:：]\s*NASDAQ|\$NVDA\b|\(NVDA(?:\.[A-Z]+)?\))", re.I),
        re.compile(r"\bNVDA\b", re.I),
    ),
    "AAPL": (
        re.compile(r"\bApple\b", re.I),
        re.compile(r"(?:NASDAQ\s*[:：]\s*AAPL|AAPL\s*[:：]\s*NASDAQ|\$AAPL\b|\(AAPL(?:\.[A-Z]+)?\))", re.I),
        re.compile(r"\bAAPL\b", re.I),
    ),
    "TSM": (
        re.compile(r"\bTSMC\b|Taiwan Semiconductor|台積電|台積公司|台湾積体電路", re.I),
        re.compile(r"(?:NYSE\s*[:：]\s*TSM|TSM\s*[:：]\s*NYSE|\$TSM\b|\(TSM(?:\.[A-Z]+)?\))", re.I),
    ),
    "PLTR": (
        re.compile(r"\bPalantir\b", re.I),
        re.compile(r"(?:NASDAQ\s*[:：]\s*PLTR|PLTR\s*[:：]\s*NASDAQ|\$PLTR\b|\(PLTR(?:\.[A-Z]+)?\))", re.I),
        re.compile(r"\bPLTR\b", re.I),
    ),
    "MSFT": (
        re.compile(r"\bMicrosoft\b", re.I),
        re.compile(r"(?:NASDAQ\s*[:：]\s*MSFT|MSFT\s*[:：]\s*NASDAQ|\$MSFT\b|\(MSFT(?:\.[A-Z]+)?\))", re.I),
        re.compile(r"\bMSFT\b", re.I),
    ),
    "GOOG": (
        re.compile(r"\bAlphabet\b|\bGoogle\b", re.I),
        re.compile(r"(?:NASDAQ\s*[:：]\s*GOO?GL?|GOO?GL?\s*[:：]\s*NASDAQ|\$GOO?GL?\b|\(GOO?GL?(?:\.[A-Z]+)?\))", re.I),
        re.compile(r"\bGOOG(?:L)?\b", re.I),
    ),
    "EMXC": (
        re.compile(r"\bEMXC\b|iShares MSCI Emerging Markets ex China|Emerging Markets ex China ETF", re.I),
    ),
    "EWY": (
        re.compile(r"\bEWY\b|iShares MSCI South Korea ETF|MSCI South Korea ETF", re.I),
    ),
    "VT": (
        re.compile(r"Vanguard Total World Stock ETF|Vanguard Total World|(?:NYSEARCA\s*[:：]\s*VT|VT\s*[:：]\s*NYSEARCA|\$VT\b)|\bVT\s+ETF\b", re.I),
    ),
}

_FALSE_POSITIVE = {
    "NVDA": (re.compile(r"\bNavitas Semiconductor\b", re.I),),
    "VT": (
        re.compile(r"\bVirginia Tech\b|\bVT\s+(?:game|football|campus|student|Hokies|Blacksburg)\b", re.I),
    ),
}

# Sources that may corroborate an official event.  They never make a raw item
# publishable on their own; the verified producer still requires a primary
# company/IR/regulatory source.
_TRUSTED_SECONDARY = (
    "Reuters", "Associated Press", "AP News", "Bloomberg", "Financial Times",
    "The Wall Street Journal", "Wall Street Journal", "CNBC", "MarketWatch",
    "Nikkei Asia", "Nikkei", "BBC", "The Guardian",
)

# Explicitly low-signal/analysis/social sources.  Keep them in discovery for
# breadth, but never use them as automatic verification evidence.
_BLOCKED_AUTO_SOURCES = (
    "Moomoo", "Stocktwits", "The Motley Fool", "Motley Fool", "GuruFocus",
    "24/7 Wall St", "Seeking Alpha", "Barchart", "FXLeaders", "StartupHub",
    "simplywall", "TradingView",
)

EVENT_PATTERNS = (
    ("earnings", re.compile(r"financial results|quarterly results|earnings|reports? .*quarter|revenue report|results for .*quarter", re.I)),
    ("guidance", re.compile(r"guidance|forecast|outlook", re.I)),
    ("product-event", re.compile(r"apple event|special event|introduc(?:e|es|ed)|unveil(?:s|ed)?|launch(?:es|ed)?|new product|new chip|new model", re.I)),
    ("partnership", re.compile(r"partner(?:s|ship|ed)?|strategic agreement|collaboration|joint venture|investment", re.I)),
    ("regulatory", re.compile(r"SEC\b|antitrust|regulat|court|lawsuit|settlement|investigation|filing", re.I)),
    ("capital", re.compile(r"dividend|buyback|repurchase|share offering|placement|capital expenditure|capex", re.I)),
)


def normalize(value: str | None) -> str:
    return " ".join(str(value or "").split())


def _finance_context(text: str) -> bool:
    return bool(re.search(
        r"\b(stock|shares?|earnings|revenue|guidance|analyst|NASDAQ|NYSE|ETF|investor|market|quarter|SEC|AI|chip|cloud|product|event)\b|股|財報|營收|業績|投資",
        text,
        re.I,
    ))


def match_tickers(title: str, source: str = "", query: str = "") -> list[str]:
    text = normalize(f"{title} {source}")
    found: list[str] = []
    for ticker in TRACKED:
        if any(pattern.search(text) for pattern in _FALSE_POSITIVE.get(ticker, ())):
            # A false-positive exclusion can be overridden only by the canonical
            # company/fund name also being present.
            canonical_override = {
                "NVDA": re.search(r"\bNVIDIA\b", text, re.I),
                "VT": re.search(r"Vanguard Total World", text, re.I),
            }.get(ticker)
            if not canonical_override:
                continue
        if any(pattern.search(text) for pattern in _PATTERNS[ticker]):
            # Short finance tickers are accepted only in a finance/news context.
            if ticker in {"NVDA", "AAPL", "PLTR", "MSFT", "GOOG", "EMXC", "EWY"}:
                has_name = bool(_PATTERNS[ticker][0].search(text))
                if not has_name and not _finance_context(text + " " + normalize(query)):
                    continue
            found.append(ticker)
    return found


def candidate_is_stock_relevant(title: str, source: str = "", query: str = "") -> bool:
    return bool(match_tickers(title, source, query))


def is_trusted_secondary(source: str) -> bool:
    name = normalize(source).lower()
    if any(blocked.lower() in name for blocked in _BLOCKED_AUTO_SOURCES):
        return False
    return any(trusted.lower() in name for trusted in _TRUSTED_SECONDARY)


def classify_event(*values: str) -> str | None:
    text = " ".join(normalize(value) for value in values if value)
    for label, pattern in EVENT_PATTERNS:
        if pattern.search(text):
            return label
    return None


def token_set(value: str) -> set[str]:
    return {
        token.lower()
        for token in re.findall(r"[A-Za-z0-9]{3,}|[\u3400-\u9fff]{2,}", normalize(value))
        if token.lower() not in {"the", "and", "for", "with", "from", "that", "this", "inc", "corp", "corporation"}
    }


def overlap_score(a: str, b: str) -> float:
    left, right = token_set(a), token_set(b)
    if not left or not right:
        return 0.0
    return len(left & right) / max(1, min(len(left), len(right)))


def best_corroboration(ticker: str, official_text: str, candidates: Iterable[dict]) -> dict | None:
    event = classify_event(official_text)
    ranked: list[tuple[float, dict]] = []
    for candidate in candidates:
        if not isinstance(candidate, dict):
            continue
        if ticker not in match_tickers(candidate.get("title", ""), candidate.get("source", ""), candidate.get("query", "")):
            continue
        if not is_trusted_secondary(candidate.get("source", "")):
            continue
        candidate_event = classify_event(candidate.get("title", ""), candidate.get("query", ""))
        score = overlap_score(official_text, candidate.get("title", ""))
        if event and candidate_event == event:
            score += 0.35
        if score >= 0.45:
            ranked.append((score, candidate))
    ranked.sort(key=lambda item: item[0], reverse=True)
    return ranked[0][1] if ranked else None
