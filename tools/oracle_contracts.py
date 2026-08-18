"""Manifest, timelock, and unknown-state contracts for QSOL-ORACLE."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any


def validate_manifest(manifest: dict[str, Any], root: Path, *, declared_path_keys: set[str], provenance_kinds: set[str], collector_kinds: set[str], freshness_states: set[str]) -> list[str]:
    if manifest.get("protocol") != "QSOL-ORACLE/1": raise ValueError("manifest protocol mismatch")
    if manifest.get("ledger_model") != "single-writer-append-only": raise ValueError("manifest must declare the single-writer append-only ledger model")
    files = manifest.get("files")
    if not isinstance(files, list) or not files or not all(isinstance(item, str) for item in files): raise ValueError("manifest.files must be a non-empty list of repository-relative strings")
    if len(set(files)) != len(files): raise ValueError("manifest.files must not contain duplicates")
    for relative in files:
        path = Path(relative)
        if path.is_absolute() or ".." in path.parts: raise ValueError(f"manifest contains unsafe path: {relative}")
        if not (root / path).exists(): raise ValueError(f"manifest references missing file: {relative}")
    for key in declared_path_keys:
        declared = manifest.get(key)
        if not isinstance(declared, str) or declared not in files: raise ValueError(f"manifest {key} must name a path included in manifest.files")
    if set(manifest.get("provenance_kinds", [])) != provenance_kinds: raise ValueError("manifest provenance_kinds must match validator semantics")
    if set(manifest.get("collectors", [])) != collector_kinds: raise ValueError("manifest collectors must match collector implementation")
    if set(manifest.get("freshness_states", [])) != freshness_states: raise ValueError("manifest freshness_states must match collector implementation")
    paths = manifest.get("release_fingerprint_paths")
    if not isinstance(paths, list) or not paths: raise ValueError("manifest.release_fingerprint_paths must be non-empty")
    for relative in paths:
        if relative not in files: raise ValueError(f"release fingerprint path must be listed in manifest.files: {relative}")
    return files


def timelock_state(contract: dict[str, Any], at: datetime, parse_time) -> str:
    if at.tzinfo is None: raise ValueError("evaluation time must be timezone-aware")
    return "eligible" if at >= parse_time(contract["not_before"]) else "locked"


def unknown_response(missing_evidence: list[str], suggested_searches: list[str]) -> dict[str, Any]:
    return {"protocol":"QSOL-ORACLE/1","state":"unknown","message":"Sorry, I don't have enough information to establish that reliably.","missing_evidence":missing_evidence,"suggested_searches":suggested_searches,"search_suggestions_are_evidence":False}
