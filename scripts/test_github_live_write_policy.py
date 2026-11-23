from copy import deepcopy
import unittest
from datetime import timedelta
from tempfile import TemporaryDirectory
from pathlib import Path
from test_editorial_authority_ci import TestKey,CLOCK,b64,sign_claims
from today_first_live import canonical
from github_live_write_policy import confirm,confirm_app_transport
from today_first_live import REPO

RULE={"id":41,"source":REPO,"source_type":"Repository","target":"branch","enforcement":"active",
      "conditions":{"ref_name":{"include":["refs/heads/main"],"exclude":[]}},"rules":[{"type":"update"}],
      "bypass_actors":[{"actor_type":"Integration","actor_id":92,"bypass_mode":"always"}]}

class ActivatedPolicyProof(unittest.TestCase):
    def check(self, rule=RULE, active=None, pin="92"):
        details={"rulesets/41":rule, "rules/branches/main":[{"type":"update","ruleset_id":41}] if active is None else active}
        return confirm(details.__getitem__,ruleset_id="41",publisher_integration_id=pin)

    def test_active_scoped_single_integration_is_required(self):
        self.assertEqual(self.check()["publisherIntegrationId"],92)

    def test_empty_configuration_evaluate_or_missing_update_rules_fail_closed(self):
        with self.assertRaisesRegex(ValueError,"PINS_REQUIRED"):self.check(pin="")
        with self.assertRaisesRegex(ValueError,"UPDATE_RESTRICTION"):self.check(active=[])
        with self.assertRaisesRegex(ValueError,"RULESET_SCOPE"):self.check(dict(RULE,enforcement="evaluate"))

    def test_missing_and_broad_bypass_fail_closed(self):
        for change in (None,RULE["bypass_actors"]+[{"actor_type":"RepositoryRole","actor_id":5,"bypass_mode":"always"}]):
            with self.subTest(roster=change),self.assertRaisesRegex(ValueError,"BYPASS_ROSTER"):
                self.check(dict(RULE,bypass_actors=change))

    def test_parent_repo_or_other_target_cannot_authorize_main(self):
        with self.assertRaisesRegex(ValueError,"RULESET_SCOPE"):
            self.check(dict(RULE, source="other/repository"))
        with self.assertRaisesRegex(ValueError,"MAIN_SCOPE"):
            self.check(dict(RULE,conditions={"ref_name":{"include":["refs/heads/other"],"exclude":[]}}))

    def test_app_lookup_and_single_repository_installation_required(self):
        docs={"apps/newsroom":dict(id=92,slug="newsroom"),"installation/repositories?per_page=2":
              {"total_count":1,"repositories":[{"full_name":REPO}]}}
        self.assertEqual(confirm_app_transport(docs.__getitem__,login="newsroom[bot]",app_id="92")["githubAppId"],92)
        with self.assertRaisesRegex(ValueError,"APP_PIN"):
            confirm_app_transport(docs.__getitem__,login="newsroom[bot]",app_id="93")
        docs["installation/repositories?per_page=2"]["total_count"]=2
        with self.assertRaisesRegex(ValueError,"INSTALLATION_SCOPE"):
            confirm_app_transport(docs.__getitem__,login="newsroom[bot]",app_id="92")
        with self.assertRaisesRegex(ValueError,"IDENTITY"):
            confirm_app_transport(docs.__getitem__,login="personal-user",app_id="92")

    def test_fresh_core_attestation_supplies_hidden_roster_without_admin_writer(self):
        with TemporaryDirectory() as directory:
            key=TestKey(Path(directory),b"P"*32)
            rule=dict(RULE,updated_at="2026-01-10T03:59:00Z")
            hidden={k:v for k,v in rule.items() if k!="bypass_actors"}
            records={"rulesets/41":hidden,"rules/branches/main":[{"type":"update","ruleset_id":41}]}
            att=dict(scope="AI_GROUP_CORE_GITHUB_RULESET_OBSERVATION_V1",repository=REPO,branch="refs/heads/main",
                     rulesetId=41,rulesetUpdatedAt=rule["updated_at"],mainParent="a"*40,draftSha256="b"*64,
                     issuedAt=CLOCK.isoformat(),expiresAt=(CLOCK+timedelta(minutes=4)).isoformat(),bypassActors=rule["bypass_actors"])
            options=dict(ruleset_id="41",publisher_integration_id="92",approval=canonical(sign_claims(key,att)),
                         core_key=b64(key.public),main_parent="a"*40,draft_sha256="b"*64)
            self.assertEqual(confirm(records.__getitem__,now=CLOCK,**options)["approvedRuleset"],41)
            with self.assertRaisesRegex(ValueError,"ATTESTATION_EXPIRED"):
                confirm(records.__getitem__,now=CLOCK+timedelta(minutes=5),**options)
            hidden["updated_at"]="2026-01-10T04:01:00Z"
            with self.assertRaisesRegex(ValueError,"ATTESTATION_MISMATCH"):
                confirm(records.__getitem__,now=CLOCK,**options)

if __name__=="__main__":unittest.main()
