"""Read the exact prepublish Git tree and verify a staged Publisher effect."""
from scheduled_publisher_preflight_receipt import CANDIDATE, need, sha

BRANCH = "prepublish-news"
LEGACY = "data/prepublish.json"


def paths_at(api, commit):
    """One Git-tree read of the two distinct historical and signed stage paths."""
    commit=sha(commit)
    record=api("git/commits/"+commit)
    need(record.get("sha")==commit,"STAGING_COMMIT_IDENTITY_HOLD")
    root_sha=sha(record["tree"]["sha"])
    root=api("git/trees/"+root_sha)
    need(root.get("sha")==root_sha and root.get("truncated") is False,"STAGING_ROOT_TREE_UNVERIFIED_HOLD")
    data=[entry for entry in root["tree"] if entry["path"]=="data"]
    need(len(data)==1 and data[0]["type"]=="tree" and data[0]["mode"]=="040000","STAGING_DATA_TREE_UNVERIFIED_HOLD")
    tree_sha=sha(data[0]["sha"])
    tree=api("git/trees/"+tree_sha)
    need(tree.get("sha")==tree_sha and tree.get("truncated") is False,"STAGING_DATA_TREE_UNVERIFIED_HOLD")
    result={}
    for path in (CANDIDATE, LEGACY):
        hits=[row for row in tree["tree"] if row["path"]==path.removeprefix("data/")]
        if not hits:
            result[path]=None
            continue
        need(len(hits)==1 and hits[0]["type"]=="blob" and hits[0]["mode"]=="100644",
             "STAGING_EXPECTED_REGULAR_FILE_HOLD")
        result[path]=sha(hits[0]["sha"])
    return result


def stage_headline(event):
    return "Stage Core-authorized Cantonese Live [event "+sha(event,64)+"]"


def readback(*, api, branch_head, parent, draft_blob, event, publisher):
    """Prove the current tip was the exact, independently verified staged Git write."""
    tip=sha(branch_head(BRANCH))
    if tip==parent:
        return None
    commit=api("commits/"+tip)
    signature=commit["commit"].get("verification") or {}
    author=(commit.get("author") or {}).get("login")
    files=commit.get("files")
    need(commit.get("sha")==tip and [p["sha"] for p in commit["parents"]]==[parent]
         and commit["commit"]["message"].splitlines()[0]==stage_headline(event)
         and isinstance(author,str) and author.casefold()==publisher.casefold()
         and signature.get("verified") is True and signature.get("reason")=="valid",
         "STAGING_EVENT_WRITER_OR_PARENT_UNVERIFIED_HOLD")
    need(isinstance(files,list) and len(files)==1 and files[0]["filename"]==CANDIDATE
         and files[0]["status"] in {"added","modified"} and files[0]["sha"]==draft_blob
         and paths_at(api,tip)[CANDIDATE]==draft_blob,
         "STAGING_EVENT_EXACT_BYTES_UNVERIFIED_HOLD")
    need(branch_head(BRANCH)==tip,"STAGING_EVENT_SUPERSEDED_HOLD")
    return tip
