import copy, importlib.util, json, unittest
from pathlib import Path
import sys
ROOT=Path(__file__).resolve().parents[1]
TOOLS=ROOT/"tools"
if str(TOOLS) not in sys.path: sys.path.insert(0,str(TOOLS))
SPEC=importlib.util.spec_from_file_location("membrane", ROOT/"tools"/"nexus_membrane.py")
membrane=importlib.util.module_from_spec(SPEC); SPEC.loader.exec_module(membrane)
from nexus_membrane_common import build_envelope, validate_envelope, MembraneError
from nexus_query import build_query, execute
from nexus_view import build_view
from oracle_ledger import load_ledger, sha256_value

class NexusTransportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls): cls.events=load_ledger(ROOT/"ledger"/"events.jsonl")
    def test_contract_validates(self):
        c=json.loads((ROOT/"contracts"/"nexus-membrane.json").read_text()); membrane.validate_contract(c); self.assertEqual(c["protocol"],"QSOL-ORACLE-NEXUS/1")
    def test_query_deterministic_read_only(self):
        q=build_query(request_id="q1", subject="QSOLKCB/QSOL-CONTEXT"); before=copy.deepcopy(self.events)
        self.assertEqual(execute(self.events,q),execute(self.events,q)); self.assertEqual(self.events,before); self.assertEqual(execute(self.events,q)["payload"]["state"],"known")
    def test_query_no_match_unknown(self): self.assertEqual(execute(self.events,build_query(request_id="q2",subject="none"))["payload"]["state"],"unknown")
    def test_stenographer_view_external_not_native(self):
        v=build_view(self.events[0],request_id="v1")["payload"]; self.assertFalse(v["nexus_stenographer"]["native_record"]); self.assertFalse(v["nexus_stenographer"]["append_to_native_stenographer_ledger"]); self.assertNotIn("record_ref",v)
    def test_hidden_reasoning_rejected(self):
        with self.assertRaisesRegex(MembraneError,"hidden chain-of-thought"): build_envelope(direction="nexus-to-oracle",kind="visible_claim_audit",request_id="bad",payload={"chain_of_thought":"private"})
    def test_vote_authority_escalation_rejected(self):
        e=build_query(request_id="vote",subject="x"); e["council_vote_authority"]=True; base=copy.deepcopy(e); base.pop("envelope_sha256"); e["envelope_sha256"]=sha256_value(base)
        with self.assertRaisesRegex(MembraneError,"council_vote_authority"): validate_envelope(e)
    def test_worldstore_authority_escalation_rejected(self):
        e=build_query(request_id="world",subject="x"); e["worldstore_mutation_authorized"]=True; base=copy.deepcopy(e); base.pop("envelope_sha256"); e["envelope_sha256"]=sha256_value(base)
        with self.assertRaisesRegex(MembraneError,"worldstore_mutation_authorized"): validate_envelope(e)
if __name__=="__main__": unittest.main()
