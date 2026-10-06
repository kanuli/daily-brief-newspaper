#!/usr/bin/env python3
"""Editor-in-Chief newsroom assignment engine.

Classifies faults before assigning robots. Discovery shortage, verification/
copy conversion, publication, merge, Stock, Vocab, Pages and Voice are distinct
failure domains. Dispatch is never treated as success; every assignment names
the outcome evidence the next supervisory cycle must verify.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SOFT_TARGETS = {
    "world": 3, "asia": 3, "hong-kong": 6, "japan": 6,
    "market-economy": 4, "finance": 4, "ai-tech": 4,
    "manga-anime": 24, "manchester-united": 12, "football": 8,
}

def load(path: str, default: Any) -> Any:
    p=Path(path)
    if not p.is_file():
        return default
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except Exception:
        return default

def parse_iso(value: Any):
    try:
        return datetime.fromisoformat(str(value).replace("Z","+00:00")).astimezone(timezone.utc)
    except Exception:
        return None

def add(plan: list[dict[str,Any]], robot: str, workflow: str, fault: str, reason: str,
        *, mode: str="normal", evidence: list[str] | None=None, desks: list[str] | None=None):
    # One assignment per robot/workflow; deep supersedes normal.
    for row in plan:
        if row["workflow"] == workflow:
            if mode == "deep" and row.get("mode") != "deep":
                row["mode"] = "deep"
                row["faultClass"] = fault
                row["reason"] = reason
            if desks:
                row["desks"] = sorted(set((row.get("desks") or []) + desks))
            return
    plan.append({
        "robot": robot,
        "workflow": workflow,
        "mode": mode,
        "faultClass": fault,
        "reason": reason,
        "desks": desks or [],
        "verifyNextCycle": evidence or [],
    })

def main() -> int:
    ap=argparse.ArgumentParser()
    ap.add_argument("--staging", required=True)
    ap.add_argument("--freshness", required=True)
    ap.add_argument("--editor-status", required=True)
    ap.add_argument("--sentinel", required=True)
    ap.add_argument("--stock-rc", type=int, required=True)
    ap.add_argument("--publication-rc", type=int, required=True)
    ap.add_argument("--vocab-rc", type=int, required=True)
    ap.add_argument("--output", required=True)
    args=ap.parse_args()

    now=datetime.now(timezone.utc)
    staging=load(args.staging,{})
    freshness=load(args.freshness,{})
    editor=load(args.editor_status,{})
    sentinel=load(args.sentinel,{})
    plan=[]

    # 1) Discovery health: freshness alone is insufficient.
    stamp=parse_iso(staging.get("lastSearchAt") or staging.get("lastSearchStartedAt"))
    age=999999.0 if stamp is None else max(0.0,(now-stamp).total_seconds()/60.0)
    underfilled=staging.get("underfilledDesks") if isinstance(staging.get("underfilledDesks"),dict) else {}
    query_audit=staging.get("queryAudit") if isinstance(staging.get("queryAudit"),dict) else {}
    floor_failed=sorted(
        desk for desk,row in query_audit.items()
        if isinstance(row,dict) and int(row.get("floorMetThisRun") or 0) != 1
    )
    discovery_bad=sorted(set(underfilled) | set(floor_failed))
    if age > 25:
        add(plan,"collector","rolling-news-search.yml","collection-stale",
            f"discovery staging is {age:.1f} minutes old",
            evidence=["lastSearchAt advances","collector run completes"])
    if discovery_bad:
        add(plan,"collector","rolling-news-search.yml","discovery-underfilled",
            "current collection completed but desk discovery outcome is under target",
            mode="deep", desks=discovery_bad,
            evidence=["underfilledDesks reduced or cleared","queryAudit.floorMetThisRun=1 for affected desks"])

    # 2) Published desk health: distinguish shortage from conversion failure.
    stale_desks=[]
    stale_with_candidates=[]
    stale_without_candidates=[]
    for desk,row in (freshness.get("desks") or {}).items():
        if not isinstance(row,dict):
            continue
        ageh=row.get("newestAgeHours")
        hard_bad=(not row.get("fresh",False)) or (not row.get("dailySynced",True))
        soft=SOFT_TARGETS.get(desk,6)
        soft_bad=isinstance(ageh,(int,float)) and ageh > soft
        if hard_bad or soft_bad:
            stale_desks.append(desk)
            staging_key="finance" if desk=="market-economy" else desk
            candidates=(staging.get("desks") or {}).get(staging_key) or []
            current_candidates=[
                x for x in candidates if isinstance(x,dict) and parse_iso(x.get("publishedAt")) is not None
            ]
            if current_candidates:
                stale_with_candidates.append(desk)
            else:
                stale_without_candidates.append(desk)

    if stale_without_candidates:
        add(plan,"collector","rolling-news-search.yml","discovery-missing-for-stale-desk",
            "published desks are stale and staging has no usable current candidates",
            mode="deep", desks=stale_without_candidates,
            evidence=["affected desks gain current candidates","query floor satisfied"])
    if stale_with_candidates:
        add(plan,"general-producer","general-news-producer.yml","desk-stale-with-candidates",
            "staging already has candidates; verification/copy conversion is the bottleneck",
            desks=stale_with_candidates,
            evidence=["verified draft produced","stale desk list shrinks","Live publication advances"])
        add(plan,"desk-merge","merge-live-into-desk.yml","desk-freshness-gap",
            "published Rolling Desk remains stale after candidates exist",
            desks=stale_with_candidates,
            evidence=["desk-latest generatedAt advances","desk newestAgeHours improves"])

    # 3) Live.
    if any(isinstance(f,dict) and f.get("code") in {"LIVE_STALE","PERSISTENT_LIVE_STALE"} for f in editor.get("findings") or []):
        add(plan,"live-publisher","live-publication-maintenance.yml","live-stale",
            "Editor-in-Chief reports Live publication stale",
            evidence=["live.lastUpdated advances","publication-current validator passes"])

    # 4) Stock normal/deep based on measured prior outcome.
    deep_stock=any(
        isinstance(x,dict) and x.get("area")=="stock-deep"
        for x in editor.get("repairPlan") or []
    ) or any(
        isinstance(f,dict) and f.get("code")=="STOCK_RECOVERY_NO_PROGRESS"
        for f in editor.get("findings") or []
    )
    if args.stock_rc != 0:
        add(plan,"stock","stock-publication-maintenance.yml",
            "stock-no-progress" if deep_stock else "stock-stale",
            "Stock validator failed; use alternate deep path after no measurable prior progress" if deep_stock else "Stock validator failed",
            mode="deep" if deep_stock else "normal",
            evidence=["generatedAt or lastCheckedAt advances","stock validator passes","public stock probe matches"])

    # 5) Vocab.
    if args.vocab_rc != 0:
        add(plan,"vocab","daily-japanese-vocab.yml","vocab-stale",
            "today's HKT dated vocab/latest contract failed",
            evidence=["dated file exists with today's date","latest.date equals today"])

    # 6) Daily/current publication.
    failed_pages=set(sentinel.get("persistentFailedPages") or [])
    if args.publication_rc != 0 or "index.html" in failed_pages:
        add(plan,"daily-recovery","daily-today-recovery.yml","daily-currentness",
            "Daily/current publication validator or public index failed",
            evidence=["current Daily date passes","public index matches repository"])

    # 7) Pages/public propagation.
    page_fault=any(
        isinstance(f,dict) and (f.get("area")=="pages" or str(f.get("code","")).startswith("PUBLIC_"))
        and f.get("severity")=="critical"
        for f in editor.get("findings") or []
    )
    if failed_pages or page_fault:
        add(plan,"pages","pages.yml","public-mismatch",
            "public Pages/probe remains stale or mismatched",
            evidence=["fresh public probe","repository/public state match"])

    # 8) Voice remains asynchronous.
    voice=editor.get("voiceWorkflowAudit") or {}
    if not voice.get("coverageComplete",True):
        add(plan,"voice","canto-nano-production.yml","voice-backlog",
            "voice coverage is incomplete",
            evidence=["pendingArticleCount=0","coverageComplete=true"])

    evidence={
        "checkedAt":now.isoformat().replace("+00:00","Z"),
        "collectorAgeMinutes":round(age,1),
        "discoveryUnderfilledDesks":discovery_bad,
        "publishedStaleDesks":sorted(stale_desks),
        "staleDesksWithCandidates":sorted(stale_with_candidates),
        "staleDesksWithoutCandidates":sorted(stale_without_candidates),
        "assignments":plan,
        "healthy":len(plan)==0,
    }
    Path(args.output).write_text(json.dumps(evidence,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    print(json.dumps(evidence,ensure_ascii=False,indent=2))
    return 0

if __name__=="__main__":
    raise SystemExit(main())
