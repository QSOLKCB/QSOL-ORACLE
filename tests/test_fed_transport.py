import copy
import io
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import fed_transport
from oracle_ledger import validate_ledger


class FedTransportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.events = validate_ledger(ROOT / "ledger" / "events.jsonl")

    def request(self, **overrides):
        value = {
            "protocol": fed_transport.PROTOCOL,
            "kind": fed_transport.REQUEST_KIND,
            "request_id": "test-request",
            "query": {
                "event_hash": "80468db2bf709982ce4eead9de02ba088306fd365dc999f860139e51987ed8ad",
                "limit": 256,
            },
            "research": None,
            "synthetic_input": False,
            "evidence_promotion_requested": False,
            "authority_requested": False,
            "remote_execution_requested": False,
        }
        value.update(overrides)
        return value

    def missing_requirement(self, **overrides):
        value = {
            "id": "primary",
            "kind": "primary_source",
            "satisfied": False,
            "detail": "No primary record has been observed.",
        }
        value.update(overrides)
        return value

    def test_contract_validates_and_pins_fed_consumer(self):
        contract = fed_transport.validate_contract()
        self.assertEqual(contract["consumer_pin"]["commit"], fed_transport.PINNED_FED_COMMIT)
        self.assertFalse(contract["transport"]["network_required"])
        self.assertTrue(contract["transport"]["canonical_input_required"])
        self.assertTrue(contract["transport"]["deterministic_output"])
        self.assertEqual(
            contract["transport"]["response_budget_policy"],
            "truncate-discovery-searches-before-response-limit",
        )
        self.assertTrue(all(value is False for value in contract["authority_firewall"].values()))

    def test_contract_validation_rejects_any_transport_semantic_drift(self):
        original = fed_transport.CONTRACT
        contract = json.loads(original.read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "contract.json"
            for field in ("canonical_input_required", "deterministic_output"):
                drifted = copy.deepcopy(contract)
                drifted["transport"][field] = False
                path.write_text(json.dumps(drifted), encoding="utf-8")
                fed_transport.CONTRACT = path
                with self.subTest(field=field):
                    with self.assertRaisesRegex(fed_transport.TransportError, "profile_drift"):
                        fed_transport.validate_contract()
        fed_transport.CONTRACT = original

    def test_known_export_is_deterministic_non_authoritative_and_read_only(self):
        before = copy.deepcopy(self.events)
        request = self.request()
        one = fed_transport.export_observation(self.events, request)
        two = fed_transport.export_observation(self.events, request)
        self.assertEqual(one, two)
        self.assertEqual(self.events, before)
        self.assertEqual(one["observation"]["state"], "known")
        self.assertEqual(
            one["observation"]["evidence_refs"],
            [{
                "reference": "oracle-event:80468db2bf709982ce4eead9de02ba088306fd365dc999f860139e51987ed8ad",
                "is_evidence": True,
            }],
        )
        self.assertFalse(one["observation"]["truth_claim"])
        self.assertFalse(one["observation"]["evidence_promotion"])
        self.assertEqual(one["observation"]["authority_effect"], "none")
        self.assertFalse(one["ledger_mutated"])
        self.assertEqual(one["transport_authority"], "none")
        fed_transport.validate_response(one, self.events)

    def test_unknown_research_generates_discovery_only_non_evidence(self):
        request = self.request(
            query={"subject": "subject-that-does-not-exist", "limit": 256},
            research={
                "subject": "missing subject",
                "question": "What is the primary record?",
                "requirements": [self.missing_requirement()],
            },
        )
        response = fed_transport.export_observation(self.events, request)
        observation = response["observation"]
        self.assertEqual(observation["state"], "unknown")
        self.assertEqual(observation["evidence_refs"], [])
        self.assertTrue(observation["suggested_searches"])
        self.assertTrue(all(
            item["purpose"] == "discovery-only"
            and item["is_evidence"] is False
            and item["admissible_as_evidence_without_observation"] is False
            for item in observation["suggested_searches"]
        ))

    def test_declared_missing_evidence_overrides_a_matching_event(self):
        request = self.request(
            research={
                "subject": "QSOLKCB/QSOL-CONTEXT",
                "question": "Do we have every required primary source?",
                "requirements": [self.missing_requirement()],
            }
        )
        response = fed_transport.export_observation(self.events, request)
        self.assertEqual(response["observation"]["state"], "unknown")
        self.assertEqual(len(response["observation"]["evidence_refs"]), 1)
        self.assertTrue(response["observation"]["suggested_searches"])

    def test_research_requirement_schema_is_enforced_exactly(self):
        extra = self.missing_requirement(governance_authority=True)
        request = self.request(
            query={"subject": "missing", "limit": 256},
            research={"subject": "x", "question": "y", "requirements": [extra]},
        )
        with self.assertRaisesRegex(fed_transport.TransportError, "requirement_fields"):
            fed_transport.export_observation(self.events, request)

        oversized = self.missing_requirement(id="x" * 257)
        request["research"]["requirements"] = [oversized]
        with self.assertRaisesRegex(fed_transport.TransportError, "requirement_id"):
            fed_transport.export_observation(self.events, request)

    def test_large_unknown_search_set_is_trimmed_to_response_budget(self):
        requirements = [
            {
                "id": f"r{i}",
                "kind": "primary_source",
                "satisfied": False,
                "detail": "missing",
            }
            for i in range(64)
        ]
        request = self.request(
            query={"subject": "not-present", "limit": 256},
            research={
                "subject": "s" * 4096,
                "question": "q",
                "requirements": requirements,
            },
        )
        response = fed_transport.export_observation(self.events, request)
        rendered = fed_transport.canonical_bytes(response)
        self.assertLessEqual(len(rendered), fed_transport.MAX_LINE_BYTES)
        self.assertLess(len(response["observation"]["suggested_searches"]), 64)

    def test_authority_synthetic_promotion_and_execution_requests_fail_closed(self):
        for field in (
            "synthetic_input",
            "evidence_promotion_requested",
            "authority_requested",
            "remote_execution_requested",
        ):
            request = self.request()
            request[field] = True
            with self.subTest(field=field):
                with self.assertRaises(fed_transport.TransportError):
                    fed_transport.export_observation(self.events, request)

    def test_hidden_reasoning_fields_fail_closed(self):
        request = self.request(research={
            "subject": "x",
            "question": "y",
            "requirements": [{
                "id": "r",
                "kind": "scope",
                "satisfied": False,
                "detail": "missing",
                "chain_of_thought": "private",
            }],
        })
        with self.assertRaises((fed_transport.TransportError, ValueError)):
            fed_transport.export_observation(self.events, request)

    def test_conflict_requires_two_conflict_supporting_references(self):
        events = [
            {
                "sequence": 0,
                "event_hash": "1" * 64,
                "subject": "x",
                "event_type": "e",
                "provenance_kind": "primary_observation",
                "evidence": {"state": "conflict"},
            },
            {
                "sequence": 1,
                "event_hash": "2" * 64,
                "subject": "x",
                "event_type": "e",
                "provenance_kind": "primary_observation",
                "evidence": {"state": "conflict"},
            },
        ]
        response = fed_transport.export_observation(
            events, self.request(query={"subject": "x", "limit": 256})
        )
        self.assertEqual(response["observation"]["state"], "conflict")
        self.assertEqual(len(response["observation"]["evidence_refs"]), 2)

        unrelated = copy.deepcopy(events[1])
        unrelated["evidence"]["state"] = "observed"
        with self.assertRaisesRegex(
            fed_transport.TransportError, "conflict_requires_two_conflict_supporting"
        ):
            fed_transport.export_observation(
                [events[0], unrelated],
                self.request(query={"subject": "x", "limit": 256}),
            )

    def test_evidence_references_must_be_canonical_ledger_members(self):
        response = fed_transport.export_observation(self.events, self.request())
        response["observation"]["evidence_refs"][0]["reference"] = "https://example.invalid/evidence"
        payload = dict(response)
        payload.pop("response_sha256")
        response["response_sha256"] = fed_transport._sha256_transport(payload)
        with self.assertRaisesRegex(fed_transport.TransportError, "not_oracle_event"):
            fed_transport.validate_response(response, self.events)

        response = fed_transport.export_observation(self.events, self.request())
        response["observation"]["evidence_refs"][0]["reference"] = "oracle-event:" + "f" * 64
        payload = dict(response)
        payload.pop("response_sha256")
        response["response_sha256"] = fed_transport._sha256_transport(payload)
        with self.assertRaisesRegex(fed_transport.TransportError, "not_in_ledger"):
            fed_transport.validate_response(response, self.events)

    def test_noncanonical_nfc_json_is_rejected(self):
        request = self.request(request_id="e\u0301")
        raw = json.dumps(
            request, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
        self.assertNotEqual(raw, fed_transport.canonical_bytes(request))
        with self.assertRaisesRegex(fed_transport.TransportError, "noncanonical_transport_json"):
            fed_transport.parse_canonical_line(raw)

    def test_nfc_query_matches_decomposed_ledger_field(self):
        events = [{
            "sequence": 0,
            "event_hash": "3" * 64,
            "subject": "e\u0301",
            "event_type": "observed",
            "provenance_kind": "primary_observation",
            "evidence": {"state": "observed"},
        }]
        response = fed_transport.export_observation(
            events, self.request(query={"subject": "é", "limit": 256})
        )
        self.assertEqual(response["observation"]["state"], "known")
        self.assertEqual(response["returned"], 1)

    def test_source_event_digest_does_not_use_transport_string_limits(self):
        events = [{
            "sequence": 0,
            "event_hash": "4" * 64,
            "subject": "x",
            "event_type": "observed",
            "provenance_kind": "primary_observation",
            "evidence": {"state": "observed"},
            "note": "n" * 9000,
        }]
        response = fed_transport.export_observation(
            events, self.request(query={"subject": "x", "limit": 256})
        )
        self.assertEqual(response["observation"]["state"], "known")
        self.assertRegex(response["source_events_sha256"], r"^[0-9a-f]{64}$")

    def test_bounded_jsonl_reader_rejects_oversized_or_unterminated_input(self):
        with self.assertRaisesRegex(fed_transport.TransportError, "too_large"):
            list(fed_transport._bounded_lines(io.BytesIO(b"x" * (fed_transport.MAX_LINE_BYTES + 2))))
        with self.assertRaisesRegex(fed_transport.TransportError, "missing_newline"):
            list(fed_transport._bounded_lines(io.BytesIO(b"{}")))

    def test_request_fixture_is_canonical_and_exportable(self):
        raw = (ROOT / "fixtures" / "fed-known-request.jsonl").read_bytes()
        self.assertTrue(raw.endswith(b"\n"))
        request = fed_transport.parse_canonical_line(raw[:-1])
        response = fed_transport.export_observation(self.events, request)
        self.assertEqual(response["request_id"], "fed-known-fixture")

    def test_response_digest_detects_tampering(self):
        response = fed_transport.export_observation(self.events, self.request())
        response["transport_authority"] = "admin"
        with self.assertRaises(fed_transport.TransportError):
            fed_transport.validate_response(response, self.events)


if __name__ == "__main__":
    unittest.main()
