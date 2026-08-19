#!/usr/bin/env python3
"""CLI and contract validator for QSOL-ORACLE↔NEXUS Phase 3."""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from nexus_audit import audit, build_request_from_source
from nexus_membrane_common import MembraneError, TRANSPORT_PROTOCOL
from nexus_query import build_query, execute
from nexus_view import build_view
from oracle_ledger import validate_ledger

ROOT = Path(__file__).resolve().parents[1]
LEDGER = ROOT / "ledger" / "events.jsonl"
CONTRACT = ROOT / "contracts" / "nexus-membrane.json"
_GIT_SHA1 = re.compile(r"^[0-9a-f]{40}$")

_EXPECTED_DIRECTIONS = {
    "nexus-to-oracle": ["evidence_query", "visible_claim_audit"],
    "oracle-to-nexus": ["evidence_result", "stenographer_event_view", "claim_audit_receipt"],
}
_EXPECTED_FIREWALL = {
    "oracle_council_seat": False,
    "oracle_vote_authority": False,
    "oracle_worldstore_mutation_authority": False,
    "oracle_governance_authority": False,
    "oracle_output_mutation_authority": False,
}
_EXPECTED_HIDDEN_COT = {
    "accepted": False,
    "requested": False,
    "persisted": False,
    "reconstructed": False,
    "audit_scope": "visible-claims-and-explicit-evidence-only",
}
_EXPECTED_STENOGRAPHER = {
    "target": "QSOL-NEXUS Courtroom Stenographer",
    "observed_native_schema": "nexus-stenographer/1",
    "native_record_scope": "ai_actions_only",
    "oracle_view_scope": "external_evidence",
    "append_oracle_views_to_native_ledger": False,
    "presentation_authority": "presentation-only",
    "failure_semantics": "fail-passive-with-visible-completeness-gap",
}
_EXPECTED_QUERY = {
    "matching": "exact-structured-fields-only",
    "mutation": False,
    "semantic_truth_from_match": False,
    "maximum_limit": 1000,
}
_EXPECTED_AUDIT = {
    "input": "visible_claims_plus_explicit_event_hashes",
    "findings": [
        "citation_support",
        "claim_exceeds_evidence",
        "inference_presented_as_fact",
        "conflict_suppressed",
        "unknown_suppressed",
    ],
    "blocks_nexus_output": False,
    "mutates_nexus_output": False,
    "governs_nexus": False,
}
_EXPECTED_SOURCE_KEYS = {
    "repository",
    "commit",
    "path",
    "native_schema",
    "authority",
    "record_scope",
}


def validate_contract(contract: dict) -> None:
    required = {
        "type",
        "protocol",
        "version",
        "relationship",
        "oracle_role",
        "nexus_role",
        "operations",
        "directions",
        "authority_firewall",
        "hidden_chain_of_thought",
        "stenographer_bridge",
        "query_semantics",
        "claim_audit",
        "source_observation",
    }
    if not isinstance(contract, dict) or set(contract) != required:
        raise MembraneError("NEXUS membrane contract fields are invalid")
    if (
        contract["type"] != "qsol-oracle-nexus-membrane"
        or contract["protocol"] != TRANSPORT_PROTOCOL
        or contract["version"] != "1.0.0"
        or contract["relationship"] != "evidentiary-membrane"
    ):
        raise MembraneError("NEXUS membrane contract identity invalid")
    if contract["oracle_role"] != "WITNESSES" or contract["nexus_role"] != "REASONS":
        raise MembraneError("NEXUS membrane role split invalid")
    if contract["operations"] != ["evidence.query", "event.view", "visible_claim.audit"]:
        raise MembraneError("NEXUS membrane operations invalid")
    if contract["directions"] != _EXPECTED_DIRECTIONS:
        raise MembraneError("NEXUS membrane directions invalid")
    if contract["authority_firewall"] != _EXPECTED_FIREWALL:
        raise MembraneError("NEXUS membrane authority firewall invalid")
    if contract["hidden_chain_of_thought"] != _EXPECTED_HIDDEN_COT:
        raise MembraneError("NEXUS membrane hidden-reasoning boundary invalid")
    if contract["stenographer_bridge"] != _EXPECTED_STENOGRAPHER:
        raise MembraneError("NEXUS Stenographer bridge invalid")
    if contract["query_semantics"] != _EXPECTED_QUERY:
        raise MembraneError("NEXUS membrane query semantics invalid")
    if contract["claim_audit"] != _EXPECTED_AUDIT:
        raise MembraneError("NEXUS membrane claim-audit boundary invalid")

    source = contract["source_observation"]
    if not isinstance(source, dict) or set(source) != _EXPECTED_SOURCE_KEYS:
        raise MembraneError("NEXUS source-observation fields invalid")
    if (
        source["repository"] != "QSOLKCB/QSOL-NEXUS"
        or source["path"] != "src/nexus_runtime/stenographer.py"
        or source["native_schema"] != "nexus-stenographer/1"
        or source["authority"] != "zero"
        or source["record_scope"] != "ai_actions_only"
        or not isinstance(source["commit"], str)
        or _GIT_SHA1.fullmatch(source["commit"]) is None
    ):
        raise MembraneError("NEXUS source-observation boundary invalid")


def load_validated_events(path: Path = LEDGER) -> list[dict]:
    try:
        return validate_ledger(path)
    except (OSError, ValueError, TypeError) as exc:
        raise MembraneError("canonical ORACLE ledger failed validation") from exc


def _print(value):
    print(json.dumps(value, indent=2, sort_keys=True))
    return 0


def main() -> int:
    p = argparse.ArgumentParser()
    sub = p.add_subparsers(dest="cmd", required=True)
    sub.add_parser("validate")
    q = sub.add_parser("query")
    q.add_argument("--request-id", required=True)
    q.add_argument("--subject")
    q.add_argument("--event-hash")
    q.add_argument("--event-type")
    q.add_argument("--provenance-kind")
    q.add_argument("--evidence-state")
    q.add_argument("--limit", type=int, default=100)
    v = sub.add_parser("view")
    v.add_argument("--request-id", required=True)
    v.add_argument("--event-hash", required=True)
    a = sub.add_parser("audit")
    a.add_argument("--request-id", required=True)
    a.add_argument("--input", required=True)

    args = p.parse_args()
    events = load_validated_events()
    if args.cmd == "validate":
        contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
        validate_contract(contract)
        return _print(
            {
                "status": "valid",
                "protocol": TRANSPORT_PROTOCOL,
                "operations": contract["operations"],
                "authority": "evidence-only",
                "ledger_integrity": "valid",
            }
        )
    if args.cmd == "query":
        return _print(
            execute(
                events,
                build_query(
                    request_id=args.request_id,
                    subject=args.subject,
                    event_hash=args.event_hash,
                    event_type=args.event_type,
                    provenance_kind=args.provenance_kind,
                    evidence_state=args.evidence_state,
                    limit=args.limit,
                ),
            )
        )
    if args.cmd == "view":
        event = next((e for e in events if e.get("event_hash") == args.event_hash), None)
        if event is None:
            raise MembraneError("event not found")
        return _print(build_view(event, request_id=args.request_id))

    source = json.loads(Path(args.input).read_text(encoding="utf-8"))
    return _print(audit(events, build_request_from_source(request_id=args.request_id, source=source)))


if __name__ == "__main__":
    raise SystemExit(main())
