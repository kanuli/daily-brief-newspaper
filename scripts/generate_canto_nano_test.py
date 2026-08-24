#!/usr/bin/env python3
"""Generate fixed public listening samples for canto-tts-nano-v1."""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from canto_tts import CantoTTS

OUT = Path("audio/canto-nano-test")
OUT.mkdir(parents=True, exist_ok=True)

SAMPLES = [
    (
        "sample-short",
        "短句",
        "大家好，呢度係香港廣東話新聞語音測試。",
    ),
    (
        "sample-news",
        "一般新聞句",
        "香港天文台今日下午表示，本港部分地區錄得超過三十毫米雨量，提醒市民外出時留意天氣變化。",
    ),
    (
        "sample-numbers",
        "新聞長句／數字",
        "加拿大政府宣布，九月八日起對部分美國商品實施對等關稅措施，市場正關注下一輪貿易談判會否重啟，以及相關措施對消費者物價嘅影響。",
    ),
]


def main() -> int:
    tts = CantoTTS()
    manifest = {
        "model": "typangaa/canto-tts-nano",
        "engine": "canto-tts-nano-v1",
        "language": "yue-HK",
        "quality": "duration_filter",
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "samples": [],
    }
    for sample_id, label, text in SAMPLES:
        out = OUT / f"{sample_id}.wav"
        print(f"Generating {sample_id}: {text}", flush=True)
        tts.synthesize(text, str(out), quality="duration_filter", max_attempts=3)
        if not out.is_file() or out.stat().st_size < 50000:
            raise RuntimeError(f"invalid output: {out}")
        manifest["samples"].append({
            "id": sample_id,
            "label": label,
            "text": text,
            "audio": str(out).replace("\\", "/"),
            "bytes": out.stat().st_size,
        })
    (OUT / "manifest.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print("CANTO_NANO_TEST_GENERATION_OK", len(SAMPLES))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
