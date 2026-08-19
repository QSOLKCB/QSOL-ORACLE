"""Visible-claim-only audits for NEXUS responses."""
from __future__ import annotations

import copy
from typing import Any

from oracle_ledger import sha256_value
from nexus_membrane_common import (
    MembraneError,
    bounded_text,
    build_envelope,
    is_sha256,
    scan_hidden_reasoning,
    validate_envelope,
)

AUDIT_PROTOCOL = "QSOL-ORACLE-NEXUS-AUDIT/1"
PRESENTATIONS = frozenset({"fact", "inference", "unknown", "conflict"})
FINDINGS = frozenset(
    {
        "citation_support",
        "claim_exceeds_evidence",
        "inference_presented_as_fact",
        "conflict_suppressed",
        "unknown_suppressed",
    }
)
_AUDIT_SOURCE_FIELDS = frozenset({"response_id", "visible_claims", "hidden_reasoning_provided"})


def build_request(*, request_id: str, response_id: str, claims: list[dict[str, Any]]) -> dict[str, Any]:
    payload = {
        "response_id": bounded_text(response_id, "response_id", 256),
        "visible_claims": copy.deepcopy(claims),
        "hidden_reasoning_provided": False,
    }
    validate_request(payload)
    return build_envelope(
        direction="nexus-to-oracle",
        kind="visible_claim_audit",
        request_id=request_id,
        payload=payload,
    )


def build_request_from_source(*, request_id: str, source: dict[str, Any]) -> dict[str, Any]:
    """Validate the complete caller object before selecting audit fields."""
    if not isinstance(source, dict):
        raise MembraneError("visible-claim audit source must be an object")
    scan_hidden_reasoning(source)
    if not {"response_id", "visible_claims"}.issubset(source):
        raise MembraneError("visible-claim audit source fields are incomplete")
    if not set(source).issubset(_AUDIT_SOURCE_FIELDS):
        raise MembraneError("visible-claim audit source contains unsupported fields")
    payload = {
        "response_id": source["response_id"],
        "visible_claims": copy.deepcopy(source["visible_claims"]),
        "hidden_reasoning_provided": source.get("hidden_reasoning_provided", False),
    }
    validate_request(payload)
    return build_envelope(
        direction="nexus-to-oracle",
        kind="visible_claim_audit",
        request_id=request_id,
        payload=payload,
    )


def validate_request(payload: dict[str, Any]) -> None:
    if not isinstance(payload, dict) or set(payload) != _AUDIT_SOURCE_FIELDS:
        raise MembraneError("visible-claim audit payload is invalid")
    bounded_text(payload["response_id"], "response_id", 256)
    if payload["hidden_reasoning_provided"] is not False:
        raise MembraneError("hidden reasoning must not be supplied for audit")
    claims = payload["visible_claims"]
    if not isinstance(claims, list) or len(claims) > 512:
        raise MembraneError("visible_claims must be a bounded list")
    seen = set()
    for claim in claims:
        if not isinstance(claim, dict) or set(claim) != {
            "claim_id",
            "text",
            "presentation",
            "evidence_refs",
        }:
            raise MembraneError("visible claim schema is invalid")
        claim_id = bounded_text(claim["claim_id"], "claim_id", 128)
        if claim_id in seen:
            raise MembraneError("visible claim IDs must be unique")
        seen.add(claim_id)
        bounded_text(claim["text"], "claim text", 16384)
        if claim["presentation"] not in PRESENTATIONS:
            raise MembraneError("visible claim presentation is invalid")
        refs = claim["evidence_refs"]
        if (
            not isinstance(refs, list)
            or len(refs) > 256
            or len(set(refs)) != len(refs)
            or not all(is_sha256(r) for r in refs)
        ):
            raise MembraneError("visible claim evidence_refs are invalid")
    scan_hidden_reasoning(payload)


def _findings(claim: dict[str, Any], index: dict[str, dict[str, Any]]) -> list[str]:
    refs = claim["evidence_refs"]
    presentation = claim["presentation"]
    out: set[str] = set()

    if not refs:
        if presentation != "unknown":
            out.add("claim_exceeds_evidence")
        return sorted(out)

    events: list[dict[str, Any]] = []
    for ref in refs:
        event = index.get(ref)
        if event is None:
            out.add("citation_support")
        else:
            events.append(event)

    if not events:
        if presentation in {"fact", "inference"}:
            out.add("claim_exceeds_evidence")
        return sorted(out)

    states = {
        e.get("evidence", {}).get("state")
        for e in events
        if isinstance(e.get("evidence"), dict)
    }
    provenance = {e.get("provenance_kind") for e in events}

    if "conflict" in states and presentation != "conflict":
        out.add("conflict_suppressed")
    if "unknown" in states and presentation not in {"unknown", "conflict"}:
        out.add("unknown_suppressed")

    if presentation == "fact":
        if provenance and provenance <= {"derived_statement"}:
            out.add("inference_presented_as_fact")
        # A citation proves the observation exists. The membrane currently has
        # no machine-verifiable relation from arbitrary visible claim text to
        # the semantics of that event, so citation presence is not claim support.
        out.add("claim_exceeds_evidence")

    return sorted(out)


def audit(events: list[dict[str, Any]], request: dict[str, Any]) -> dict[str, Any]:
    validate_envelope(request)
    if request["kind"] != "visible_claim_audit" or request["direction"] != "nexus-to-oracle":
        raise MembraneError("expected visible-claim audit request")
    validate_request(request["payload"])
    index = {
        e["event_hash"]: e
        for e in events
        if isinstance(e, dict) and is_sha256(e.get("event_hash"))
    }

    results = []
    all_findings: set[str] = set()
    for claim in request["payload"]["visible_claims"]:
        findings = _findings(claim, index)
        all_findings.update(findings)
        results.append(
            {
                "claim_id": claim["claim_id"],
                "presentation": claim["presentation"],
                "evidence_refs": list(claim["evidence_refs"]),
                "findings": findings,
                "structurally_consistent": not findings,
            }
        )

    payload = {
        "protocol": AUDIT_PROTOCOL,
        "response_id": request["payload"]["response_id"],
        "scope": "visible-claims-and-explicit-evidence-only",
        "claim_results": results,
        "findings": sorted(all_findings),
        "status": "no-structural-objection" if not all_findings else "attention",
        "hidden_reasoning_examined": False,
        "hidden_reasoning_required": False,
        "nexus_output_modified": False,
        "nexus_output_blocked": False,
        "worldstore_mutated": False,
        "governance_action_taken": False,
        "truth_claim": False,
        "authority": "audit-only",
    }
    payload["audit_sha256"] = sha256_value(payload)
    envelope = build_envelope(
        direction="oracle-to-nexus",
        kind="claim_audit_receipt",
        request_id=request["request_id"],
        payload=payload,
    )
    validate_receipt(envelope)
    return envelope


def validate_receipt(envelope: dict[str, Any]) -> None:
    validate_envelope(envelope)
    if envelope["kind"] != "claim_audit_receipt" or envelope["direction"] != "oracle-to-nexus":
        raise MembraneError("expected claim-audit receipt")

    payload = envelope["payload"]
    required = {
        "protocol",
        "response_id",
        "scope",
        "claim_results",
        "findings",
        "status",
        "hidden_reasoning_examined",
        "hidden_reasoning_required",
        "nexus_output_modified",
        "nexus_output_blocked",
        "worldstore_mutated",
        "governance_action_taken",
        "truth_claim",
        "authority",
        "audit_sha256",
    }
    if not isinstance(payload, dict) or set(payload) != required:
        raise MembraneError("claim-audit receipt fields are invalid")
    if (
        payload["protocol"] != AUDIT_PROTOCOL
        or payload["scope"] != "visible-claims-and-explicit-evidence-only"
        or payload["authority"] != "audit-only"
    ):
        raise MembraneError("claim-audit receipt boundary invalid")
    bounded_text(payload["response_id"], "response_id", 256)

    false_fields = (
        "hidden_reasoning_examined",
        "hidden_reasoning_required",
        "nexus_output_modified",
        "nexus_output_blocked",
        "worldstore_mutated",
        "governance_action_taken",
        "truth_claim",
    )
    if any(payload[field] is not False for field in false_fields):
        raise MembraneError("claim-audit receipt must not gain control or hidden-reasoning authority")

    results = payload["claim_results"]
    if not isinstance(results, list) or len(results) > 512:
        raise MembraneError("claim-audit claim_results are invalid")

    aggregate: set[str] = set()
    seen_ids: set[str] = set()
    for result in results:
        expected_fields = {
            "claim_id",
            "presentation",
            "evidence_refs",
            "findings",
            "structurally_consistent",
        }
        if not isinstance(result, dict) or set(result) != expected_fields:
            raise MembraneError("claim-audit result fields are invalid")
        claim_id = bounded_text(result["claim_id"], "claim_id", 128)
        if claim_id in seen_ids:
            raise MembraneError("claim-audit result IDs must be unique")
        seen_ids.add(claim_id)
        if result["presentation"] not in PRESENTATIONS:
            raise MembraneError("claim-audit result presentation is invalid")
        refs = result["evidence_refs"]
        if (
            not isinstance(refs, list)
            or len(refs) > 256
            or len(set(refs)) != len(refs)
            or not all(is_sha256(ref) for ref in refs)
        ):
            raise MembraneError("claim-audit result evidence_refs are invalid")
        findings = result["findings"]
        if (
            not isinstance(findings, list)
            or findings != sorted(set(findings))
            or not set(findings) <= FINDINGS
        ):
            raise MembraneError("claim-audit result findings are invalid")
        if result["structurally_consistent"] is not (len(findings) == 0):
            raise MembraneError("claim-audit structural consistency is invalid")
        aggregate.update(findings)

    findings = payload["findings"]
    expected_findings = sorted(aggregate)
    if findings != expected_findings:
        raise MembraneError("claim-audit aggregate findings are invalid")

    expected_status = "no-structural-objection" if not findings else "attention"
    if payload["status"] != expected_status:
        raise MembraneError("claim-audit status does not match findings")

    base = copy.deepcopy(payload)
    supplied = base.pop("audit_sha256")
    if not is_sha256(supplied) or supplied != sha256_value(base):
        raise MembraneError("claim-audit receipt SHA-256 mismatch")
