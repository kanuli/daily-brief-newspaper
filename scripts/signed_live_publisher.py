"""Exact, single-use GitHub Live mutation for the existing Publisher's authorized interface."""
import base64
from contextlib import closing
from datetime import timedelta
from hashlib import sha1
import json
import os
import re
import sqlite3
import stat
import subprocess

from editorial_stage_authority import ARTICLE_KEYS, HEX, OID, authenticate, digest
from scheduled_publication_contract import stamp
from today_first_live import LIVE, REPO, candidate_live, canonical, require, strict_json

EIC_SCOPE="AI_GROUP_CANTONESE_EIC_LIVE_WRITE_V1"
CORE_SCOPE="AI_GROUP_CORE_LIVE_WRITE_V1"
FIELDS={"scope","actor","decision","repository","branch","path","mainParent","stagedCommit",
        "publisher","draftSha256","evidenceSha256","coreCustodySha256","eventId","issuedAt","expiresAt","articles"}
PRINCIPAL=re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]{0,79}(?:\[bot\])?\Z")
TRANSPORT_FAILURES=(OSError,subprocess.SubprocessError,KeyError,ValueError,TypeError,AttributeError)


def git_blob(raw):
    return sha1(b"blob "+str(len(raw)).encode()+b"\0"+raw).hexdigest()


def verify_release(raw, envelope, evidence, *, pins, parent, staged, publisher, now):
    article_set=candidate_live(raw,now=now)["items"]
    packet=strict_json(envelope)
    require(isinstance(packet,dict) and set(packet)=={"eic","core"},"invalid publication authority packet")
    editorial,eic=authenticate(packet["eic"],pins["eic"])
    granted,core=authenticate(packet["core"],pins["core"])
    require(eic!=core and set(editorial)==FIELDS and set(granted)==FIELDS|{"eicReceiptSha256"},
            "publication authority roles or schema invalid")
    require((editorial["scope"],editorial["actor"],editorial["decision"])==
            (EIC_SCOPE,"CANTONESE_EIC","APPROVE_LIVE_WRITE")
            and (granted["scope"],granted["actor"],granted["decision"])==
            (CORE_SCOPE,"CENTRAL_CORE","AUTHORIZE_LIVE_WRITE"),"incorrect live publication scope")
    require(granted["eicReceiptSha256"]==digest(canonical(packet["eic"])),"publication Core receipt does not bind EIC")
    require(OID.fullmatch(parent) and OID.fullmatch(staged) and PRINCIPAL.fullmatch(publisher)
            and HEX.fullmatch(editorial["eventId"]) and HEX.fullmatch(editorial["coreCustodySha256"]),
            "invalid publisher, commit, event or custody identity")
    evidence_rows=strict_json(evidence)
    require(isinstance(evidence_rows,list) and len(evidence_rows)==len(article_set),"publication evidence inventory mismatch")
    source_by_id={row["articleId"]:row for row in evidence_rows}
    require(len(source_by_id)==len(article_set),"duplicate publication evidence")
    bound=[]
    for item in article_set:
        source=source_by_id.get(item["id"])
        require(isinstance(source,dict) and set(source)=={"articleId","name","url","publishedAt","verifiedAt","documentSha256"}
                and HEX.fullmatch(source["documentSha256"])
                and (source["name"],source["url"],source["publishedAt"],source["verifiedAt"])==
                    (item["sourceName"],item["sourceUrl"],item["publishedAt"],item["verifiedAt"]),
                "publication primary source and evidence disagree")
        bound.append(dict({k:item[k] for k in ARTICLE_KEYS},articleSha256=digest(canonical(item)),
                          documentSha256=source["documentSha256"]))
    fields=dict(repository=REPO,branch="main",path=LIVE,mainParent=parent,stagedCommit=staged,publisher=publisher,
                draftSha256=digest(raw),evidenceSha256=digest(evidence),articles=bound,
                coreCustodySha256=editorial["coreCustodySha256"],eventId=editorial["eventId"])
    require(all(editorial[k]==granted[k]==v for k,v in fields.items()),
            "publication claims do not match exact source, predecessor, or destination")
    eic_time, core_time=stamp(editorial["issuedAt"]),stamp(granted["issuedAt"])
    eic_end, core_end=stamp(editorial["expiresAt"]),stamp(granted["expiresAt"])
    require(stamp(strict_json(raw)["lastUpdated"])<=eic_time<=core_time<=now<core_end<=eic_end
            and eic_end-eic_time<=timedelta(minutes=30) and core_end-core_time<=timedelta(minutes=30),
            "publication authorization expired or out of order")
    return dict(fields,authorizationSha256=digest(canonical(packet)),liveBlob=git_blob(raw),
                expiresAt=granted["expiresAt"])


def reservation_db(directory):
    info=directory.stat(follow_symlinks=False)
    require(stat.S_ISDIR(info.st_mode) and info.st_uid==os.geteuid() and not info.st_mode&0o077,
            "private publication journal directory required")
    path=directory/"live-release.sqlite3"
    flags=os.O_CREAT|os.O_RDWR|os.O_NOFOLLOW
    fd=os.open(path,flags,0o600)
    try:
        info=os.fstat(fd)
        require(stat.S_ISREG(info.st_mode) and info.st_uid==os.geteuid() and not info.st_mode&0o077,
                "publication journal ownership is invalid")
    finally:
        os.close(fd)
    return sqlite3.connect(path,timeout=3,isolation_level=None)


def headline(bound):
    return "Publish Core-authorized Cantonese Live [event "+bound["eventId"]+"]"


def mutation_packet(bound, raw):
    return {
        "query":"mutation($input:CreateCommitOnBranchInput!) {createCommitOnBranch(input:$input){commit{oid}}}",
        "variables":{"input":{
            "branch":{"repositoryNameWithOwner":REPO,"branchName":"main"},
            "expectedHeadOid":bound["mainParent"],
            "message":{"headline":headline(bound)},
            "fileChanges":{"additions":[{"path":LIVE,"contents":base64.b64encode(raw).decode()}]},
        }},
    }


def confirmed_successor(bound, *, branch_head, api, require_github_signature=False):
    observed=branch_head("main")
    predecessor=bound["mainParent"]
    if observed==predecessor:
        return None
    cursor=observed
    seen=set()
    for _ in range(12):
        require(OID.fullmatch(cursor) and cursor not in seen,"PUBLISH_GITHUB_HISTORY_UNPROVEN_HOLD")
        seen.add(cursor)
        commit=api("commits/"+cursor)
        parents=[p["sha"] for p in commit["parents"]]
        require(commit["sha"]==cursor and parents,"PUBLISH_GITHUB_HISTORY_UNPROVEN_HOLD")
        if parents[0]!=predecessor:
            cursor=parents[0]
            continue
        verification=commit["commit"].get("verification") or {}
        files=commit.get("files",[])
        author=(commit.get("author") or {}).get("login")
        require(parents==[predecessor] and commit["commit"]["message"].splitlines()[0]==headline(bound)
                and isinstance(author,str) and author.casefold()==bound["publisher"].casefold()
                and len(files)==1 and files[0]["filename"]==LIVE and files[0]["sha"]==bound["liveBlob"],
                "PUBLISH_GITHUB_EFFECT_UNPROVEN_HOLD")
        if require_github_signature:
            require(verification.get("verified") is True and verification.get("reason")=="valid",
                    "PUBLISH_GITHUB_COMMIT_SIGNATURE_HOLD")
        require(branch_head("main")==observed,"published head moved during verification")
        return dict(eventId=bound["eventId"],authorizationSha256=bound["authorizationSha256"],
                    coreCustodySha256=bound["coreCustodySha256"],commit=cursor,liveBlob=bound["liveBlob"],
                    draftSha256=bound["draftSha256"],publisher=author,observedMainTip=observed,
                    writeIsObservedHead=cursor==observed,githubSignatureVerified=verification.get("verified") is True)
    raise ValueError("PUBLISH_GITHUB_HISTORY_DEPTH_HOLD")


def publish_once(raw,envelope,evidence,*,pins,parent,staged,publisher,directory,clock,
                 branch_head,api,staged_blob,mutation,check_mutation_ready,require_github_signature=False):
    """The only external mutation is a CAS; pending operations can only reconcile by readback."""
    packet = strict_json(envelope)
    try:
        event = packet["eic"]["claims"]["eventId"]
    except (KeyError, TypeError) as exc:
        raise ValueError("invalid publication authority packet") from exc
    require(isinstance(event, str) and HEX.fullmatch(event), "invalid publication event identity")
    with closing(reservation_db(directory)) as store:
        store.execute("PRAGMA journal_mode=WAL")
        store.execute("PRAGMA synchronous=FULL")
        store.execute("""CREATE TABLE IF NOT EXISTS releases (
                      event TEXT PRIMARY KEY, binding TEXT NOT NULL, receipt TEXT, admitted_at TEXT)""")
        store.execute("BEGIN IMMEDIATE")
        try:
            # Older reservations lack a trusted admission time. Preserve them, but
            # require them to pass the live clock check rather than guessing a time.
            if "admitted_at" not in {column[1] for column in store.execute("PRAGMA table_info(releases)")}:
                store.execute("ALTER TABLE releases ADD COLUMN admitted_at TEXT")
            row = store.execute("SELECT binding, receipt, admitted_at FROM releases WHERE event=?", (event,)).fetchone()
            current = clock()
            admitted = stamp(row[2]) if row and row[2] else current
            require(admitted <= current, "publication clock precedes durable admission")
            bound = verify_release(raw, envelope, evidence, pins=pins, parent=parent, staged=staged,
                                   publisher=publisher, now=admitted)
            if row:
                require(row[0] == bound["authorizationSha256"], "publication event reused with changed approval")
            else:
                # New reservations alone are eligible to request Git mutation.
                check_mutation_ready()
                require(branch_head("main")==parent and branch_head("prepublish-news")==staged
                        and staged_blob(staged)==bound["liveBlob"],"publication predecessor or staged bytes changed")
                before_write = clock()
                require(admitted <= before_write < stamp(bound["expiresAt"]),
                        "publication clock changed or approval expired before mutation")
                store.execute("INSERT INTO releases(event,binding,receipt,admitted_at) VALUES(?,?,NULL,?)",
                              (event, bound["authorizationSha256"], admitted.isoformat()))
            store.commit()
        except BaseException:
            store.rollback()
            raise
        if row and row[1]:
            recorded=json.loads(row[1])
            if require_github_signature:
                require(recorded.get("githubSignatureVerified") is True,"retained GitHub signature is unverified")
            return dict(recorded,status="ALREADY_RECORDED")
        reply=None
        if not row:
            require(clock()<stamp(bound["expiresAt"]),"publication approval expired before mutation")
            try:
                reply=mutation(mutation_packet(bound,raw))
            except TRANSPORT_FAILURES:
                # A successful write can lose its response. The next action is read-only.
                pass
        proof=confirmed_successor(bound,branch_head=branch_head,api=api,require_github_signature=require_github_signature)
        require(proof is not None,"PUBLISH_OUTCOME_UNKNOWN_HOLD; reservation retained")
        if reply is not None:
            require(reply==proof["commit"],"GitHub mutation response differs from confirmed commit")
        store.execute("UPDATE releases SET receipt=? WHERE event=? AND binding=? AND receipt IS NULL",
                      (canonical(proof).decode(),event,bound["authorizationSha256"]))
        return dict(proof,status="RECONCILED" if row else "RECORDED")
