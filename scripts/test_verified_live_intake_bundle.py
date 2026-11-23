"""Reproduce the malformed mixed-label/raw-route pattern at the upstream intake."""
from hashlib import sha256
import unittest

from emit_verified_live import emit, emit_bundle
from editorial_stage_authority import verify
from test_editorial_authority_ci import CLOCK, COPY, SOURCES
from today_first_live import canonical, strict_json


def intake(*, meta=None, primary=None, desk="hong-kong"):
    obj = {
        "copy": dict(COPY, **(meta or {})),
        "primaryUrl": primary or SOURCES[0]["url"],
        "verifiedSources": SOURCES,
        "verifiedSourcesSha256": sha256(canonical(SOURCES)).hexdigest(),
        "editorialDesk": desk,
    }
    raw=canonical(obj)
    return raw, sha256(raw).hexdigest()


class IncomingLiveBundle(unittest.TestCase):
    def test_raw_route_and_secondary_label_do_not_override_verified_primary(self):
        args = intake(meta={"sourceName":"mismatched-name", "desk":"world", "deskSlugs":["wrong"],
                             "sources":[{"name":"wrong", "url":SOURCES[0]["url"]}]})
        live,evidence=emit_bundle(*args,now=CLOCK)
        item,=strict_json(live)["items"]
        self.assertEqual(item["desk"],"hong-kong")
        self.assertNotIn("wrong",item["deskSlugs"])
        self.assertEqual(item["sourceName"],SOURCES[0]["name"])
        self.assertEqual(item["publishedAt"],SOURCES[0]["publishedAt"])
        self.assertEqual(strict_json(evidence),[dict(SOURCES[0],articleId=item["id"])])
        self.assertEqual(live,emit(*args,now=CLOCK))

    def test_bad_independent_digest_and_missing_verified_primary_hold(self):
        raw, digest=intake()
        with self.assertRaisesRegex(ValueError,"independently supplied digest"):
            emit_bundle(raw,"0"*64,now=CLOCK)
        with self.assertRaisesRegex(ValueError,"primary source not linked"):
            emit_bundle(*intake(primary="https://example.com/unverified/story"),now=CLOCK)
        with self.assertRaisesRegex(ValueError,"unknown editorial desk"):
            emit_bundle(*intake(desk="wrong"),now=CLOCK)

    def test_binding_stays_unsigned(self):
        draft,evidence=emit_bundle(*intake(),now=CLOCK)
        with self.assertRaisesRegex(ValueError,"invalid EIC/Core packet"):
            verify(draft,evidence,evidence,pins={},parent="a"*40,validator="b"*40,now=CLOCK)


if __name__=="__main__":
    unittest.main()
