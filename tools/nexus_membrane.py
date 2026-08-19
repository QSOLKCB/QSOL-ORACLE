#!/usr/bin/env python3
"""CLI and contract validator for QSOL-ORACLE↔NEXUS Phase 3."""
from __future__ import annotations
import argparse, json, sys
from pathlib import Path
TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))
from nexus_membrane_common import MembraneError, TRANSPORT_PROTOCOL
from nexus_query import build_query, execute
from nexus_view import build_view
from nexus_audit import build_request, audit
from oracle_ledger import load_ledger

ROOT = Path(__file__).resolve().parents[1]
LEDGER = ROOT / "ledger" / "events.jsonl"
CONTRACT = ROOT / "contracts" / "nexus-membrane.json"
def validate_contract(contract: dict) -> None:
    if not isinstance(contract, dict) or contract.get("protocol") != TRANSPORT_PROTOCOL: raise MembraneError("NEXUS membrane contract protocol mismatch")
    if contract.get("oracle_role") != "WITNESSES" or contract.get("nexus_role") != "REASONS": raise MembraneError("NEXUS membrane role split invalid")
    expected = {"oracle_council_seat": False, "oracle_vote_authority": False, "oracle_worldstore_mutation_authority": False, "oracle_governance_authority": False, "oracle_output_mutation_authority": False}
    if contract.get("authority_firewall") != expected: raise MembraneError("NEXUS membrane authority firewall invalid")
    cot = contract.get("hidden_chain_of_thought", {})
    if any(cot.get(k) is not False for k in ("accepted", "requested", "persisted", "reconstructed")): raise MembraneError("NEXUS membrane hidden-reasoning boundary invalid")
    steno = contract.get("stenographer_bridge", {})
    if steno.get("native_record_scope") != "ai_actions_only" or steno.get("append_oracle_views_to_native_ledger") is not False: raise MembraneError("NEXUS Stenographer bridge invalid")
    if contract.get("operations") != ["evidence.query", "event.view", "visible_claim.audit"]: raise MembraneError("NEXUS membrane operations invalid")


def _print(value): print(json.dumps(value, indent=2, sort_keys=True)); return 0

def main() -> int:
    p=argparse.ArgumentParser(); sub=p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("validate")
    q=sub.add_parser("query"); q.add_argument("--request-id", required=True); q.add_argument("--subject"); q.add_argument("--event-hash"); q.add_argument("--event-type"); q.add_argument("--provenance-kind"); q.add_argument("--evidence-state"); q.add_argument("--limit", type=int, default=100)
    v=sub.add_parser("view"); v.add_argument("--request-id", required=True); v.add_argument("--event-hash", required=True)
    a=sub.add_parser("audit"); a.add_argument("--request-id", required=True); a.add_argument("--input", required=True)
    args=p.parse_args(); events=load_ledger(LEDGER)
    if args.cmd=="validate":
        contract=json.loads(CONTRACT.read_text()); validate_contract(contract)
        return _print({"status":"valid","protocol":TRANSPORT_PROTOCOL,"operations":contract["operations"],"authority":"evidence-only"})
    if args.cmd=="query": return _print(execute(events, build_query(request_id=args.request_id, subject=args.subject, event_hash=args.event_hash, event_type=args.event_type, provenance_kind=args.provenance_kind, evidence_state=args.evidence_state, limit=args.limit)))
    if args.cmd=="view":
        event=next((e for e in events if e.get("event_hash")==args.event_hash), None)
        if event is None: raise MembraneError("event not found")
        return _print(build_view(event, request_id=args.request_id))
    source=json.loads(Path(args.input).read_text())
    return _print(audit(events, build_request(request_id=args.request_id, response_id=source["response_id"], claims=source["visible_claims"])))

if __name__ == "__main__": raise SystemExit(main())
