#!/usr/bin/env python3
import json
import re
import ssl
import time
import unicodedata
import unittest
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urljoin
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
DAILY_JS = ROOT / "assets/js/daily-extras.js"
CENTRAL_ROOT = "https://kanuli.github.io/japanese-vocab-game/"
CENTRAL_WORDLIST = urljoin(CENTRAL_ROOT, "wordlist.html")
ENGINE = "supertonic3"
VOICE = "F1"
CASES = (
    ("早足", "はやあし"),
    ("四月", "しがつ"),
    ("そのまま", "そのまま"),
)


def request(url: str, *, headers=None, timeout=45):
    merged = {
        "User-Agent": "daily-brief-vocab-audio-regression/2.0",
        "Cache-Control": "no-cache",
        "Pragma": "no-cache",
    }
    if headers:
        merged.update(headers)
    return Request(url, headers=merged)


def fetch_bytes(url: str, *, headers=None, timeout=45):
    with urlopen(request(url, headers=headers), timeout=timeout, context=ssl.create_default_context()) as res:
        body = res.read()
        return body, {k.lower(): v for k, v in res.headers.items()}, res.status, res.geturl()


def fetch_text(url: str):
    body, _, status, _ = fetch_bytes(url)
    if status != 200:
        raise AssertionError(f"HTTP {status}: {url}")
    return body.decode("utf-8")


def fetch_json(url: str):
    return json.loads(fetch_text(url))


def normalize_reading(value: str) -> str:
    text = unicodedata.normalize("NFKC", str(value or ""))
    text = "".join(chr(ord(ch) - 0x60) if "ァ" <= ch <= "ヶ" else ch for ch in text)
    return re.sub(r"\s+", "", text)


def find_script_url(html: str, filename: str) -> str:
    match = re.search(rf'<script[^>]+src=["\']([^"\']*{re.escape(filename)}[^"\']*)["\']', html, re.I)
    if not match:
        raise AssertionError(f"central wordlist no longer loads {filename}")
    return urljoin(CENTRAL_ROOT, match.group(1))


def parse_delta_catalog_paths(source: str):
    block = re.search(r"supertonic3\s*:\s*\[([^\]]+)\]", source, re.S)
    if not block:
        raise AssertionError("cannot parse central Supertonic 3 delta catalog precedence")
    paths = re.findall(r"['\"]([^'\"]+\.json(?:\?[^'\"]*)?)['\"]", block.group(1))
    if not paths:
        raise AssertionError("central Supertonic 3 delta catalog list is empty")
    return paths


def parse_base_catalog_path(source: str):
    match = re.search(r"supertonic3\s*:\s*\{.*?\bcatalog\s*:\s*['\"]([^'\"]+)['\"]", source, re.S)
    if not match:
        raise AssertionError("cannot parse central Supertonic 3 base catalog")
    return match.group(1)


def lookup_word(catalog: dict, written: str, reading: str):
    words = catalog.get("words") if isinstance(catalog, dict) else None
    if not isinstance(words, dict):
        return None, None
    exact = f"{reading}|{written}"
    if exact in words:
        return exact, words[exact]
    wanted = normalize_reading(reading)
    for key, value in words.items():
        source_reading = str(key).split("|", 1)[0]
        if normalize_reading(source_reading) == wanted:
            return key, value
    return None, None


def first_json(urls):
    errors = []
    for url in urls:
        if not url:
            continue
        absolute = urljoin(CENTRAL_ROOT, url)
        try:
            return fetch_json(absolute), absolute
        except Exception as exc:
            errors.append(f"{absolute}: {exc}")
    raise AssertionError("all authoritative index URLs failed: " + " | ".join(errors))


def fetch_exact_range(urls, offset: int, size: int):
    end = offset + size - 1
    errors = []
    for candidate in urls:
        if not candidate:
            continue
        url = urljoin(CENTRAL_ROOT, candidate)
        try:
            req = request(url, headers={"Range": f"bytes={offset}-{end}"})
            with urlopen(req, timeout=45, context=ssl.create_default_context()) as res:
                headers = {k.lower(): v for k, v in res.headers.items()}
                status = res.status
                content_length = headers.get("content-length")
                if status == 200 and content_length and int(content_length) != size:
                    raise AssertionError(f"server ignored Range and returned {content_length} bytes")
                body = res.read(size + 1)
                if status not in (200, 206):
                    raise AssertionError(f"HTTP {status}")
                if len(body) != size:
                    raise AssertionError(f"expected {size} bytes, received {len(body)}")
                if status == 206:
                    content_range = headers.get("content-range", "")
                    match = re.fullmatch(r"bytes\s+(\d+)-(\d+)/(\d+|\*)", content_range)
                    if not match:
                        raise AssertionError(f"invalid Content-Range: {content_range!r}")
                    start_seen, end_seen, total = match.groups()
                    if int(start_seen) != offset or int(end_seen) != end:
                        raise AssertionError(f"Content-Range mismatch: {content_range}")
                    if total != "*" and end >= int(total):
                        raise AssertionError(f"range exceeds source asset bounds: {content_range}")
                return body, url, status, headers
        except (HTTPError, URLError, OSError, AssertionError) as exc:
            errors.append(f"{url}: {exc}")
    raise AssertionError("all authoritative packed assets failed: " + " | ".join(errors))


class DailyVocabAudioSourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.js = DAILY_JS.read_text(encoding="utf-8")
        cache_buster = int(time.time())
        cls.wordlist_html = fetch_text(f"{CENTRAL_WORDLIST}?daily-brief-regression={cache_buster}")
        cls.delta_url = find_script_url(cls.wordlist_html, "wordaudio-delta-voices.js")
        cls.base_url = find_script_url(cls.wordlist_html, "wordaudio-multivoice.js")
        cls.delta_source = fetch_text(cls.delta_url)
        cls.base_source = fetch_text(cls.base_url)

        catalog_paths = parse_delta_catalog_paths(cls.delta_source)
        catalog_paths.append(parse_base_catalog_path(cls.base_source))
        cls.catalogs = []
        cls.catalog_errors = []
        for path in catalog_paths:
            url = urljoin(CENTRAL_ROOT, path)
            try:
                payload = fetch_json(url)
                cls.catalogs.append((url, payload))
            except Exception as exc:
                # Production resolver intentionally continues through its
                # precedence chain when one optional delta layer is unavailable.
                cls.catalog_errors.append(f"{url}: {exc}")
        if not cls.catalogs:
            raise AssertionError("no authoritative japanese-vocab-game catalog could be loaded")
        cls.index_cache = {}
        cls.records = {}

    def test_daily_delegates_to_exact_central_wordlist_runtime(self):
        self.assertIn('CENTRAL_WORDLIST_URL = "https://kanuli.github.io/japanese-vocab-game/wordlist.html"', self.js)
        self.assertIn('typeof win.WA.speak === "function"', self.js)
        self.assertIn("win.JAPANESE_NAS_AUDIO?.primary === true", self.js)
        self.assertIn("await win.WA.speak(reading", self.js)
        self.assertIn('PRODUCTION_ENGINE = "supertonic3"', self.js)
        self.assertIn('PRODUCTION_VOICE = "F1"', self.js)
        self.assertIn("Date.now()", self.js, "central wordlist HTML must be cache-busted automatically")
        for stale in (
            "raw.githubusercontent.com/kanuli/japanese-vocab-game/main",
            "/api/v1/vocabulary/",
            "word-supertonic3-runtime-delta-catalog.json",
            "word-supertonic3-delta-catalog.json",
            "word-supertonic3-catalog.json",
            "ST3_LAYERS",
            "findF1Recording",
            "rangeBytes",
            "Range: `bytes=",
        ):
            self.assertNotIn(stale, self.js, f"independent Daily-Brief audio resolver remains: {stale}")
        for written, _ in CASES:
            self.assertNotIn(written, self.js, f"word-specific Daily-Brief audio hack found: {written}")

    def test_central_runtime_keeps_nas_primary_and_hosted_fallback(self):
        self.assertRegex(self.delta_source, r"\bplayNas\s*\(")
        self.assertRegex(self.delta_source, r"primary\s*:\s*true")
        self.assertIn("baseSpeak", self.delta_source)
        self.assertGreaterEqual(len(parse_delta_catalog_paths(self.delta_source)), 2)

    def test_central_range_semantics_are_inclusive_and_size_checked(self):
        for source in (self.delta_source, self.base_source):
            self.assertRegex(source, r"offset\s*\+\s*size\s*-\s*1")
            self.assertRegex(source, r"Range\s*:\s*`bytes=\$\{offset\}-\$\{end\}`")
            self.assertRegex(source, r"byteLength\s*!==\s*size")

    @classmethod
    def resolve_authoritative_f1(cls, written: str, reading: str):
        cache_key = (written, reading)
        if cache_key in cls.records:
            return cls.records[cache_key]

        for catalog_url, catalog in cls.catalogs:
            if str(catalog.get("status", "ready")) not in ("", "ready"):
                continue
            voices = catalog.get("voices") or catalog.get("speakers") or {}
            if not isinstance(voices, dict) or VOICE not in voices:
                continue
            key, lookup = lookup_word(catalog, written, reading)
            if key is None or not isinstance(lookup, (list, tuple)) or len(lookup) < 2:
                continue

            voice_meta = voices[VOICE]
            index_urls = [
                voice_meta.get("indexGithubUrl"),
                voice_meta.get("indexUrl"),
                voice_meta.get("indexHfUrl"),
            ]
            index_key = tuple(url for url in index_urls if url)
            if index_key not in cls.index_cache:
                cls.index_cache[index_key] = first_json(index_urls)
            index, index_url = cls.index_cache[index_key]

            member_id, shard = lookup[0], lookup[1]
            bundles = index.get("bundles") if isinstance(index, dict) else None
            bundle = bundles.get(str(shard)) if isinstance(bundles, dict) else None
            if not isinstance(bundle, dict):
                continue
            members = bundle.get("members")
            member = members.get(str(member_id)) if isinstance(members, dict) else None
            if not isinstance(member, (list, tuple)) or len(member) < 2:
                continue
            offset, size = int(member[0]), int(member[1])
            if offset < 0 or size <= 0:
                raise AssertionError(f"invalid central range for {written}|{reading}: {member}")

            asset_urls = [bundle.get("githubUrl"), bundle.get("hfUrl"), bundle.get("url")]
            body, asset_url, status, headers = fetch_exact_range(asset_urls, offset, size)
            record = {
                "catalog_url": catalog_url,
                "catalog_key": key,
                "index_url": index_url,
                "asset_url": asset_url,
                "offset": offset,
                "size": size,
                "end": offset + size - 1,
                "status": status,
                "headers": headers,
                "body": body,
            }
            cls.records[cache_key] = record
            return record

        raise AssertionError(
            f"authoritative F1 record not found for {written}|{reading}; "
            f"catalog errors={cls.catalog_errors}"
        )

    def assert_authoritative_case(self, written: str, reading: str):
        record = self.resolve_authoritative_f1(written, reading)
        self.assertGreater(record["size"], 0)
        self.assertEqual(record["end"], record["offset"] + record["size"] - 1)
        self.assertEqual(len(record["body"]), record["size"])
        body = record["body"]
        looks_like_mp3 = body.startswith(b"ID3") or (len(body) >= 2 and body[0] == 0xFF and (body[1] & 0xE0) == 0xE0)
        self.assertTrue(looks_like_mp3, f"central segment does not start at an MP3 boundary: {written}|{reading}")
        return record

    def test_hayaashi_authoritative_f1_record_is_complete(self):
        self.assert_authoritative_case("早足", "はやあし")

    def test_shigatsu_authoritative_f1_record_is_complete(self):
        self.assert_authoritative_case("四月", "しがつ")

    def test_sonomama_follows_same_central_record_without_local_repair(self):
        self.assert_authoritative_case("そのまま", "そのまま")
        self.assertNotRegex(self.js, r"そのまま.*(?:override|patch|replace|audio)")


if __name__ == "__main__":
    unittest.main(verbosity=2)