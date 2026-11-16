"""Read-only normalized observations of existing ChatGPT Tasks.

This is an application intake schema, NOT a ChatGPT API or signing authority.
Owner reports and exported receipts remain unsigned until the existing Core
independently authorizes them. No scheduler, publisher or retry executor exists here.
"""
from datetime import datetime, timezone
import re

TASKS = {
    '6a8690a77d608191ae9a860ff3435f92': ('Newsroom Publisher', 'cantonese_newspaper', 'kanuli/daily-brief-newspaper'),
    '6a8a76ba60948191aaead84a11d8f91c': ('Newsroom Watchdog', 'cantonese_newspaper', 'kanuli/daily-brief-newspaper'),
    '6a91a8df95948191903fc3050f308347': ('Japanese Pages Health Watch', 'japanese_learning', 'kanuli/japanese-vocab-game'),
}
PUBLISHER = '6a8690a77d608191ae9a860ff3435f92'

def stamp(value):
    if not isinstance(value, str):
        raise ValueError('SCHEDULED_TIMESTAMP_REQUIRED')
    result = datetime.fromisoformat(value.replace('Z', '+00:00'))
    if result.tzinfo is None or result.utcoffset() is None:
        raise ValueError('SCHEDULED_TIMEZONE_REQUIRED')
    return result.astimezone(timezone.utc)

def unavailable(task_id, checked_at):
    return dict(schema='SCHEDULED_SERVICE_OBSERVATION_V1', task_id=task_id,
                repository=TASKS[task_id][2], checked_at=checked_at, enabled=None,
                provenance='NO_DIRECT_TASK_INTERFACE', run_history_access='UNAVAILABLE')

def assess(data):
    if data.get('schema') != 'SCHEDULED_SERVICE_OBSERVATION_V1' or data.get('task_id') not in TASKS:
        raise ValueError('SCHEDULED_TASK_IDENTITY_HOLD')
    name, branch, repo = TASKS[data['task_id']]
    if data.get('repository') != repo or data.get('provenance') not in {
            'OWNER_SUPPLIED_REPORT', 'RECORDED_OFFICIAL_RECEIPT', 'NO_DIRECT_TASK_INTERFACE'}:
        raise ValueError('SCHEDULED_TASK_SCOPE_HOLD')
    checked = stamp(data['checked_at'])
    enabled = data.get('enabled')
    if enabled is not None and type(enabled) is not bool:
        raise ValueError('SCHEDULED_ENABLED_TYPE_HOLD')
    access = data.get('run_history_access')
    if access not in {'UNAVAILABLE', 'RECORDED_RECEIPT_ONLY'}:
        raise ValueError('SCHEDULED_HISTORY_SCOPE_HOLD')
    reasons = ['SCHEDULED_OBSERVATION_UNSIGNED']
    if access == 'UNAVAILABLE':
        reasons.append('SCHEDULED_TASK_RUN_HISTORY_UNAVAILABLE')
    state = 'ENABLED_REPORTED' if enabled is True else 'DISABLED_REPORTED' if enabled is False else 'ENABLEMENT_NOT_VERIFIED'
    if enabled is False:
        reasons.append('SCHEDULED_TASK_REPORTED_DISABLED')
    run = data.get('last_run')
    run_state, after = 'NOT_VERIFIED', 'NOT_VERIFIED'
    if run is not None:
        if not isinstance(run, dict) or run.get('task_id') != data['task_id']:
            raise ValueError('SCHEDULED_RUN_TASK_MISMATCH_HOLD')
        at = stamp(run['completed_at'])
        if at > checked or run.get('result') not in {'SUCCESS', 'FAILURE', 'SAFETY_BLOCKED', 'NO_COMMIT'}:
            raise ValueError('SCHEDULED_RUN_RESULT_HOLD')
        run_state = run['result'] + '_REPORTED'
        if data.get('reenabled_at') is not None:
            enabled_at = stamp(data['reenabled_at'])
            if enabled_at > checked:
                raise ValueError('SCHEDULED_ENABLEMENT_TIME_HOLD')
            after = 'AFTER_REENABLE_REPORTED' if at >= enabled_at else 'BEFORE_REENABLE_REPORTED'
        if run['result'] == 'SAFETY_BLOCKED':
            reasons.append('SAFETY_BLOCK_REPORTED_NO_ALTERNATE_RETRY')
        elif run['result'] != 'SUCCESS':
            reasons.append('SCHEDULED_EXECUTION_FAILURE_REPORTED')
    else:
        reasons.append('SCHEDULED_EXECUTION_NOT_VERIFIED')
    commit = data.get('github_commit')
    commit_state = 'NOT_VERIFIED'
    if commit is not None:
        if (commit.get('repository') != repo or not re.fullmatch(r'[0-9a-f]{40}', str(commit.get('sha', '')))
                or stamp(commit['committed_at']) > checked):
            raise ValueError('SCHEDULED_COMMIT_BINDING_HOLD')
        # A real GitHub commit is still not proof of which Scheduled Task ran.
        commit_state = 'COMMIT_RECORDED_TASK_CORRELATION_NOT_VERIFIED'
    elif data['task_id'] == PUBLISHER:
        reasons.append('PUBLISHER_VERIFIED_COMMIT_MISSING')
    website = data.get('website_observation')
    if website is not None:
        if (not isinstance(website, dict) or website.get('url') != 'https://kanuli.github.io/' + repo.split('/')[1] + '/'
                or type(website.get('http')) is not int or not 0 <= website['http'] <= 599
                or stamp(website['observed_at']) > checked
                or not re.fullmatch(r'[0-9a-f]{64}', str(website.get('body_sha256', '')))):
            raise ValueError('SCHEDULED_WEBSITE_OBSERVATION_HOLD')
    actions = data.get('github_actions', [])
    if not isinstance(actions, list) or len(actions) > 30:
        raise ValueError('SCHEDULED_GITHUB_ACTIONS_BOUND_HOLD')
    for action in actions:
        if (not isinstance(action, dict) or type(action.get('id')) is not int
                or action['id'] < 1 or action.get('url') != f"https://github.com/{repo}/actions/runs/{action['id']}"
                or stamp(action['updated_at']) > checked
                or action.get('conclusion') not in {None, 'success', 'failure', 'skipped', 'cancelled', 'timed_out', 'neutral', 'action_required', 'stale'}):
            raise ValueError('SCHEDULED_GITHUB_ACTION_SCOPE_HOLD')
    if any(a.get('conclusion') in {'failure', 'timed_out'} for a in actions):
        reasons.append('GITHUB_ACTION_FAILURE_RECORDED')
    deployment = next((a for a in actions if a.get('path') == 'dynamic/pages/pages-build-deployment'), None)
    return dict(task_id=data['task_id'], name=name, branch=branch, repository=repo,
                task_enablement=state, run_state=run_state, run_after_reenable=after,
                evidence_provenance=data['provenance'], checked_at=data['checked_at'],
                last_recorded_run=({k:run[k] for k in ('task_id','completed_at','result')} if run else None),
                github_commit=({k:commit[k] for k in ('repository','sha','committed_at')} if commit else None),
                run_history_access=access, github_commit_state=commit_state,
                publication_verified='NOT_VERIFIED', eic_verified='NOT_VERIFIED', cto_verified='NOT_VERIFIED',
                website_observation=website, github_actions=actions,
                website_state=('HTTP_200_RECORDED' if website.get('http') == 200 else 'HTTP_FAILURE_RECORDED') if website else 'NOT_VERIFIED',
                github_pages_deployment=deployment or 'NOT_VERIFIED',
                reason_codes=reasons, outcome='HOLD', authenticated=False,
                automatic_retry_allowed=False, task_mutation_allowed=False, external_send=False,
                next_action=('EIC_REQUEST_OFFICIAL_SAFETY_REVIEW_NO_ALTERNATE_WRITE_CHANNEL'
                             if 'SAFETY_BLOCK_REPORTED_NO_ALTERNATE_RETRY' in reasons
                             else 'OWNER_OBTAIN_ORIGINAL_TASK_RUN_RECEIPT_AND_INDEPENDENT_GITHUB_EVIDENCE'))
