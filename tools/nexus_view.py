"""Presentation-only ORACLE event views for the NEXUS Courtroom Stenographer."""
from __future__ import annotations

import copy
from typing import Any

from oracle_ledger import sha256_value
from nexus_membrane_common import MembraneError, build_envelope, is_sha256, validate_envelope

VIEW_PROTOCOL = "QSOL-ORACLE-STENOGRAPHER-VIEW/1"
STENO_BOUNDARY = {
    "target_surface": "Courtroom Stenographer",
    "native_schema": "nexus-stenographer/1",
    "native_record": False,
    "native_record_scope": "ai_actions_only",
    "external_view_scope": "oracle_evidence",
    "append_to_native_stenographer_ledger": False,
    "read_only": True,
}


def build_view(event: dict[str, Any], *, request_id: str) -> dict[str, Any]:
    if not isinstance(event, dict) or not is_sha256(event.get("event_hash")):
        raise MembraneError("ORACLE event identity is invalid")
    view = {
        "protocol": VIEW_PROTOCOL,
        "view_type": "oracle_witness_event",
        "event_hash": event["event_hash"],
        "sequence": event.get("sequence"),
        "subject": event.get("subject"),
        "event_type": event.get("event_type"),
        "observed_at": event.get("observed_at"),
        "source": copy.deepcopy(event.get("source")),
        "provenance_kind": event.get("provenance_kind"),
        "derived_from": copy.deepcopy(event.get("derived_from")),
        "target_event_hash": event.get("target_event_hash"),
        "evidence": copy.deepcopy(event.get("evidence")),
        "authority": "presentation-only",
        "truth_claim": False,
        "hidden_reasoning_included": False,
        "nexus_stenographer": copy.deepcopy(STENO_BOUNDARY),
    }
    view["view_sha256"] = sha256_value(view)
    validate_view_payload(view)
    return build_envelope(
        direction="oracle-to-nexus",
        kind="stenographer_event_view",
        request_id=request_id,
        payload=view,
    )


def validate_view_payload(view: dict[str, Any]) -> None:
    required = {
        "protocol", "view_type", "event_hash", "sequence", "subject", "event_type",
        "observed_at", "source", "provenance_kind", "derived_from", "target_event_hash",
        "evidence", "authority", "truth_claim", "hidden_reasoning_included",
        "nexus_stenographer", "view_sha256",
    }
    if not isinstance(view, dict) or set(view) != required:
        raise MembraneError("Stenographer event view fields are invalid")
    if view["protocol"] != VIEW_PROTOCOL or view["view_type"] != "oracle_witness_event":
        raise MembraneError("Stenographer event view protocol mismatch")
    if not is_sha256(view["event_hash"]) or view["authority"] != "presentation-only":
        raise MembraneError("Stenographer event view authority invalid")
    if view["truth_claim"] is not False or view["hidden_reasoning_included"] is not False:
        raise MembraneError("Stenographer event view trust boundary invalid")
    if view["nexus_stenographer"] != STENO_BOUNDARY:
        raise MembraneError("NEXUS Stenographer compatibility boundary invalid")
    derived_from = view["derived_from"]
    if derived_from is not None and (
        not isinstance(derived_from, list) or not derived_from
        or len(set(derived_from)) != len(derived_from)
        or not all(is_sha256(item) for item in derived_from)
    ):
        raise MembraneError("Stenographer event view derived_from is invalid")
    target = view["target_event_hash"]
    if target is not None and not is_sha256(target):
        raise MembraneError("Stenographer event view target_event_hash is invalid")
    provenance = view["provenance_kind"]
    if provenance in {"correction", "supersession"}:
        if not isinstance(derived_from, list) or target is None or target not in derived_from:
            raise MembraneError("Stenographer correction/supersession relationship is incomplete")
    elif target is not None:
        raise MembraneError("Stenographer target_event_hash is reserved for corrections/supersessions")
    payload = copy.deepcopy(view)
    supplied = payload.pop("view_sha256")
    if supplied != sha256_value(payload):
        raise MembraneError("Stenographer event view SHA-256 mismatch")


def validate_view(envelope: dict[str, Any]) -> None:
    validate_envelope(envelope)
    if envelope["kind"] != "stenographer_event_view" or envelope["direction"] != "oracle-to-nexus":
        raise MembraneError("expected an ORACLE Stenographer event view")
    validate_view_payload(envelope["payload"])
