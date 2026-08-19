#!/usr/bin/env python3
"""Deterministic research-continuation contracts for QSOL-ORACLE."""
from __future__ import annotations

import hashlib
import json
from typing import Any

RESEARCH_PROTOCOL = "QSOL-ORACLE-RESEARCH/1"
CONFLICT_PROTOCOL = "QSOL-ORACLE-CONFLICT/1"
REQUIREMENT_CLASSES = {
    "primary_source": "primary-source-absent",
    "current_state": "current-state-unverified",
    "identity": "identity-unresolved",
    "provenance": "provenance-incomplete",
    "conflict_resolution": "conflict-unresolved",
    "execution": "execution-unverified",
    "scope": "scope-unspecified",
}
SOURCE_TARGETS = {
    "primary-source-absent": ("first-party-primary-record", "Locate the original first-party record, publication, repository artifact, or authoritative registry entry."),
    "current-state-unverified": ("live-authoritative-state", "Observe the current first-party state rather than relying on a cached or remembered value."),
    "identity-unresolved": ("canonical-identity-record", "Resolve the canonical identifier from a first-party registry, repository, DOI record, or governing contract."),
    "provenance-incomplete": ("provenance-record", "Locate source metadata that closes the claim-to-source provenance chain."),
    "conflict-unresolved": ("conflict-resolution-primary-records", "Collect primary records for each incompatible observation plus any explicit correction or supersession."),
    "execution-unverified": ("execution-receipt", "Locate a direct execution result, platform receipt, or validation log for the claimed action."),
    "scope-unspecified": ("governing-scope-contract", "Resolve the governing scope or ask for an explicit scope before searching for an answer."),
}


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def sha256_value(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def _is_sha256(value: Any) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(c in "0123456789abcdef" for c in value)


def _require_nonempty(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be a non-empty string")
    return value.strip()


def classify_missing_evidence(requirements: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if not isinstance(requirements, list):
        raise ValueError("requirements must be a list")
    seen: set[str] = set()
    missing: list[dict[str, Any]] = []
    for index, requirement in enumerate(requirements):
        if not isinstance(requirement, dict):
            raise ValueError(f"requirement {index} must be an object")
        rid = _require_nonempty(requirement.get("id"), f"requirement {index} id")
        if rid in seen:
            raise ValueError(f"duplicate requirement id: {rid}")
        seen.add(rid)
        kind = requirement.get("kind")
        if kind not in REQUIREMENT_CLASSES:
            raise ValueError(f"requirement {rid}: unsupported kind {kind!r}")
        satisfied = requirement.get("satisfied")
        if not isinstance(satisfied, bool):
            raise ValueError(f"requirement {rid}: satisfied must be boolean")
        detail = _require_nonempty(requirement.get("detail"), f"requirement {rid} detail")
        if not satisfied:
            missing.append({"requirement_id": rid, "requirement_kind": kind, "class": REQUIREMENT_CLASSES[kind], "detail": detail})
    missing.sort(key=lambda item: (item["class"], item["requirement_id"]))
    return missing


def generate_primary_source_targets(subject: str, missing_evidence: list[dict[str, Any]]) -> list[dict[str, Any]]:
    subject = _require_nonempty(subject, "subject")
    targets: list[dict[str, Any]] = []
    for item in missing_evidence:
        if not isinstance(item, dict) or item.get("class") not in SOURCE_TARGETS:
            raise ValueError("unsupported missing-evidence class")
        target_kind, rationale = SOURCE_TARGETS[item["class"]]
        targets.append({
            "requirement_id": _require_nonempty(item.get("requirement_id"), "missing requirement_id"),
            "target_kind": target_kind,
            "subject": subject,
            "rationale": rationale,
            "is_evidence": False,
            "status": "target-only",
        })
    targets.sort(key=lambda item: (item["target_kind"], item["requirement_id"]))
    return targets


def generate_suggested_searches(primary_source_targets: list[dict[str, Any]]) -> list[dict[str, Any]]:
    searches: list[dict[str, Any]] = []
    for target in primary_source_targets:
        if not isinstance(target, dict) or target.get("is_evidence") is not False or target.get("status") != "target-only":
            raise ValueError("primary source targets must remain target-only non-evidence")
        subject = _require_nonempty(target.get("subject"), "target subject")
        target_kind = _require_nonempty(target.get("target_kind"), "target kind")
        rid = _require_nonempty(target.get("requirement_id"), "target requirement_id")
        searches.append({
            "requirement_id": rid,
            "query": f"{subject} {target_kind.replace('-', ' ')}",
            "purpose": "discovery-only",
            "is_evidence": False,
            "admissible_as_evidence_without_observation": False,
        })
    searches.sort(key=lambda item: (item["query"], item["requirement_id"]))
    return searches


def build_unknown_response(*, subject: str, question: str, requirements: list[dict[str, Any]], plausible_answer: str | None = None) -> dict[str, Any]:
    subject = _require_nonempty(subject, "subject")
    question = _require_nonempty(question, "question")
    missing = classify_missing_evidence(requirements)
    if not missing:
        raise ValueError("unknown response requires at least one unsatisfied requirement")
    targets = generate_primary_source_targets(subject, missing)
    searches = generate_suggested_searches(targets)
    envelope: dict[str, Any] = {
        "protocol": RESEARCH_PROTOCOL,
        "state": "unknown",
        "subject": subject,
        "question": question,
        "answer": None,
        "reason": "insufficient-evidence",
        "missing_evidence": missing,
        "primary_source_targets": targets,
        "suggested_searches": searches,
        "suggested_searches_are_evidence": False,
        "plausible_completion_used": False,
        "plausible_completion_allowed": False,
        "truth_claim": False,
    }
    envelope["envelope_sha256"] = sha256_value(envelope)
    return envelope


def validate_unknown_response(envelope: dict[str, Any]) -> None:
    if envelope.get("protocol") != RESEARCH_PROTOCOL or envelope.get("state") != "unknown":
        raise ValueError("unknown response protocol or state mismatch")
    if envelope.get("answer") is not None or envelope.get("truth_claim") is not False:
        raise ValueError("unknown response must not contain a truth-claiming answer")
    if envelope.get("suggested_searches_are_evidence") is not False or envelope.get("plausible_completion_used") is not False or envelope.get("plausible_completion_allowed") is not False:
        raise ValueError("unknown response evidence/plausibility boundary invalid")
    missing = envelope.get("missing_evidence")
    targets = envelope.get("primary_source_targets")
    searches = envelope.get("suggested_searches")
    if not isinstance(missing, list) or not missing or not isinstance(targets, list) or not isinstance(searches, list):
        raise ValueError("unknown response research continuation fields malformed")
    for target in targets:
        if (
            not isinstance(target, dict)
            or target.get("is_evidence") is not False
            or target.get("status") != "target-only"
            or not isinstance(target.get("requirement_id"), str)
            or not target["requirement_id"]
            or not isinstance(target.get("target_kind"), str)
            or not target["target_kind"]
            or not isinstance(target.get("subject"), str)
            or not target["subject"]
        ):
            raise ValueError("primary source targets must remain target-only non-evidence")
    for search in searches:
        if (
            not isinstance(search, dict)
            or search.get("is_evidence") is not False
            or search.get("admissible_as_evidence_without_observation") is not False
            or search.get("purpose") != "discovery-only"
        ):
            raise ValueError("suggested searches must remain discovery-only non-evidence")
    supplied = envelope.get("envelope_sha256")
    payload = dict(envelope)
    payload.pop("envelope_sha256", None)
    if supplied != sha256_value(payload):
        raise ValueError("unknown response SHA-256 mismatch")


def build_conflict_bundle(*, subject: str, dimension: str, observations: list[dict[str, Any]]) -> dict[str, Any]:
    subject = _require_nonempty(subject, "subject")
    dimension = _require_nonempty(dimension, "dimension")
    if not isinstance(observations, list) or len(observations) < 2:
        raise ValueError("conflict bundle requires at least two observations")
    normalized: list[dict[str, Any]] = []
    for index, observation in enumerate(observations):
        if not isinstance(observation, dict) or not _is_sha256(observation.get("receipt_sha256")):
            raise ValueError(f"observation {index}: receipt_sha256 invalid")
        locator = _require_nonempty(observation.get("source_locator"), f"observation {index} source_locator")
        if "value" not in observation:
            raise ValueError(f"observation {index}: value is required")
        normalized.append({
            "receipt_sha256": observation["receipt_sha256"],
            "source_locator": locator,
            "value": observation["value"],
            "value_sha256": sha256_value(observation["value"]),
        })
    normalized.sort(key=lambda item: (item["receipt_sha256"], item["source_locator"]))
    distinct = sorted({item["value_sha256"] for item in normalized})
    if len(distinct) < 2:
        raise ValueError("conflict bundle requires materially incompatible values")
    bundle: dict[str, Any] = {
        "protocol": CONFLICT_PROTOCOL,
        "state": "conflict",
        "subject": subject,
        "dimension": dimension,
        "observations": normalized,
        "distinct_value_sha256": distinct,
        "resolution": "unresolved",
        "consensus_value": None,
        "averaging_forbidden": True,
        "truth_claim": False,
    }
    bundle["bundle_sha256"] = sha256_value(bundle)
    return bundle


def validate_conflict_bundle(bundle: dict[str, Any]) -> None:
    if bundle.get("protocol") != CONFLICT_PROTOCOL or bundle.get("state") != "conflict" or bundle.get("resolution") != "unresolved":
        raise ValueError("conflict bundle protocol/state mismatch")
    if bundle.get("consensus_value") is not None or bundle.get("averaging_forbidden") is not True or bundle.get("truth_claim") is not False:
        raise ValueError("conflict bundle must preserve unresolved non-truth-authoritative disagreement")
    observations = bundle.get("observations")
    if not isinstance(observations, list) or len(observations) < 2:
        raise ValueError("conflict bundle observations invalid")
    recomputed: list[str] = []
    seen_receipts: set[tuple[str, str]] = set()
    for index, item in enumerate(observations):
        if not isinstance(item, dict):
            raise ValueError("conflict observation malformed")
        receipt = item.get("receipt_sha256")
        locator = item.get("source_locator")
        if not _is_sha256(receipt) or not isinstance(locator, str) or not locator.strip():
            raise ValueError("conflict observation provenance fields invalid")
        key = (receipt, locator.strip())
        if key in seen_receipts:
            raise ValueError("conflict bundle contains duplicate provenance observation")
        seen_receipts.add(key)
        if "value" not in item:
            raise ValueError(f"conflict observation {index} missing value")
        value_digest = sha256_value(item["value"])
        if item.get("value_sha256") != value_digest:
            raise ValueError("conflict observation value SHA-256 mismatch")
        recomputed.append(value_digest)
    distinct = sorted(set(recomputed))
    if len(distinct) < 2:
        raise ValueError("conflict bundle no longer contains incompatible values")
    if bundle.get("distinct_value_sha256") != distinct:
        raise ValueError("conflict bundle distinct-value digest list mismatch")
    supplied = bundle.get("bundle_sha256")
    payload = dict(bundle)
    payload.pop("bundle_sha256", None)
    if supplied != sha256_value(payload):
        raise ValueError("conflict bundle SHA-256 mismatch")
