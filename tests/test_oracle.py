import copy
import importlib.util
import json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("qsol_oracle", ROOT / "tools" / "oracle.py")
oracle = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(oracle)
collectors = oracle.collectors


class OracleTests(unittest.TestCase):
    def test_repository_validates(self):
        report = oracle.validate_repository(ROOT)
        self.assertEqual(report["status"], "valid")
        self.assertEqual(report["ledger_model"], "single-writer-append-only")
        self.assertGreaterEqual(report["events"], 2)
        self.assertEqual(report["collector_count"], 9)

    def test_timelock_is_locked_before_deadline(self):
        contract = oracle.load_json(ROOT / "contracts" / "qsol-context-2056.json")
        at = datetime.fromisoformat("2026-08-18T06:18:00+09:30")
        self.assertEqual(oracle.timelock_state(contract, at), "locked")

    def test_timelock_is_eligible_at_deadline(self):
        contract = oracle.load_json(ROOT / "contracts" / "qsol-context-2056.json")
        at = datetime.fromisoformat("2056-08-18T00:00:00+09:30")
        self.assertEqual(oracle.timelock_state(contract, at), "eligible")

    def test_unknown_is_actionable_but_not_evidence(self):
        result = oracle.unknown_response(
            ["current primary source"],
            ["author institutional repository", "latest replication"],
        )
        self.assertEqual(result["state"], "unknown")
        self.assertFalse(result["search_suggestions_are_evidence"])
        self.assertEqual(len(result["suggested_searches"]), 2)

    def test_ledger_tampering_is_detected(self):
        events = oracle.load_ledger(ROOT / "ledger" / "events.jsonl")
        tampered = copy.deepcopy(events)
        tampered[0]["note"] = "This definitely proves everything, probably."
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "events.jsonl"
            with path.open("w", encoding="utf-8") as handle:
                for event in tampered:
                    handle.write(json.dumps(event, sort_keys=True, separators=(",", ":")) + "\n")
            with self.assertRaises(ValueError):
                oracle.validate_ledger(path)

    def test_contract_digest_is_witnessed(self):
        contract = oracle.load_json(ROOT / "contracts" / "qsol-context-2056.json")
        digest = oracle.sha256_value(contract)
        events = oracle.load_ledger(ROOT / "ledger" / "events.jsonl")
        event = next(e for e in events if e["event_id"] == "timelock.qsol-context.2056")
        self.assertEqual(event["evidence"]["payload_sha256"], digest)
        self.assertEqual(event["provenance_kind"], "primary_observation")

    def test_manifest_rejects_duplicate_files(self):
        manifest = oracle.load_json(ROOT / "manifest.json")
        manifest["files"] = manifest["files"] + [manifest["files"][0]]
        with self.assertRaisesRegex(ValueError, "duplicates"):
            oracle.validate_manifest(manifest, ROOT)

    def test_manifest_declared_paths_must_be_listed(self):
        manifest = oracle.load_json(ROOT / "manifest.json")
        manifest["files"].remove(manifest["entrypoint"])
        with self.assertRaisesRegex(ValueError, "entrypoint"):
            oracle.validate_manifest(manifest, ROOT)

    def test_event_hash_is_independent_of_mapping_order(self):
        left = {"b": 2, "a": 1, "event_hash": "ignored"}
        right = {"a": 1, "event_hash": "also ignored", "b": 2}
        self.assertEqual(oracle.event_hash(left), oracle.event_hash(right))

    def _relation_event(self, kind: str):
        events = oracle.load_ledger(ROOT / "ledger" / "events.jsonl")
        target = events[-1]["event_hash"]
        event_type = "evidence.correction" if kind == "correction" else "evidence.supersession"
        event = {
            "protocol": "QSOL-ORACLE/1",
            "sequence": len(events),
            "event_id": f"test.{kind}",
            "event_type": event_type,
            "subject": "test",
            "observed_at": "2026-08-18T06:30:00+09:30",
            "source": {"kind": "maintainer_directive", "locator": "test://relation"},
            "provenance_kind": kind,
            "derived_from": [target],
            "target_event_hash": target,
            "evidence": {"state": "observed", "payload_sha256": None},
            "authority": "observation-only",
            "previous_hash": target,
            "note": f"Explicit {kind} relation preserving prior history.",
        }
        event["event_hash"] = oracle.event_hash(event)
        return events, event

    def test_explicit_correction_event_validates(self):
        events, event = self._relation_event("correction")
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "events.jsonl"
            with path.open("w", encoding="utf-8") as handle:
                for item in [*events, event]:
                    handle.write(json.dumps(item, sort_keys=True, separators=(",", ":")) + "\n")
            self.assertEqual(oracle.validate_ledger(path)[-1]["event_type"], "evidence.correction")

    def test_explicit_supersession_event_validates(self):
        events, event = self._relation_event("supersession")
        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "events.jsonl"
            with path.open("w", encoding="utf-8") as handle:
                for item in [*events, event]:
                    handle.write(json.dumps(item, sort_keys=True, separators=(",", ":")) + "\n")
            self.assertEqual(oracle.validate_ledger(path)[-1]["event_type"], "evidence.supersession")

    def test_correction_requires_explicit_target(self):
        _, event = self._relation_event("correction")
        event.pop("target_event_hash")
        event["event_hash"] = oracle.event_hash(event)
        with self.assertRaisesRegex(ValueError, "target_event_hash"):
            oracle.validate_event_shape(event, event["sequence"])

    def test_derived_statement_requires_prior_event_reference(self):
        events = oracle.load_ledger(ROOT / "ledger" / "events.jsonl")
        derived = {
            "protocol": "QSOL-ORACLE/1",
            "sequence": len(events),
            "event_id": "test.derived",
            "event_type": "test.derived",
            "subject": "test",
            "observed_at": "2026-08-18T06:30:00+09:30",
            "source": {"kind": "nexus_output", "locator": "test://nexus"},
            "provenance_kind": "derived_statement",
            "derived_from": [events[-1]["event_hash"]],
            "evidence": {"state": "observed", "payload_sha256": None},
            "authority": "observation-only",
            "previous_hash": events[-1]["event_hash"],
            "note": "Derived statement explicitly anchored to an earlier witnessed event.",
        }
        derived["event_hash"] = oracle.event_hash(derived)

        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "events.jsonl"
            with path.open("w", encoding="utf-8") as handle:
                for event in [*events, derived]:
                    handle.write(json.dumps(event, sort_keys=True, separators=(",", ":")) + "\n")
            validated = oracle.validate_ledger(path)
            self.assertEqual(validated[-1]["provenance_kind"], "derived_statement")

    def test_derived_statement_rejects_unseen_reference(self):
        events = oracle.load_ledger(ROOT / "ledger" / "events.jsonl")
        derived = {
            "protocol": "QSOL-ORACLE/1",
            "sequence": len(events),
            "event_id": "test.bad-derived",
            "event_type": "test.derived",
            "subject": "test",
            "observed_at": "2026-08-18T06:30:00+09:30",
            "source": {"kind": "nexus_output", "locator": "test://nexus"},
            "provenance_kind": "derived_statement",
            "derived_from": ["0" * 64],
            "evidence": {"state": "observed", "payload_sha256": None},
            "authority": "observation-only",
            "previous_hash": events[-1]["event_hash"],
            "note": "This should fail because the provenance reference is not in prior history.",
        }
        derived["event_hash"] = oracle.event_hash(derived)

        with tempfile.TemporaryDirectory() as temp_dir:
            path = Path(temp_dir) / "events.jsonl"
            with path.open("w", encoding="utf-8") as handle:
                for event in [*events, derived]:
                    handle.write(json.dumps(event, sort_keys=True, separators=(",", ":")) + "\n")
            with self.assertRaisesRegex(ValueError, "earlier canonical events"):
                oracle.validate_ledger(path)

    def test_detached_signature_binds_bytes_without_claiming_truth(self):
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
        oracle.validate_detached_signature_envelope(envelope, object_bytes)
        self.assertFalse(envelope["truth_claim"])
        self.assertEqual(envelope["authority"], "authentication-evidence-only")
        with self.assertRaisesRegex(ValueError, "object digest"):
            oracle.validate_detached_signature_envelope(envelope, b"tampered")

    def test_ledger_checkpoint_is_deterministic(self):
        left = oracle.build_ledger_checkpoint(ROOT / "ledger" / "events.jsonl")
        right = oracle.build_ledger_checkpoint(ROOT / "ledger" / "events.jsonl")
        self.assertEqual(left, right)
        self.assertFalse(left["truth_claim"])
        oracle.validate_ledger_checkpoint(left, ROOT / "ledger" / "events.jsonl")

    def test_release_fingerprint_is_deterministic(self):
        manifest = oracle.load_json(ROOT / "manifest.json")
        left = oracle.build_release_fingerprint(ROOT, manifest)
        right = oracle.build_release_fingerprint(ROOT, manifest)
        self.assertEqual(left, right)
        self.assertFalse(left["truth_claim"])
        oracle.validate_release_fingerprint(left, ROOT, manifest)

    def test_freshness_stale_does_not_mean_false(self):
        result = collectors.freshness_state(
            "2026-08-01T00:00:00Z",
            "2026-08-19T00:00:00Z",
            86400,
        )
        self.assertEqual(result["state"], "stale")
        self.assertFalse(result["stale_means_false"])
        self.assertFalse(result["fresh_means_true"])

    def test_freshness_undated_is_explicit(self):
        result = collectors.freshness_state(None, "2026-08-19T00:00:00Z", 86400)
        self.assertEqual(result["state"], "undated")
        self.assertIsNone(result["age_seconds"])

    def test_all_offline_collector_fixtures_are_deterministic(self):
        fixture = json.loads((ROOT / "fixtures" / "collectors.json").read_text(encoding="utf-8"))
        case_ids = [case["id"] for case in fixture["cases"]]
        self.assertEqual(set(case_ids), collectors.COLLECTOR_KINDS)
        for case_id in case_ids:
            with self.subTest(case=case_id):
                _, left = collectors.load_fixture_case(ROOT / "fixtures" / "collectors.json", case_id)
                _, right = collectors.load_fixture_case(ROOT / "fixtures" / "collectors.json", case_id)
                self.assertEqual(left, right)
                collectors.validate_receipt(left)
                self.assertEqual(left["authority"], "observation-only")
                self.assertFalse(left["truth_claim"])

    def test_github_actions_receipt_is_workflow_report_not_truth(self):
        _, receipt = collectors.load_fixture_case(ROOT / "fixtures" / "collectors.json", "github.actions")
        self.assertEqual(receipt["observation"]["conclusion"], "success")
        self.assertEqual(
            receipt["observation"]["validation_receipt_semantics"],
            "workflow-reported-result-only",
        )
        self.assertFalse(receipt["truth_claim"])

    def test_qsol_substrate_preserves_parent_authority_boundary(self):
        _, receipt = collectors.load_fixture_case(ROOT / "fixtures" / "collectors.json", "qsol.substrate")
        self.assertEqual(receipt["observation"]["scope"], "canonical_public_payload")
        self.assertIn("not-oracle-semantic-authority", receipt["observation"]["authority_semantics"])

    def test_qsol_ark_collects_recovery_capability_without_inheriting_authority(self):
        _, receipt = collectors.load_fixture_case(ROOT / "fixtures" / "collectors.json", "qsol.ark")
        self.assertEqual(receipt["observation"]["implemented_recovery_tiers"], ["T0", "T1", "T2", "T3", "T4"])
        self.assertEqual(receipt["observation"]["recovery_stage_count"], 8)
        self.assertIn("not-oracle-recovery-authority", receipt["observation"]["authority_semantics"])

    def test_qsol_int_exposes_untested_drift(self):
        _, receipt = collectors.load_fixture_case(ROOT / "fixtures" / "collectors.json", "qsol.int")
        self.assertEqual(receipt["observation"]["compatibility"], "compatible")
        self.assertEqual(receipt["observation"]["drift_state"], "untested")
        self.assertIn("not-oracle-composition-authority", receipt["observation"]["authority_semantics"])

    def test_live_url_builders_are_deterministic(self):
        self.assertEqual(
            collectors.github_url("github.repository", "QSOLKCB/QSOL-ORACLE"),
            "https://api.github.com/repos/QSOLKCB/QSOL-ORACLE",
        )
        self.assertEqual(
            collectors.github_url("github.tag", "QSOLKCB/QSOL-ORACLE", "v1.0.0"),
            "https://api.github.com/repos/QSOLKCB/QSOL-ORACLE/git/ref/tags/v1.0.0",
        )
        self.assertEqual(
            collectors.zenodo_url("21935097"),
            "https://zenodo.org/api/records/21935097",
        )


if __name__ == "__main__":
    unittest.main()
