"""Deterministic EIC repair investigation planning, not a live repair executor.

Only creates a bounded diagnostic/verification scope; every mutating step requires
existing EIC/Robot authority and exact owner approval outside this module.
"""
from __future__ import annotations
import hashlib
import json

def plan(triage:dict)->dict:
    if not isinstance(triage,dict):
        raise TypeError('triage must be an object')
    triggers=[]
    if triage.get('collector')=='RECENT_SUCCESS':
        triggers.append('COLLECTOR_CANDIDATES_RECENT')
    if triage.get('editor_in_chief')=='RECENT_FAILURE':
        triggers.append('EIC_ASSIGNMENT_FAILED')
    if triage.get('publication_validator')!='PASS':
        triggers.append('PUBLISH_VALIDATOR_NOT_PASS')
    if triage.get('publication_recovery')!='NOT_VERIFIED':
        triggers.append('UNTRUSTED_RECOVERY_CLAIM_REJECTED')
    scope=[
      dict(step='CHECK_LATEST_PUBLISHER_ACTION_AND_DISPATCH_GATES',role='CANTONESE_EIC',mutating=False),
      dict(step='COMPARE_SOURCE_ARTICLE_FETCH_AND_VERIFICATION_LOGS',role='CANTONESE_EIC',mutating=False),
      dict(step='BUILD_EIC_APPROVABLE_FIX_AND_ROLLBACK',role='EXISTING_ROBOT',mutating=False),
      dict(step='EXECUTE_ONLY_IF_SCOPED_OWNER_APPROVAL',role='EXISTING_ROBOT',mutating=True,authorization='REQUIRED_NOT_GRANTED'),
      dict(step='VERIFY_FRESH_DESK_EDITOR_LIVE_AND_PUBLIC_PROOF',role='CANTONESE_EIC',mutating=False),
      dict(step='INDEPENDENT_CTO_VERIFY',role='CTO',mutating=False),
    ]
    facts=dict(incident_owner='CANTONESE_EIC',recovery='NOT_VERIFIED',root_cause='NOT_VERIFIED',
               trigger_codes=triggers,steps=scope,NO_SEND=True,auto_repair=False,
               production_change_authorized=False)
    canonical=json.dumps(facts,sort_keys=True,separators=(',',':'),ensure_ascii=True).encode()
    return {**facts,'scope_sha256':hashlib.sha256(canonical).hexdigest()}
