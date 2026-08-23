#!/usr/bin/env python3
"""Live-local QSOL-ORACLE -> QSOL-FED evidence export transport.

The transport is intentionally local stdio JSONL. It reads the validated ORACLE
ledger, emits attributed observations, and has no network or mutation capability.
"""
from __future__ import annotations

import argparse
import copy
import hashlib
import json
from pathlib import Path
import re
import sys
import unicodedata
from typing import Any, BinaryIO, Iterator

TOOLS = Path(__file__).resolve().parent
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

from nexus_membrane_common import MembraneError, scan_hidden_reasoning
from oracle_ledger import canonical_bytes as ledger_canonical_bytes
from oracle_ledger import validate_ledger
from research import build_unknown_response, classify_missing_evidence

ROOT = Path(__file__).resolve().parents[1]
LEDGER = ROOT / "ledger" / "events.jsonl"
CONTRACT = ROOT / "contracts" / "fed-membrane.json"
OBSERVATION_SCHEMA = ROOT / "schema" / "fed-oracle-observation.schema.json"
REQUEST_SCHEMA = ROOT / "schema" / "fed-transport-request.schema.json"
RESPONSE_SCHEMA = ROOT / "schema" / "fed-transport-response.schema.json"

PROTOCOL = "QSOL-ORACLE-FED/1"
REQUEST_KIND = "evidence.export"
RESPONSE_KIND = "evidence.export.result"
OBSERVATION_SCHEMA_ID = "qsol-fed-oracle-observation/1"
PINNED_FED_COMMIT = "407d0ed75c7d8a76bd49b3c30e74a0ae2c59f1e6"
MAX_LINE_BYTES = 65_536
MAX_DEPTH = 32
MAX_STRING_UTF8 = 8_192
MAX_ARRAY_ITEMS = 1_024
MAX_OBJECT_MEMBERS = 1_024
SAFE_INTEGER_MIN = -(2**53 - 1)
SAFE_INTEGER_MAX = 2**53 - 1

QUERY_FIELDS = frozenset({"subject", "event_hash", "event_type", "provenance_kind", "evidence_state", "limit"})
REQUEST_FIELDS = frozenset({
    "protocol", "kind", "request_id", "query", "research", "synthetic_input",
    "evidence_promotion_requested", "authority_requested", "remote_execution_requested",
})
RESPONSE_FIELDS = frozenset({
    "protocol", "kind", "request_id", "observation", "total_matches", "returned",
    "truncated", "source_events_sha256", "ledger_mutated", "transport_authority",
    "response_sha256",
})
REQUIREMENT_FIELDS = frozenset({"id", "kind", "satisfied", "detail"})
REQUIREMENT_KINDS = frozenset({
    "primary_source", "current_state", "identity", "provenance",
    "conflict_resolution", "execution", "scope",
})
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_ORACLE_EVENT_REF = re.compile(r"^oracle-event:([0-9a-f]{64})$")

_EXPECTED_TRANSPORT = {
    "profile": "local-stdio-jsonl",
    "network_required": False,
    "outbound_network_client": False,
    "canonical_input_required": True,
    "deterministic_output": True,
    "maximum_line_bytes": MAX_LINE_BYTES,
    "request_kind": REQUEST_KIND,
    "response_kind": RESPONSE_KIND,
    "response_budget_policy": "truncate-discovery-searches-before-response-limit",
    "failure_semantics": "fail-closed-process-error-no-partial-authority",
}
_EXPECTED_OBSERVATION = {
    "evidence_reference_prefix": "oracle-event:",
    "maximum_evidence_refs": 256,
    "conflict_requires_distinct_evidence_refs": True,
    "conflict_supporting_reference_policy": "evidence.state=conflict only",
    "reference_uniqueness": "NFC-normalized reference",
    "ledger_membership_required_when_validating_live_response": True,
    "suggested_search_purpose": "discovery-only",
    "suggested_search_is_evidence": False,
    "research_missing_evidence_forces_unknown": True,
    "synthetic_input": False,
    "truth_claim": False,
    "evidence_promotion": False,
    "authority_effect": "none",
}
_EXPECTED_FIREWALL = {
    "transport_creates_truth": False,
    "transport_promotes_evidence": False,
    "transport_creates_governance_authority": False,
    "transport_creates_or_reweights_votes": False,
    "transport_installs_capabilities": False,
    "transport_mutates_citizenship": False,
    "transport_rewrites_history": False,
    "transport_triggers_remote_execution": False,
    "transport_mutates_oracle_ledger": False,
    "transport_accepts_synthetic_input": False,
    "transport_accepts_hidden_reasoning": False,
}
_EXPECTED_PHASE_GATE = (
    "a valid local transport request may receive attributed ORACLE observations only; "
    "known/conflict/unknown are preserved, explicit missing evidence forces unknown, "
    "conflict requires two conflict-supporting canonical ledger references, searches remain "
    "non-evidence and are bounded by the response budget, the ledger remains unchanged, and "
    "no response creates truth, evidence promotion, authority, governance, capability, "
    "citizenship, history rewrite, or execution rights"
)


class TransportError(ValueError):
    """Fail-closed ORACLE-FED transport validation error."""


class PairObject(list):
    pass


def _reject_float(_: str) -> None:
    raise TransportError("floating_point_forbidden")


def _reject_constant(_: str) -> None:
    raise TransportError("non_finite_number_forbidden")


def _pairs_hook(pairs: list[tuple[str, Any]]) -> PairObject:
    return PairObject(pairs)


def _nfc(value: str) -> str:
    if any(0xD800 <= ord(char) <= 0xDFFF for char in value):
        raise TransportError("lone_surrogate")
    normalized = unicodedata.normalize("NFC", value)
    if len(normalized.encode("utf-8")) > MAX_STRING_UTF8:
        raise TransportError("string_too_large")
    return normalized


def _ledger_nfc(value: str) -> str:
    if any(0xD800 <= ord(char) <= 0xDFFF for char in value):
        raise TransportError("ledger_string_contains_lone_surrogate")
    return unicodedata.normalize("NFC", value)


def _normalize(value: Any, depth: int = 1) -> Any:
    if depth > MAX_DEPTH:
        raise TransportError("max_depth_exceeded")
    if value is None or isinstance(value, bool):
        return value
    if isinstance(value, int) and not isinstance(value, bool):
        if not SAFE_INTEGER_MIN <= value <= SAFE_INTEGER_MAX:
            raise TransportError("integer_out_of_range")
        return value
    if isinstance(value, str):
        return _nfc(value)
    if isinstance(value, PairObject):
        if len(value) > MAX_OBJECT_MEMBERS:
            raise TransportError("too_many_object_members")
        raw_seen: set[str] = set()
        normalized_seen: set[str] = set()
        result: dict[str, Any] = {}
        for raw_key, child in value:
            if not isinstance(raw_key, str) or raw_key in raw_seen:
                raise TransportError("duplicate_or_non_string_key")
            raw_seen.add(raw_key)
            key = _nfc(raw_key)
            if key in normalized_seen:
                raise TransportError("normalized_duplicate_key")
            normalized_seen.add(key)
            result[key] = _normalize(child, depth + 1)
        return result
    if isinstance(value, list):
        if len(value) > MAX_ARRAY_ITEMS:
            raise TransportError("too_many_array_items")
        return [_normalize(child, depth + 1) for child in value]
    if isinstance(value, dict):
        if len(value) > MAX_OBJECT_MEMBERS:
            raise TransportError("too_many_object_members")
        result: dict[str, Any] = {}
        seen: set[str] = set()
        for raw_key, child in value.items():
            if not isinstance(raw_key, str):
                raise TransportError("non_string_key")
            key = _nfc(raw_key)
            if key in seen:
                raise TransportError("normalized_duplicate_key")
            seen.add(key)
            result[key] = _normalize(child, depth + 1)
        return result
    raise TransportError(f"unsupported_value:{type(value).__name__}")


def canonical_bytes(value: Any) -> bytes:
    normalized = _normalize(copy.deepcopy(value))
    rendered = json.dumps(normalized, ensure_ascii=False, allow_nan=False, sort_keys=True, separators=(",", ":"))
    encoded = rendered.encode("utf-8")
    if len(encoded) > MAX_LINE_BYTES:
        raise TransportError("transport_line_too_large")
    return encoded


def parse_canonical_line(raw: bytes) -> dict[str, Any]:
    if not raw or len(raw) > MAX_LINE_BYTES:
        raise TransportError("transport_line_size_invalid")
    try:
        text = raw.decode("utf-8")
        parsed = json.loads(text, object_pairs_hook=_pairs_hook, parse_float=_reject_float, parse_constant=_reject_constant)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise TransportError("malformed_transport_json") from exc
    normalized = _normalize(parsed)
    if not isinstance(normalized, dict):
        raise TransportError("transport_request_must_be_object")
    if canonical_bytes(normalized) != raw:
        raise TransportError("noncanonical_transport_json")
    return normalized


def _sha256_transport(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def _sha256_ledger_value(value: Any) -> str:
    return hashlib.sha256(ledger_canonical_bytes(value)).hexdigest()


def _bounded(value: Any, label: str, maximum: int) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise TransportError(f"{label}_invalid")
    return _nfc(value.strip())


def _validate_requirements(requirements: Any) -> list[dict[str, Any]]:
    if not isinstance(requirements, list) or not 1 <= len(requirements) <= 64:
        raise TransportError("research_requirements_invalid")
    normalized_ids: set[str] = set()
    for requirement in requirements:
        if not isinstance(requirement, dict) or set(requirement) != REQUIREMENT_FIELDS:
            raise TransportError("research_requirement_fields_invalid")
        rid = _bounded(requirement["id"], "research_requirement_id", 256)
        if rid in normalized_ids:
            raise TransportError("research_requirement_id_duplicate")
        normalized_ids.add(rid)
        if requirement["kind"] not in REQUIREMENT_KINDS:
            raise TransportError("research_requirement_kind_invalid")
        if not isinstance(requirement["satisfied"], bool):
            raise TransportError("research_requirement_satisfied_invalid")
        _bounded(requirement["detail"], "research_requirement_detail", 4096)
    try:
        missing = classify_missing_evidence(requirements)
    except ValueError as exc:
        raise TransportError("research_requirements_invalid") from exc
    if not missing:
        raise TransportError("research_requires_missing_evidence")
    return missing


def validate_request(request: dict[str, Any]) -> None:
    if not isinstance(request, dict) or set(request) != REQUEST_FIELDS:
        raise TransportError("request_fields_invalid")
    if request["protocol"] != PROTOCOL or request["kind"] != REQUEST_KIND:
        raise TransportError("request_protocol_or_kind_invalid")
    _bounded(request["request_id"], "request_id", 256)
    for field in ("synthetic_input", "evidence_promotion_requested", "authority_requested", "remote_execution_requested"):
        if request[field] is not False:
            raise TransportError(f"{field}_must_be_false")
    scan_hidden_reasoning(request)

    query = request["query"]
    if not isinstance(query, dict) or set(query).difference(QUERY_FIELDS):
        raise TransportError("query_fields_invalid")
    for field in ("subject", "event_type", "provenance_kind", "evidence_state"):
        if field in query:
            _bounded(query[field], field, 512)
    if "event_hash" in query and (not isinstance(query["event_hash"], str) or _SHA256.fullmatch(query["event_hash"]) is None):
        raise TransportError("event_hash_invalid")
    limit = query.get("limit", 256)
    if type(limit) is not int or not 1 <= limit <= 256:
        raise TransportError("query_limit_invalid")

    research = request["research"]
    if research is not None:
        if not isinstance(research, dict) or set(research) != {"subject", "question", "requirements"}:
            raise TransportError("research_fields_invalid")
        _bounded(research["subject"], "research_subject", 4096)
        _bounded(research["question"], "research_question", 4096)
        _validate_requirements(research["requirements"])
    canonical_bytes(request)


def _event_field_equal(event: dict[str, Any], field: str, requested: Any) -> bool:
    observed = event.get(field)
    if not isinstance(observed, str) or not isinstance(requested, str):
        return observed == requested
    return _ledger_nfc(observed) == unicodedata.normalize("NFC", requested)


def _matches(event: dict[str, Any], query: dict[str, Any]) -> bool:
    if "event_hash" in query and event.get("event_hash") != query["event_hash"]:
        return False
    for field in ("subject", "event_type", "provenance_kind"):
        if field in query and not _event_field_equal(event, field, query[field]):
            return False
    if "evidence_state" in query:
        evidence = event.get("evidence")
        state = evidence.get("state") if isinstance(evidence, dict) else None
        if not isinstance(state, str) or _ledger_nfc(state) != unicodedata.normalize("NFC", query["evidence_state"]):
            return False
    return True


def _execute_query(events: list[dict[str, Any]], query: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(events, list) or not all(isinstance(event, dict) for event in events):
        raise TransportError("canonical_event_list_invalid")
    ordered = sorted(events, key=lambda event: event.get("sequence", -1))
    matches = [event for event in ordered if _matches(event, query)]
    states = {
        _ledger_nfc(state)
        for event in matches
        if isinstance(event.get("evidence"), dict)
        and isinstance((state := event["evidence"].get("state")), str)
    }
    if not matches or (states and states <= {"unknown"}):
        state = "unknown"
    elif "conflict" in states:
        state = "conflict"
    else:
        state = "known"
    limit = query.get("limit", 256)
    selected = matches[:limit]
    return {"state": state, "total_matches": len(matches), "selected": selected, "query_truncated": len(matches) > len(selected)}


def _ledger_hashes(events: list[dict[str, Any]]) -> set[str]:
    hashes: set[str] = set()
    for event in events:
        event_hash = event.get("event_hash")
        if isinstance(event_hash, str) and _SHA256.fullmatch(event_hash):
            hashes.add(event_hash)
    return hashes


def _validate_observation(observation: dict[str, Any], *, ledger_hashes: set[str] | None = None) -> None:
    expected = {"schema", "state", "evidence_refs", "suggested_searches", "synthetic_input", "truth_claim", "evidence_promotion", "authority_effect"}
    if not isinstance(observation, dict) or set(observation) != expected:
        raise TransportError("observation_fields_invalid")
    if observation["schema"] != OBSERVATION_SCHEMA_ID or observation["state"] not in {"known", "conflict", "unknown"}:
        raise TransportError("observation_identity_or_state_invalid")
    if observation["synthetic_input"] is not False or observation["truth_claim"] is not False or observation["evidence_promotion"] is not False or observation["authority_effect"] != "none":
        raise TransportError("observation_authority_boundary_invalid")

    refs = observation["evidence_refs"]
    if not isinstance(refs, list) or len(refs) > 256:
        raise TransportError("observation_evidence_refs_invalid")
    seen: set[str] = set()
    evidence_true = 0
    for item in refs:
        if not isinstance(item, dict) or set(item) != {"reference", "is_evidence"}:
            raise TransportError("observation_evidence_ref_invalid")
        reference = _bounded(item["reference"], "evidence_reference", 8192)
        match = _ORACLE_EVENT_REF.fullmatch(reference)
        if match is None:
            raise TransportError("observation_evidence_reference_not_oracle_event")
        event_hash = match.group(1)
        if ledger_hashes is not None and event_hash not in ledger_hashes:
            raise TransportError("observation_evidence_reference_not_in_ledger")
        key = unicodedata.normalize("NFC", reference)
        if key in seen:
            raise TransportError("observation_duplicate_evidence_reference")
        seen.add(key)
        if not isinstance(item["is_evidence"], bool):
            raise TransportError("observation_evidence_flag_invalid")
        evidence_true += int(item["is_evidence"])
    if observation["state"] == "known" and evidence_true < 1:
        raise TransportError("known_requires_evidence")
    if observation["state"] == "conflict" and evidence_true < 2:
        raise TransportError("conflict_requires_distinct_evidence")

    searches = observation["suggested_searches"]
    if not isinstance(searches, list) or len(searches) > 64:
        raise TransportError("observation_searches_invalid")
    for item in searches:
        if not isinstance(item, dict) or set(item) != {"query", "purpose", "is_evidence", "admissible_as_evidence_without_observation"}:
            raise TransportError("observation_search_invalid")
        _bounded(item["query"], "suggested_search", 8192)
        if item["purpose"] != "discovery-only" or item["is_evidence"] is not False or item["admissible_as_evidence_without_observation"] is not False:
            raise TransportError("suggested_search_became_evidence")
    canonical_bytes(observation)


def _reference_events(state: str, selected: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if state != "conflict":
        return selected
    supporting = [
        event
        for event in selected
        if isinstance(event.get("evidence"), dict)
        and isinstance(event["evidence"].get("state"), str)
        and _ledger_nfc(event["evidence"]["state"]) == "conflict"
    ]
    hashes = {event.get("event_hash") for event in supporting if isinstance(event.get("event_hash"), str) and _SHA256.fullmatch(event["event_hash"])}
    if len(hashes) < 2:
        raise TransportError("conflict_requires_two_conflict_supporting_references")
    return supporting


def _make_refs(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    refs: list[dict[str, Any]] = []
    seen: set[str] = set()
    for event in events:
        event_hash = event.get("event_hash")
        if not isinstance(event_hash, str) or _SHA256.fullmatch(event_hash) is None:
            raise TransportError("selected_event_hash_invalid")
        reference = f"oracle-event:{event_hash}"
        if reference in seen:
            raise TransportError("duplicate_selected_event")
        seen.add(reference)
        refs.append({"reference": reference, "is_evidence": True})
    return refs


def _response_shell(request_id: str, observation: dict[str, Any], *, total_matches: int, source_events_sha256: str) -> dict[str, Any]:
    returned = len(observation["evidence_refs"])
    return {
        "protocol": PROTOCOL,
        "kind": RESPONSE_KIND,
        "request_id": request_id,
        "observation": observation,
        "total_matches": total_matches,
        "returned": returned,
        "truncated": total_matches > returned,
        "source_events_sha256": source_events_sha256,
        "ledger_mutated": False,
        "transport_authority": "none",
        "response_sha256": "0" * 64,
    }


def _budget_searches(request_id: str, observation: dict[str, Any], candidates: list[dict[str, Any]], *, total_matches: int, source_events_sha256: str) -> list[dict[str, Any]]:
    accepted: list[dict[str, Any]] = []
    for candidate in candidates[:64]:
        trial = copy.deepcopy(observation)
        trial["suggested_searches"] = accepted + [candidate]
        shell = _response_shell(request_id, trial, total_matches=total_matches, source_events_sha256=source_events_sha256)
        try:
            canonical_bytes(shell)
        except TransportError as exc:
            if str(exc) == "transport_line_too_large":
                break
            raise
        accepted.append(candidate)
    return accepted


def export_observation(events: list[dict[str, Any]], request: dict[str, Any]) -> dict[str, Any]:
    validate_request(request)
    query_result = _execute_query(events, request["query"])
    state = query_result["state"]
    selected = query_result["selected"]

    if request["research"] is not None:
        _validate_requirements(request["research"]["requirements"])
        state = "unknown"

    reference_events = _reference_events(state, selected)
    refs = _make_refs(reference_events)
    source_digest = _sha256_ledger_value(reference_events)

    observation = {
        "schema": OBSERVATION_SCHEMA_ID,
        "state": state,
        "evidence_refs": refs,
        "suggested_searches": [],
        "synthetic_input": False,
        "truth_claim": False,
        "evidence_promotion": False,
        "authority_effect": "none",
    }

    if state == "unknown" and request["research"] is not None:
        research = request["research"]
        try:
            unknown = build_unknown_response(subject=research["subject"], question=research["question"], requirements=research["requirements"])
        except ValueError as exc:
            raise TransportError("unknown_research_generation_failed") from exc
        candidates = [
            {"query": item["query"], "purpose": "discovery-only", "is_evidence": False, "admissible_as_evidence_without_observation": False}
            for item in unknown["suggested_searches"][:64]
        ]
        observation["suggested_searches"] = _budget_searches(
            request["request_id"], observation, candidates,
            total_matches=query_result["total_matches"], source_events_sha256=source_digest,
        )

    ledger_hashes = _ledger_hashes(events)
    _validate_observation(observation, ledger_hashes=ledger_hashes)

    response = _response_shell(request["request_id"], observation, total_matches=query_result["total_matches"], source_events_sha256=source_digest)
    response.pop("response_sha256")
    response["response_sha256"] = _sha256_transport(response)
    validate_response(response, events)
    return response


def validate_response(response: dict[str, Any], events: list[dict[str, Any]] | None = None) -> None:
    if not isinstance(response, dict) or set(response) != RESPONSE_FIELDS:
        raise TransportError("response_fields_invalid")
    if response["protocol"] != PROTOCOL or response["kind"] != RESPONSE_KIND:
        raise TransportError("response_protocol_or_kind_invalid")
    _bounded(response["request_id"], "response_request_id", 256)
    if type(response["total_matches"]) is not int or response["total_matches"] < 0:
        raise TransportError("response_total_matches_invalid")
    if type(response["returned"]) is not int or not 0 <= response["returned"] <= 256:
        raise TransportError("response_returned_invalid")
    if response["returned"] > response["total_matches"] or response["truncated"] is not (response["total_matches"] > response["returned"]):
        raise TransportError("response_count_or_truncation_invalid")
    if not isinstance(response["source_events_sha256"], str) or _SHA256.fullmatch(response["source_events_sha256"]) is None:
        raise TransportError("response_source_digest_invalid")
    if response["ledger_mutated"] is not False or response["transport_authority"] != "none":
        raise TransportError("response_authority_boundary_invalid")
    hashes = _ledger_hashes(events) if events is not None else None
    _validate_observation(response["observation"], ledger_hashes=hashes)
    supplied = response["response_sha256"]
    if not isinstance(supplied, str) or _SHA256.fullmatch(supplied) is None:
        raise TransportError("response_digest_invalid")
    payload = dict(response)
    payload.pop("response_sha256")
    if supplied != _sha256_transport(payload):
        raise TransportError("response_digest_mismatch")
    if response["returned"] != len(response["observation"]["evidence_refs"]):
        raise TransportError("response_reference_count_mismatch")
    canonical_bytes(response)


def validate_contract() -> dict[str, Any]:
    contract = json.loads(CONTRACT.read_text(encoding="utf-8"))
    required = {"type", "protocol", "version", "relationship", "oracle_role", "fed_role", "consumer_pin", "transport", "states", "observation", "authority_firewall", "phase_gate"}
    if not isinstance(contract, dict) or set(contract) != required:
        raise TransportError("fed_membrane_contract_fields_invalid")
    if contract["type"] != "qsol-oracle-fed-membrane" or contract["protocol"] != PROTOCOL or contract["version"] != "1.0.0" or contract["relationship"] != "evidence-export-membrane" or contract["oracle_role"] != "WITNESSES" or contract["fed_role"] != "CONSUMES_ATTRIBUTED_OBSERVATIONS":
        raise TransportError("fed_membrane_contract_identity_invalid")
    if contract["consumer_pin"] != {"repository": "QSOLKCB/QSOL-FED", "commit": PINNED_FED_COMMIT, "schema_path": "schemas/oracle-observation-v1.schema.json", "schema_id": OBSERVATION_SCHEMA_ID}:
        raise TransportError("fed_consumer_pin_drift")
    if contract["transport"] != _EXPECTED_TRANSPORT:
        raise TransportError("fed_transport_profile_drift")
    if contract["states"] != ["known", "conflict", "unknown"]:
        raise TransportError("fed_transport_state_set_drift")
    if contract["observation"] != _EXPECTED_OBSERVATION:
        raise TransportError("fed_transport_observation_contract_drift")
    if contract["authority_firewall"] != _EXPECTED_FIREWALL:
        raise TransportError("fed_transport_authority_firewall_drift")
    if contract["phase_gate"] != _EXPECTED_PHASE_GATE:
        raise TransportError("fed_transport_phase_gate_drift")

    observation_schema = json.loads(OBSERVATION_SCHEMA.read_text(encoding="utf-8"))
    request_schema = json.loads(REQUEST_SCHEMA.read_text(encoding="utf-8"))
    response_schema = json.loads(RESPONSE_SCHEMA.read_text(encoding="utf-8"))
    if observation_schema.get("$id") != OBSERVATION_SCHEMA_ID or observation_schema.get("additionalProperties") is not False:
        raise TransportError("fed_observation_schema_drift")
    if request_schema.get("$id") != "qsol-oracle-fed-request/1" or request_schema.get("additionalProperties") is not False:
        raise TransportError("fed_request_schema_drift")
    if response_schema.get("$id") != "qsol-oracle-fed-response/1" or response_schema.get("additionalProperties") is not False:
        raise TransportError("fed_response_schema_drift")
    return contract


def _load_request(path: Path) -> dict[str, Any]:
    raw = path.read_bytes()
    if raw.endswith(b"\n"):
        raw = raw[:-1]
    return parse_canonical_line(raw)


def _write_response(response: dict[str, Any]) -> None:
    sys.stdout.buffer.write(canonical_bytes(response) + b"\n")
    sys.stdout.buffer.flush()


def _bounded_lines(stream: BinaryIO) -> Iterator[bytes]:
    while True:
        raw_line = stream.readline(MAX_LINE_BYTES + 2)
        if raw_line == b"":
            return
        if len(raw_line) > MAX_LINE_BYTES + 1:
            raise TransportError("jsonl_line_too_large")
        if not raw_line.endswith(b"\n"):
            raise TransportError("jsonl_line_missing_newline_or_too_large")
        yield raw_line[:-1]


def serve(events: list[dict[str, Any]]) -> int:
    for raw in _bounded_lines(sys.stdin.buffer):
        request = parse_canonical_line(raw)
        _write_response(export_observation(events, request))
    return 0


def main() -> int:
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("validate")
    export = sub.add_parser("export")
    export.add_argument("--request", required=True, type=Path)
    sub.add_parser("serve")
    args = parser.parse_args()

    if args.command == "validate":
        contract = validate_contract()
        print(json.dumps({"status": "valid", "protocol": PROTOCOL, "transport": contract["transport"]["profile"], "authority": "none"}, sort_keys=True))
        return 0

    try:
        events = validate_ledger(LEDGER)
    except (OSError, ValueError, TypeError) as exc:
        raise TransportError("canonical_oracle_ledger_invalid") from exc
    if args.command == "export":
        _write_response(export_observation(events, _load_request(args.request)))
        return 0
    return serve(events)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (TransportError, MembraneError, ValueError) as exc:
        print(f"qsol-oracle-fed transport error: {exc}", file=sys.stderr)
        raise SystemExit(2)
