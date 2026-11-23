"""Build an exact non-Live Git CAS after a verified existing Core delegation.

The caller must supply a workflow identity from its authenticated transport.
This module issues no grants and possesses no GitHub credentials. Live stays
on the dedicated signed Publisher path.
"""
import base64
from datetime import timedelta
import hashlib
import re

from editorial_stage_authority import authenticate, HEX, OID
from non_live_writer_scope import scope_review
from scheduled_publication_contract import stamp
from today_first_live import REPO, require, strict_json

MAX_BYTES = 4 * 1024 * 1024
SCOPE = "AI_GROUP_CORE_NON_LIVE_GIT_DATA_V1"
BRANCH = "main"
FIELDS = {"scope", "issuer", "repository", "branch", "workflow", "expectedHead", "eventId",
          "issuedAt", "expiresAt", "files"}


def prepare(core_grant, *, files, workflow_identity, core_key, expected_head, now):
    """Return the immutable CAS packet bound to exact authorized non-Live updates."""
    require(isinstance(files,dict) and files and all(isinstance(raw,bytes) for raw in files.values()),
            "invalid gateway file inventory")
    require(sum(len(raw) for raw in files.values()) <= MAX_BYTES and all(files.values()),
            "gateway mutation outside bounded size")
    scope_review(workflow_identity, [{"filename":path,"status":"modified"} for path in files])
    claims,_ = authenticate(strict_json(core_grant), core_key)
    require(set(claims) == FIELDS and OID.fullmatch(expected_head) is not None,
            "invalid Core gateway schema or expected predecessor")
    require((claims["scope"], claims["issuer"], claims["repository"], claims["branch"],
             claims["workflow"], claims["expectedHead"]) ==
            (SCOPE, "CENTRAL_CORE", REPO, BRANCH, workflow_identity, expected_head),
            "gateway role, destination or predecessor mismatch")
    event = claims["eventId"]
    require(isinstance(event,str) and HEX.fullmatch(event) is not None,
            "invalid non-Live event identity")
    issued,expires = stamp(claims["issuedAt"]),stamp(claims["expiresAt"])
    require(issued <= now < expires and expires-issued<=timedelta(minutes=5),
            "expired, future or overlong Core data delegation")
    expected = [{"path":path,"sha256":hashlib.sha256(raw).hexdigest()} for path,raw in sorted(files.items())]
    require(claims["files"] == expected,"non-Live grant does not name exact file bytes")
    return {"query":"mutation($input:CreateCommitOnBranchInput!) {createCommitOnBranch(input:$input){commit{oid}}}",
            "variables":{"input":{
                "branch":{"repositoryNameWithOwner":REPO,"branchName":BRANCH},
                "expectedHeadOid":expected_head,
                "message":{"headline":"Core-authorized non-Live data update [event "+event+"]"},
                "fileChanges":{"additions":[{"path":path,"contents":base64.b64encode(raw).decode()}
                                            for path,raw in sorted(files.items())]}}}}


def commit_once(core_grant, *, files, workflow_identity, core_key, expected_head, clock, read_head, git_cas):
    """Call the authorized remote CAS exactly once, with no retry after uncertainty."""
    packet = prepare(core_grant,files=files,workflow_identity=workflow_identity,core_key=core_key,
                     expected_head=expected_head,now=clock())
    require(read_head()==expected_head,"non-Live predecessor moved")
    # A remote read must not extend the granting interval, or admit a moved clock.
    claims= strict_json(core_grant)["claims"]
    require(stamp(claims["issuedAt"])<=clock()<stamp(claims["expiresAt"]),
            "expired Core data delegation before send")
    commit = git_cas(packet)
    require(isinstance(commit,str) and re.fullmatch(r"[a-f0-9]{40}",commit) and commit!=expected_head,
            "non-Live CAS outcome unverified")
    return commit
