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


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def sha256_value(value: Any) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


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
        return json.load(handle)


def load_ledger(path: Path = LEDGER) -> list[dict[str, Any]]:
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


def validate_event_shape(event: dict[str, Any], index: int) -> None:
    required = {
        "protocol",
        "sequence",
        "event_id",
        "event_type",
        "subject",
        "observed_at",
        "source",
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
        raise ValueError(f"event {index}: sequence must equal ledger position")
    parse_time(event["observed_at"])
    if event.get("evidence", {}).get("state") not in {"observed", "conflict", "unknown"}:
        raise ValueError(f"event {index}: invalid evidence state")


def validate_ledger(path: Path = LEDGER) -> list[dict[str, Any]]:
    events = load_ledger(path)
    if not events:
        raise ValueError("ledger must contain a genesis event")

    previous: str | None = None
    seen_ids: set[str] = set()
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

        expected = event_hash(event)
        if event["event_hash"] != expected:
            raise ValueError(
                f"event {index}: event_hash mismatch; expected {expected}, "
                f"got {event['event_hash']}"
            )
        previous = event["event_hash"]

    return events


def timelock_state(contract: dict[str, Any], at: datetime) -> str:
    if at.tzinfo is None:
        raise ValueError("evaluation time must be timezone-aware")
    deadline = parse_time(contract["not_before"])
    return "eligible" if at >= deadline else "locked"


def unknown_response(
    missing_evidence: list[str], suggested_searches: list[str]
) -> dict[str, Any]:
    return {
        "protocol": "QSOL-ORACLE/1",
        "state": "unknown",
        "message": "Sorry, I don't have enough information to establish that reliably.",
        "missing_evidence": missing_evidence,
        "suggested_searches": suggested_searches,
        "search_suggestions_are_evidence": False,
    }


def validate_repository(root: Path = ROOT) -> dict[str, Any]:
    manifest = load_json(root / "manifest.json")
    if manifest.get("protocol") != "QSOL-ORACLE/1":
        raise ValueError("manifest protocol mismatch")

    for relative in manifest.get("files", []):
        if not (root / relative).exists():
            raise ValueError(f"manifest references missing file: {relative}")

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
