#!/usr/bin/env python3
"""Deterministic research-continuation contracts for QSOL-ORACLE.

This module deliberately does not guess what evidence a free-form claim "probably"
needs. Callers declare structured requirements; ORACLE classifies unsatisfied
requirements, proposes primary-source targets, and labels discovery searches as
non-evidence.
"""

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
    "primary-source-absent": (
        "first-party-primary-record",
        "Locate the original first-party record, publication, repository artifact, or authoritative registry entry.",
    ),
    "current-state-unverified": (
        "live-authoritative-state",
        "Observe the current first-party state rather than relying on a cached or remembered value.",
    ),
    "identity-unresolved": (
        "canonical-identity-record",
        "Resolve the canonical identifier from a first-party registry, repository, DOI record, or governing contract.",
    ),
    "provenance-incomplete": (
        "provenance-record",
        "Locate source metadata that closes the claim-to-source provenance chain.",
    ),
    "conflict-unresolved": (
        "conflict-resolution-primary-records",
        "Collect primary records for each incompatible observation plus any explicit correction or supersession.",
    ),
    "execution-unverified": (
        "execution-receipt",
        "Locate a direct execution result, platform receipt, or validation log for the claimed action.",
    ),
    "scope-unspecified": (
        "governing-scope-contract",
        "Resolve the governing scope or ask for an explicit scope before searching for an answer.",
    ),
}


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def sha256_value(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def _require_nonempty(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be a non-empty string")
    return value.strip()


def classify_missing_evidence(requirements: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Classify explicitly declared unsatisfied evidence requirements.

    This is intentionally structural rather than NLP-based. The caller declares
    requirements; ORACLE refuses to manufacture missing requirements from rhetoric.
    """
    if not isinstance(requirements, list):
        raise ValueError("requirements must be a list")

    seen: set[str] = set()
    missing: list[dict[str, Any]] = []
    for index, requirement in enumerate(requirements):
        if not isinstance(requirement, dict):
            raise ValueError(f"requirement {index} must be an object")
        requirement_id = _require_nonempty(requirement.get("id"), f"requirement {index} id")
        if requirement_id in seen:
            raise ValueError(f"duplicate requirement id: {requirement_id}")
        seen.add(requirement_id)

        kind = requirement.get("kind")
        if kind not in REQUIREMENT_CLASSES:
            raise ValueError(f"requirement {requirement_id}: unsupported kind {kind!r}")
        satisfied = requirement.get("satisfied")
        if not isinstance(satisfied, bool):
            raise ValueError(f"requirement {requirement_id}: satisfied must be boolean")
        detail = _require_nonempty(
            requirement.get("detail"), f"requirement {requirement_id} detail"
        )
        if satisfied:
            continue
        missing.append(
            {
                "requirement_id": requirement_id,
                "requirement_kind": kind,
                "class": REQUIREMENT_CLASSES[kind],
                "detail": detail,
            }
        )

    missing.sort(key=lambda item: (item["class"], item["requirement_id"]))
    return missing


def generate_primary_source_targets(
    subject: str, missing_evidence: list[dict[str, Any]]
) -> list[dict[str, Any]]:
    subject = _require_nonempty(subject, "subject")
    targets: list[dict[str, Any]] = []
    for missing in missing_evidence:
        if not isinstance(missing, dict):
            raise ValueError("missing_evidence items must be objects")
        missing_class = missing.get("class")
        if missing_class not in SOURCE_TARGETS:
            raise ValueError(f"unsupported missing-evidence class: {missing_class!r}")
        target_kind, rationale = SOURCE_TARGETS[missing_class]
        targets.append(
            {
                "requirement_id": missing["requirement_id"],
                "target_kind": target_kind,
                "subject": subject,
                "rationale": rationale,
                "is_evidence": False,
                "status": "target-only",
            }
        )
    targets.sort(key=lambda item: (item["target_kind"], item["requirement_id"]))
    return targets


def generate_suggested_searches(
    primary_source_targets: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    searches: list[dict[str, Any]] = []
    for target in primary_source_targets:
        if not isinstance(target, dict):
            raise ValueError("primary_source_targets items must be objects")
        subject = _require_nonempty(target.get("subject"), "target subject")
        target_kind = _require_nonempty(target.get("target_kind"), "target kind")
        requirement_id = _require_nonempty(
            target.get("requirement_id"), "target requirement_id"
        )
        searches.append(
            {
                "requirement_id": requirement_id,
                "query": f"{subject} {target_kind.replace('-', ' ')}",
                "purpose": "discovery-only",
                "is_evidence": False,
                "admissible_as_evidence_without_observation": False,
            }
        )
    searches.sort(key=lambda item: (item["query"], item["requirement_id"]))
    return searches


def build_unknown_response(
    *,
    subject: str,
    question: str,
    requirements: list[dict[str, Any]],
    plausible_answer: str | None = None,
) -> dict[str, Any]:
    """Build a structured unknown envelope and intentionally ignore plausible_answer.

    A caller may pass a plausible completion to test the boundary. It is not
    incorporated into the response while evidence is missing.
    """
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
    if envelope.get("protocol") != RESEARCH_PROTOCOL:
        raise ValueError("unknown response protocol mismatch")
    if envelope.get("state") != "unknown":
        raise ValueError("unknown response state must be unknown")
    if envelope.get("answer") is not None:
        raise ValueError("unknown response must not contain a guessed answer")
    if envelope.get("suggested_searches_are_evidence") is not False:
        raise ValueError("suggested searches must be labelled non-evidence")
    if envelope.get("plausible_completion_used") is not False:
        raise ValueError("unknown response must not use plausible completion")
    if envelope.get("plausible_completion_allowed") is not False:
        raise ValueError("unknown response must forbid plausible completion")
    if envelope.get("truth_claim") is not False:
        raise ValueError("unknown response must not claim truth")
    missing = envelope.get("missing_evidence")
    if not isinstance(missing, list) or not missing:
        raise ValueError("unknown response requires missing_evidence")
    searches = envelope.get("suggested_searches")
    if not isinstance(searches, list):
        raise ValueError("unknown response suggested_searches must be a list")
    for search in searches:
        if (
            not isinstance(search, dict)
            or search.get("is_evidence") is not False
            or search.get("admissible_as_evidence_without_observation") is not False
        ):
            raise ValueError("suggested searches must remain discovery-only non-evidence")
    supplied = envelope.get("envelope_sha256")
    payload = dict(envelope)
    payload.pop("envelope_sha256", None)
    if supplied != sha256_value(payload):
        raise ValueError("unknown response SHA-256 mismatch")


def build_conflict_bundle(
    *,
    subject: str,
    dimension: str,
    observations: list[dict[str, Any]],
) -> dict[str, Any]:
    """Preserve incompatible observations without averaging them into certainty."""
    subject = _require_nonempty(subject, "subject")
    dimension = _require_nonempty(dimension, "dimension")
    if not isinstance(observations, list) or len(observations) < 2:
        raise ValueError("conflict bundle requires at least two observations")

    normalized: list[dict[str, Any]] = []
    for index, observation in enumerate(observations):
        if not isinstance(observation, dict):
            raise ValueError(f"observation {index} must be an object")
        receipt_sha256 = observation.get("receipt_sha256")
        if (
            not isinstance(receipt_sha256, str)
            or len(receipt_sha256) != 64
            or any(c not in "0123456789abcdef" for c in receipt_sha256)
        ):
            raise ValueError(f"observation {index}: receipt_sha256 invalid")
        locator = _require_nonempty(
            observation.get("source_locator"), f"observation {index} source_locator"
        )
        if "value" not in observation:
            raise ValueError(f"observation {index}: value is required")
        normalized.append(
            {
                "receipt_sha256": receipt_sha256,
                "source_locator": locator,
                "value": observation["value"],
                "value_sha256": sha256_value(observation["value"]),
            }
        )

    normalized.sort(key=lambda item: (item["receipt_sha256"], item["source_locator"]))
    distinct_values = sorted({item["value_sha256"] for item in normalized})
    if len(distinct_values) < 2:
        raise ValueError("conflict bundle requires materially incompatible values")

    bundle: dict[str, Any] = {
        "protocol": CONFLICT_PROTOCOL,
        "state": "conflict",
        "subject": subject,
        "dimension": dimension,
        "observations": normalized,
        "distinct_value_sha256": distinct_values,
        "resolution": "unresolved",
        "consensus_value": None,
        "averaging_forbidden": True,
        "truth_claim": False,
    }
    bundle["bundle_sha256"] = sha256_value(bundle)
    return bundle


def validate_conflict_bundle(bundle: dict[str, Any]) -> None:
    if bundle.get("protocol") != CONFLICT_PROTOCOL:
        raise ValueError("conflict bundle protocol mismatch")
    if bundle.get("state") != "conflict" or bundle.get("resolution") != "unresolved":
        raise ValueError("conflict bundle must preserve unresolved conflict")
    if bundle.get("consensus_value") is not None:
        raise ValueError("conflict bundle must not invent a consensus value")
    if bundle.get("averaging_forbidden") is not True:
        raise ValueError("conflict bundle must forbid averaging")
    if bundle.get("truth_claim") is not False:
        raise ValueError("conflict bundle must not claim truth")
    observations = bundle.get("observations")
    if not isinstance(observations, list) or len(observations) < 2:
        raise ValueError("conflict bundle observations invalid")
    distinct = {sha256_value(item.get("value")) for item in observations}
    if len(distinct) < 2:
        raise ValueError("conflict bundle no longer contains incompatible values")
    for item in observations:
        if item.get("value_sha256") != sha256_value(item.get("value")):
            raise ValueError("conflict observation value SHA-256 mismatch")
    supplied = bundle.get("bundle_sha256")
    payload = dict(bundle)
    payload.pop("bundle_sha256", None)
    if supplied != sha256_value(payload):
        raise ValueError("conflict bundle SHA-256 mismatch")
