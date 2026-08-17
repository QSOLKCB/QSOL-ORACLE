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


if __name__ == "__main__":
    unittest.main()
