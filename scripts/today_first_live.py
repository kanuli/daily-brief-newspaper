"""Prepare an explicitly Core-authorized Live-only Pages artifact."""
import argparse
import base64
from datetime import datetime, timedelta, timezone
import hashlib
import json
import os
from pathlib import Path, PureWindowsPath
import re
import shutil
import subprocess
import tarfile
from tempfile import TemporaryDirectory
import time
import urllib.request

import build_static_news_fallback as renderer
from desk_freshness_policy import HKT, PUBLIC_DESK_FRESHNESS_HOURS, current_daily_dates, routed_slugs
from merge_live_into_desk import DESK_LABELS, live_coverage_diagnostics
from pages_publication_receipt import FILES as RECEIPT_FILES, RECEIPT as PAGES_RECEIPT, build as build_receipt
from scheduled_publication_contract import CONTRACT, publisher_errors, stamp
from verified_draft_pending import locator_only_url
from today_first_replacement import public_state as replacement_public_state, stage as stage_replacement

SCOPE = "AI_GROUP_CORE_LIVE_PAGES_RELEASE_V1"
REPO = "kanuli/daily-brief-newspaper"
SITE = "https://kanuli.github.io/daily-brief-newspaper/"
CANDIDATE = "data/scheduled-live-candidate.json"
LIVE = "data/live.json"
MAX_DRAFT = 1_048_576
LIVE_OUTPUTS = {LIVE, "live.html", PAGES_RECEIPT}
REPLACEMENT_READBACK = (*RECEIPT_FILES, "data/stocks-latest.json", "stocks.html")
CLAIMS = {"scope", "repository", "actor", "decision", "candidateCommit", "siteBaseCommit",
          "draftSha256", "issuedAt", "expiresAt"}


def require(ok, message):
    if not ok:
        raise ValueError(message)


def hash_bytes(raw):
    return hashlib.sha256(raw).hexdigest()


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def strict_json(raw):
    def pairs(rows):
        result = {}
        for key, val in rows:
            require(key not in result, "duplicate JSON key")
            result[key] = val
        return result
    return json.loads(raw, object_pairs_hook=pairs)


def verify_ed25519(public, message, signature, *, openssl):
    try:
        from cryptography.exceptions import InvalidSignature
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey
    except ImportError:
        pass
    else:
        try:
            Ed25519PublicKey.from_public_bytes(public).verify(signature, message)
        except InvalidSignature as exc:
            raise ValueError("invalid Core approval signature") from exc
        return
    # OpenSSL 3 verification for runners without the Python binding.
    with TemporaryDirectory() as temporary:
        root = Path(temporary)
        # RFC 8410 SubjectPublicKeyInfo for a provisioned existing Core key.
        key, msg, sig = [root / name for name in ("key.der", "claims", "sig")]
        key.write_bytes(bytes.fromhex("302a300506032b6570032100") + public)
        msg.write_bytes(message)
        sig.write_bytes(signature)
        p = subprocess.run([openssl, "pkeyutl", "-verify", "-pubin", "-keyform", "DER",
                            "-inkey", str(key), "-rawin", "-in", str(msg), "-sigfile", str(sig)],
                           timeout=10, capture_output=True)
        require(p.returncode == 0, "invalid Core approval signature")


def verify_approval(token, pin, raw, candidate, site_base, now, *, openssl="openssl"):
    require(bool(token and pin), "CORE_LIVE_APPROVAL_UNAVAILABLE")
    require(len(token) <= 4096 and len(pin) <= 88, "approval exceeds size bounds")
    envelope = strict_json(base64.b64decode(token, validate=True))
    require(isinstance(envelope, dict) and set(envelope) == {"claims", "signature"}, "invalid approval envelope")
    claims = envelope["claims"]
    require(isinstance(claims, dict) and set(claims) == CLAIMS, "unrecognized Core release claims")
    require((claims["scope"], claims["repository"], claims["actor"], claims["decision"]) ==
            (SCOPE, REPO, "CANTONESE_EIC", "APPROVE_LIVE_PAGES"), "wrong approval authority or scope")
    require((claims["candidateCommit"], claims["siteBaseCommit"], claims["draftSha256"]) ==
            (candidate, site_base, hash_bytes(raw)), "approval does not bind the exact input and site base")
    issued, expires = stamp(claims["issuedAt"]), stamp(claims["expiresAt"])
    require(issued <= now < expires and expires - issued <= timedelta(minutes=30), "invalid or expired Core approval")
    public = base64.b64decode(pin, validate=True)
    signature = base64.b64decode(envelope["signature"], validate=True)
    require(len(public) == 32 and len(signature) == 64, "invalid Ed25519 public key or signature")
    verify_ed25519(public, canonical(claims), signature, openssl=openssl)
    return issued


def candidate_live(raw, *, now):
    require(0 < len(raw) <= MAX_DRAFT, "Live payload size outside bounds")
    live = strict_json(raw)
    require(isinstance(live, dict) and live.get("publicationContract") == CONTRACT, "scheduled Live contract required")
    require(live.get("date") == now.astimezone(HKT).date().isoformat(), "Live must use today's Hong Kong date")
    errors = publisher_errors(live, now=now)
    require(not errors, "Live candidate rejected: " + "; ".join(errors))
    require(now - stamp(live["lastUpdated"]) <= timedelta(minutes=90), "Live candidate exceeds freshness window")
    for item in live["items"]:
        limit = min(PUBLIC_DESK_FRESHNESS_HOURS[desk] for desk in item["deskSlugs"])
        require(now - stamp(item["publishedAt"]) <= timedelta(hours=limit), "original source no longer fresh")
        require(not locator_only_url(item["sourceUrl"]), "original publisher article required")
        labels = {label.casefold(): desk for desk, label in DESK_LABELS.items()}
        labels.update({desk: desk for desk in DESK_LABELS}, finance="market-economy")
        require(all(labels.get(item[k].strip().casefold(), item["desk"]) == item["desk"]
                    for k in ("section", "sectionLabel")), "editorial section contradicts the primary desk")
        if item["desk"] in {"football", "manchester-united", "manga-anime"}:
            copy_evidence = {k: item[k] for k in ("id", "title", "dek", "summary")}
            require(item["desk"] in routed_slugs(copy_evidence), "specialist route not established by the article")
    # This is publisher input, not a completed Rolling Desk checkpoint.
    require(not live.get("coverage") and isinstance(live.get("coverage", {}), dict),
            "candidate must not assert Rolling Desk coverage")
    return live


def diagnostics(live, *, daily, desk, stock, now):
    dates = current_daily_dates(now=now)
    try:
        stock_at = stamp(stock.get("generatedAt"))
        stock_recent = timedelta(0) <= now - stock_at <= timedelta(hours=24)
    except (TypeError, ValueError, AttributeError):
        stock_recent = False
    result = {"daily": "CURRENT_DATE" if daily.get("date") in dates else "STALE_OR_MISSING",
              "stock": "RECENT_TIMESTAMP" if stock_recent else "STALE_OR_MISSING",
              "desk": "NOT_VERIFIED", "coverage": None}
    if not isinstance(desk.get("desks"), dict):
        return result
    try:
        coverage = live_coverage_diagnostics(live, desk, now=now)
        result["coverage"] = coverage
        result["desk"] = "COMPLETE_PROJECTION" if coverage["status"] == "COMPLETE" else "STALE_OR_INCOMPLETE"
    except (SystemExit, ValueError, TypeError, AttributeError):
        result["desk"] = "INVALID_EXISTING_DESK"
    return result


def prepare(site, raw, *, token, pin, candidate, site_base, current_public, now, openssl="openssl"):
    live = candidate_live(raw, now=now)
    issued = verify_approval(token, pin, raw, candidate, site_base, now, openssl=openssl)
    require(stamp(live["lastUpdated"]) <= issued, "Core approved before edition was produced")
    if current_public == raw:
        return {"decision": "ALREADY_PUBLIC", "draftSha256": hash_bytes(raw)}
    historical_errors = []
    try:
        old = strict_json(current_public)
        old_at = stamp(old.get("lastUpdated")) if isinstance(old, dict) and old.get("lastUpdated") else None
        if isinstance(old, dict) and isinstance(old.get("items"), list):
            historical_errors = [str(item.get("id", "")) for item in old["items"]
                                 if isinstance(item, dict) and not item.get("timeLabel")]
    except (ValueError, TypeError, AttributeError):
        old = {}
        old_at = None  # bad historical input is not reused as today's candidate
    require(old_at is None or stamp(live["lastUpdated"]) > old_at, "would replace a newer or same-edition Live")
    def material(items):
        return sorted(canonical({k: item.get(k) for k in ("id", "sourceUrl", "title", "body", "publishedAt")})
                      for item in items if isinstance(item, dict))
    if (isinstance(old, dict) and old.get("date") == live["date"] and not historical_errors
            and isinstance(old.get("items"), list) and material(old["items"]) == material(live["items"])):
        # Only a valid previously published Live can make a correction redundant.
        # An older malformed artifact is not a substitute for the independent candidate.
        try:
            previously_valid = old.get("publicationContract") == CONTRACT and not publisher_errors(old, now=now)
        except (KeyError, TypeError, ValueError):
            previously_valid = False
        if previously_valid:
            return {"decision": "NO_MATERIAL_CHANGE", "draftSha256": hash_bytes(raw)}
    def load(name):
        try:
            row = strict_json((site / name).read_bytes())
            return row if isinstance(row, dict) else {}
        except (OSError, ValueError):
            return {}
    checks = diagnostics(live, daily=load("data/latest.json"), desk=load("data/desk-latest.json"),
                         stock=load("data/stocks-latest.json"), now=now)
    checks["historicalLiveMissingTimeLabel"] = historical_errors
    root = renderer.ROOT
    renderer.ROOT = site
    try:
        renderer.build_live(live)
    finally:
        renderer.ROOT = root
    rendered = (site / "live.html").read_bytes()
    require(all(renderer.esc(item["title"]).encode() in rendered for item in live["items"]), "Live HTML missing article")
    (site / LIVE).write_bytes(raw)
    require((site / LIVE).read_bytes() == raw, "completed artifact changed approved Live bytes")
    return {"decision": "READY", "draftSha256": hash_bytes(raw), "liveHtmlSha256": hash_bytes(rendered),
            "previousPublicLiveSha256": hash_bytes(current_public), "diagnostics": checks}


def git(*args):
    return subprocess.check_output(["git", *args], timeout=40)


def public_bytes(name):
    request = urllib.request.Request(SITE + name, headers={"Cache-Control": "no-cache"})
    with urllib.request.urlopen(request, timeout=15) as response:
        require(response.geturl() == SITE + name, "unexpected Pages readback redirect")
        limit = 16 * MAX_DRAFT if name == "data/desk-latest.json" else 4 * MAX_DRAFT
        raw = response.read(limit + 1)
    require(len(raw) <= limit, "Pages readback exceeds bounds")
    return raw


def live_base_receipt(raw, commit):
    receipt = strict_json(raw)
    require(isinstance(receipt, dict) and receipt.get("schema") == "PUBLICATION_BUILD_RECEIPT_V1"
            and receipt.get("sourceCommit") == commit, "published Pages base does not match the approved commit")
    for key in ("runId", "runAttempt"):
        require(isinstance(receipt.get(key), str) and re.fullmatch(r"[1-9][0-9]*", receipt[key]),
                "invalid base Pages run identity")
    files = receipt.get("files")
    require(isinstance(files, dict) and set(files) == set(RECEIPT_FILES)
            and all(isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) for value in files.values()),
            "invalid base Pages content receipt")
    require(isinstance(receipt.get("builderCommit",commit),str)
            and re.fullmatch(r"[0-9a-f]{40}",receipt.get("builderCommit",commit)),
            "invalid base Pages builder identity")
    return receipt


def extract_base(site, archive_path):
    # Pages publishes its built tar, not the source Git tree. Never restore a
    # tracked tree over the output of a build, including non-Live prerenders.
    with tarfile.open(archive_path, "r:") as archive:
        names = set()
        total = 0
        for entry in archive:
            if entry.name == "." and entry.isdir():
                continue
            name = entry.name[2:] if entry.name.startswith("./") else entry.name
            parts = name.split("/")
            require(not PureWindowsPath(name).drive and "\\" not in name and ":" not in name
                    and all(part.casefold() not in {"", ".", "..", ".git", ".github", ".env"}
                            and not part.casefold().startswith(".env.") for part in parts)
                    and (entry.isfile() or entry.isdir()) and name.casefold() not in names,
                    "unsafe Pages artifact entry")
            names.add(name.casefold())
            require(len(names) <= 20_000, "Pages base artifact exceeds file limit")
            dest = site.joinpath(*parts)
            if entry.isdir():
                dest.mkdir(parents=True, exist_ok=True)
                continue
            total += entry.size
            require(total <= 1024 ** 3, "Pages base artifact exceeds size limit")
            dest.parent.mkdir(parents=True, exist_ok=True)
            with archive.extractfile(entry) as source, dest.open("xb") as out:
                shutil.copyfileobj(source, out)


def validate_base(site, raw_receipt, commit, *, read_public):
    require((site / PAGES_RECEIPT).read_bytes() == raw_receipt, "artifact and public Pages receipts differ")
    receipt = live_base_receipt(raw_receipt, commit)
    for name, expected in receipt["files"].items():
        require(hash_bytes((site / name).read_bytes()) == expected
                and hash_bytes(read_public(name)) == expected, f"Pages base content mismatch: {name}")
    for name in ("data/stocks-latest.json", "stocks.html"):
        require((site / name).read_bytes() == read_public(name), f"Pages base content mismatch: {name}")
    return (site / LIVE).read_bytes()


def preserved_site_hash(site):
    manifest = {}
    for path in sorted(site.rglob("*")):
        name = path.relative_to(site).as_posix()
        require(not path.is_symlink(), "unexpected symlink in Pages site")
        if path.is_file() and name not in LIVE_OUTPUTS:
            digest = hashlib.sha256()
            with path.open("rb") as stream:
                for block in iter(lambda: stream.read(1024 * 1024), b""):
                    digest.update(block)
            manifest[name] = digest.hexdigest()
    return hash_bytes(canonical(manifest))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("operation", choices=("base", "prepare", "check", "verify"))
    args = parser.parse_args()
    if args.operation == "verify":
        receipt = strict_json(Path(os.environ["RUNNER_TEMP"], "today-first-result.json").read_bytes())
        for attempt in range(8):
            try:
                if (hash_bytes(public_bytes(PAGES_RECEIPT)) == receipt["pagesReceiptSha256"]
                        and hash_bytes(public_bytes(LIVE)) == receipt["draftSha256"]
                        and hash_bytes(public_bytes("live.html")) == receipt["liveHtmlSha256"]):
                    print("TODAY_FIRST_PUBLIC_LIVE_MATCH", receipt["draftSha256"])
                    return
            except (OSError, ValueError):
                pass
            if attempt < 7:
                time.sleep(3)
        raise ValueError("public Live bytes or HTML did not match approval")
    candidate, site_base = os.environ["LIVE_CANDIDATE_COMMIT"], os.environ["LIVE_SITE_BASE_COMMIT"]
    require(all(re.fullmatch(r"[a-f0-9]{40}", v) for v in (candidate, site_base)), "exact commits required")
    runner = Path(os.environ["RUNNER_TEMP"])
    site = runner / "today-first-site"
    base_path = runner / "today-first-base-receipt.json"
    now = datetime.now(timezone.utc)
    base_mode = os.environ.get("LIVE_BASE_MODE", "existing")
    require(base_mode in {"existing", "replacement"}, "unknown Pages base mode")
    replacement = base_mode == "replacement"
    if replacement:
        require(os.environ.get("LIVE_REPLACEMENT_ENABLED") == "true"
                and os.environ.get("LIVE_REPLACEMENT_SOURCE") == site_base,
                "separately approved replacement baseline is not enabled")
    token, pin = os.environ.get("LIVE_CORE_APPROVAL"), os.environ.get("LIVE_CORE_PUBLIC_KEY")
    if args.operation == "base":
        try:
            raw_receipt = public_bytes(PAGES_RECEIPT)
        except OSError as exc:
            raise ValueError("PAGES_BASE_RECEIPT_UNAVAILABLE_HOLD") from exc
        base = live_base_receipt(raw_receipt, site_base)
        base_path.write_bytes(raw_receipt)
        with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as out:
            out.write(f"run_id={base['runId']}\nrun_attempt={base['runAttempt']}\n")
            out.write(f"builder_commit={base.get('builderCommit',site_base)}\n")
        return
    if args.operation == "check":
        raw = (site / LIVE).read_bytes()
        receipt = strict_json((runner / "today-first-result.json").read_bytes())
        candidate_live(raw, now=now)  # recheck HKT midnight and source freshness before deploy
        verify_approval(token, pin, raw, candidate, site_base, now)
        require(receipt["decision"] == "READY" and hash_bytes(raw) == receipt["draftSha256"]
                and hash_bytes((site / "live.html").read_bytes()) == receipt["liveHtmlSha256"],
                "built Live payload changed")
        require(hash_bytes(public_bytes(LIVE)) == receipt["previousPublicLiveSha256"],
                "public Live moved during preparation")
        if replacement:
            require(replacement_public_state(public_bytes, PAGES_RECEIPT, REPLACEMENT_READBACK, canonical=canonical)
                    == os.environ["LIVE_REPLACEMENT_PUBLIC_PIN"] == receipt["replacementPublicSha256"]
                    and os.environ["LIVE_REPLACEMENT_SITE_PIN"] == receipt["replacementBaselineSha256"],
                    "replacement base or pinned public snapshot moved before deployment")
        else:
            require(public_bytes(PAGES_RECEIPT) == base_path.read_bytes(), "public Pages base moved before deployment")
        require(hash_bytes((site / PAGES_RECEIPT).read_bytes()) == receipt["pagesReceiptSha256"],
                "built Pages receipt changed")
        require(preserved_site_hash(site) == receipt["preservedSiteSha256"],
                "non-Live Pages artifact changed before deployment")
        return
    require(git("rev-parse", "refs/remotes/origin/prepublish-news").decode().strip() == candidate,
            "candidate branch moved")
    require(git("ls-tree", candidate, "--", CANDIDATE).startswith(b"100644 blob "), "candidate is not a regular file")
    require(0 < int(git("cat-file", "-s", f"{candidate}:{CANDIDATE}")) <= MAX_DRAFT, "candidate file outside bounds")
    raw = git("show", f"{candidate}:{CANDIDATE}")
    verify_approval(token, pin, raw, candidate, site_base, now)
    site.mkdir()
    if replacement:
        current_public = public_bytes(LIVE)
        manifest = stage_replacement(site, git, site_base, PAGES_RECEIPT,
                    site_pin=os.environ["LIVE_REPLACEMENT_SITE_PIN"],
                    read=lambda name: current_public if name == LIVE else public_bytes(name),
                    tracked_files=REPLACEMENT_READBACK, public_pin=os.environ["LIVE_REPLACEMENT_PUBLIC_PIN"],
                    canonical=canonical)
    else:
        extract_base(site, runner / "today-first-base-artifact" / "artifact.tar")
        current_public = validate_base(site, base_path.read_bytes(), site_base, read_public=public_bytes)
    preserved = preserved_site_hash(site)
    receipt = prepare(site, raw, token=token, pin=pin,
                      candidate=candidate, site_base=site_base, current_public=current_public,
                      now=datetime.now(timezone.utc))
    if receipt["decision"] == "READY":
        lineage = build_receipt(site, commit=site_base, run_id=os.environ["GITHUB_RUN_ID"],
                                attempt=os.environ["GITHUB_RUN_ATTEMPT"])
        builder = os.environ["GITHUB_SHA"]
        require(bool(re.fullmatch(r"[0-9a-f]{40}",builder)), "invalid workflow builder identity")
        lineage.update(builderCommit=builder, liveCandidateCommit=candidate, liveDraftSha256=receipt["draftSha256"],
                       preservedSiteSha256=preserved)
        if replacement:
            release = dict(replacementBaselineSha256=manifest,
                           replacementPublicSha256=os.environ["LIVE_REPLACEMENT_PUBLIC_PIN"])
            lineage.update(release)
            receipt.update(release)
        else:
            lineage["previousPagesReceiptSha256"] = hash_bytes(base_path.read_bytes())
        next_receipt = canonical(lineage)
        (site / PAGES_RECEIPT).write_bytes(next_receipt)
        receipt["pagesReceiptSha256"] = hash_bytes(next_receipt)
        require(preserved_site_hash(site) == preserved, "Live rendering modified the preserved site")
        receipt["preservedSiteSha256"] = preserved
    (runner / "today-first-result.json").write_text(json.dumps(receipt), encoding="utf-8")
    with open(os.environ["GITHUB_OUTPUT"], "a", encoding="utf-8") as out:
        out.write("decision=" + receipt["decision"] + "\n")
    print(json.dumps(receipt, sort_keys=True))


if __name__ == "__main__":
    main()
