"""Test Pages receipt inventory against exact Git-source vocabulary bytes."""
import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from pages_publication_receipt import FILES, RECEIPT, build, verify

WORD = "data/vocab/2026-11-23.json"
LATEST = "data/vocab/latest.json"


def git_blob(raw):
    return hashlib.sha1(b"blob " + str(len(raw)).encode() + b"\0" + raw).hexdigest()


class VocabularyReceiptTests(unittest.TestCase):
    def setUp(self):
        self.root = Path(self.enterContext(TemporaryDirectory()))
        for name in FILES:
            target = self.root / name
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(name)
        (self.root / WORD).parent.mkdir()
        self.sample = self.put(WORD, "2026-11-23")
        (self.root / LATEST).write_bytes(self.sample)
        self.inventory = {path: git_blob(self.sample) for path in (WORD, LATEST)}

    def put(self, path, date):
        value = json.dumps({"date": date, "words": [{"reading": "ためし"}]}).encode()
        (self.root / path).write_bytes(value)
        return value

    def make(self, inventory=None):
        return build(self.root, commit="a"*40, run_id="311", attempt="1",
                     vocab_inventory=self.inventory if inventory is None else inventory)

    def test_full_artifact_binds_required_dated_and_latest_paths(self):
        receipt = self.make()
        self.assertEqual(receipt["schema"], "PUBLICATION_BUILD_RECEIPT_V2")
        self.assertEqual(set(receipt["files"])-set(FILES), {WORD,LATEST})
        (self.root / RECEIPT).write_text(json.dumps(receipt))
        verify(lambda path: (self.root / path).read_bytes(), receipt)

    def test_missing_or_modified_built_path_blocks_build(self):
        (self.root / WORD).unlink()
        with self.assertRaisesRegex(ValueError, "absent"):
            self.make()
        self.put(WORD, "2026-11-24")
        with self.assertRaisesRegex(ValueError, "differs"):
            self.make()

    def test_wrong_date_and_wrong_latest_block_even_if_git_hashes_match(self):
        swapped = self.put(WORD, "2026-11-24")
        with self.assertRaisesRegex(ValueError, "date does not match"):
            self.make(dict(self.inventory, **{WORD: git_blob(swapped)}))
        (self.root / WORD).write_bytes(self.sample)
        alternate = self.put(LATEST, "2026-11-22")
        with self.assertRaisesRegex(ValueError, "latest does not match"):
            self.make(dict(self.inventory, **{LATEST: git_blob(alternate)}))

    def test_public_missing_and_changed_path_are_detected_after_build(self):
        receipt = self.make()
        (self.root / RECEIPT).write_text(json.dumps(receipt))
        (self.root / WORD).unlink()
        with self.assertRaises(FileNotFoundError):
            verify(lambda path: (self.root / path).read_bytes(), receipt)
        self.put(WORD, "2026-11-24")
        with self.assertRaisesRegex(ValueError, "public Pages content hash mismatch: .*11-23"):
            verify(lambda path: (self.root / path).read_bytes(), receipt)

    def test_v1_is_still_accepted_for_its_existing_scope(self):
        receipt = build(self.root, commit="a"*40, run_id="311", attempt="1")
        (self.root / RECEIPT).write_text(json.dumps(receipt))
        verify(lambda path: (self.root / path).read_bytes(), receipt)
        self.assertEqual(receipt["schema"], "PUBLICATION_BUILD_RECEIPT_V1")


if __name__ == "__main__":
    unittest.main()
