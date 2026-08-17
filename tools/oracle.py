#!/usr/bin/env python3
"""Small, dependency-free reference tooling for QSOL-ORACLE."""

from __future__ import annotations

import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
LEDGER = ROOT / "ledger" / "events.jsonl"
TIMELOCK = ROOT / "contracts" / "qsol-context-2056.json"
MANIFEST = ROOT / "manifest.json"

PROVENANCE_KINDS = {
    "primary_observation",
    "derived_statement",
    "correction",
    "metadata",
}
HASH_REFS_REQUIRED = {"derived_statement", "correction"}
DECLARED_PATH_KEYS = {
    "entrypoint",
    "constitution",
    "nexus_boundary",
    "ledger",
    "event_schema",
    "founding_timelock",
}


def canonical_bytes(value: Any) -> bytes:
    """Encode a value as deterministic canonical JSON bytes."""
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def sha256_value(value: Any) -> str:
    """Return SHA-256 over canonical JSON bytes."""
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def event_hash(event: dict[str, Any]) -> str:
    """Return the deterministic identity of an event excluding event_hash itself."""
    payload = dict(event)
    payload.pop("event_hash", None)
    return sha256_value(payload)


def parse_time(value: str) -> datetime:
    """Parse an ISO-8601 timestamp and require an explicit timezone."""
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        raise ValueError("timestamps must contain an explicit UTC offset")
    return parsed


def load_json(path: Path) -> dict[str, Any]:
    """Load one UTF-8 JSON object."""
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def load_ledger(path: Path = LEDGER) -> list[dict[str, Any]]:
    """Load the canonical single-writer JSONL ledger in file order."""
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
    return (
        isinstance(value, str)
        and len(value) == 64
        and all(character in "0123456789abcdef" for character in value)
    )


def validate_event_shape(event: dict[str, Any], index: int) -> None:
    """Validate the authority and provenance boundary of one witness event."""
    required = {
        "protocol",
        "sequence",
        "event_id",
        "event_type",
        "subject",
        "observed_at",
        "source",
        "provenance_kind",
        "evidence",
        "authority",
        "previous_hash",
        "note",
        "event_hash",
    }
    missing = required.difference(event)
    if missing:
        raise ValueError(f"event {index}: missing fields: {sorted(missing)}")
    if event["protocol"] != "QSOL-ORACLE/1":
        raise ValueError(f"event {index}: unsupported protocol")
    if event["authority"] != "observation-only":
        raise ValueError(f"event {index}: ORACLE authority must remain observation-only")
    if event["sequence"] != index:
        raise ValueError(
            f"event {index}: sequence must equal canonical file position; "
            "QSOL-ORACLE/1 uses a single-writer append-only ledger"
        )
    parse_time(event["observed_at"])

    provenance_kind = event.get("provenance_kind")
    if provenance_kind not in PROVENANCE_KINDS:
        raise ValueError(f"event {index}: invalid provenance_kind {provenance_kind!r}")

    derived_from = event.get("derived_from")
    if provenance_kind in HASH_REFS_REQUIRED:
        if not isinstance(derived_from, list) or not derived_from:
            raise ValueError(
                f"event {index}: {provenance_kind} requires non-empty derived_from"
            )
        if len(set(derived_from)) != len(derived_from):
            raise ValueError(f"event {index}: derived_from must not contain duplicates")
        if not all(_is_sha256(reference) for reference in derived_from):
            raise ValueError(f"event {index}: derived_from must contain SHA-256 event hashes")
    elif derived_from is not None:
        raise ValueError(
            f"event {index}: derived_from is reserved for derived_statement/correction events"
        )

    if event.get("evidence", {}).get("state") not in {"observed", "conflict", "unknown"}:
        raise ValueError(f"event {index}: invalid evidence state")


def validate_ledger(path: Path = LEDGER) -> list[dict[str, Any]]:
    """Validate the single-writer append-only hash chain in canonical file order."""
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
            raise ValueError(
                f"event {index}: previous_hash mismatch; expected {previous!r}, "
                f"got {event['previous_hash']!r}"
            )

        derived_from = event.get("derived_from", [])
        missing_refs = [reference for reference in derived_from if reference not in seen_hashes]
        if missing_refs:
            raise ValueError(
                f"event {index}: derived_from must reference earlier canonical events; "
                f"missing {missing_refs}"
            )

        expected = event_hash(event)
        if event["event_hash"] != expected:
            raise ValueError(
                f"event {index}: event_hash mismatch; expected {expected}, "
                f"got {event['event_hash']}"
            )
        previous = event["event_hash"]
        seen_hashes.add(previous)

    return events


def validate_manifest(manifest: dict[str, Any], root: Path) -> list[str]:
    """Validate manifest path safety, uniqueness, declared contracts, and existence."""
    if manifest.get("protocol") != "QSOL-ORACLE/1":
        raise ValueError("manifest protocol mismatch")
    if manifest.get("ledger_model") != "single-writer-append-only":
        raise ValueError("manifest must declare the single-writer append-only ledger model")

    files = manifest.get("files")
    if not isinstance(files, list) or not files or not all(isinstance(item, str) for item in files):
        raise ValueError("manifest.files must be a non-empty list of repository-relative strings")
    if len(set(files)) != len(files):
        raise ValueError("manifest.files must not contain duplicates")

    for relative in files:
        path = Path(relative)
        if path.is_absolute() or ".." in path.parts:
            raise ValueError(f"manifest contains unsafe path: {relative}")
        if not (root / path).exists():
            raise ValueError(f"manifest references missing file: {relative}")

    for key in DECLARED_PATH_KEYS:
        declared = manifest.get(key)
        if not isinstance(declared, str) or declared not in files:
            raise ValueError(f"manifest {key} must name a path included in manifest.files")

    return files


def timelock_state(contract: dict[str, Any], at: datetime) -> str:
    """Return locked or eligible without granting execution authority."""
    if at.tzinfo is None:
        raise ValueError("evaluation time must be timezone-aware")
    deadline = parse_time(contract["not_before"])
    return "eligible" if at >= deadline else "locked"


def unknown_response(
    missing_evidence: list[str], suggested_searches: list[str]
) -> dict[str, Any]:
    """Return an actionable unknown without laundering search hints into evidence."""
    return {
        "protocol": "QSOL-ORACLE/1",
        "state": "unknown",
        "message": "Sorry, I don't have enough information to establish that reliably.",
        "missing_evidence": missing_evidence,
        "suggested_searches": suggested_searches,
        "search_suggestions_are_evidence": False,
    }


def validate_repository(root: Path = ROOT) -> dict[str, Any]:
    """Validate repository contracts, manifest, ledger, and founding timelock witness."""
    manifest = load_json(root / "manifest.json")
    validate_manifest(manifest, root)

    constitution = load_json(root / "ai" / "constitution.json")
    if constitution.get("maximal_truth_mode") is not True:
        raise ValueError("Maximum Truth Mode has been disabled. This is how prophecies happen.")
    if "UNKNOWN > PLAUSIBLE_GUESS" not in constitution.get("invariants", []):
        raise ValueError("constitution must prefer unknown to plausible invention")

    events = validate_ledger(root / "ledger" / "events.jsonl")
    contract = load_json(root / "contracts" / "qsol-context-2056.json")
    if contract.get("protocol") != "QSOL-TIMELOCK/1":
        raise ValueError("timelock protocol mismatch")
    if contract.get("fail_closed") is not True:
        raise ValueError("timelock must fail closed")
    if contract.get("credential_policy", {}).get("store_long_lived_credentials") is not False:
        raise ValueError("30-year credentials are forbidden")

    contract_digest = sha256_value(contract)
    matching = [e for e in events if e.get("event_id") == "timelock.qsol-context.2056"]
    if len(matching) != 1:
        raise ValueError("ledger must contain exactly one founding timelock directive event")
    witnessed_digest = matching[0]["evidence"]["payload_sha256"]
    if witnessed_digest != contract_digest:
        raise ValueError(
            "timelock witness digest mismatch: contract changed without a new witness event"
        )

    return {
        "protocol": "QSOL-ORACLE/1",
        "status": "valid",
        "events": len(events),
        "ledger_model": manifest["ledger_model"],
        "ledger_head": events[-1]["event_hash"],
        "timelock_contract_sha256": contract_digest,
    }


def command_validate(_: argparse.Namespace) -> int:
    report = validate_repository()
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0


def command_timelock(args: argparse.Namespace) -> int:
    contract = load_json(TIMELOCK)
    at = parse_time(args.at) if args.at else datetime.now(timezone.utc)
    state = timelock_state(contract, at)
    output = {
        "protocol": contract["protocol"],
        "contract_id": contract["contract_id"],
        "subject": contract["subject"],
        "evaluated_at": at.isoformat(),
        "not_before": contract["not_before"],
        "state": state,
        "execution_authorized": False,
        "note": (
            "Deadline maturity creates eligibility only; publication still requires every "
            "fail-closed precondition and a current authorized executor."
        ),
    }
    print(json.dumps(output, indent=2, sort_keys=True))
    return 0


def command_unknown(args: argparse.Namespace) -> int:
    result = unknown_response(args.missing, args.search)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="QSOL-ORACLE reference tooling")
    subparsers = parser.add_subparsers(dest="command", required=True)

    validate = subparsers.add_parser("validate", help="validate contracts and witness ledger")
    validate.set_defaults(func=command_validate)

    timelock = subparsers.add_parser("timelock", help="evaluate the QSOL-CONTEXT timelock")
    timelock.add_argument("--at", help="ISO-8601 evaluation time; defaults to current UTC time")
    timelock.set_defaults(func=command_timelock)

    unknown = subparsers.add_parser("unknown", help="emit an actionable unknown response")
    unknown.add_argument("--missing", action="append", default=[], help="missing evidence item")
    unknown.add_argument("--search", action="append", default=[], help="suggested search target")
    unknown.set_defaults(func=command_unknown)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
