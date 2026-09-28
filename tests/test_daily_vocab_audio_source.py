#!/usr/bin/env python3
import json
import re
import ssl
import unittest
from pathlib import Path
from urllib.parse import quote, urljoin
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
DAILY_JS = ROOT / "assets/js/daily-extras.js"
CENTRAL_RESOLVER = "https://raw.githubusercontent.com/kanuli/japanese-vocab-game/main/wordaudio-delta-voices.js"
ENGINE = "supertonic3"
VOICE = "F1"
CASES = (
    ("早足", "はやあし"),
    ("四月", "しがつ"),
    ("そのまま", "そのまま"),
)


def fetch(url: str, *, timeout: int = 20) -> tuple[bytes, dict[str, str], int]:
    req = Request(url, headers={"User-Agent": "daily-brief-vocab-audio-regression/1.0", "Cache-Control": "no-cache"})
    with urlopen(req, timeout=timeout, context=ssl.create_default_context()) as res:
        body = res.read()
        return body, {k.lower(): v for k, v in res.headers.items()}, res.status


def central_config() -> tuple[str, str]:
    body, _, status = fetch(CENTRAL_RESOLVER)
    assert status == 200
    source = body.decode("utf-8")
    match = re.search(r"\bNAS_BASE\s*=\s*['\"]([^'\"]+)['\"]", source)
    assert match, "central resolver no longer exposes NAS_BASE"
    assert re.search(r"primary\s*:\s*true", source), "central resolver is no longer NAS-primary"
    assert re.search(r"playNas\s*\(", source), "central resolver no longer uses playNas"
    return match.group(1).rstrip("/"), source


def select_result(payload: dict, written: str, reading: str) -> dict | None:
    rows = payload.get("results") if isinstance(payload, dict) else None
    rows = rows if isinstance(rows, list) else []
    for row in rows:
        if str(row.get("word", "")) == written and str(row.get("reading", "")) == reading:
            return row
    for row in rows:
        if str(row.get("reading", "")) == reading:
            return row
    return rows[0] if rows else None


class DailyVocabAudioSourceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.js = DAILY_JS.read_text(encoding="utf-8")
        cls.api_base, cls.central_source = central_config()

    def test_daily_uses_central_production_resolver_and_no_local_range_mapping(self):
        self.assertIn("japanese-vocab-game/main", self.js)
        self.assertIn("wordaudio-delta-voices.js", self.js)
        self.assertIn("/api/v1/vocabulary/", self.js)
        self.assertIn('PRODUCTION_ENGINE = "supertonic3"', self.js)
        self.assertIn('PRODUCTION_VOICE = "F1"', self.js)
        self.assertIn('cache: "no-store"', self.js)
        for stale in (
            "ST3_LAYERS",
            "word-supertonic3-runtime-delta-catalog.json",
            "word-supertonic3-delta-catalog.json",
            "word-supertonic3-catalog.json",
            "findF1Recording",
            "rangeBytes",
            "Range: `bytes=",
            "offset + size - 1",
        ):
            self.assertNotIn(stale, self.js, f"stale independent Daily-Brief mapping remains: {stale}")

    def _assert_case(self, written: str, reading: str):
        lookup = f"{self.api_base}/api/v1/vocabulary/{quote(written)}?engine={ENGINE}&voice={VOICE}"
        body, _, status = fetch(lookup)
        self.assertEqual(status, 200, lookup)
        payload = json.loads(body.decode("utf-8"))
        row = select_result(payload, written, reading)
        self.assertIsNotNone(row, f"central production record missing: {written}|{reading}")
        self.assertEqual(str(row.get("reading", "")), reading)
        audios = row.get("audios") if isinstance(row.get("audios"), list) else []
        asset = next((a for a in audios if a.get("engine") == ENGINE and a.get("voice") == VOICE), None)
        self.assertIsNotNone(asset, f"central F1 asset missing: {written}|{reading}")
        audio_url = str(asset.get("audio_url", ""))
        self.assertTrue(audio_url, f"central F1 audio_url missing: {written}|{reading}")
        if not re.match(r"^https?://", audio_url, re.I):
            audio_url = urljoin(self.api_base + "/", audio_url)
        audio, headers, audio_status = fetch(audio_url)
        self.assertEqual(audio_status, 200, audio_url)
        self.assertGreater(len(audio), 0, f"empty central F1 audio: {written}|{reading}")
        if headers.get("content-length"):
            self.assertEqual(len(audio), int(headers["content-length"]), f"incomplete central audio response: {written}|{reading}")
        return row, asset, audio_url, len(audio)

    def test_hayaashi_matches_central_production_record(self):
        self._assert_case("早足", "はやあし")

    def test_shigatsu_matches_central_production_record(self):
        self._assert_case("四月", "しがつ")

    def test_sonomama_follows_central_record_without_local_repair(self):
        self._assert_case("そのまま", "そのまま")
        self.assertNotRegex(self.js, r"そのまま.*(?:override|patch|replace|audio)")


if __name__ == "__main__":
    unittest.main(verbosity=2)
