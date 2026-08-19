import copy
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from nexus_audit import audit, build_request, build_request_from_source, validate_receipt
from nexus_membrane_common import MembraneError
from oracle_ledger import sha256_value, validate_ledger


class NexusAuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.events = validate_ledger(ROOT / "ledger" / "events.jsonl")

    def test_primary_observation_is_not_arbitrary_claim_support(self):
        target = self.events[1]["event_hash"]
        request = build_request(request_id="a1", response_id="r1", claims=[{"claim_id":"c1","text":"The Moon is made of cheese.","presentation":"fact","evidence_refs":[target]}])
        out = audit(self.events, request)
        validate_receipt(out)
        self.assertEqual(out["payload"]["status"], "attention")
        self.assertIn("claim_exceeds_evidence", out["payload"]["findings"])
        self.assertFalse(out["payload"]["claim_results"][0]["structurally_consistent"])
        self.assertFalse(out["payload"]["nexus_output_blocked"])

    def test_missing_citation_attention_not_block(self):
        request = build_request(request_id="a2", response_id="r2", claims=[{"claim_id":"c2","text":"Missing citation.","presentation":"fact","evidence_refs":["0"*64]}])
        out = audit(self.events, request)
        self.assertIn("citation_support", out["payload"]["findings"])
        self.assertIn("claim_exceeds_evidence", out["payload"]["findings"])
        self.assertFalse(out["payload"]["nexus_output_blocked"])

    def test_inference_presented_as_fact(self):
        derived = copy.deepcopy(self.events[-1]); derived["event_hash"]="1"*64; derived["provenance_kind"]="derived_statement"
        request = build_request(request_id="a3", response_id="r3", claims=[{"claim_id":"c3","text":"Derived as fact.","presentation":"fact","evidence_refs":[derived["event_hash"]]}])
        findings = audit([*self.events, derived], request)["payload"]["findings"]
        self.assertIn("inference_presented_as_fact", findings)
        self.assertIn("claim_exceeds_evidence", findings)

    def test_conflict_unknown_suppression(self):
        conflict=copy.deepcopy(self.events[-1]); conflict["event_hash"]="3"*64; conflict["evidence"]={"state":"conflict","payload_sha256":"4"*64}
        unknown=copy.deepcopy(self.events[-1]); unknown["event_hash"]="5"*64; unknown["evidence"]={"state":"unknown","payload_sha256":None}
        request=build_request(request_id="a4",response_id="r4",claims=[{"claim_id":"c4","text":"Conflict hidden.","presentation":"fact","evidence_refs":[conflict["event_hash"]]},{"claim_id":"c5","text":"Unknown hidden.","presentation":"fact","evidence_refs":[unknown["event_hash"]]}])
        findings=audit([*self.events, conflict, unknown], request)["payload"]["findings"]
        self.assertIn("conflict_suppressed", findings); self.assertIn("unknown_suppressed", findings)

    def test_missing_reference_does_not_hide_valid_conflict_diagnostic(self):
        conflict=copy.deepcopy(self.events[-1]); conflict["event_hash"]="7"*64; conflict["evidence"]={"state":"conflict","payload_sha256":"8"*64}
        request=build_request(request_id="a4b",response_id="r4b",claims=[{"claim_id":"c4b","text":"Conflict hidden with one bad citation.","presentation":"fact","evidence_refs":["0"*64, conflict["event_hash"]]}])
        findings=audit([*self.events, conflict], request)["payload"]["findings"]
        self.assertIn("citation_support", findings); self.assertIn("conflict_suppressed", findings)

    def test_source_hidden_reasoning_is_rejected_before_rebuild(self):
        with self.assertRaisesRegex(MembraneError, "hidden reasoning"):
            build_request_from_source(request_id="hidden", source={"response_id":"r-hidden","visible_claims":[],"hidden_reasoning_provided":True})
        with self.assertRaisesRegex(MembraneError, "hidden chain-of-thought"):
            build_request_from_source(request_id="hidden", source={"response_id":"r-hidden","visible_claims":[],"chain_of_thought":"private"})

    def test_receipt_cannot_gain_output_control(self):
        request=build_request(request_id="a5",response_id="r5",claims=[{"claim_id":"c6","text":"Unknown.","presentation":"unknown","evidence_refs":[]}])
        out=audit(self.events,request); out["payload"]["nexus_output_blocked"]=True
        base=copy.deepcopy(out["payload"]); base.pop("audit_sha256"); out["payload"]["audit_sha256"]=sha256_value(base)
        env=copy.deepcopy(out); env.pop("envelope_sha256"); out["envelope_sha256"]=sha256_value(env)
        with self.assertRaisesRegex(MembraneError,"must not gain control"): validate_receipt(out)

    def test_receipt_requires_complete_consistent_contract(self):
        request=build_request(request_id="a6",response_id="r6",claims=[{"claim_id":"c7","text":"Unknown.","presentation":"unknown","evidence_refs":[]}])
        out=audit(self.events,request); out["payload"].pop("claim_results")
        base=copy.deepcopy(out["payload"]); base.pop("audit_sha256"); out["payload"]["audit_sha256"]=sha256_value(base)
        env=copy.deepcopy(out); env.pop("envelope_sha256"); out["envelope_sha256"]=sha256_value(env)
        with self.assertRaisesRegex(MembraneError,"fields are invalid"): validate_receipt(out)
        out=audit(self.events,request); out["payload"]["status"]="attention"
        base=copy.deepcopy(out["payload"]); base.pop("audit_sha256"); out["payload"]["audit_sha256"]=sha256_value(base)
        env=copy.deepcopy(out); env.pop("envelope_sha256"); out["envelope_sha256"]=sha256_value(env)
        with self.assertRaisesRegex(MembraneError,"status does not match"): validate_receipt(out)


if __name__ == "__main__": unittest.main()
