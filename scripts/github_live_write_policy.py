"""Refuse Live mutation without an independently configured, active writer restriction."""
import re
from datetime import timedelta
from editorial_stage_authority import authenticate
from scheduled_publication_contract import stamp
from today_first_live import strict_json
from today_first_live import REPO,require

def confirm(api, *, ruleset_id, publisher_integration_id, approval=None, core_key=None,
            now=None, main_parent=None, draft_sha256=None):
    for value in (ruleset_id,publisher_integration_id):
        require(isinstance(value,str) and re.fullmatch(r"[1-9][0-9]{0,19}",value),"LIVE_WRITER_POLICY_PINS_REQUIRED")
    ident=int(ruleset_id)
    active=api("rules/branches/main")
    require(isinstance(active,list) and any(r.get("type")=="update" and r.get("ruleset_id")==ident for r in active),
            "LIVE_WRITER_UPDATE_RESTRICTION_NOT_ACTIVE")
    detail=api("rulesets/"+ruleset_id)
    require(detail.get("id")==ident and detail.get("target")=="branch" and detail.get("source")==REPO
            and detail.get("source_type")=="Repository" and detail.get("enforcement")=="active"
            and any(item.get("type")=="update" for item in detail.get("rules",[])),
            "LIVE_WRITER_RULESET_SCOPE_UNPROVEN")
    patterns=detail.get("conditions",{}).get("ref_name",{})
    require(patterns.get("include") in (["refs/heads/main"],["~DEFAULT_BRANCH"])
            and patterns.get("exclude")==[],"LIVE_WRITER_MAIN_SCOPE_UNPROVEN")
    roster=detail.get("bypass_actors")
    if approval is not None:
        record,_=authenticate(strict_json(approval),core_key)
        expected=dict(scope="AI_GROUP_CORE_GITHUB_RULESET_OBSERVATION_V1",repository=REPO,
                      branch="refs/heads/main",rulesetId=ident,rulesetUpdatedAt=detail["updated_at"],
                      mainParent=main_parent,draftSha256=draft_sha256)
        require(set(record)==set(expected)|{"issuedAt","expiresAt","bypassActors"}
                and all(record[k]==v for k,v in expected.items()),"LIVE_WRITER_POLICY_ATTESTATION_MISMATCH")
        issued,expiry=stamp(record["issuedAt"]),stamp(record["expiresAt"])
        require(issued<=now<expiry and expiry-issued<=timedelta(minutes=5),"LIVE_WRITER_POLICY_ATTESTATION_EXPIRED")
        require(roster is None or roster==record["bypassActors"], "LIVE_WRITER_POLICY_ROSTER_DRIFT")
        roster=record["bypassActors"]
    require(roster==[{"actor_type":"Integration","actor_id":int(publisher_integration_id),"bypass_mode":"always"}],
            "LIVE_WRITER_BYPASS_ROSTER_UNPROVEN")
    return {"repository":REPO,"branch":"main","approvedRuleset":ident,"publisherIntegrationId":int(publisher_integration_id)}


def confirm_app_transport(root_api, *, login, app_id):
    """The exclusive ruleset enforces acceptance. These reads pin the intended actor and scope."""
    m=re.fullmatch(r"([a-z0-9][a-z0-9-]{0,79})\[bot\]",login)
    require(m and isinstance(app_id,str) and re.fullmatch(r"[1-9][0-9]{0,19}",app_id),
            "LIVE_PUBLISHER_APP_IDENTITY_REQUIRED")
    slug=m[1]
    app=root_api("apps/"+slug)
    require(app.get("id")==int(app_id) and app.get("slug")==slug,"LIVE_PUBLISHER_APP_PIN_MISMATCH")
    scope=root_api("installation/repositories?per_page=2")
    names=[r.get("full_name") for r in scope.get("repositories",[])]
    require(scope.get("total_count")==1 and names==[REPO],"LIVE_PUBLISHER_INSTALLATION_SCOPE_HOLD")
    return {"expectedCommitAuthor":login,"githubAppId":int(app_id),"credentialRepository":REPO}
