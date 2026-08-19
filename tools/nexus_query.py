"""Read-only QSOL-ORACLE evidence queries for NEXUS."""
from __future__ import annotations
import copy
from typing import Any
from nexus_membrane_common import MembraneError, build_envelope, validate_envelope, is_sha256, bounded_text

QUERY_FIELDS = frozenset({"subject", "event_hash", "event_type", "provenance_kind", "evidence_state", "limit"})


def build_query(*, request_id: str, **filters: Any) -> dict[str, Any]:
    query = {k: v for k, v in filters.items() if v is not None}
    if set(query).difference(QUERY_FIELDS):
        raise MembraneError("unsupported evidence query field")
    query.setdefault("limit", 100)
    validate_query(query)
    return build_envelope(direction="nexus-to-oracle", kind="evidence_query", request_id=request_id, payload=query)


def validate_query(query: dict[str, Any]) -> None:
    if not isinstance(query, dict) or not set(query).issubset(QUERY_FIELDS):
        raise MembraneError("evidence query payload is invalid")
    if "event_hash" in query and not is_sha256(query["event_hash"]):
        raise MembraneError("event_hash must be a lowercase SHA-256")
    for field in ("subject", "event_type", "provenance_kind", "evidence_state"):
        if field in query:
            bounded_text(query[field], field, 512)
    limit = query.get("limit", 100)
    if type(limit) is not int or not 1 <= limit <= 1000:
        raise MembraneError("query limit must be in [1, 1000]")


def _matches(event: dict[str, Any], query: dict[str, Any]) -> bool:
    pairs = (("event_hash", "event_hash"), ("subject", "subject"), ("event_type", "event_type"), ("provenance_kind", "provenance_kind"))
    for query_key, event_key in pairs:
        if query.get(query_key) is not None and event.get(event_key) != query[query_key]:
            return False
    if query.get("evidence_state") is not None:
        evidence = event.get("evidence") if isinstance(event.get("evidence"), dict) else {}
        if evidence.get("state") != query["evidence_state"]:
            return False
    return True


def execute(events: list[dict[str, Any]], request: dict[str, Any]) -> dict[str, Any]:
    validate_envelope(request)
    if request["direction"] != "nexus-to-oracle" or request["kind"] != "evidence_query":
        raise MembraneError("expected a NEXUS evidence query")
    validate_query(request["payload"])
    if not isinstance(events, list) or not all(isinstance(event, dict) for event in events):
        raise MembraneError("canonical event list is invalid")
    ordered = sorted(events, key=lambda e: e.get("sequence", -1))
    matches = [copy.deepcopy(e) for e in ordered if _matches(e, request["payload"])]
    states = {e.get("evidence", {}).get("state") for e in matches if isinstance(e.get("evidence"), dict)}
    state = "unknown" if not matches or (states and states <= {"unknown"}) else ("conflict" if "conflict" in states else "known")
    limit = request["payload"].get("limit", 100)
    payload = {
        "state": state, "query": copy.deepcopy(request["payload"]), "total_matches": len(matches),
        "returned": min(len(matches), limit), "truncated": len(matches) > limit,
        "events": matches[:limit], "semantic_truth_established": False, "ledger_mutated": False,
    }
    return build_envelope(direction="oracle-to-nexus", kind="evidence_result", request_id=request["request_id"], payload=payload)
