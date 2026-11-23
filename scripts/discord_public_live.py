"""Allow a reader Live notice only for the exact publicly verified release."""
from hashlib import sha256
import re
from urllib.request import Request, urlopen

from today_first_live import LIVE, MAX_DRAFT, PAGES_RECEIPT, REPO, SITE, strict_json


def public_get(path):
    url = SITE + path
    request = Request(url, headers={"Cache-Control": "no-cache", "User-Agent": "DailyBriefGitHubActions/1.0"})
    with urlopen(request, timeout=12) as response:
        if response.geturl() != url or response.status != 200:
            raise ValueError("unexpected public Live URL or response")
        raw = response.read(4 * MAX_DRAFT + 1)
    if not raw or len(raw) > 4 * MAX_DRAFT:
        raise ValueError("public Live response outside bounds")
    return raw


def verified_readback(local=None, *, read=public_get):
    initial = read(PAGES_RECEIPT)
    receipt = strict_json(initial)
    if not isinstance(receipt, dict) or receipt.get("schema") not in {
            "PUBLICATION_BUILD_RECEIPT_V1", "PUBLICATION_BUILD_RECEIPT_V2"}:
        raise ValueError("unverified public Pages receipt")
    files = receipt.get("files")
    remote = read(LIVE)
    if (not isinstance(files, dict) or (local is not None and remote != local)
            or files.get(LIVE) != sha256(remote).hexdigest()
            or files.get("live.html") != sha256(read("live.html")).hexdigest()
            or read(PAGES_RECEIPT) != initial):
        raise ValueError("public Live payload, HTML or receipt does not match")
    return receipt, remote


def require_public_live(local, *, read=public_get):
    receipt, _ = verified_readback(local, read=read)
    return receipt["files"][LIVE]


def published_live_for_run(event, *, read=public_get):
    run = event.get("workflow_run", {})
    if (event.get("action") != "completed" or event.get("repository", {}).get("full_name") != REPO
            or run.get("head_repository", {}).get("full_name") != REPO or run.get("head_branch") != "main"
            or run.get("path") != ".github/workflows/pages.yml" or run.get("conclusion") != "success"):
        raise ValueError("unverified Pages workflow provenance")
    receipt, raw = verified_readback(read=read)
    candidate = receipt.get("liveCandidateCommit")
    if candidate is None:
        return None  # The full-newspaper notice retains its existing repository-triggered route.
    digest = receipt["files"][LIVE]
    if (not isinstance(candidate, str) or not re.fullmatch(r"[0-9a-f]{40}",candidate)
            or receipt.get("runId") != str(run.get("id")) or receipt.get("runAttempt") != str(run.get("run_attempt"))
            or receipt.get("builderCommit") != run.get("head_sha") or receipt.get("liveDraftSha256") != digest):
        raise ValueError("public Live is not the exact completed Pages release")
    data = strict_json(raw)
    if not isinstance(data, dict) or not isinstance(data.get("items"), list) or not data["items"]:
        raise ValueError("invalid published Live payload")
    return data, digest

