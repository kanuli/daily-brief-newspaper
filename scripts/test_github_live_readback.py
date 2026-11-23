"""Pinned GitHub readback cases for a delayed or superseded scheduled publication."""
from copy import deepcopy
import unittest
from signed_live_publisher import confirmed_successor,headline

BASE,WRITE,HEAD=("a"*40,"b"*40,"c"*40)
BLOB="e"*40
BOUND=dict(mainParent=BASE,publisher="publisher-test",eventId="0"*64,
           authorizationSha256="1"*64,coreCustodySha256="2"*64,draftSha256="3"*64,liveBlob=BLOB)


def history(verified=True):
    return {
      HEAD:dict(sha=HEAD,parents=[{"sha":WRITE}],author={"login":"other-change"},commit={"message":"unrelated"}),
      WRITE:dict(sha=WRITE,parents=[{"sha":BASE}],author={"login":"publisher-test"},
                 commit=dict(message=headline(BOUND),verification={"verified":verified,"reason":"valid" if verified else "unsigned"}),
                 files=[dict(filename="data/live.json",sha=BLOB)])
    }


class GitHubReadback(unittest.TestCase):
    def check(self, records,tip=HEAD):
        requests=[]
        def fetch(path):
            requests.append(path)
            return records[path.rsplit("/",1)[1]]
        return confirmed_successor(BOUND,branch_head=lambda _:tip,api=fetch,require_github_signature=True),requests

    def test_later_main_change_does_not_destroy_exact_first_parent_proof(self):
        seen,reads=self.check(history())
        self.assertEqual(seen["commit"],WRITE)
        self.assertFalse(seen["writeIsObservedHead"])
        self.assertTrue(seen["githubSignatureVerified"])
        self.assertEqual(reads,["commits/"+HEAD,"commits/"+WRITE])

    def test_matching_account_and_bytes_without_github_signature_holds(self):
        with self.assertRaisesRegex(ValueError,"COMMIT_SIGNATURE_HOLD"):
            self.check(history(verified=False))

    def test_validly_signed_wrong_writer_or_file_or_parent_holds(self):
        for changes in (dict(author={"login":"unknown"}),
                        dict(files=[dict(filename="data/other.json",sha=BLOB)]),
                        dict(parents=[{"sha":BASE},{"sha":"f"*40}])):
            with self.subTest(changes=changes):
                v=history();v[WRITE].update(changes)
                with self.assertRaisesRegex(ValueError,"EFFECT_UNPROVEN"):
                    self.check(v)

    def test_cyclic_or_excess_history_fails_closed(self):
        v=history();v[HEAD]["parents"]=[{"sha":HEAD}]
        with self.assertRaisesRegex(ValueError,"HISTORY_UNPROVEN"):
            self.check(v)

if __name__=="__main__":unittest.main()
