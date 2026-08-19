import copy
import importlib.util
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

SPEC = importlib.util.spec_from_file_location("membrane", ROOT / "tools" / "nexus_membrane.py")
membrane = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(membrane)

from nexus_membrane_common import MembraneError, build_envelope, validate_envelope
from nexus_query import build_query, execute
from nexus_view import build_view
from oracle_ledger import sha256_value, validate_ledger


class NexusTransportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.events = validate_ledger(ROOT / "ledger" / "events.jsonl")

    def test_contract_validates(self):
        contract = json.loads((ROOT / "contracts" / "nexus-membrane.json").read_text())
        membrane.validate_contract(contract)
        self.assertEqual(contract["protocol"], "QSOL-ORACLE-NEXUS/1")

    def test_contract_rejects_safety_boundary_drift_and_extra_fields(self):
        contract=json.loads((ROOT/"contracts"/"nexus-membrane.json").read_text()); contract["query_semantics"]["semantic_truth_from_match"]=True
        with self.assertRaisesRegex(MembraneError,"query semantics"): membrane.validate_contract(contract)
        contract=json.loads((ROOT/"contracts"/"nexus-membrane.json").read_text()); contract["claim_audit"]["blocks_nexus_output"]=True
        with self.assertRaisesRegex(MembraneError,"claim-audit"): membrane.validate_contract(contract)
        contract=json.loads((ROOT/"contracts"/"nexus-membrane.json").read_text()); contract["authority_firewall"]["surprise_authority"]=False
        with self.assertRaisesRegex(MembraneError,"authority firewall"): membrane.validate_contract(contract)

    def test_cli_loader_rejects_invalid_canonical_ledger(self):
        with tempfile.TemporaryDirectory() as temp:
            path=Path(temp)/"events.jsonl"; broken=copy.deepcopy(self.events); broken[-1]["previous_hash"]="0"*64
            path.write_text("\n".join(json.dumps(item) for item in broken)+"\n")
            with self.assertRaisesRegex(MembraneError,"ledger failed validation"): membrane.load_validated_events(path)

    def test_query_deterministic_read_only(self):
        query=build_query(request_id="q1",subject="QSOLKCB/QSOL-CONTEXT"); before=copy.deepcopy(self.events)
        self.assertEqual(execute(self.events,query),execute(self.events,query)); self.assertEqual(self.events,before); self.assertEqual(execute(self.events,query)["payload"]["state"],"known")

    def test_query_no_match_unknown(self):
        self.assertEqual(execute(self.events,build_query(request_id="q2",subject="none"))["payload"]["state"],"unknown")

    def test_stenographer_view_external_not_native(self):
        view=build_view(self.events[0],request_id="v1")["payload"]; self.assertFalse(view["nexus_stenographer"]["native_record"]); self.assertFalse(view["nexus_stenographer"]["append_to_native_stenographer_ledger"]); self.assertNotIn("record_ref",view)

    def test_stenographer_view_preserves_correction_relationship(self):
        target=self.events[-1]["event_hash"]; event=copy.deepcopy(self.events[-1]); event["event_hash"]="6"*64; event["event_type"]="evidence.correction"; event["provenance_kind"]="correction"; event["derived_from"]=[target]; event["target_event_hash"]=target
        view=build_view(event,request_id="v-correction")["payload"]; self.assertEqual(view["derived_from"],[target]); self.assertEqual(view["target_event_hash"],target)

    def test_hidden_reasoning_rejected(self):
        with self.assertRaisesRegex(MembraneError,"hidden chain-of-thought"):
            build_envelope(direction="nexus-to-oracle",kind="visible_claim_audit",request_id="bad",payload={"chain_of_thought":"private"})

    def test_vote_authority_escalation_rejected(self):
        envelope=build_query(request_id="vote",subject="x"); envelope["council_vote_authority"]=True; base=copy.deepcopy(envelope); base.pop("envelope_sha256"); envelope["envelope_sha256"]=sha256_value(base)
        with self.assertRaisesRegex(MembraneError,"council_vote_authority"): validate_envelope(envelope)

    def test_worldstore_authority_escalation_rejected(self):
        envelope=build_query(request_id="world",subject="x"); envelope["worldstore_mutation_authorized"]=True; base=copy.deepcopy(envelope); base.pop("envelope_sha256"); envelope["envelope_sha256"]=sha256_value(base)
        with self.assertRaisesRegex(MembraneError,"worldstore_mutation_authorized"): validate_envelope(envelope)


if __name__ == "__main__": unittest.main()
