#!/usr/bin/env python3
"""Fail-closed publication-clearance tooling for QSOL-TIMELOCK/1.

The scanner operates only on a local repository path supplied by the operator.
It never publishes, uploads, or copies repository contents. Findings identify
paths and detector IDs only; suspected secret values are never emitted.
"""

from __future__ import annotations

import fnmatch
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCAN_PROTOCOL = "QSOL-PUBLICATION-SCAN/1"
CLASSIFICATION_PROTOCOL = "QSOL-PUBLICATION-CLASSIFICATION/1"
CLEARANCE_PROTOCOL = "QSOL-PUBLICATION-CLEARANCE/1"

CLASSIFICATIONS = {
    "public",
    "redact-before-publication",
    "permanent-deny",
}

FILENAME_DETECTORS = {
    "sensitive-filename-dotenv": [".env", ".env.*"],
    "sensitive-filename-private-key": ["id_rsa", "id_ed25519", "*.key"],
}

CONTENT_DETECTORS: tuple[tuple[str, re.Pattern[bytes]], ...] = (
    (
        "private-key-material",
        re.compile(br"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----"),
    ),
    (
        "github-token-shape",
        re.compile(br"(?:github_pat_[A-Za-z0-9_]{20,}|gh[pousr]_[A-Za-z0-9]{20,})"),
    ),
)


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=False
    ).encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_value(value: Any) -> str:
    return sha256_bytes(canonical_bytes(value))


def _is_commit_id(value: Any) -> bool:
    if not isinstance(value, str) or len(value) not in {40, 64}:
        return False
    return all(c in "0123456789abcdef" for c in value)


def _normalize_time(value: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError("evaluation time must be a non-empty ISO-8601 string")
    if value.endswith("Z"):
        value = value[:-1] + "+00:00"
    parsed = datetime.fromisoformat(value)
    if parsed.tzinfo is None:
        raise ValueError("evaluation time must contain an explicit UTC offset")
    return parsed.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")


def _timelock_state(contract: dict[str, Any], evaluated_at: str) -> str:
    now = datetime.fromisoformat(_normalize_time(evaluated_at).replace("Z", "+00:00"))
    not_before_raw = contract.get("not_before")
    if not isinstance(not_before_raw, str):
        raise ValueError("timelock contract not_before missing")
    not_before = datetime.fromisoformat(
        _normalize_time(not_before_raw).replace("Z", "+00:00")
    )
    return "eligible" if now >= not_before else "locked"


def _safe_relative(path_value: str) -> str:
    if not isinstance(path_value, str) or not path_value:
        raise ValueError("classification path must be a non-empty string")
    path = Path(path_value)
    if path.is_absolute() or ".." in path.parts:
        raise ValueError(f"unsafe classification path: {path_value}")
    normalized = path.as_posix()
    if normalized.startswith("./"):
        normalized = normalized[2:]
    if normalized in {"", "."}:
        raise ValueError("classification path must identify a file")
    return normalized


def _load_classification(classification: dict[str, Any]) -> dict[str, dict[str, Any]]:
    if classification.get("protocol") != CLASSIFICATION_PROTOCOL:
        raise ValueError("classification manifest protocol mismatch")
    if not _is_commit_id(classification.get("source_commit")):
        raise ValueError("classification source_commit must be a 40- or 64-hex commit id")
    entries = classification.get("entries")
    if not isinstance(entries, list):
        raise ValueError("classification entries must be a list")
    by_path: dict[str, dict[str, Any]] = {}
    for index, entry in enumerate(entries):
        if not isinstance(entry, dict):
            raise ValueError(f"classification entry {index} must be an object")
        path = _safe_relative(entry.get("path"))
        if path in by_path:
            raise ValueError(f"duplicate classification path: {path}")
        level = entry.get("classification")
        if level not in CLASSIFICATIONS:
            raise ValueError(f"classification entry {path}: unsupported classification")
        expected = entry.get("sha256")
        if expected is not None and (
            not isinstance(expected, str)
            or len(expected) != 64
            or any(c not in "0123456789abcdef" for c in expected)
        ):
            raise ValueError(f"classification entry {path}: sha256 invalid")
        reason = entry.get("reason")
        if reason is not None and not isinstance(reason, str):
            raise ValueError(f"classification entry {path}: reason must be a string")
        by_path[path] = {
            "classification": level,
            "sha256": expected,
            "reason": reason,
        }
    return by_path


def _filename_findings(relative: str) -> list[str]:
    name = Path(relative).name
    findings: list[str] = []
    for detector_id, patterns in FILENAME_DETECTORS.items():
        if any(fnmatch.fnmatch(name, pattern) for pattern in patterns):
            findings.append(detector_id)
    return findings


def _content_findings(raw: bytes) -> list[str]:
    findings: list[str] = []
    for detector_id, pattern in CONTENT_DETECTORS:
        if pattern.search(raw):
            findings.append(detector_id)
    return findings


def scan_repository(
    repo_root: Path,
    classification: dict[str, Any],
    *,
    subject: str,
    source_commit: str,
) -> dict[str, Any]:
    """Classify every local file and fail closed on omissions or sensitive findings."""
    repo_root = Path(repo_root).resolve()
    if not repo_root.is_dir():
        raise ValueError("repository root must be an existing directory")
    if not isinstance(subject, str) or not subject.strip():
        raise ValueError("subject must be a non-empty string")
    if classification.get("subject") != subject.strip():
        raise ValueError("classification manifest subject mismatch")
    if not _is_commit_id(source_commit):
        raise ValueError("source_commit must be a 40- or 64-hex commit id")
    if classification.get("source_commit") != source_commit:
        raise ValueError("classification manifest source_commit mismatch")

    by_path = _load_classification(classification)
    records: list[dict[str, Any]] = []
    sensitive_findings: list[dict[str, str]] = []
    unsafe_symlinks: list[str] = []

    for path in sorted(repo_root.rglob("*"), key=lambda p: p.as_posix()):
        try:
            relative = path.relative_to(repo_root).as_posix()
        except ValueError as exc:
            raise ValueError("repository scan escaped root") from exc
        if relative == ".git" or relative.startswith(".git/"):
            continue
        if path.is_symlink():
            unsafe_symlinks.append(relative)
            records.append(
                {
                    "path": relative,
                    "kind": "symlink",
                    "bytes": None,
                    "sha256": None,
                    "classification": by_path.get(relative, {}).get(
                        "classification", "unclassified"
                    ),
                    "classification_hash_matches": False,
                }
            )
            continue
        if not path.is_file():
            continue

        raw = path.read_bytes()
        digest = sha256_bytes(raw)
        declared = by_path.get(relative)
        if declared is None:
            classification_level = "unclassified"
            hash_matches = False
        else:
            classification_level = declared["classification"]
            expected = declared.get("sha256")
            hash_matches = expected is None or expected == digest
            if not hash_matches:
                classification_level = "unclassified"

        records.append(
            {
                "path": relative,
                "kind": "file",
                "bytes": len(raw),
                "sha256": digest,
                "classification": classification_level,
                "classification_hash_matches": hash_matches,
            }
        )

        detectors = sorted(set(_filename_findings(relative) + _content_findings(raw)))
        for detector_id in detectors:
            sensitive_findings.append({"path": relative, "detector": detector_id})

    present_paths = {item["path"] for item in records}
    orphan_entries = sorted(set(by_path).difference(present_paths))
    counts = {
        "files": sum(1 for item in records if item["kind"] == "file"),
        "symlinks": len(unsafe_symlinks),
        "public": sum(1 for item in records if item["classification"] == "public"),
        "redact_before_publication": sum(
            1 for item in records if item["classification"] == "redact-before-publication"
        ),
        "permanent_deny": sum(
            1 for item in records if item["classification"] == "permanent-deny"
        ),
        "unclassified": sum(
            1 for item in records if item["classification"] == "unclassified"
        ),
        "sensitive_findings": len(sensitive_findings),
        "orphan_classification_entries": len(orphan_entries),
    }
    gates = {
        "zero_unclassified_material": counts["unclassified"] == 0,
        "zero_permanent_deny_material": counts["permanent_deny"] == 0,
        "zero_redaction_required": counts["redact_before_publication"] == 0,
        "zero_sensitive_findings": counts["sensitive_findings"] == 0,
        "zero_unsafe_symlinks": counts["symlinks"] == 0,
        "zero_orphan_classification_entries": counts["orphan_classification_entries"] == 0,
    }
    report: dict[str, Any] = {
        "protocol": SCAN_PROTOCOL,
        "subject": subject.strip(),
        "source_commit": source_commit,
        "classification_manifest_sha256": sha256_value(classification),
        "records": records,
        "sensitive_findings": sensitive_findings,
        "unsafe_symlinks": sorted(unsafe_symlinks),
        "orphan_classification_entries": orphan_entries,
        "counts": counts,
        "gates": gates,
        "publishable_from_classification": all(gates.values()),
        "secret_values_in_report": False,
        "authority": "local-publication-safety-scan-only",
        "truth_claim": False,
    }
    report["scan_sha256"] = sha256_value(report)
    return report


def validate_scan(report: dict[str, Any]) -> None:
    if report.get("protocol") != SCAN_PROTOCOL:
        raise ValueError("publication scan protocol mismatch")
    if report.get("secret_values_in_report") is not False:
        raise ValueError("publication scan must not expose secret values")
    if report.get("authority") != "local-publication-safety-scan-only":
        raise ValueError("publication scan authority mismatch")
    if report.get("truth_claim") is not False:
        raise ValueError("publication scan must not claim semantic truth")
    gates = report.get("gates")
    if not isinstance(gates, dict):
        raise ValueError("publication scan gates missing")
    counts = report.get("counts")
    if not isinstance(counts, dict):
        raise ValueError("publication scan counts missing")
    expected_publishable = all(value is True for value in gates.values())
    if report.get("publishable_from_classification") is not expected_publishable:
        raise ValueError("publication scan publishability does not match gates")
    supplied = report.get("scan_sha256")
    payload = dict(report)
    payload.pop("scan_sha256", None)
    if supplied != sha256_value(payload):
        raise ValueError("publication scan SHA-256 mismatch")


def build_clearance_receipt(
    scan: dict[str, Any],
    contract: dict[str, Any],
    *,
    evaluated_at: str,
    provenance_requirements_passed: bool,
) -> dict[str, Any]:
    validate_scan(scan)
    if contract.get("protocol") != "QSOL-TIMELOCK/1":
        raise ValueError("timelock contract protocol mismatch")
    if contract.get("fail_closed") is not True:
        raise ValueError("timelock contract must fail closed")
    if contract.get("credential_policy", {}).get("store_long_lived_credentials") is not False:
        raise ValueError("timelock contract must forbid long-lived stored credentials")

    normalized_time = _normalize_time(evaluated_at)
    state = _timelock_state(contract, normalized_time)
    subject_matches = scan.get("subject") == contract.get("subject")
    gates = {
        "deadline_reached": state == "eligible",
        "source_repository_resolved": subject_matches,
        "classification_scan_valid": True,
        "no_unclassified_material": scan["gates"]["zero_unclassified_material"],
        "no_permanent_deny_material": scan["gates"]["zero_permanent_deny_material"],
        "no_redaction_required": scan["gates"]["zero_redaction_required"],
        "no_sensitive_findings": scan["gates"]["zero_sensitive_findings"],
        "no_unsafe_symlinks": scan["gates"]["zero_unsafe_symlinks"],
        "no_orphan_classification_entries": scan["gates"]["zero_orphan_classification_entries"],
        "provenance_requirements_passed": provenance_requirements_passed is True,
    }
    clearance_state = "cleared" if all(gates.values()) else "blocked"
    receipt: dict[str, Any] = {
        "protocol": CLEARANCE_PROTOCOL,
        "contract_id": contract.get("contract_id"),
        "subject": contract.get("subject"),
        "source_commit": scan.get("source_commit"),
        "evaluated_at": normalized_time,
        "timelock_state": state,
        "classification_scan_sha256": scan.get("scan_sha256"),
        "gates": gates,
        "clearance_state": clearance_state,
        "execution_authority_included": False,
        "execution_authorized": False,
        "authority": "publication-clearance-only",
        "truth_claim": False,
    }
    receipt["receipt_sha256"] = sha256_value(receipt)
    return receipt


def validate_clearance_receipt(
    receipt: dict[str, Any],
    *,
    scan: dict[str, Any] | None = None,
    contract: dict[str, Any] | None = None,
) -> None:
    if receipt.get("protocol") != CLEARANCE_PROTOCOL:
        raise ValueError("publication clearance protocol mismatch")
    if receipt.get("authority") != "publication-clearance-only":
        raise ValueError("publication clearance authority mismatch")
    if receipt.get("execution_authority_included") is not False:
        raise ValueError("publication clearance must not include execution authority")
    if receipt.get("execution_authorized") is not False:
        raise ValueError("publication clearance must not authorize execution")
    if receipt.get("truth_claim") is not False:
        raise ValueError("publication clearance must not claim semantic truth")
    gates = receipt.get("gates")
    if not isinstance(gates, dict) or not gates:
        raise ValueError("publication clearance gates missing")
    expected_state = "cleared" if all(value is True for value in gates.values()) else "blocked"
    if receipt.get("clearance_state") != expected_state:
        raise ValueError("publication clearance state does not match gates")
    if scan is not None:
        validate_scan(scan)
        if receipt.get("classification_scan_sha256") != scan.get("scan_sha256"):
            raise ValueError("publication clearance scan binding mismatch")
        if receipt.get("source_commit") != scan.get("source_commit"):
            raise ValueError("publication clearance source commit mismatch")
    if contract is not None:
        if receipt.get("contract_id") != contract.get("contract_id"):
            raise ValueError("publication clearance contract binding mismatch")
        if receipt.get("subject") != contract.get("subject"):
            raise ValueError("publication clearance subject mismatch")
        if receipt.get("timelock_state") != _timelock_state(contract, receipt["evaluated_at"]):
            raise ValueError("publication clearance timelock state mismatch")
    supplied = receipt.get("receipt_sha256")
    payload = dict(receipt)
    payload.pop("receipt_sha256", None)
    if supplied != sha256_value(payload):
        raise ValueError("publication clearance SHA-256 mismatch")


def validate_publication_safety_policy(policy: dict[str, Any], contract: dict[str, Any]) -> None:
    if policy.get("protocol") != "QSOL-PUBLICATION-SAFETY/1":
        raise ValueError("publication safety policy protocol mismatch")
    if policy.get("subject") != contract.get("subject"):
        raise ValueError("publication safety policy subject mismatch")
    if policy.get("classification_protocol") != CLASSIFICATION_PROTOCOL:
        raise ValueError("publication safety classification protocol mismatch")
    if policy.get("default_classification") != "unclassified":
        raise ValueError("publication safety policy must default to unclassified")
    if policy.get("fail_closed") is not True:
        raise ValueError("publication safety policy must fail closed")
    declared = set(policy.get("classifications", []))
    if declared != CLASSIFICATIONS:
        raise ValueError("publication safety classifications mismatch scanner")
    required_gates = {
        "zero_unclassified_material",
        "zero_permanent_deny_material",
        "zero_redaction_required",
        "zero_sensitive_findings",
        "zero_unsafe_symlinks",
        "zero_orphan_classification_entries",
    }
    if set(policy.get("gates", [])) != required_gates:
        raise ValueError("publication safety gates mismatch scanner")
    if policy.get("execution_authority") != "separate-from-clearance":
        raise ValueError("publication safety policy must separate execution authority")


def validate_recovery_instructions(
    instructions: dict[str, Any], contract: dict[str, Any]
) -> None:
    if instructions.get("protocol") != "QSOL-ORACLE-ARK-RECOVERY/1":
        raise ValueError("ARK recovery instructions protocol mismatch")
    if instructions.get("subject") != contract.get("subject"):
        raise ValueError("ARK recovery subject mismatch")
    if instructions.get("contract_id") != contract.get("contract_id"):
        raise ValueError("ARK recovery contract mismatch")
    if instructions.get("preservation_target") != "QSOLKCB/QSOL-ARK":
        raise ValueError("ARK recovery preservation target mismatch")
    if instructions.get("credential_recovery") != "never-restore-historic-credentials":
        raise ValueError("ARK recovery must forbid historic credential restoration")
    if instructions.get("executor_replaceable") is not True:
        raise ValueError("ARK recovery must preserve executor replaceability")
    steps = instructions.get("recovery_steps")
    if not isinstance(steps, list) or len(steps) < 5:
        raise ValueError("ARK recovery instructions are incomplete")


def validate_archive_plan(plan: dict[str, Any], contract: dict[str, Any]) -> None:
    if plan.get("protocol") != "QSOL-TIMELOCK-ARCHIVE/1":
        raise ValueError("archive plan protocol mismatch")
    if plan.get("subject") != contract.get("subject"):
        raise ValueError("archive plan subject mismatch")
    if plan.get("not_before") != contract.get("not_before"):
        raise ValueError("archive plan not_before mismatch")
    minimum = plan.get("minimum_independent_locations")
    locations = plan.get("location_classes")
    if not isinstance(minimum, int) or minimum < 3:
        raise ValueError("archive plan requires at least three independent locations")
    if not isinstance(locations, list) or len(locations) < minimum:
        raise ValueError("archive plan location classes are insufficient")
    classes = {item.get("class") for item in locations if isinstance(item, dict)}
    required = {"source-host", "doi-archive", "independent-content-archive"}
    if not required.issubset(classes):
        raise ValueError("archive plan missing required independent location classes")
    if any(item.get("replaceable") is not True for item in locations):
        raise ValueError("archive plan location providers must be replaceable")
    if plan.get("publication_clearance_required") is not True:
        raise ValueError("archive plan must require publication clearance")
    if plan.get("truth_authority_from_archive_presence") is not False:
        raise ValueError("archive presence must not become semantic truth authority")
