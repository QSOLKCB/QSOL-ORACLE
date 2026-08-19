#!/usr/bin/env python3
"""Fail-closed publication-clearance tooling for QSOL-TIMELOCK/1.

The scanner binds a classification manifest to an exact, clean, non-shallow Git
checkout and inspects every blob reachable from every local Git ref.  It never
uploads candidate bytes and never includes suspected secret values in reports.
"""
from __future__ import annotations

import fnmatch
import hashlib
import json
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

SCAN_PROTOCOL = "QSOL-PUBLICATION-SCAN/1"
CLASSIFICATION_PROTOCOL = "QSOL-PUBLICATION-CLASSIFICATION/1"
CLEARANCE_PROTOCOL = "QSOL-PUBLICATION-CLEARANCE/1"

CLASSIFICATIONS = {"public", "redact-before-publication", "permanent-deny"}
SCAN_GATE_NAMES = {
    "zero_unclassified_material",
    "zero_permanent_deny_material",
    "zero_redaction_required",
    "zero_sensitive_findings",
    "zero_unsafe_symlinks",
    "zero_orphan_classification_entries",
    "source_commit_matches_head",
    "working_tree_clean",
    "complete_git_history",
    "all_git_refs_scanned",
}

FILENAME_DETECTORS = {
    "sensitive-filename-dotenv": [".env", ".env.*"],
    "sensitive-filename-private-key": ["id_rsa", "id_ed25519", "*.key"],
}
CONTENT_DETECTORS: tuple[tuple[str, re.Pattern[bytes]], ...] = (
    ("private-key-material", re.compile(br"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----")),
    ("github-token-shape", re.compile(br"(?:github_pat_[A-Za-z0-9_]{20,}|gh[pousr]_[A-Za-z0-9]{20,})")),
)


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_value(value: Any) -> str:
    return sha256_bytes(canonical_bytes(value))


def _is_sha256(value: Any) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(c in "0123456789abcdef" for c in value)


def _is_commit_id(value: Any) -> bool:
    return isinstance(value, str) and len(value) in {40, 64} and all(c in "0123456789abcdef" for c in value)


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
    raw = contract.get("not_before")
    if not isinstance(raw, str):
        raise ValueError("timelock contract not_before missing")
    not_before = datetime.fromisoformat(_normalize_time(raw).replace("Z", "+00:00"))
    return "eligible" if now >= not_before else "locked"


def _safe_relative(path_value: str) -> str:
    if not isinstance(path_value, str) or not path_value:
        raise ValueError("classification path must be a non-empty string")
    path = Path(path_value)
    if path.is_absolute() or ".." in path.parts:
        raise ValueError(f"unsafe classification path: {path_value}")
    normalized = path.as_posix().removeprefix("./")
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
        if expected is not None and not _is_sha256(expected):
            raise ValueError(f"classification entry {path}: sha256 invalid")
        reason = entry.get("reason")
        if reason is not None and not isinstance(reason, str):
            raise ValueError(f"classification entry {path}: reason must be a string")
        by_path[path] = {"classification": level, "sha256": expected, "reason": reason}
    return by_path


def _filename_findings(relative: str) -> list[str]:
    name = Path(relative).name
    return [detector for detector, patterns in FILENAME_DETECTORS.items() if any(fnmatch.fnmatch(name, pattern) for pattern in patterns)]


def _content_findings(raw: bytes) -> list[str]:
    return [detector for detector, pattern in CONTENT_DETECTORS if pattern.search(raw)]


def _git(repo_root: Path, *args: str, check: bool = True) -> bytes:
    try:
        proc = subprocess.run(
            ["git", "-C", str(repo_root), *args],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
        )
    except OSError as exc:
        raise ValueError("git executable is unavailable for publication scan") from exc
    if check and proc.returncode != 0:
        raise ValueError(f"git publication scan command failed: {' '.join(args)}")
    return proc.stdout


def _git_text(repo_root: Path, *args: str) -> str:
    try:
        return _git(repo_root, *args).decode("utf-8").strip()
    except UnicodeDecodeError as exc:
        raise ValueError("git publication scan returned non-UTF-8 metadata") from exc


def _resolve_git_scope(repo_root: Path, source_commit: str) -> dict[str, Any]:
    top = Path(_git_text(repo_root, "rev-parse", "--show-toplevel")).resolve()
    if top != repo_root:
        raise ValueError("repository root must be the Git worktree root")
    head = _git_text(repo_root, "rev-parse", "HEAD")
    if head != source_commit:
        raise ValueError("source_commit must equal the resolved Git HEAD")
    if _git_text(repo_root, "cat-file", "-t", source_commit) != "commit":
        raise ValueError("source_commit must resolve to a Git commit")
    source_tree = _git_text(repo_root, "rev-parse", f"{source_commit}^{{tree}}")
    status = _git(repo_root, "status", "--porcelain=v1", "--untracked-files=all")
    if status:
        raise ValueError("publication scan requires a clean working tree with no untracked files")
    shallow = _git_text(repo_root, "rev-parse", "--is-shallow-repository")
    if shallow != "false":
        raise ValueError("publication scan requires complete non-shallow Git history")

    refs = [line for line in _git_text(repo_root, "for-each-ref", "--format=%(refname)").splitlines() if line]
    if not refs:
        raise ValueError("publication scan requires at least one local Git ref")
    ref_tips: list[dict[str, str]] = []
    unsupported: list[str] = []
    commit_tips: list[str] = []
    for ref in sorted(refs):
        raw = _git(repo_root, "rev-parse", f"{ref}^{{commit}}", check=False)
        try:
            commit = raw.decode("ascii").strip()
        except UnicodeDecodeError:
            commit = ""
        if not _is_commit_id(commit):
            unsupported.append(ref)
            continue
        ref_tips.append({"ref": ref, "commit": commit})
        commit_tips.append(commit)
    if unsupported:
        raise ValueError("publication scan found Git refs that do not resolve to commits")
    if source_commit not in commit_tips:
        commit_tips.append(source_commit)
    commits = [line for line in _git_text(repo_root, "rev-list", "--topo-order", "--reverse", *sorted(set(commit_tips))).splitlines() if line]
    if source_commit not in commits:
        raise ValueError("source_commit is not reachable from scanned Git history")
    return {
        "head_commit": head,
        "source_tree": source_tree,
        "working_tree_clean": True,
        "is_shallow_repository": False,
        "ref_tips": ref_tips,
        "ref_tips_sha256": sha256_value(ref_tips),
        "commit_count": len(commits),
        "commits": commits,
    }


def scan_repository(repo_root: Path, classification: dict[str, Any], *, subject: str, source_commit: str) -> dict[str, Any]:
    """Scan every blob reachable from every local Git ref and fail closed."""
    repo_root = Path(repo_root).resolve()
    if not repo_root.is_dir():
        raise ValueError("repository root must be an existing directory")
    if not isinstance(subject, str) or not subject.strip():
        raise ValueError("subject must be a non-empty string")
    subject = subject.strip()
    if classification.get("subject") != subject:
        raise ValueError("classification manifest subject mismatch")
    if not _is_commit_id(source_commit):
        raise ValueError("source_commit must be a 40- or 64-hex commit id")
    if classification.get("source_commit") != source_commit:
        raise ValueError("classification manifest source_commit mismatch")

    by_path = _load_classification(classification)
    git_scope = _resolve_git_scope(repo_root, source_commit)
    records: list[dict[str, Any]] = []
    sensitive: list[dict[str, str]] = []
    symlinks: set[str] = set()
    present_paths: set[str] = set()
    seen_variants: set[tuple[str, str, str]] = set()
    seen_sensitive: set[tuple[str, str, str]] = set()

    for commit in git_scope["commits"]:
        tree = _git(repo_root, "ls-tree", "-rz", "--full-tree", commit)
        for entry in tree.split(b"\0"):
            if not entry:
                continue
            try:
                meta, raw_path = entry.split(b"\t", 1)
                mode, obj_type, oid = meta.decode("ascii").split(" ", 2)
                relative = raw_path.decode("utf-8")
            except (ValueError, UnicodeDecodeError) as exc:
                raise ValueError("Git tree entry is malformed") from exc
            relative = _safe_relative(relative)
            present_paths.add(relative)
            kind = "symlink" if mode == "120000" else ("gitlink" if mode == "160000" else "file")
            variant_key = (relative, oid, kind)
            if variant_key in seen_variants:
                continue
            seen_variants.add(variant_key)

            if obj_type == "blob":
                raw = _git(repo_root, "cat-file", "blob", oid)
                digest = sha256_bytes(raw)
                byte_count: int | None = len(raw)
            elif kind == "gitlink" and obj_type == "commit":
                raw = b""
                digest = None
                byte_count = None
            else:
                raise ValueError("publication scan encountered unsupported Git tree object")

            declared = by_path.get(relative)
            if declared is None:
                level, hash_matches = "unclassified", False
            else:
                expected = declared.get("sha256")
                hash_matches = expected is None or (digest is not None and expected == digest)
                level = declared["classification"] if hash_matches else "unclassified"

            records.append({
                "path": relative,
                "kind": kind,
                "object_id": oid,
                "bytes": byte_count,
                "sha256": digest,
                "classification": level,
                "classification_hash_matches": hash_matches,
                "first_seen_commit": commit,
            })
            if kind == "symlink":
                symlinks.add(relative)

            if obj_type == "blob":
                for detector in sorted(set(_filename_findings(relative) + _content_findings(raw))):
                    finding_key = (relative, oid, detector)
                    if finding_key not in seen_sensitive:
                        seen_sensitive.add(finding_key)
                        sensitive.append({"path": relative, "object_id": oid, "detector": detector})

    records.sort(key=lambda item: (item["path"], item["object_id"], item["kind"]))
    sensitive.sort(key=lambda item: (item["path"], item["object_id"], item["detector"]))
    orphan_entries = sorted(set(by_path).difference(present_paths))
    counts = _derive_counts(records, sensitive, sorted(symlinks), orphan_entries, git_scope)
    gates = _derive_gates(counts, git_scope)
    report: dict[str, Any] = {
        "protocol": SCAN_PROTOCOL,
        "subject": subject,
        "source_commit": source_commit,
        "classification_manifest_sha256": sha256_value(classification),
        "git_scope": {k: v for k, v in git_scope.items() if k != "commits"},
        "records": records,
        "sensitive_findings": sensitive,
        "unsafe_symlinks": sorted(symlinks),
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


def _derive_counts(records: list[dict[str, Any]], sensitive: list[dict[str, Any]], symlinks: list[str], orphan_entries: list[str], git_scope: dict[str, Any]) -> dict[str, int]:
    return {
        "files": sum(1 for item in records if item.get("kind") == "file"),
        "gitlinks": sum(1 for item in records if item.get("kind") == "gitlink"),
        "symlinks": len(symlinks),
        "public": sum(1 for item in records if item.get("classification") == "public"),
        "redact_before_publication": sum(1 for item in records if item.get("classification") == "redact-before-publication"),
        "permanent_deny": sum(1 for item in records if item.get("classification") == "permanent-deny"),
        "unclassified": sum(1 for item in records if item.get("classification") == "unclassified"),
        "sensitive_findings": len(sensitive),
        "orphan_classification_entries": len(orphan_entries),
        "git_refs": len(git_scope.get("ref_tips", [])),
        "git_commits": int(git_scope.get("commit_count", 0)),
    }


def _derive_gates(counts: dict[str, int], git_scope: dict[str, Any]) -> dict[str, bool]:
    return {
        "zero_unclassified_material": counts["unclassified"] == 0,
        "zero_permanent_deny_material": counts["permanent_deny"] == 0,
        "zero_redaction_required": counts["redact_before_publication"] == 0,
        "zero_sensitive_findings": counts["sensitive_findings"] == 0,
        "zero_unsafe_symlinks": counts["symlinks"] == 0,
        "zero_orphan_classification_entries": counts["orphan_classification_entries"] == 0,
        "source_commit_matches_head": git_scope.get("head_commit") is not None,
        "working_tree_clean": git_scope.get("working_tree_clean") is True,
        "complete_git_history": git_scope.get("is_shallow_repository") is False,
        "all_git_refs_scanned": counts["git_refs"] > 0 and counts["git_commits"] > 0,
    }


def validate_scan(report: dict[str, Any]) -> None:
    if report.get("protocol") != SCAN_PROTOCOL:
        raise ValueError("publication scan protocol mismatch")
    if report.get("secret_values_in_report") is not False or report.get("truth_claim") is not False:
        raise ValueError("publication scan safety semantics invalid")
    if report.get("authority") != "local-publication-safety-scan-only":
        raise ValueError("publication scan authority mismatch")
    if not _is_commit_id(report.get("source_commit")):
        raise ValueError("publication scan source_commit invalid")
    git_scope = report.get("git_scope")
    if not isinstance(git_scope, dict):
        raise ValueError("publication scan Git scope missing")
    if git_scope.get("head_commit") != report.get("source_commit"):
        raise ValueError("publication scan source commit is not bound to Git HEAD")
    if not isinstance(git_scope.get("source_tree"), str) or not git_scope["source_tree"]:
        raise ValueError("publication scan source tree missing")
    refs = git_scope.get("ref_tips")
    if not isinstance(refs, list) or not refs:
        raise ValueError("publication scan Git refs missing")
    if git_scope.get("ref_tips_sha256") != sha256_value(refs):
        raise ValueError("publication scan Git ref digest mismatch")
    if git_scope.get("working_tree_clean") is not True or git_scope.get("is_shallow_repository") is not False:
        raise ValueError("publication scan Git checkout is not publication-safe")
    if type(git_scope.get("commit_count")) is not int or git_scope["commit_count"] < 1:
        raise ValueError("publication scan Git commit count invalid")

    records = report.get("records")
    sensitive = report.get("sensitive_findings")
    symlinks = report.get("unsafe_symlinks")
    orphans = report.get("orphan_classification_entries")
    if not isinstance(records, list) or not isinstance(sensitive, list) or not isinstance(symlinks, list) or not isinstance(orphans, list):
        raise ValueError("publication scan findings malformed")
    seen: set[tuple[str, str, str]] = set()
    for item in records:
        if not isinstance(item, dict):
            raise ValueError("publication scan record malformed")
        path = _safe_relative(item.get("path"))
        kind = item.get("kind")
        oid = item.get("object_id")
        if kind not in {"file", "symlink", "gitlink"} or not isinstance(oid, str) or not oid:
            raise ValueError("publication scan record identity malformed")
        key = (path, oid, kind)
        if key in seen:
            raise ValueError("publication scan contains duplicate record")
        seen.add(key)
        level = item.get("classification")
        if level not in CLASSIFICATIONS | {"unclassified"}:
            raise ValueError("publication scan record classification malformed")
        digest = item.get("sha256")
        if kind != "gitlink" and not _is_sha256(digest):
            raise ValueError("publication scan record SHA-256 malformed")
        if kind == "gitlink" and digest is not None:
            raise ValueError("publication scan gitlink digest must be null")
        if type(item.get("classification_hash_matches")) is not bool:
            raise ValueError("publication scan classification binding malformed")
    for finding in sensitive:
        if not isinstance(finding, dict) or set(finding) != {"path", "object_id", "detector"}:
            raise ValueError("publication scan sensitive finding malformed")
        _safe_relative(finding["path"])
        if not isinstance(finding["object_id"], str) or not isinstance(finding["detector"], str):
            raise ValueError("publication scan sensitive finding malformed")
    for path in symlinks + orphans:
        _safe_relative(path)

    expected_counts = _derive_counts(records, sensitive, symlinks, orphans, git_scope)
    if report.get("counts") != expected_counts:
        raise ValueError("publication scan counts do not match reported findings")
    expected_gates = _derive_gates(expected_counts, git_scope)
    if set(expected_gates) != SCAN_GATE_NAMES or report.get("gates") != expected_gates:
        raise ValueError("publication scan gates do not match reported findings")
    if report.get("publishable_from_classification") is not all(expected_gates.values()):
        raise ValueError("publication scan publishability does not match derived gates")
    supplied = report.get("scan_sha256")
    payload = dict(report)
    payload.pop("scan_sha256", None)
    if supplied != sha256_value(payload):
        raise ValueError("publication scan SHA-256 mismatch")


def build_clearance_receipt(scan: dict[str, Any], contract: dict[str, Any], *, evaluated_at: str, provenance_requirements_passed: bool) -> dict[str, Any]:
    validate_scan(scan)
    if contract.get("protocol") != "QSOL-TIMELOCK/1" or contract.get("fail_closed") is not True:
        raise ValueError("timelock contract invalid")
    if contract.get("credential_policy", {}).get("store_long_lived_credentials") is not False:
        raise ValueError("timelock contract must forbid long-lived stored credentials")
    normalized = _normalize_time(evaluated_at)
    state = _timelock_state(contract, normalized)
    scan_gates = scan["gates"]
    gates = {
        "deadline_reached": state == "eligible",
        "source_repository_resolved": scan.get("subject") == contract.get("subject"),
        "classification_scan_valid": True,
        **{name: scan_gates[name] for name in sorted(SCAN_GATE_NAMES)},
        "provenance_requirements_passed": provenance_requirements_passed is True,
    }
    receipt: dict[str, Any] = {
        "protocol": CLEARANCE_PROTOCOL,
        "contract_id": contract.get("contract_id"),
        "subject": contract.get("subject"),
        "source_commit": scan.get("source_commit"),
        "evaluated_at": normalized,
        "timelock_state": state,
        "classification_scan_sha256": scan.get("scan_sha256"),
        "gates": gates,
        "clearance_state": "cleared" if all(gates.values()) else "blocked",
        "execution_authority_included": False,
        "execution_authorized": False,
        "authority": "publication-clearance-only",
        "truth_claim": False,
    }
    receipt["receipt_sha256"] = sha256_value(receipt)
    return receipt


def validate_clearance_receipt(receipt: dict[str, Any], *, scan: dict[str, Any] | None = None, contract: dict[str, Any] | None = None) -> None:
    if receipt.get("protocol") != CLEARANCE_PROTOCOL or receipt.get("authority") != "publication-clearance-only":
        raise ValueError("publication clearance protocol or authority mismatch")
    if receipt.get("execution_authority_included") is not False or receipt.get("execution_authorized") is not False:
        raise ValueError("publication clearance must not grant execution authority")
    if receipt.get("truth_claim") is not False:
        raise ValueError("publication clearance must not claim semantic truth")
    if not _is_commit_id(receipt.get("source_commit")) or not _is_sha256(receipt.get("classification_scan_sha256")):
        raise ValueError("publication clearance bindings malformed")
    gates = receipt.get("gates")
    if not isinstance(gates, dict) or not gates or not all(type(v) is bool for v in gates.values()):
        raise ValueError("publication clearance gates missing")
    expected_state = "cleared" if all(gates.values()) else "blocked"
    if receipt.get("clearance_state") != expected_state:
        raise ValueError("publication clearance state does not match gates")
    if scan is not None:
        validate_scan(scan)
        if receipt.get("classification_scan_sha256") != scan.get("scan_sha256") or receipt.get("source_commit") != scan.get("source_commit"):
            raise ValueError("publication clearance scan binding mismatch")
        expected_scan_gates = {name: scan["gates"][name] for name in SCAN_GATE_NAMES}
        for name, value in expected_scan_gates.items():
            if gates.get(name) is not value:
                raise ValueError("publication clearance gates do not match validated scan")
    if contract is not None:
        if receipt.get("contract_id") != contract.get("contract_id") or receipt.get("subject") != contract.get("subject"):
            raise ValueError("publication clearance contract binding mismatch")
        if receipt.get("timelock_state") != _timelock_state(contract, receipt.get("evaluated_at")):
            raise ValueError("publication clearance timelock state mismatch")
    supplied = receipt.get("receipt_sha256")
    payload = dict(receipt)
    payload.pop("receipt_sha256", None)
    if supplied != sha256_value(payload):
        raise ValueError("publication clearance SHA-256 mismatch")


def validate_publication_safety_policy(policy: dict[str, Any], contract: dict[str, Any]) -> None:
    if policy.get("protocol") != "QSOL-PUBLICATION-SAFETY/1" or policy.get("subject") != contract.get("subject"):
        raise ValueError("publication safety policy binding mismatch")
    if policy.get("classification_protocol") != CLASSIFICATION_PROTOCOL or policy.get("default_classification") != "unclassified" or policy.get("fail_closed") is not True:
        raise ValueError("publication safety policy classification semantics invalid")
    if set(policy.get("classifications", [])) != CLASSIFICATIONS:
        raise ValueError("publication safety classifications mismatch scanner")
    if set(policy.get("gates", [])) != SCAN_GATE_NAMES:
        raise ValueError("publication safety gates mismatch scanner")
    if policy.get("git_ref_scope") != "all-local-refs-complete-history-clean-head-bound":
        raise ValueError("publication safety policy must require complete Git ref coverage")
    if policy.get("execution_authority") != "separate-from-clearance":
        raise ValueError("publication safety policy must separate execution authority")


def validate_recovery_instructions(instructions: dict[str, Any], contract: dict[str, Any]) -> None:
    if instructions.get("protocol") != "QSOL-ORACLE-ARK-RECOVERY/1" or instructions.get("subject") != contract.get("subject") or instructions.get("contract_id") != contract.get("contract_id"):
        raise ValueError("ARK recovery instructions binding mismatch")
    if instructions.get("preservation_target") != "QSOLKCB/QSOL-ARK" or instructions.get("credential_recovery") != "never-restore-historic-credentials" or instructions.get("executor_replaceable") is not True:
        raise ValueError("ARK recovery safety semantics invalid")
    steps = instructions.get("recovery_steps")
    if not isinstance(steps, list) or len(steps) < 5:
        raise ValueError("ARK recovery instructions are incomplete")


def validate_archive_plan(plan: dict[str, Any], contract: dict[str, Any]) -> None:
    if plan.get("protocol") != "QSOL-TIMELOCK-ARCHIVE/1" or plan.get("subject") != contract.get("subject") or plan.get("not_before") != contract.get("not_before"):
        raise ValueError("archive plan binding mismatch")
    minimum, locations = plan.get("minimum_independent_locations"), plan.get("location_classes")
    if not isinstance(minimum, int) or minimum < 3 or not isinstance(locations, list) or len(locations) < minimum:
        raise ValueError("archive plan location classes are insufficient")
    classes = {item.get("class") for item in locations if isinstance(item, dict)}
    if not {"source-host", "doi-archive", "independent-content-archive"}.issubset(classes):
        raise ValueError("archive plan missing required independent location classes")
    if any(not isinstance(item, dict) or item.get("replaceable") is not True for item in locations):
        raise ValueError("archive plan location providers must be replaceable")
    if plan.get("publication_clearance_required") is not True or plan.get("truth_authority_from_archive_presence") is not False:
        raise ValueError("archive plan safety semantics invalid")
