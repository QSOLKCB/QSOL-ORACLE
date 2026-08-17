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


class OracleTests(unittest.TestCase):
    def test_repository_validates(self):
        report = oracle.validate_repository(ROOT)
        self.assertEqual(report["status"], "valid")
        self.assertEqual(report["ledger_model"], "single-writer-append-only")
        self.assertGreaterEqual(report["events"], 2)

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


if __name__ == "__main__":
    unittest.main()
