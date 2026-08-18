"""Deterministic append-only ledger primitives for QSOL-ORACLE."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any

PROVENANCE_KINDS = {
    "primary_observation",
    "derived_statement",
    "correction",
    "supersession",
    "metadata",
}
HASH_REFS_REQUIRED = {"derived_statement", "correction", "supersession"}
RELATION_EVENT_TYPES = {
    "evidence.correction": "correction",
    "evidence.supersession": "supersession",
}


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_value(value: Any) -> str:
    return sha256_bytes(canonical_bytes(value))


def event_hash(event: dict[str, Any]) -> str:
    payload = dict(event)
    payload.pop("event_hash", None)
    return sha256_value(payload)


def parse_time(value: str) -> datetime:
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        raise ValueError("timestamps must contain an explicit UTC offset")
    return parsed


def load_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as handle:
        payload = json.load(handle)
    if not isinstance(payload, dict):
        raise ValueError(f"{path}: expected a JSON object")
    return payload


def load_ledger(path: Path) -> list[dict[str, Any]]:
    events: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, raw in enumerate(handle, 1):
            line = raw.strip()
            if not line:
                continue
            try:
                event = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"ledger line {line_number}: invalid JSON: {exc}") from exc
            if not isinstance(event, dict):
                raise ValueError(f"ledger line {line_number}: event must be an object")
            events.append(event)
    return events


def _is_sha256(value: Any) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(c in "0123456789abcdef" for c in value)


def validate_event_shape(event: dict[str, Any], index: int) -> None:
    required = {
        "protocol", "sequence", "event_id", "event_type", "subject", "observed_at",
        "source", "provenance_kind", "evidence", "authority", "previous_hash", "note", "event_hash",
    }
    missing = required.difference(event)
    if missing:
        raise ValueError(f"event {index}: missing fields: {sorted(missing)}")
    if event["protocol"] != "QSOL-ORACLE/1":
        raise ValueError(f"event {index}: unsupported protocol")
    if event["authority"] != "observation-only":
        raise ValueError(f"event {index}: ORACLE authority must remain observation-only")
    if event["sequence"] != index:
        raise ValueError(f"event {index}: sequence must equal canonical file position; QSOL-ORACLE/1 uses a single-writer append-only ledger")
    parse_time(event["observed_at"])

    source = event.get("source")
    if not isinstance(source, dict) or not source.get("kind") or not source.get("locator"):
        raise ValueError(f"event {index}: source.kind and source.locator are required")

    provenance_kind = event.get("provenance_kind")
    if provenance_kind not in PROVENANCE_KINDS:
        raise ValueError(f"event {index}: invalid provenance_kind {provenance_kind!r}")

    derived_from = event.get("derived_from")
    if provenance_kind in HASH_REFS_REQUIRED:
        if not isinstance(derived_from, list) or not derived_from:
            raise ValueError(f"event {index}: {provenance_kind} requires non-empty derived_from")
        if len(set(derived_from)) != len(derived_from):
            raise ValueError(f"event {index}: derived_from must not contain duplicates")
        if not all(_is_sha256(reference) for reference in derived_from):
            raise ValueError(f"event {index}: derived_from must contain SHA-256 event hashes")
    elif derived_from is not None:
        raise ValueError(f"event {index}: derived_from is reserved for derived/correction/supersession events")

    relation_kind = RELATION_EVENT_TYPES.get(event.get("event_type"))
    target = event.get("target_event_hash")
    if relation_kind:
        if provenance_kind != relation_kind:
            raise ValueError(f"event {index}: {event['event_type']} requires provenance_kind={relation_kind}")
        if not _is_sha256(target):
            raise ValueError(f"event {index}: {event['event_type']} requires target_event_hash")
        if target not in derived_from:
            raise ValueError(f"event {index}: target_event_hash must be present in derived_from")
    elif provenance_kind in {"correction", "supersession"}:
        expected_type = "evidence.correction" if provenance_kind == "correction" else "evidence.supersession"
        raise ValueError(f"event {index}: {provenance_kind} must use event_type={expected_type}")
    elif target is not None:
        raise ValueError(f"event {index}: target_event_hash is reserved for correction/supersession")

    evidence = event.get("evidence")
    if not isinstance(evidence, dict):
        raise ValueError(f"event {index}: evidence must be an object")
    if evidence.get("state") not in {"observed", "conflict", "unknown"}:
        raise ValueError(f"event {index}: invalid evidence state")
    payload_sha = evidence.get("payload_sha256")
    if payload_sha is not None and not _is_sha256(payload_sha):
        raise ValueError(f"event {index}: evidence.payload_sha256 must be SHA-256 or null")


def validate_ledger(path: Path) -> list[dict[str, Any]]:
    events = load_ledger(path)
    if not events:
        raise ValueError("ledger must contain a genesis event")
    previous: str | None = None
    seen_ids: set[str] = set()
    seen_hashes: set[str] = set()
    for index, event in enumerate(events):
        validate_event_shape(event, index)
        if event["event_id"] in seen_ids:
            raise ValueError(f"event {index}: duplicate event_id {event['event_id']!r}")
        seen_ids.add(event["event_id"])
        if event["previous_hash"] != previous:
            raise ValueError(f"event {index}: previous_hash mismatch; expected {previous!r}, got {event['previous_hash']!r}")
        derived_from = event.get("derived_from", [])
        missing_refs = [reference for reference in derived_from if reference not in seen_hashes]
        if missing_refs:
            raise ValueError(f"event {index}: derived_from must reference earlier canonical events; missing {missing_refs}")
        target = event.get("target_event_hash")
        if target is not None and target not in seen_hashes:
            raise ValueError(f"event {index}: target_event_hash must reference an earlier event")
        expected = event_hash(event)
        if event["event_hash"] != expected:
            raise ValueError(f"event {index}: event_hash mismatch; expected {expected}, got {event['event_hash']}")
        previous = event["event_hash"]
        seen_hashes.add(previous)
    return events
