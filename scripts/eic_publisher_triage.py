"""Deterministic, fail-closed Cantonese publication dependency triage.

Consumes bounded public GitHub run metadata and unprivileged NAS observation.
Produces analysis, not repair authorization or a fabricated root cause.
"""
from __future__ import annotations
import datetime as dt
import hashlib
import json
from typing import Any
from publisher_job_chain_v13 import analyze as analyze_job_chain


def _instant(value: Any):
    if not isinstance(value, str): return None
    try:
        x = dt.datetime.fromisoformat(value.replace('Z', '+00:00'))
        return x.astimezone(dt.timezone.utc) if x.tzinfo is not None else None
    except (ValueError, OverflowError):
        return None


def _recent(run: dict, now: dt.datetime, days: int = 3) -> bool:
    stamp = _instant(run.get('updated_at')) or _instant(run.get('created_at'))
    return bool(stamp and -dt.timedelta(minutes=10) <= now-stamp <= dt.timedelta(days=days))


def classify(github: dict, nas: dict | None, now: dt.datetime) -> dict:
    """No network or side-effects. Does not interpret 'Publisher stuck' as verified root cause."""
    if now.tzinfo is None: raise ValueError('timezone aware now required')
    now = now.astimezone(dt.timezone.utc)
    runs = github.get('recent_runs') or []
    recent = [r for r in runs if isinstance(r, dict) and _recent(r, now)]
    def matching(fragment: str):
        return next((r for r in recent if fragment in str(r.get('name','')).lower()), None)
    collector = matching('rolling news search')
    eic = matching('editor-in-chief')
    assignment = github.get('assignment') or {}
    if not isinstance(assignment, dict): assignment={}
    source = ((nas or {}).get('source') or {}) if isinstance(nas,dict) else {}
    payload = source.get('payload') or {} if isinstance(source,dict) else {}
    if not isinstance(payload,dict):payload={}
    desk = payload.get('desk_latest') or {}
    publication_ok = assignment.get('publicationValidatorOk') is True
    stale = assignment.get('staleDeskCount')
    if not isinstance(stale,int) or isinstance(stale,bool) or stale < 0: stale=None
    nas_healthy = payload.get('healthy') is True
    collected_at = _instant(source.get('collected_at'))
    nas_fresh = bool(collected_at and dt.timedelta(minutes=-10)<=now-collected_at<=dt.timedelta(minutes=10))
    collector_ok = bool(collector and collector.get('conclusion')=='success')
    eic_failure = bool(eic and eic.get('conclusion')=='failure')
    # A source-supplied `source_authenticated` flag is itself untrusted.
    # This diagnostic consumes unsigned/indirect captures and no independent
    # cryptographic publication verification receipt. It CANNOT declare recovery.
    claimed_current = bool(publication_ok and stale == 0 and nas_fresh and nas_healthy
                           and isinstance(desk,dict) and desk.get('fresh') is True)

    job_chain=analyze_job_chain(github, now=now)
    result={
        'schema':'CANTONESE_PUBLISHER_TRIAGE_V1', 'observed_at_utc':now.isoformat(),
        'source_trust':'UNSIGNED_NAS_OBSERVATION' if source and source.get('source_authenticated') is False else 'NOT_VERIFIED',
        'collector':'RECENT_SUCCESS' if collector_ok else 'NOT_VERIFIED_OR_FAILED',
        'editor_in_chief':'RECENT_FAILURE' if eic_failure else 'NOT_VERIFIED_OR_OTHER',
        'stale_desk_count':stale,
        'publication_validator':'PASS' if publication_ok else 'NOT_PASS',
        'publication_recovery':'NOT_VERIFIED',
        'publication_claim':'CURRENT_UNVERIFIED_CLAIM' if claimed_current else 'NOT_CURRENT_OR_UNVERIFIED',
        'independent_publication_receipt':'MISSING',
        'github_job_chain':job_chain,
        'trust_boundary':'UNSIGNED_CAPTURE_CANNOT_SELF_ATTEST',

        'producer_october_failure':'HISTORICAL_SEPARATE_INCIDENT',
        'external_publisher_root_cause':'NOT_VERIFIED',
        'next_authorized_owner':'CANTONESE_EIC',
        'recommended_scope':'INVESTIGATE_EXTERNAL_PUBLISHER_WITH_EIC; DO_NOT_RETRY_IDENTICAL_STUCK_ASSIGNMENT',
        'NO_SEND':True, 'NO_AUTO_REPAIR':True, 'production_change_authorized':False,
        'evidence_refs':[r.get('html_url') for r in (collector,eic) if isinstance(r,dict) and isinstance(r.get('html_url'),str)],
    }
    # Deterministic digest over evidence content, excluding wall clock and volatile source details.
    proof={k:result[k] for k in ('collector','editor_in_chief','stale_desk_count','publication_validator',
        'producer_october_failure','external_publisher_root_cause','evidence_refs','publication_claim','trust_boundary','github_job_chain')}
    result['evidence_fingerprint_sha256']=hashlib.sha256(json.dumps(proof,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    return result
