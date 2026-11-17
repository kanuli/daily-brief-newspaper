# NAS-first Cantonese Newsroom — staged migration / Phase 2

Status: **DEVELOPMENT ONLY / NO NAS DEPLOYMENT / NO PUBLICATION** (2026-11-17 HKT)

## Purpose

Move discovery and newsroom work-state from GitHub Actions/branch JSON to the
existing Synology NAS, while preserving **the existing Central Core and EIC/Robot
hierarchy**. GitHub remains a downstream publication transport for exact,
previously approved artifacts, not the source of truth for ongoing newsroom work.
This path is intentionally a small vertical slice; it is not a new management
system or a replacement for the Central Core.

## Implemented in this branch

- `nas/newsroom/intake.py` reuses `scripts/rolling_news_collector.py` **unchanged**
  as a NAS-local subprocess. It does not call GitHub Actions or modify the checked-out
  repository. It can also import one already-produced staging snapshot offline.
- SQLite uses WAL, `busy_timeout=30000`, a single immediate transaction per intake
  cycle and idempotent `(desk,candidate_id)` keys. It retains original source
  publication timestamps separately from observation timestamps.
- The untrusted `PENDING_SOURCE_VERIFICATION` queue is a **read-only EIC intake
  surface**. Repeated collection never resets a previous `REJECTED`/verified
  queue decision. No command creates EIC approval or a publisher commit.
- `health` returns machine-readable queue counts for future CTO/Website Monitor
  integration; this is not a production health receipt.

No editorial thresholds, desk publication rules, signer trust, LLM routing,
GitHub release controls or scheduled ChatGPT tasks are changed.

## Real NAS prerequisites — not assumed

The last actual NAS evidence (2026-11-16/17) showed DSM 7.4.1, local
`/volume2` Btrfs, available space, Python 3.8.15 (and Python 3.9.22 separately
probed), SQLite 3.40, but Docker socket permission **DENIED** for UID 1026.
The existing NAS EIC app was observed by source hash, not demonstrated to be
an authorized signing/ACK connector. Thus there is **no basis** to claim
native Phase 2 signer/ACK, P19 or Store-18 production completion.

Run only in an independently authorized NAS pilot using an approved interpreter
that passes the included tests. The database **must** reside on NAS-local storage;
do not put an active WAL database on SMB/NFS or H: Windows mapped NAS share.
Do not access/reconfigure Docker socket or alter existing Container Manager
permissions as a workaround.

## Example interface (paths MUST be scoped and confirmed by NAS operator)

Use the same files in a verified local checkout or a read-only source bundle.
The following are command interfaces, not commands that were run on the NAS:

```sh
python3 nas/newsroom/intake.py --db /approved/nas-local/state/news.sqlite init
python3 nas/newsroom/intake.py --db /approved/nas-local/state/news.sqlite ingest --snapshot /approved/staging.json
python3 nas/newsroom/intake.py --db /approved/nas-local/state/news.sqlite inbox --limit 25
python3 nas/newsroom/intake.py --db /approved/nas-local/state/news.sqlite health
# Networked 15-minute collection, only after isolated NAS pilot approval:
python3 nas/newsroom/intake.py --db /approved/nas-local/state/news.sqlite collect --repo /approved/newsroom/checkout --mode normal
```

The `collect` entrypoint invokes the existing collector, not the Google/Gemma
local fallback. The script refuses unknown desks, invalid rows and fake approval
fields. One bad candidate is counted and skipped, rather than blocking other
news; a structurally broken snapshot rolls back the entire database transaction.

## Phase 2: required **integration**, not imaginary acceptance

1. **Central Core identity and dispatch:** map the new pending verification queue
   to the **existing EIC → verification Robot → EIC → CTO** path using real
   signed assignments and native ACK evidence. The current code only exposes an
   inbox; it cannot claim source verification or EIC signoff.
2. **Evidence:** Robot must fetch the original publisher, attach confirmed
   source and time evidence, and explicitly record failure. RSS title alone is
   not verified. An on-demand approved LLM may write copy only from supported
   source evidence; model offline must not stop collection.
3. **EIC editorial decision:** use the existing Core authorization and signed
   decision schema; do not invent a parallel `approved=true` or accept a
   checksum as a signature. Store immutable approval against exact draft bytes.
4. **Single publication outbox:** only Core-authorized, verified EIC output may
   enter publication. Generate Live, Desk and Daily independently so that
   one stale desk or an absent Daily does not block a valid Live story.
   This requires **review of the currently deployed merge/coverage contracts**;
   no gate has been disabled in this branch.
5. **GitHub publisher:** post immutable EIC-approved bytes using a compare-and-swap
   GitHub update; record commit, blob and public Pages evidence. A failed
   transport retries boundedly without reapproving or blindly replaying stale
   Live. Real deployment authorizations are separate.
6. **Native Phase 2 safety:** previous P19=NOT_CLOSED; Store-18=PARTIAL;
   Synology signer/ACK NOT_VERIFIED; production activation not proven.
   Continue these tests separately and do not substitute newsroom SQLite unit
   tests for native container/signer acceptance.

## Operational cutover

- Keep current production schedules/permissions unchanged until a **single
  current source-backed Live story** has been approved and publicly verified
  through the new pipeline. There is **no three-batch prerequisite**.
- Never run two competing publication writers. After authoritative cutover,
  redesign **Newsroom Publisher** as NAS intake/research support (not a direct
  GitHub writer), and **Newsroom Watchdog** as NAS queue/outbox/Pages monitor
  (not a second publisher). Both user-controlled task IDs and enabled states
  are preserved unless the owner separately authorizes changes.
- Preserve one-way migration: GitHub staging remains secondary/residual until
  the NAS ingestion loop is verified and ownership is explicitly switched.
- Roll back by stopping only the scoped pilot and restoring the last
  independently approved publication route; never delete accepted news or
  alter unrelated NAS services.

## Immediate evidence gap

This branch contains a real, testable NAS intake slice, but it is not deployed
to Synology: this ChatGPT session lacks a verified DSM administrative execution
channel. The next actionable native step is an authorized read-only inspection
of the actual NAS Python/SQLite and EIC interfaces, followed by an isolated
pilot—not a production Docker restart or hidden schedule change.
