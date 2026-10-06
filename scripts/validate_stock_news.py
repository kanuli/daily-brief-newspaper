#!/usr/bin/env python3
import json, pathlib, re
from datetime import datetime, time, timezone
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

ROOT = pathlib.Path(__file__).resolve().parents[1]
PATH = ROOT / "data" / "stocks-latest.json"
EXPECTED = ["GOOG","GLDM","ICE","MCD","EMXC","GBTC","DBA","AAPL","EWY","META","MSFT","NVDA","TSM","PLTR","VT"]
ETF = {"GLDM","EMXC","GBTC","DBA","EWY","VT"}
REQUIRED = ["id","storyType","impact","impactLabel","title","dek","summary","body","context","why","watchNext","sourceName","sourceUrl","timeLabel"]
PUBLIC = ("title","dek","summary","body","context","why","watchNext")
BANNED = ("Stock News核實","Stock News 核實","自動核實器","本自動稿","人工編輯核實稿","自動速報","暫無新聞","暫無新消息","沒有新聞","沒有新消息")
MAX_COVERAGE_CHECK_AGE_HOURS = 3.0
MAX_SUBSTANTIVE_STORY_AGE_HOURS = 48.0
TIME_FIELDS = ("primaryPublishedAt","sourcePublishedAt","eventPublishedAt","marketAsOfAt","publishedAt")
ID_DATE_RE = re.compile(r"(?:^|[-_])(20\d{6})(?:$|[-_])")
HKT = ZoneInfo("Asia/Hong_Kong")

def fail(msg): raise SystemExit("Stock News validation failed: " + msg)
def req(c,msg):
    if not c: fail(msg)
def text(v): return isinstance(v,str) and bool(v.strip())
def ts(v):
    try:
        d=datetime.fromisoformat(str(v).replace("Z","+00:00")); return d if d.tzinfo else None
    except Exception: return None
def url(v):
    try: p=urlparse(v); return p.scheme in {"http","https"} and bool(p.netloc)
    except Exception: return False
def substantive_time(story):
    for f in TIME_FIELDS:
        d=ts(story.get(f))
        if d: return d.astimezone(timezone.utc),f
    m=ID_DATE_RE.search(str(story.get("id") or ""))
    if m:
        d=datetime.combine(datetime.strptime(m.group(1),"%Y%m%d").date(),time(0),tzinfo=HKT)
        return d.astimezone(timezone.utc),"story-id-date"
    return None,None

def main():
    data=json.loads(PATH.read_text(encoding="utf-8")); now=datetime.now(timezone.utc)
    req(data.get("mode")=="TRACKED_STOCK_NEWS","wrong mode")
    req(data.get("collectionStatus")=="COMPLETE","latest 15-symbol source collection is not complete")
    req(data.get("tracked")==EXPECTED,"tracked list/order must match 15-symbol contract")
    checked=ts(data.get("lastCheckedAt")); req(checked,"lastCheckedAt missing/invalid")
    check_age=(now-checked.astimezone(timezone.utc)).total_seconds()/3600
    req(-1 <= check_age <= MAX_COVERAGE_CHECK_AGE_HOURS,f"source/editorial review stale ({check_age:.1f}h; max 3.0h)")
    tickers=data.get("tickers"); req(isinstance(tickers,dict) and list(tickers.keys())==EXPECTED,"ticker keys/order mismatch")
    fresh=data.get("coverageFreshness"); req(isinstance(fresh,dict) and list(fresh.keys())==EXPECTED,"coverageFreshness keys/order mismatch")
    seen=set()
    for ticker in EXPECTED:
        block=tickers[ticker]; stories=block.get("stories")
        req(block.get("assetType")==("ETF" if ticker in ETF else "EQUITY"),f"{ticker}: assetType mismatch")
        req(isinstance(stories,list) and 1 <= len(stories) <= 3,f"{ticker}: requires 1-3 stories")
        row=fresh[ticker]; req(row.get("reviewEvidenceFound") is True,f"{ticker}: no current review evidence")
        r=ts(row.get("lastReviewedAt")); req(r,f"{ticker}: invalid lastReviewedAt")
        rage=(now-r.astimezone(timezone.utc)).total_seconds()/3600; req(-1 <= rage <= 3.0,f"{ticker}: review stale")
        ages=[]
        for i,s in enumerate(stories):
            req(isinstance(s,dict),f"{ticker}[{i}]: invalid story")
            for f in REQUIRED: req(text(s.get(f)),f"{ticker}[{i}]: {f} required")
            req(s["id"] not in seen,f"duplicate id {s['id']}"); seen.add(s["id"])
            req(s.get("impact") in {"↑","↓","↔"},f"{ticker}[{i}]: invalid impact")
            if ticker in ETF: req("ETF READ-THROUGH" in s["storyType"].upper(),f"{ticker}[{i}]: ETF label required")
            req(url(s["sourceUrl"]),f"{ticker}[{i}]: invalid sourceUrl")
            req(100 <= len(s["body"].strip()) <= 1200 and "\n\n" in s["body"],f"{ticker}[{i}]: body depth invalid")
            for f in PUBLIC:
                t=str(s.get(f) or ""); req(not any(x in t for x in BANNED) and "no news" not in t.lower(),f"{ticker}[{i}]: process/no-news filler")
            sources=s.get("sources"); req(isinstance(sources,list) and sources,f"{ticker}[{i}]: sources required")
            for src in sources: req(text(src.get("name")) and url(src.get("url")),f"{ticker}[{i}]: malformed source")
            d,field=substantive_time(s)
            if d:
                age=(now-d).total_seconds()/3600
                if age >= -1: ages.append((age,s["id"],field))
        req(ages,f"{ticker}: no real substantive timestamp/date")
        age,sid,field=min(ages,key=lambda x:x[0])
        substantive_current=age <= MAX_SUBSTANTIVE_STORY_AGE_HOURS
        req(row.get("substantiveCurrent") is substantive_current,f"{ticker}: substantiveCurrent metadata mismatch")
        expected_status="CURRENT_VERIFIED_CATALYST" if substantive_current else "NO_RECENT_VERIFIED_CATALYST"
        req(row.get("contentStatus")==expected_status,f"{ticker}: contentStatus must be {expected_status}")
        req(row.get("coverageStale") is not True and row.get("stale") is not True,f"{ticker}: current review cannot be marked stale")
    req(not data.get("staleSymbols"),f"staleSymbols present: {data.get('staleSymbols')}")
    req(not data.get("staleContentSymbols"),f"staleContentSymbols present: {data.get('staleContentSymbols')}")
    quiet=set(data.get("noRecentCatalystSymbols") or [])
    expected_quiet={
        ticker for ticker in EXPECTED
        if (fresh.get(ticker) or {}).get("contentStatus")=="NO_RECENT_VERIFIED_CATALYST"
    }
    req(quiet==expected_quiet,f"noRecentCatalystSymbols mismatch: expected {sorted(expected_quiet)}, got {sorted(quiet)}")
    q=data.get("qualityGates") or {}; req(q.get("freshnessGateMet") is True,"current-review freshness gate must pass")
    req(q.get("substantiveFreshnessGateMet") is True,"current-review substantive outcome gate must pass")
    req(q.get("truthfulNoCatalystGateMet") is True,"truthful no-catalyst gate must pass")
    print(f"Stock News validation OK: 15 tickers, {len(seen)} stories; 3h review freshness + truthful catalyst/no-catalyst outcomes PASS")

if __name__=="__main__": main()
