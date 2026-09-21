#!/usr/bin/env python3
"""Recover stale public desks with curated, source-backed current stories.

The helper is deliberately conservative: it never rewrites timestamps and it
never promotes a recovery story after that story has exceeded the desk's real
freshness SLA.  An expired fallback is skipped instead of aborting the whole
Live repair chain, so one specialist desk cannot block unrelated recovery.
"""
from __future__ import annotations

import datetime as dt
import json
import os
import tempfile
from pathlib import Path
from typing import Any

from desk_freshness_policy import PUBLIC_DESK_FRESHNESS_HOURS, editorial_story_time

ROOT = Path(__file__).resolve().parents[1]
DESK_PATH = ROOT / "data" / "desk-latest.json"
HKT = dt.timezone(dt.timedelta(hours=8))

# These are editorially verified emergency fallbacks, not a substitute for the
# normal newsroom producer.  Keep genuine publication timestamps: freshness is
# proved from the source event/report time, never from the recovery run time.
RECOVERY_POOL: dict[str, list[dict[str, Any]]] = {
    "manga-anime": [
        {
            "id": "manga-anime-rayearth-kyomaf-pv2-two-cours-20260921",
            "desk": "manga-anime",
            "deskSlugs": ["manga-anime"],
            "section": "漫畫／動畫｜《魔法騎士雷阿斯》",
            "sectionLabel": "漫畫／動畫",
            "status": "LATEST",
            "title": "《魔法騎士雷阿斯》京まふ公開第二彈主PV　確認連續兩季播出",
            "dek": "官方在京都國際漫畫動畫展公開第二彈主PV及主題曲資訊；新作10月7日起在朝日電視台系播出，並採連續兩季安排。",
            "summary": "《魔法騎士雷阿斯》官方9月21日發布京まふ活動報告，確認現場公開第二彈主PV及OP、ED資訊；ORICON同日報道主要聲優登台介紹最新動畫消息。",
            "body": "電視動畫《魔法騎士雷阿斯》官方網站9月21日發布京都國際漫畫動畫展2026舞台活動報告。獅堂光、龍咲海、鳳凰寺風及克雷夫的聲優佐倉綾音、大久保瑠美、高橋李依及梶裕貴登台，現場公開第二彈主PV，以及片頭、片尾主題曲資訊。官方前一日亦確認作品會由10月7日起逢星期三晚上11時45分在朝日電視台系全國網絡播出，並採連續兩季安排。\n\nORICON於9月21日12時50分（日本時間）報道同一舞台活動，確認四名聲優出席並介紹最新動畫資訊。今次更新包括新的宣傳影片、主題曲及播出安排，屬作品正式發布的新進展，而非舊聞重新包裝。",
            "context": "新版《魔法騎士雷阿斯》改編自CLAMP同名漫畫，官方已公布10月7日起在日本播出；今次京まふ舞台進一步補充宣傳影片、音樂及播出期數資訊。",
            "why": "官方在正式播出前數周公布新的PV、主題曲及連續兩季安排，直接影響觀眾對作品製作及播出規模的預期，屬漫畫／動畫版的當日有效更新。",
            "watchNext": "留意10月7日首播前是否再公布配信平台、追加宣傳片及其他角色資訊，以及首播後的觀眾與市場反應。",
            "sourceName": "TV動畫《魔法騎士雷阿斯》官方 / ORICON NEWS",
            "sourceUrl": "https://rayearth-anime.com/news/129/",
            "publishedAt": "2026-09-21T12:50:00+09:00",
            "verifiedAt": "2026-09-21T18:13:00+08:00",
            "timeLabel": "2026年9月21日 11:50 HKT報道；18:13 HKT核實",
            "sources": [
                {
                    "name": "TV動畫《魔法騎士雷阿斯》官方 — 京まふ2026特別舞台活動報告",
                    "url": "https://rayearth-anime.com/news/129/",
                },
                {
                    "name": "TV動畫《魔法騎士雷阿斯》官方 — 第二彈主PV、主題曲及連續兩季播出",
                    "url": "https://rayearth-anime.com/news/126/",
                },
                {
                    "name": "ORICON NEWS — 《魔法騎士雷阿斯》聲優京まふ活動報道",
                    "url": "https://www.oricon.co.jp/news/2481809/full/",
                },
            ],
        }
    ],
    "hong-kong": [
        {
            "id": "hong-kong-mable-chan-apec-transport-beijing-20260921-1601",
            "desk": "hong-kong",
            "deskSlugs": ["hong-kong"],
            "section": "香港｜運輸／對外交流",
            "sectionLabel": "香港",
            "status": "LATEST",
            "title": "陳美寶周二赴北京出席APEC運輸部長會議　將與民航局交流航空發展",
            "dek": "運輸及物流局局長陳美寶9月22日赴北京出席亞太經合組織運輸部長會議及全球可持續交通高峰論壇，並會拜訪國家民航局。",
            "summary": "香港政府9月21日公布，陳美寶將赴北京出席APEC運輸部長會議並發言，期間與其他與會部長交流，亦會與國家民航局就航空發展交換意見。",
            "body": "香港政府9月21日下午公布，運輸及物流局局長陳美寶將於9月22日上午啓程前往北京，出席同日下午舉行的亞太區經濟合作組織運輸部長會議，以及全球可持續交通高峰論壇。政府表示，陳美寶會在運輸部長會議發言，並與其他與會部長交流共同關注的議題。\n\n陳美寶此行亦會拜訪國家民用航空局，就航空發展交換意見；運輸及物流局常任秘書長丘卓恒和民航處處長黃嘉華會參與相關會面。香港電台其後於16時01分報道有關行程。陳美寶預計9月23日下午返港，離港期間由運輸及物流局副局長廖振新署任局長。",
            "context": "APEC運輸部長會議是區內經濟體就交通、物流及相關政策合作交流的平台。香港亦正推進航空、航運及可持續交通相關政策。",
            "why": "運輸及物流政策涉及香港國際航空及物流樞紐定位；局長在APEC部長級會議發言及與國家民航局會面，屬香港公共政策與對外交流的當日重要發展。",
            "watchNext": "留意會議期間香港提出的交通及物流合作倡議、與國家民航局會面內容，以及會後是否公布新的航空或可持續交通合作安排。",
            "sourceName": "香港特區政府新聞公報 / 香港電台",
            "sourceUrl": "https://www.info.gov.hk/gia/general/202609/21/P2026092100295.htm",
            "publishedAt": "2026-09-21T16:01:00+08:00",
            "verifiedAt": "2026-09-21T18:13:00+08:00",
            "timeLabel": "2026年9月21日 16:01 HKT報道；18:13 HKT核實",
            "sources": [
                {
                    "name": "香港特區政府 — 運輸及物流局局長赴北京出席亞太經合組織運輸部長會議",
                    "url": "https://www.info.gov.hk/gia/general/202609/21/P2026092100295.htm",
                },
                {
                    "name": "香港電台 — 陳美寶明赴北京出席亞太區經濟合作組織運輸部長會議",
                    "url": "https://news.rthk.hk/rthk/ch/component/k2/1870946-20260921.htm",
                },
            ],
        }
    ],
}


def newest_age_hours(stories: list[dict[str, Any]], now: dt.datetime) -> float:
    stamps = []
    for story in stories:
        if not isinstance(story, dict):
            continue
        stamp = editorial_story_time(story, now=now.astimezone(dt.timezone.utc))
        if stamp is not None:
            stamps.append(stamp.astimezone(HKT))
    if not stamps:
        return float("inf")
    return max(0.0, (now - max(stamps)).total_seconds() / 3600.0)


def freshest_valid_candidate(
    slug: str,
    candidates: list[dict[str, Any]],
    now: dt.datetime,
) -> dict[str, Any] | None:
    sla = PUBLIC_DESK_FRESHNESS_HOURS[slug]
    valid: list[tuple[dt.datetime, dict[str, Any]]] = []
    for story in candidates:
        stamp = editorial_story_time(story, now=now.astimezone(dt.timezone.utc))
        if stamp is None:
            print(f"SPECIALIST_FRESHNESS_RECOVERY_CANDIDATE_INVALID slug={slug} id={story.get('id')} reason=no-timestamp")
            continue
        age = max(0.0, (now.astimezone(dt.timezone.utc) - stamp).total_seconds() / 3600.0)
        if age > sla:
            print(
                f"SPECIALIST_FRESHNESS_RECOVERY_CANDIDATE_STALE slug={slug} "
                f"id={story.get('id')} age_h={age:.2f} sla_h={sla}"
            )
            continue
        valid.append((stamp, story))
    if not valid:
        return None
    valid.sort(key=lambda row: row[0], reverse=True)
    return valid[0][1]


def apply_recovery(
    data: dict[str, Any],
    *,
    now: dt.datetime,
    recovery_pool: dict[str, list[dict[str, Any]]] = RECOVERY_POOL,
) -> tuple[bool, list[str]]:
    desks = data.setdefault("desks", {})
    changed = False
    recovered: list[str] = []

    for slug, candidates in recovery_pool.items():
        if slug not in PUBLIC_DESK_FRESHNESS_HOURS:
            continue
        current = desks.setdefault(slug, [])
        sla = PUBLIC_DESK_FRESHNESS_HOURS[slug]
        age = newest_age_hours(current, now)
        if age <= sla:
            print(f"SPECIALIST_FRESHNESS_RECOVERY_SKIP slug={slug} age_h={age:.2f} sla_h={sla}")
            continue

        story = freshest_valid_candidate(slug, candidates, now)
        if story is None:
            # Crucial: an expired emergency fallback must not terminate recovery
            # for every other desk.  Downstream freshness validation remains the
            # authority and will keep this desk unhealthy until genuine news is
            # available.
            print(
                f"SPECIALIST_FRESHNESS_RECOVERY_UNAVAILABLE slug={slug} "
                f"desk_age_h={age:.2f} sla_h={sla}; continuing other repairs"
            )
            continue

        story_id = str(story.get("id") or "")
        current[:] = [x for x in current if str(x.get("id") or "") != story_id]
        current.insert(0, story)
        changed = True
        recovered.append(slug)
        print(f"SPECIALIST_FRESHNESS_RECOVERY_ADD slug={slug} age_h={age:.2f} id={story_id}")

    return changed, recovered


def atomic_write_json(path: Path, data: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=path.name + ".", suffix=".tmp", dir=path.parent)
    tmp = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            json.dump(data, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        # Parse the exact candidate before replacement so an invalid/partial
        # write can never clobber the last known-good desk snapshot.
        json.loads(tmp.read_text(encoding="utf-8"))
        os.replace(tmp, path)
    finally:
        if tmp.exists():
            tmp.unlink()


def main() -> None:
    data = json.loads(DESK_PATH.read_text(encoding="utf-8"))
    now = dt.datetime.now(HKT)
    changed, recovered = apply_recovery(data, now=now)

    if changed:
        atomic_write_json(DESK_PATH, data)
        print("SPECIALIST_FRESHNESS_RECOVERY_APPLIED slugs=" + ",".join(recovered))
    else:
        print("SPECIALIST_FRESHNESS_RECOVERY_NOOP")


if __name__ == "__main__":
    main()
