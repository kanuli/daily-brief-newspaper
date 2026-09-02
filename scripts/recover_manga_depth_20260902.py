#!/usr/bin/env python3
import json
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DESK = ROOT / "data" / "desk-latest.json"
HKT = timezone(timedelta(hours=8))

RECOVERY_STORY = {
  "id": "manga-anime-victoria-season2-special-20260902-depth",
  "desk": "manga-anime",
  "deskSlugs": ["manga-anime"],
  "section": "漫畫／Anime｜新作／續篇",
  "sectionLabel": "漫畫／動畫",
  "mediaLabel": "漫畫 / Anime",
  "status": "LATEST",
  "title": "《手札が多めのビクトリア》宣布製作第2期及新作特別篇　9月8日另播總集篇",
  "dek": "第一期9月1日深夜播畢後，製作方公布第2期與新作特別篇同步製作，並公開新視覺。",
  "summary": "電視動畫《手札が多めのビクトリア》在第一期最終話播出後宣布製作第2期及新作特別篇；9月8日深夜亦會播放回顧第一期的總集篇《これまでとこれから》。",
  "body": "電視動畫《手札が多めのビクトリア》第一期在9月1日深夜播出最終話後，製作方隨即公布新作特別篇及第2期製作決定，並公開以ビクトリア、ノンナ及ジェフリー為主角的新視覺。現階段尚未公布第2期或新作特別篇的正式播出日期。\n\n日本動畫媒體MANTANWEB與ORICON均在9月2日凌晨報道同一項正式發表。另於9月8日深夜0時30分，東京電視台系列將播放總集篇《これまでとこれから》，回顧三名主要角色由相遇、分離到重新組成家人的故事線。",
  "context": "作品改編自守雨的輕小說，由Studio DEEN製作；第一期自7月起在東京電視台系列播出，9月1日完成首季播映。",
  "why": "第2期與新作特別篇同時落實，代表作品在首季完結後立即延續動畫企劃，屬新的正式製作決定而非傳聞或舊消息重寫。",
  "watchNext": "留意製作方公布第2期與特別篇的播出時間、製作陣容及後續宣傳片，以及9月8日總集篇是否帶來更多新情報。",
  "sourceName": "ORICON NEWS／MANTANWEB",
  "sourceUrl": "https://www.oricon.co.jp/news/2477608/full/",
  "timeLabel": "9月2日12:00 HKT前核實",
  "sources": [
    {"name": "ORICON NEWS", "url": "https://www.oricon.co.jp/news/2477608/full/"},
    {"name": "MANTANWEB", "url": "https://mantan-web.jp/article/20260901dog00m200045000a.html"}
  ],
  "image": None
}


def story_date(story):
    sid = str(story.get("id") or "")
    m = re.search(r"(20\d{6})", sid)
    if not m:
        return None
    try:
        return datetime.strptime(m.group(1), "%Y%m%d").date()
    except ValueError:
        return None


def main():
    data = json.loads(DESK.read_text(encoding="utf-8"))
    if data.get("editorialStandardVersion") != 3 or data.get("contentVersion") != 3:
        raise SystemExit("desk-latest version mismatch")

    desks = data.setdefault("desks", {})
    manga = [s for s in desks.setdefault("manga-anime", []) if isinstance(s, dict)]

    # At 2 Sep HKT noon, every 30 Aug Manga/Anime item is outside the allowed
    # roughly-48-hour low-volume retention window. Do not let stale retained
    # stories satisfy the depth floor.
    cutoff_date = datetime(2026, 8, 31, tzinfo=HKT).date()
    kept = [s for s in manga if not (story_date(s) and story_date(s) < cutoff_date)]

    # Exact-ID/title dedupe after retention pruning. Current Sep 1-2 entries are
    # distinct events; the recovery story is a separate formal sequel decision.
    out, seen_ids, seen_titles = [], set(), set()
    for s in kept:
        sid = str(s.get("id") or "").strip()
        title = re.sub(r"\s+", " ", str(s.get("title") or "")).strip().casefold()
        if (sid and sid in seen_ids) or (title and title in seen_titles):
            continue
        if sid:
            seen_ids.add(sid)
        if title:
            seen_titles.add(title)
        out.append(s)

    if len(out) < 4:
        out.insert(0, RECOVERY_STORY)

    # Re-dedupe and enforce the hard floor without touching Live.
    final, seen_ids, seen_titles = [], set(), set()
    for s in out:
        sid = str(s.get("id") or "").strip()
        title = re.sub(r"\s+", " ", str(s.get("title") or "")).strip().casefold()
        if (sid and sid in seen_ids) or (title and title in seen_titles):
            continue
        if sid:
            seen_ids.add(sid)
        if title:
            seen_titles.add(title)
        final.append(s)

    if len(final) < 4:
        raise SystemExit(f"Manga/Anime current unique depth unresolved: {len(final)}/4")

    desks["manga-anime"] = final
    data["generatedAt"] = datetime.now(HKT).replace(microsecond=0).isoformat()
    DESK.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"MANGA_DEPTH_RECOVERY_PASS current_unique={len(final)} floor=4")


if __name__ == "__main__":
    main()
