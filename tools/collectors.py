#!/usr/bin/env python3
"""Dependency-free feed collectors for QSOL-ORACLE.

Collectors normalize source observations into deterministic receipts. A receipt is
an observation artifact, not a truth verdict and not a ledger append.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

FEED_PROTOCOL = "QSOL-ORACLE-FEED/1"
FIXTURE_PROTOCOL = "QSOL-ORACLE-FIXTURES/1"
COLLECTOR_KINDS = {
    "github.repository",
    "github.commit",
    "github.release",
    "github.tag",
    "github.actions",
    "zenodo.record",
    "qsol.substrate",
    "qsol.ark",
    "qsol.int",
}
FRESHNESS_STATES = {"fresh", "stale", "undated", "future-dated"}


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    ).encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_value(value: Any) -> str:
    return sha256_bytes(canonical_bytes(value))


def parse_time(value: str) -> datetime:
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        raise ValueError("timestamps must contain an explicit UTC offset")
    return parsed


def normalize_time(value: str | None) -> str | None:
    if value is None:
        return None
    if len(value) == 10:
        value = value + "T00:00:00+00:00"
    return parse_time(value).astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def freshness_state(
    source_time: str | None,
    evaluated_at: str,
    max_age_seconds: int,
) -> dict[str, Any]:
    """Evaluate freshness without converting freshness into semantic truth."""
    if max_age_seconds < 0:
        raise ValueError("max_age_seconds must be >= 0")
    evaluated = parse_time(evaluated_at)
    if source_time is None:
        return {
            "state": "undated",
            "source_time": None,
            "evaluated_at": normalize_time(evaluated_at),
            "max_age_seconds": max_age_seconds,
            "age_seconds": None,
            "stale_means_false": False,
            "fresh_means_true": False,
        }

    source = parse_time(normalize_time(source_time) or source_time)
    delta = (evaluated.astimezone(timezone.utc) - source.astimezone(timezone.utc)).total_seconds()
    if delta < 0:
        state = "future-dated"
    elif delta <= max_age_seconds:
        state = "fresh"
    else:
        state = "stale"
    return {
        "state": state,
        "source_time": normalize_time(source_time),
        "evaluated_at": normalize_time(evaluated_at),
        "max_age_seconds": max_age_seconds,
        "age_seconds": int(delta),
        "stale_means_false": False,
        "fresh_means_true": False,
    }


from collector_normalizers import NORMALIZERS, infer_source_time, _require_mapping
from collector_io import fetch_json, github_url, zenodo_url


def collect_from_payload(
    *,
    kind: str,
    subject: str,
    source_locator: str,
    payload: dict[str, Any],
    evaluated_at: str,
    max_age_seconds: int,
    acquisition_mode: str,
    source_time: str | None = None,
    fixture_sha256: str | None = None,
) -> dict[str, Any]:
    if kind not in COLLECTOR_KINDS:
        raise ValueError(f"unsupported collector kind: {kind}")
    payload = _require_mapping(payload, kind)
    observation = NORMALIZERS[kind](payload)
    effective_source_time = source_time if source_time is not None else infer_source_time(kind, payload)
    receipt: dict[str, Any] = {
        "protocol": FEED_PROTOCOL,
        "collector": kind,
        "subject": subject,
        "source": {
            "locator": source_locator,
            "payload_sha256": sha256_value(payload),
        },
        "acquisition": {
            "mode": acquisition_mode,
            "fixture_sha256": fixture_sha256,
        },
        "freshness": freshness_state(effective_source_time, evaluated_at, max_age_seconds),
        "observation": observation,
        "observation_sha256": sha256_value(observation),
        "authority": "observation-only",
        "truth_claim": False,
    }
    receipt["receipt_sha256"] = sha256_value(receipt)
    return receipt


def validate_receipt(receipt: dict[str, Any]) -> None:
    if receipt.get("protocol") != FEED_PROTOCOL:
        raise ValueError("feed receipt protocol mismatch")
    if receipt.get("collector") not in COLLECTOR_KINDS:
        raise ValueError("feed receipt collector mismatch")
    if receipt.get("authority") != "observation-only":
        raise ValueError("collector receipts must remain observation-only")
    if receipt.get("truth_claim") is not False:
        raise ValueError("collector receipt must not claim semantic truth")
    freshness = receipt.get("freshness")
    if not isinstance(freshness, dict) or freshness.get("state") not in FRESHNESS_STATES:
        raise ValueError("collector receipt freshness state invalid")
    if freshness.get("stale_means_false") is not False or freshness.get("fresh_means_true") is not False:
        raise ValueError("freshness must not be promoted to truth semantics")

    observation = receipt.get("observation")
    if not isinstance(observation, dict):
        raise ValueError("feed receipt observation must be an object")
    supplied_observation = receipt.get("observation_sha256")
    expected_observation = sha256_value(observation)
    if supplied_observation != expected_observation:
        raise ValueError("feed receipt observation SHA-256 mismatch")

    supplied = receipt.get("receipt_sha256")
    payload = dict(receipt)
    payload.pop("receipt_sha256", None)
    expected = sha256_value(payload)
    if supplied != expected:
        raise ValueError("feed receipt SHA-256 mismatch")


def load_fixture_case(path: Path, case_id: str) -> tuple[dict[str, Any], dict[str, Any]]:
    raw = path.read_bytes()
    fixture = json.loads(raw.decode("utf-8"))
    if fixture.get("protocol") != FIXTURE_PROTOCOL:
        raise ValueError("fixture protocol mismatch")
    cases = fixture.get("cases")
    if not isinstance(cases, list):
        raise ValueError("fixture cases must be a list")
    matches = [case for case in cases if isinstance(case, dict) and case.get("id") == case_id]
    if len(matches) != 1:
        raise ValueError(f"fixture must contain exactly one case {case_id!r}")
    case = matches[0]
    receipt = collect_from_payload(
        kind=case["collector"],
        subject=case["subject"],
        source_locator=case["source_locator"],
        payload=_require_mapping(case["payload"], case_id),
        evaluated_at=case["evaluated_at"],
        max_age_seconds=case["max_age_seconds"],
        acquisition_mode="fixture",
        source_time=case.get("source_time"),
        fixture_sha256=sha256_bytes(raw),
    )
    return case, receipt
