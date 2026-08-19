"""Shared QSOL-ORACLE↔NEXUS membrane envelope rules."""
from __future__ import annotations

import copy
import re
from typing import Any
from oracle_ledger import sha256_value

TRANSPORT_PROTOCOL = "QSOL-ORACLE-NEXUS/1"
DIRECTION_KIND_AUTHORITY = {
    ("nexus-to-oracle", "evidence_query"): "evidence-query-only",
    ("nexus-to-oracle", "visible_claim_audit"): "visible-claim-audit-only",
    ("oracle-to-nexus", "evidence_result"): "evidence-delivery-only",
    ("oracle-to-nexus", "claim_audit_receipt"): "visible-claim-audit-only",
    ("oracle-to-nexus", "stenographer_event_view"): "presentation-only",
}
_FORBIDDEN_REASONING_KEYS = frozenset({
    "chain_of_thought", "hidden_chain_of_thought", "hidden_reasoning",
    "private_reasoning", "reasoning_trace", "internal_monologue", "scratchpad", "cot",
})
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


class MembraneError(ValueError):
    """Fail-closed membrane validation error."""


def is_sha256(value: object) -> bool:
    return isinstance(value, str) and _SHA256.fullmatch(value) is not None


def bounded_text(value: object, label: str, maximum: int = 4096) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise MembraneError(f"{label} must be a non-empty bounded string")
    if any(ord(ch) < 0x20 and ch not in "\t\n\r" for ch in value):
        raise MembraneError(f"{label} contains forbidden control characters")
    return value.strip()


def scan_hidden_reasoning(value: object) -> None:
    if isinstance(value, dict):
        for key, nested in value.items():
            if not isinstance(key, str):
                raise MembraneError("membrane payload contains a non-string key")
            normalized = key.strip().lower().replace("-", "_").replace(" ", "_")
            if normalized in _FORBIDDEN_REASONING_KEYS:
                raise MembraneError("hidden chain-of-thought fields are forbidden at the membrane")
            scan_hidden_reasoning(nested)
    elif isinstance(value, list):
        for nested in value:
            scan_hidden_reasoning(nested)


def envelope_digest(envelope: dict[str, Any]) -> str:
    payload = copy.deepcopy(envelope)
    payload.pop("envelope_sha256", None)
    return sha256_value(payload)


def build_envelope(*, direction: str, kind: str, request_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    authority = DIRECTION_KIND_AUTHORITY.get((direction, kind))
    if authority is None:
        raise MembraneError("unsupported ORACLE↔NEXUS direction/kind pair")
    bounded_text(request_id, "request_id", 256)
    if not isinstance(payload, dict):
        raise MembraneError("membrane payload must be an object")
    scan_hidden_reasoning(payload)
    envelope = {
        "protocol": TRANSPORT_PROTOCOL, "direction": direction, "kind": kind,
        "request_id": request_id, "payload": copy.deepcopy(payload), "authority": authority,
        "hidden_reasoning_included": False, "worldstore_mutation_authorized": False,
        "council_vote_authority": False, "governance_authority": False,
        "output_mutation_authorized": False,
    }
    envelope["envelope_sha256"] = envelope_digest(envelope)
    validate_envelope(envelope)
    return envelope


def validate_envelope(envelope: dict[str, Any]) -> None:
    required = {
        "protocol", "direction", "kind", "request_id", "payload", "authority",
        "hidden_reasoning_included", "worldstore_mutation_authorized",
        "council_vote_authority", "governance_authority", "output_mutation_authorized",
        "envelope_sha256",
    }
    if not isinstance(envelope, dict) or set(envelope) != required:
        raise MembraneError("membrane envelope fields are invalid")
    if envelope["protocol"] != TRANSPORT_PROTOCOL:
        raise MembraneError("membrane protocol mismatch")
    expected = DIRECTION_KIND_AUTHORITY.get((envelope["direction"], envelope["kind"]))
    if expected is None or envelope["authority"] != expected:
        raise MembraneError("membrane direction/kind/authority mismatch")
    bounded_text(envelope["request_id"], "request_id", 256)
    if not isinstance(envelope["payload"], dict):
        raise MembraneError("membrane payload must be an object")
    scan_hidden_reasoning(envelope["payload"])
    for field in (
        "hidden_reasoning_included", "worldstore_mutation_authorized",
        "council_vote_authority", "governance_authority", "output_mutation_authorized",
    ):
        if envelope[field] is not False:
            raise MembraneError(f"{field} must remain false")
    if not is_sha256(envelope["envelope_sha256"]) or envelope["envelope_sha256"] != envelope_digest(envelope):
        raise MembraneError("membrane envelope SHA-256 mismatch")
