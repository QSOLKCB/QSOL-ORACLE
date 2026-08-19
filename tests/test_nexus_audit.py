import copy, unittest
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
TOOLS=ROOT/"tools"
if str(TOOLS) not in sys.path: sys.path.insert(0,str(TOOLS))
from oracle_ledger import load_ledger, sha256_value
from nexus_audit import build_request, audit, validate_receipt
from nexus_membrane_common import MembraneError
ROOT=Path(__file__).resolve().parents[1]

class NexusAuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.events=load_ledger(ROOT/"ledger"/"events.jsonl")
    def test_primary_observation_support(self):
        target=self.events[1]["event_hash"]; r=build_request(request_id="a1",response_id="r1",claims=[{"claim_id":"c1","text":"Directive observed.","presentation":"fact","evidence_refs":[target]}]); out=audit(self.events,r); validate_receipt(out); self.assertEqual(out["payload"]["status"],"supported"); self.assertFalse(out["payload"]["nexus_output_blocked"])
    def test_missing_citation_attention_not_block(self):
        r=build_request(request_id="a2",response_id="r2",claims=[{"claim_id":"c2","text":"Missing citation.","presentation":"fact","evidence_refs":["0"*64]}]); out=audit(self.events,r); self.assertIn("citation_support",out["payload"]["findings"]); self.assertFalse(out["payload"]["nexus_output_blocked"])
    def test_inference_presented_as_fact(self):
        d=copy.deepcopy(self.events[-1]); d["event_hash"]="1"*64; d["provenance_kind"]="derived_statement"; r=build_request(request_id="a3",response_id="r3",claims=[{"claim_id":"c3","text":"Derived as fact.","presentation":"fact","evidence_refs":[d["event_hash"]]}]); self.assertIn("inference_presented_as_fact",audit([*self.events,d],r)["payload"]["findings"])
    def test_conflict_unknown_suppression(self):
        c=copy.deepcopy(self.events[-1]); c["event_hash"]="3"*64; c["evidence"]={"state":"conflict","payload_sha256":"4"*64}; u=copy.deepcopy(self.events[-1]); u["event_hash"]="5"*64; u["evidence"]={"state":"unknown","payload_sha256":None}; r=build_request(request_id="a4",response_id="r4",claims=[{"claim_id":"c4","text":"Conflict hidden.","presentation":"fact","evidence_refs":[c["event_hash"]]},{"claim_id":"c5","text":"Unknown hidden.","presentation":"fact","evidence_refs":[u["event_hash"]]}]); f=audit([*self.events,c,u],r)["payload"]["findings"]; self.assertIn("conflict_suppressed",f); self.assertIn("unknown_suppressed",f)
    def test_receipt_cannot_gain_output_control(self):
        r=build_request(request_id="a5",response_id="r5",claims=[{"claim_id":"c6","text":"Unknown.","presentation":"unknown","evidence_refs":[]}]); out=audit(self.events,r); out["payload"]["nexus_output_blocked"]=True; base=copy.deepcopy(out["payload"]); base.pop("audit_sha256"); out["payload"]["audit_sha256"]=sha256_value(base); env=copy.deepcopy(out); env.pop("envelope_sha256"); out["envelope_sha256"]=sha256_value(env)
        with self.assertRaisesRegex(MembraneError,"must not gain control"): validate_receipt(out)
if __name__=="__main__": unittest.main()
