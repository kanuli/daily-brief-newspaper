#!/usr/bin/env python3
"""Shared Stock News matching, trust and event rules.

The rolling collector is deliberately broad, but Stock News must not confuse
short tickers with unrelated entities. The verified producer imports the same
rules so discovery and publication cannot disagree about ticker identity.
"""
from __future__ import annotations

import re
from typing import Iterable

TRACKED = (
    "GOOG", "GLDM", "ICE", "MCD", "EMXC", "GBTC", "DBA", "AAPL", "EWY",
    "META", "MSFT", "NVDA", "TSM", "PLTR", "VT",
)
ETF_TICKERS = {"GLDM", "EMXC", "GBTC", "DBA", "EWY", "VT"}

_PATTERNS = {
    "GOOG": (
        re.compile(r"\bAlphabet\b|\bGoogle\b", re.I),
        re.compile(r"(?:NASDAQ\s*[:：]\s*GOO?GL?|GOO?GL?\s*[:：]\s*NASDAQ|\$GOO?GL?\b|\(GOO?GL?(?:\.[A-Z]+)?\))", re.I),
        re.compile(r"\bGOOG(?:L)?\b", re.I),
    ),
    "GLDM": (
        re.compile(r"SPDR\s+Gold\s+MiniShares(?:\s+Trust)?|Gold\s+MiniShares", re.I),
        re.compile(r"(?:NYSEARCA\s*[:：]\s*GLDM|GLDM\s*[:：]\s*NYSEARCA|\$GLDM\b|\bGLDM\s+ETF\b|\(GLDM(?:\.[A-Z]+)?\))", re.I),
    ),
    "ICE": (
        re.compile(r"\bIntercontinental Exchange\b", re.I),
        re.compile(r"(?:NYSE\s*[:：]\s*ICE|ICE\s*[:：]\s*NYSE|\$ICE\b|\(ICE(?:\.[A-Z]+)?\))", re.I),
    ),
    "MCD": (
        re.compile(r"\bMcDonald(?:'|’)s\b|\bMcDonalds\b", re.I),
        re.compile(r"(?:NYSE\s*[:：]\s*MCD|MCD\s*[:：]\s*NYSE|\$MCD\b|\(MCD(?:\.[A-Z]+)?\)|\bMCD\b)", re.I),
    ),
    "EMXC": (
        re.compile(r"iShares MSCI Emerging Markets ex China|Emerging Markets ex China ETF", re.I),
        re.compile(r"(?:NASDAQ\s*[:：]\s*EMXC|EMXC\s*[:：]\s*NASDAQ|\$EMXC\b|\bEMXC\s+ETF\b|\(EMXC(?:\.[A-Z]+)?\)|\bEMXC\b)", re.I),
    ),
    "GBTC": (
        re.compile(r"\bGrayscale Bitcoin Trust\b", re.I),
        re.compile(r"(?:NYSEARCA\s*[:：]\s*GBTC|GBTC\s*[:：]\s*NYSEARCA|\$GBTC\b|\bGBTC\s+(?:ETF|trust)\b|\(GBTC(?:\.[A-Z]+)?\)|\bGBTC\b)", re.I),
    ),
    "DBA": (
        re.compile(r"\bInvesco DB Agriculture Fund\b|DB Agriculture Fund", re.I),
        re.compile(r"(?:NYSEARCA\s*[:：]\s*DBA|DBA\s*[:：]\s*NYSEARCA|\$DBA\b|\bDBA\s+ETF\b|\(DBA(?:\.[A-Z]+)?\))", re.I),
    ),
    "AAPL": (
        re.compile(r"\bApple\b", re.I),
        re.compile(r"(?:NASDAQ\s*[:：]\s*AAPL|AAPL\s*[:：]\s*NASDAQ|\$AAPL\b|\(AAPL(?:\.[A-Z]+)?\))", re.I),
        re.compile(r"\bAAPL\b", re.I),
    ),
    "EWY": (
        re.compile(r"iShares MSCI South Korea ETF|MSCI South Korea ETF", re.I),
        re.compile(r"(?:NYSEARCA\s*[:：]\s*EWY|EWY\s*[:：]\s*NYSEARCA|\$EWY\b|\bEWY\s+ETF\b|\(EWY(?:\.[A-Z]+)?\)|\bEWY\b)", re.I),
    ),
    "META": (
        re.compile(r"\bMeta Platforms\b|\bMeta\b", re.I),
        re.compile(r"(?:NASDAQ\s*[:：]\s*META|META\s*[:：]\s*NASDAQ|\$META\b|\(META(?:\.[A-Z]+)?\)|\bMETA\b)", re.I),
    ),
    "MSFT": (
        re.compile(r"\bMicrosoft\b", re.I),
        re.compile(r"(?:NASDAQ\s*[:：]\s*MSFT|MSFT\s*[:：]\s*NASDAQ|\$MSFT\b|\(MSFT(?:\.[A-Z]+)?\))", re.I),
        re.compile(r"\bMSFT\b", re.I),
    ),
    "NVDA": (
        re.compile(r"\bNVIDIA\b", re.I),
        re.compile(r"(?:NASDAQ\s*[:：]\s*NVDA|NVDA\s*[:：]\s*NASDAQ|\$NVDA\b|\(NVDA(?:\.[A-Z]+)?\))", re.I),
        re.compile(r"\bNVDA\b", re.I),
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
    "VT": (
        re.compile(r"Vanguard Total World Stock ETF|Vanguard Total World", re.I),
        re.compile(r"(?:NYSEARCA\s*[:：]\s*VT|VT\s*[:：]\s*NYSEARCA|\$VT\b)|\bVT\s+ETF\b", re.I),
    ),
}

_FALSE_POSITIVE = {
    "NVDA": (re.compile(r"\bNavitas Semiconductor\b", re.I),),
    "VT": (
        re.compile(r"\bVirginia Tech\b|\bVT\s+(?:game|football|campus|student|Hokies|Blacksburg)\b", re.I),
    ),
}

_TRUSTED_SECONDARY = (
    "Reuters", "Associated Press", "AP News", "Bloomberg", "Financial Times",
    "The Wall Street Journal", "Wall Street Journal", "CNBC", "MarketWatch",
    "Nikkei Asia", "Nikkei", "BBC", "The Guardian",
)

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
        r"\b(stock|shares?|earnings|revenue|guidance|analyst|NASDAQ|NYSE|NYSEARCA|ETF|trust|fund|investor|market|quarter|SEC|AI|chip|cloud|product|event|gold|bitcoin|crypto|agriculture|commodity|index)\b|股|財報|營收|業績|投資|黃金|比特幣|商品|基金",
        text,
        re.I,
    ))


def match_tickers(title: str, source: str = "", query: str = "") -> list[str]:
    text = normalize(f"{title} {source}")
    found: list[str] = []
    for ticker in TRACKED:
        if any(pattern.search(text) for pattern in _FALSE_POSITIVE.get(ticker, ())):
            canonical_override = {
                "NVDA": re.search(r"\bNVIDIA\b", text, re.I),
                "VT": re.search(r"Vanguard Total World", text, re.I),
            }.get(ticker)
            if not canonical_override:
                continue
        patterns = _PATTERNS[ticker]
        if any(pattern.search(text) for pattern in patterns):
            has_name = bool(patterns[0].search(text))
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
