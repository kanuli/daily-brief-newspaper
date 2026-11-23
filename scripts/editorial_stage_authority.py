"""Bind an independently signed EIC decision and Core grant to a single staging event."""
import base64
from contextlib import closing
from datetime import timedelta
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import sqlite3
import stat

from scheduled_publication_contract import stamp
from today_first_live import REPO, candidate_live, canonical, require, strict_json, verify_ed25519

BRANCH="prepublish-news"
TARGET="data/scheduled-live-candidate.json"
EIC_SCOPE="AI_GROUP_CANTONESE_EIC_LIVE_STAGE_V1"
CORE_SCOPE="AI_GROUP_CORE_LIVE_STAGE_V1"
KEYS={"actor","decision","scope","repository","branch","path","prepublishParent","validatorCommit",
      "draftSha256","evidenceSha256","articles","eventId","issuedAt","expiresAt"}
ARTICLE_KEYS=("id","desk","deskSlugs","sourceName","sourceUrl","publishedAt","verifiedAt")
HEX=re.compile(r"[a-f0-9]{64}\Z")
OID=re.compile(r"[a-f0-9]{40}\Z")
MAX_ENVELOPE=64*1024

def digest(raw):
    return sha256(raw).hexdigest()


def read_bounded(path):
    with path.open("rb") as reader:
        raw=reader.read(MAX_ENVELOPE+1)
    require(len(raw)<=MAX_ENVELOPE,"stage authorization exceeds size bounds")
    return raw


def authenticate(value,pin):
    require(isinstance(value,dict) and set(value)=={"claims","signature"},"invalid stage signed record")
    key=base64.b64decode(pin,validate=True)
    signature=base64.b64decode(value["signature"],validate=True)
    require(len(key)==32 and len(signature)==64,"invalid stage Ed25519 encoding")
    claims=value["claims"]
    require(isinstance(claims,dict),"invalid stage signed claims")
    verify_ed25519(key,canonical(claims),signature,openssl="openssl")
    return claims,key


def verify(raw,envelope,evidence,*,pins,parent,validator,now):
    """Inputs and keys are supplied separately. This function cannot issue grants."""
    live=candidate_live(raw,now=now)
    packet=strict_json(envelope)
    require(isinstance(packet,dict) and set(packet)=={"eic","core"},"invalid EIC/Core packet")
    eic,eic_key=authenticate(packet["eic"],pins["eic"])
    core,core_key=authenticate(packet["core"],pins["core"])
    require(eic_key!=core_key,"independent EIC and Core keys are required")
    require(set(eic)==KEYS and set(core)==KEYS|{"eicReceiptSha256"},"unknown stage claim")
    require((eic["scope"],eic["actor"],eic["decision"])==(EIC_SCOPE,"CANTONESE_EIC","APPROVE_LIVE_STAGE")
            and (core["scope"],core["actor"],core["decision"])==(CORE_SCOPE,"CENTRAL_CORE","AUTHORIZE_LIVE_STAGE"),
            "incorrect stage role, decision or scope")
    require(core["eicReceiptSha256"]==digest(canonical(packet["eic"])),"Core grant does not bind the EIC receipt")
    fields={"repository":REPO,"branch":BRANCH,"path":TARGET,"prepublishParent":parent,"validatorCommit":validator,
            "draftSha256":digest(raw),"evidenceSha256":digest(evidence),"eventId":eic["eventId"]}
    require(OID.fullmatch(parent) and OID.fullmatch(validator) and HEX.fullmatch(eic["eventId"]),
            "invalid stage event or commit identity")
    source_rows=strict_json(evidence)
    require(isinstance(source_rows,list) and len(source_rows)==len(live["items"]),"stage evidence inventory mismatch")
    by_id={row["articleId"]:row for row in source_rows}
    require(len(by_id)==len(live["items"]),"duplicate stage evidence article")
    papers=[]
    for item in live["items"]:
        source=by_id.get(item["id"])
        require(isinstance(source,dict) and set(source)=={"articleId","name","url","publishedAt","verifiedAt","documentSha256"}
                and HEX.fullmatch(source["documentSha256"])
                and (source["name"],source["url"],source["publishedAt"],source["verifiedAt"])
                ==(item["sourceName"],item["sourceUrl"],item["publishedAt"],item["verifiedAt"]),
                "stage primary source and evidence disagree")
        papers.append(dict({k:item[k] for k in ARTICLE_KEYS},articleSha256=digest(canonical(item)),
                           documentSha256=source["documentSha256"]))
    fields["articles"]=papers
    require(all(eic[key]==core[key]==value for key,value in fields.items()),
            "signed stage claims do not bind the exact payload, predecessor or destination")
    e_at,c_at,ee,ce=[stamp(cap[key]) for cap,key in (
        (eic,"issuedAt"),(core,"issuedAt"),(eic,"expiresAt"),(core,"expiresAt"))]
    require(stamp(live["lastUpdated"])<=e_at<=c_at<=now<ce<=ee
            and ee-e_at<=timedelta(minutes=30) and ce-c_at<=timedelta(minutes=30),
            "expired or out-of-order stage approval")
    return eic["eventId"],digest(canonical(packet))


def stage_once(directory,event,binding,submit,recover=None,*,prepare=None):
    """Reserve before transport. A lost result may only be cleared by a proven readback."""
    mode=directory.stat(follow_symlinks=False)
    require(stat.S_ISDIR(mode.st_mode) and mode.st_uid==os.geteuid() and not mode.st_mode&0o077,
            "private publisher journal directory required")
    path=directory/"publisher-authority.sqlite3"
    fd=os.open(path,os.O_CREAT|os.O_RDWR|os.O_NOFOLLOW,0o600)
    try:
        info=os.fstat(fd)
        require(stat.S_ISREG(info.st_mode) and info.st_uid==os.geteuid() and not info.st_mode&0o077,
                "invalid publisher journal")
    finally:
        os.close(fd)
    with closing(sqlite3.connect(path,timeout=3,isolation_level=None)) as db:
        db.execute("PRAGMA journal_mode=WAL")
        db.execute("PRAGMA synchronous=FULL")
        db.execute("CREATE TABLE IF NOT EXISTS staging (event TEXT PRIMARY KEY, binding TEXT NOT NULL, commit_sha TEXT)")
        lookup = "SELECT binding, commit_sha FROM staging WHERE event=?"
        prior = db.execute(lookup,(event,)).fetchone()
        fresh = False
        if prior is None:
            if prepare is not None:
                prepare()
            inserted = db.execute("INSERT OR IGNORE INTO staging VALUES(?,?,NULL)",(event,binding))
            fresh = inserted.rowcount == 1
            if not fresh:
                prior = db.execute(lookup,(event,)).fetchone()
        if fresh:
            commit=submit()
        else:
            require(prior[0]==binding,"staging event reused for different content")
            if prior[1] is not None:
                return prior[1],False
            require(recover is not None,"staging outcome unknown; reconcile GitHub readback before retry")
            commit=recover()
        require(isinstance(commit,str) and OID.fullmatch(commit),"unverified staged commit; reservation retained")
        db.execute("UPDATE staging SET commit_sha=? WHERE event=? AND binding=? AND commit_sha IS NULL",
                   (commit,event,binding))
        stored=db.execute("SELECT commit_sha FROM staging WHERE event=? AND binding=?",(event,binding)).fetchone()
        require(stored==(commit,),"staging readback contradicts the retained authorization")
        return commit,fresh
