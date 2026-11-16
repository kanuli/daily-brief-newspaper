"""Non-mutating GitHub Collector -> EIC job-chain correlation.

Correlating workflow metadata is not proof of the external Publisher's root cause.
"""
from __future__ import annotations
import datetime as dt
import hashlib
import json


def _stamp(value):
    if not isinstance(value, str): return None
    try:
        x = dt.datetime.fromisoformat(value.replace('Z', '+00:00'))
        return x.astimezone(dt.timezone.utc) if x.tzinfo else None
    except (ValueError, OverflowError):
        return None


def analyze(github: dict, *, now: dt.datetime) -> dict:
    if now.tzinfo is None: raise ValueError('timezone-aware now required')
    now=now.astimezone(dt.timezone.utc)
    if not isinstance(github,dict): github={}
    runs=[r for r in github.get('recent_runs', []) if isinstance(r,dict)]
    def pick(fragment):
        eligible=[]
        for r in runs:
            if fragment not in str(r.get('name','')).lower(): continue
            stamp=_stamp(r.get('updated_at')) or _stamp(r.get('created_at'))
            if stamp is not None and -600 <= (now-stamp).total_seconds() <= 172800:
                eligible.append((stamp,r))
        return sorted(eligible,key=lambda pair:pair[0],reverse=True)[0][1] if eligible else None
    collector=pick('rolling news search')
    eic=pick('editor-in-chief')
    bound=bool(collector and eic and collector.get('head_sha') and
          collector.get('head_sha')==eic.get('head_sha') and
          collector.get('head_branch')==eic.get('head_branch'))
    jobs=github.get('eic_jobs') or []
    if not isinstance(jobs,list):jobs=[]
    provenance=bool(eic and type(eic.get('id')) is int and
                    type(github.get('eic_jobs_run_id')) is int and
                    github['eic_jobs_run_id']==eic['id'])
    steps=sorted(set(step[:120] for job in jobs if isinstance(job,dict)
       and job.get('conclusion')=='failure' for step in (job.get('failed_steps') or [])
       if isinstance(step,str)))[:10] if provenance else []
    collector_ok=bool(collector and collector.get('conclusion')=='success')
    eic_failure=bool(eic and eic.get('conclusion')=='failure')
    if bound and collector_ok and eic_failure and steps:
        stage='CURRENT_COLLECTOR_SUCCESS_EIC_FAILURE_STEP'
    elif collector_ok and eic_failure:
        stage='COLLECTOR_SUCCESS_EIC_FAILURE_CAUSE_UNVERIFIED'
    else:
        stage='INCOMPLETE_OR_UNRELATED_CURRENT_WORKFLOWS'
    result=dict(collector_run_id=collector.get('id') if collector else None,
        eic_run_id=eic.get('id') if eic else None,
        same_head_sha_and_branch=bound,jobs_bound_to_run=provenance,
        failed_step_names=steps,observed_stage=stage)
    fingerprint=hashlib.sha256(json.dumps(result,sort_keys=True,separators=(',',':')).encode()).hexdigest()
    return {'schema':'CANTONESE_GITHUB_JOB_CHAIN_V1',**result,
      'publisher_internal_root_cause':'NOT_VERIFIED',
      'publication_recovery':'NOT_VERIFIED',
      'metadata_fingerprint_sha256':fingerprint,
      'independent_publication_receipt':'MISSING',
      'NO_SEND':True,'auto_repair':False}
