#!/usr/bin/env python3
"""Dependency-free reference tooling for QSOL-ORACLE."""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import collectors  # noqa: E402

LEDGER = ROOT / "ledger" / "events.jsonl"
CHECKPOINT = ROOT / "ledger" / "checkpoint.json"
RELEASE_FINGERPRINT = ROOT / "release" / "fingerprint.json"
TIMELOCK = ROOT / "contracts" / "qsol-context-2056.json"
MANIFEST = ROOT / "manifest.json"
FIXTURES = ROOT / "fixtures" / "collectors.json"

from oracle_ledger import (
    PROVENANCE_KINDS, canonical_bytes, event_hash, load_json, parse_time,
    sha256_bytes, sha256_value, validate_event_shape as _validate_event_shape,
    load_ledger as _load_ledger, validate_ledger as _validate_ledger,
)

HASH_REFS_REQUIRED = {"derived_statement", "correction", "supersession"}
RELATION_EVENT_TYPES = {
    "evidence.correction": "correction",
    "evidence.supersession": "supersession",
}
DECLARED_PATH_KEYS = {
    "entrypoint", "constitution", "nexus_boundary", "ledger", "event_schema",
    "founding_timelock", "checkpoint", "release_fingerprint", "signature_schema",
    "feed_schema", "checkpoint_schema", "release_fingerprint_schema",
    "collector_tool", "collector_fixture",
}


def load_ledger(path: Path = LEDGER):
    return _load_ledger(path)


def validate_event_shape(event, index: int) -> None:
    _validate_event_shape(event, index)


def validate_ledger(path: Path = LEDGER):
    return _validate_ledger(path)


from oracle_integrity import (
    build_ledger_checkpoint, validate_ledger_checkpoint, detached_signature_envelope,
    validate_detached_signature_envelope, build_release_fingerprint, validate_release_fingerprint,
)

def validate_manifest(manifest: dict[str, Any], root: Path) -> list[str]:
    import oracle_contracts
    return oracle_contracts.validate_manifest(manifest, root, declared_path_keys=DECLARED_PATH_KEYS, provenance_kinds=PROVENANCE_KINDS, collector_kinds=collectors.COLLECTOR_KINDS, freshness_states=collectors.FRESHNESS_STATES)


def timelock_state(contract: dict[str, Any], at: datetime) -> str:
    import oracle_contracts
    return oracle_contracts.timelock_state(contract, at, parse_time)


def unknown_response(missing_evidence: list[str], suggested_searches: list[str]) -> dict[str, Any]:
    import oracle_contracts
    return oracle_contracts.unknown_response(missing_evidence, suggested_searches)


def validate_repository(root: Path = ROOT) -> dict[str, Any]:
    """Validate repository contracts, ledger integrity, checkpoints, and release identity."""
    manifest = load_json(root / "manifest.json")
    validate_manifest(manifest, root)

    constitution = load_json(root / "ai" / "constitution.json")
    if constitution.get("maximal_truth_mode") is not True:
        raise ValueError("Maximum Truth Mode has been disabled. This is how prophecies happen.")
    invariants = constitution.get("invariants", [])
    for required in {
        "UNKNOWN > PLAUSIBLE_GUESS",
        "SIGNATURE_VALID != CLAIM_TRUE",
        "FRESH != TRUE",
        "STALE != FALSE",
    }:
        if required not in invariants:
            raise ValueError(f"constitution missing invariant: {required}")

    events = validate_ledger(root / manifest["ledger"])
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

    checkpoint = load_json(root / manifest["checkpoint"])
    validate_ledger_checkpoint(checkpoint, root / manifest["ledger"])
    fingerprint = load_json(root / manifest["release_fingerprint"])
    validate_release_fingerprint(fingerprint, root, manifest)

    return {
        "protocol": "QSOL-ORACLE/1",
        "status": "valid",
        "events": len(events),
        "ledger_model": manifest["ledger_model"],
        "ledger_head": events[-1]["event_hash"],
        "ledger_checkpoint_sha256": checkpoint["checkpoint_sha256"],
        "release_fingerprint_sha256": fingerprint["release_fingerprint_sha256"],
        "timelock_contract_sha256": contract_digest,
        "collector_count": len(collectors.COLLECTOR_KINDS),
    }




def main() -> int:
    import oracle_cli
    return oracle_cli.main(sys.modules[__name__])


if __name__ == "__main__":
    raise SystemExit(main())
