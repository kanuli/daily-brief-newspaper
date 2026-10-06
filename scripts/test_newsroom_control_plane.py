#!/usr/bin/env python3
import json, subprocess, sys, tempfile
from pathlib import Path
from datetime import datetime, timezone

ROOT=Path(__file__).resolve().parents[1]
SCRIPT=ROOT/"scripts"/"newsroom_control_plane.py"

def run_case(staging,freshness,editor=None,sentinel=None,stock_rc=0,publication_rc=0,vocab_rc=0):
    with tempfile.TemporaryDirectory() as td:
        td=Path(td)
        files={}
        for name,data in {
            "staging":staging,"freshness":freshness,"editor":editor or {},
            "sentinel":sentinel or {},
        }.items():
            p=td/f"{name}.json"; p.write_text(json.dumps(data),encoding="utf-8"); files[name]=p
        out=td/"out.json"
        subprocess.run([
            sys.executable,str(SCRIPT),
            "--staging",str(files["staging"]),
            "--freshness",str(files["freshness"]),
            "--editor-status",str(files["editor"]),
            "--sentinel",str(files["sentinel"]),
            "--stock-rc",str(stock_rc),
            "--publication-rc",str(publication_rc),
            "--vocab-rc",str(vocab_rc),
            "--output",str(out),
        ],check=True,capture_output=True,text=True)
        return json.loads(out.read_text(encoding="utf-8"))

now=datetime.now(timezone.utc).isoformat()
base_staging={
    "lastSearchAt":now,
    "underfilledDesks":{},
    "queryAudit":{"world":{"floorMetThisRun":1}},
    "desks":{"world":[{"publishedAt":now}],"japan":[{"publishedAt":now}],"manchester-united":[{"publishedAt":now}]},
}
base_fresh={
    "desks":{
        "world":{"fresh":True,"dailySynced":True,"newestAgeHours":1},
        "japan":{"fresh":True,"dailySynced":True,"newestAgeHours":1},
        "manchester-united":{"fresh":True,"dailySynced":True,"newestAgeHours":1},
    }
}

r=run_case(base_staging,base_fresh)
assert r["assignments"]==[],r

staging=dict(base_staging)
staging["underfilledDesks"]={"world":{"count":5,"floor":24}}
staging["queryAudit"]={"world":{"floorMetThisRun":0}}
r=run_case(staging,base_fresh)
collector=next(x for x in r["assignments"] if x["workflow"]=="rolling-news-search.yml")
assert collector["mode"]=="deep",r
assert collector["faultClass"]=="discovery-underfilled",r

fresh={"desks":{
    "japan":{"fresh":False,"dailySynced":True,"newestAgeHours":136},
    "manchester-united":{"fresh":False,"dailySynced":True,"newestAgeHours":202},
}}
r=run_case(base_staging,fresh)
workflows={x["workflow"] for x in r["assignments"]}
assert "general-news-producer.yml" in workflows,r
assert "merge-live-into-desk.yml" in workflows,r
assert not any(x["workflow"]=="rolling-news-search.yml" for x in r["assignments"]),r

editor={
    "findings":[{"code":"STOCK_RECOVERY_NO_PROGRESS","severity":"critical","area":"stock"}],
    "repairPlan":[{"area":"stock-deep","workflow":"stock-publication-maintenance.yml"}],
}
r=run_case(base_staging,base_fresh,editor=editor,stock_rc=1)
stock=next(x for x in r["assignments"] if x["workflow"]=="stock-publication-maintenance.yml")
assert stock["mode"]=="deep",r

print("NEWSROOM_CONTROL_PLANE_TESTS_OK")
