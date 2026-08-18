import argparse
import copy
import importlib.util
import json
import shutil
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("qsol_oracle_review", ROOT / "tools" / "oracle.py")
oracle = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(oracle)
collectors = oracle.collectors
import oracle_cli


class ReviewHardeningTests(unittest.TestCase):
    def test_receipt_rejects_tampered_observation_with_recomputed_outer_digest(self):
        _, receipt = collectors.load_fixture_case(
            ROOT / "fixtures" / "collectors.json", "github.repository"
        )
        tampered = copy.deepcopy(receipt)
        tampered["observation"]["default_branch"] = "tampered"
        payload = dict(tampered)
        payload.pop("receipt_sha256", None)
        tampered["receipt_sha256"] = collectors.sha256_value(payload)

        with self.assertRaisesRegex(ValueError, "observation SHA-256 mismatch"):
            collectors.validate_receipt(tampered)

    def test_detached_signature_rejects_empty_schema_identity_fields(self):
        object_bytes = b"signed object\n"
        envelope = oracle.detached_signature_envelope(
            object_kind="release-fingerprint",
            object_id="fixture-release",
            object_sha256=oracle.sha256_bytes(object_bytes),
            algorithm="ed25519",
            key_id="did:key:fixture",
            signature_bytes=b"fixture detached signature",
            created_at="2026-08-19T00:00:00Z",
        )
        targets = [
            ("object", "kind"),
            ("object", "id"),
            ("signature", "algorithm"),
            ("signature", "key_id"),
        ]
        for section, field in targets:
            with self.subTest(section=section, field=field):
                invalid = copy.deepcopy(envelope)
                invalid[section][field] = ""
                payload = dict(invalid)
                payload.pop("envelope_sha256", None)
                invalid["envelope_sha256"] = oracle.sha256_value(payload)
                with self.assertRaisesRegex(ValueError, "non-empty"):
                    oracle.validate_detached_signature_envelope(invalid, object_bytes)

    def test_fixture_max_age_override_applies_without_at_override(self):
        args = argparse.Namespace(
            fixture=str(ROOT / "fixtures" / "collectors.json"),
            fixture_case="github.repository",
            kind="github.repository",
            at=None,
            max_age=0,
        )
        receipt = oracle_cli._collect(oracle, args)
        self.assertEqual(receipt["freshness"]["max_age_seconds"], 0)

    def test_fixture_case_must_match_requested_collector(self):
        args = argparse.Namespace(
            fixture=str(ROOT / "fixtures" / "collectors.json"),
            fixture_case="qsol.int",
            kind="github.repository",
            at=None,
            max_age=None,
        )
        with self.assertRaisesRegex(ValueError, "fixture case collector mismatch"):
            oracle_cli._collect(oracle, args)

    def test_repository_requires_collected_is_not_canonical_invariant(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            copied_root = Path(temp_dir) / "repo"
            shutil.copytree(
                ROOT,
                copied_root,
                ignore=shutil.ignore_patterns(".git", "__pycache__", "*.pyc"),
            )
            constitution_path = copied_root / "ai" / "constitution.json"
            constitution = json.loads(constitution_path.read_text(encoding="utf-8"))
            constitution["invariants"].remove("COLLECTED != CANONICAL")
            constitution_path.write_text(
                json.dumps(constitution, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(ValueError, "COLLECTED != CANONICAL"):
                oracle.validate_repository(copied_root)

    def test_manifest_relation_event_mapping_must_match_ledger_validator(self):
        manifest = oracle.load_json(ROOT / "manifest.json")
        manifest["relation_event_types"] = {
            "correction": "evidence.supersession",
            "supersession": "evidence.correction",
        }
        with self.assertRaisesRegex(ValueError, "relation_event_types"):
            oracle.validate_manifest(manifest, ROOT)


if __name__ == "__main__":
    unittest.main()
