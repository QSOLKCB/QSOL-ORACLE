"""Integrity artifacts for QSOL-ORACLE: checkpoints, signatures, and releases."""
from __future__ import annotations

import base64
import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any


def canonical_bytes(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


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


def _is_sha256(value: Any) -> bool:
    return isinstance(value, str) and len(value) == 64 and all(c in "0123456789abcdef" for c in value)


def _load_events(path: Path) -> list[dict[str, Any]]:
    events = []
    for line_no, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not raw.strip():
            continue
        event = json.loads(raw)
        if not isinstance(event, dict):
            raise ValueError(f"ledger line {line_no}: expected JSON object")
        events.append(event)
    if not events:
        raise ValueError("ledger must contain at least one event")
    return events


def build_ledger_checkpoint(path: Path) -> dict[str, Any]:
    events = _load_events(path)
    raw = path.read_bytes()
    checkpoint: dict[str, Any] = {
        "protocol": "QSOL-ORACLE-CHECKPOINT/1",
        "ledger": path.name if path.parent.name == "ledger" else str(path),
        "event_count": len(events),
        "ledger_head": events[-1]["event_hash"],
        "ledger_bytes": len(raw),
        "ledger_sha256": sha256_bytes(raw),
        "event_hashes_sha256": sha256_value([event["event_hash"] for event in events]),
        "authority": "integrity-only",
        "truth_claim": False,
    }
    checkpoint["checkpoint_sha256"] = sha256_value(checkpoint)
    return checkpoint


def validate_ledger_checkpoint(checkpoint: dict[str, Any], path: Path) -> None:
    if checkpoint.get("protocol") != "QSOL-ORACLE-CHECKPOINT/1":
        raise ValueError("ledger checkpoint protocol mismatch")
    if checkpoint.get("authority") != "integrity-only" or checkpoint.get("truth_claim") is not False:
        raise ValueError("ledger checkpoint must remain integrity-only and non-truth-authoritative")
    if checkpoint != build_ledger_checkpoint(path):
        raise ValueError("ledger checkpoint does not match canonical ledger")


def detached_signature_envelope(*, object_kind: str, object_id: str, object_sha256: str,
                                algorithm: str, key_id: str, signature_bytes: bytes,
                                created_at: str) -> dict[str, Any]:
    if not _is_sha256(object_sha256):
        raise ValueError("signed object SHA-256 must be lowercase hexadecimal")
    parse_time(created_at)
    if not object_kind or not object_id or not algorithm or not key_id or not signature_bytes:
        raise ValueError("detached signature metadata and signature bytes must be non-empty")
    envelope: dict[str, Any] = {
        "protocol": "QSOL-ORACLE-SIGNATURE/1",
        "object": {"kind": object_kind, "id": object_id, "sha256": object_sha256},
        "signature": {
            "algorithm": algorithm,
            "key_id": key_id,
            "encoding": "base64",
            "value": base64.b64encode(signature_bytes).decode("ascii"),
            "signature_sha256": sha256_bytes(signature_bytes),
        },
        "created_at": created_at,
        "authority": "authentication-evidence-only",
        "cryptographic_verification": "external",
        "truth_claim": False,
    }
    envelope["envelope_sha256"] = sha256_value(envelope)
    return envelope


def validate_detached_signature_envelope(envelope: dict[str, Any], object_bytes: bytes | None = None) -> None:
    if envelope.get("protocol") != "QSOL-ORACLE-SIGNATURE/1":
        raise ValueError("detached signature protocol mismatch")
    if envelope.get("authority") != "authentication-evidence-only":
        raise ValueError("detached signatures must remain authentication-evidence-only")
    if envelope.get("truth_claim") is not False:
        raise ValueError("a detached signature must not be equated with semantic truth")
    if envelope.get("cryptographic_verification") != "external":
        raise ValueError("reference implementation expects external cryptographic verification")
    parse_time(envelope["created_at"])
    obj, signature = envelope.get("object"), envelope.get("signature")
    if not isinstance(obj, dict) or not _is_sha256(obj.get("sha256")):
        raise ValueError("detached signature object binding invalid")
    if not isinstance(signature, dict) or signature.get("encoding") != "base64":
        raise ValueError("detached signature encoding invalid")
    try:
        signature_bytes = base64.b64decode(signature.get("value", ""), validate=True)
    except (ValueError, TypeError) as exc:
        raise ValueError("detached signature base64 invalid") from exc
    if not signature_bytes or signature.get("signature_sha256") != sha256_bytes(signature_bytes):
        raise ValueError("detached signature byte digest mismatch")
    if object_bytes is not None and obj["sha256"] != sha256_bytes(object_bytes):
        raise ValueError("detached signature object digest does not match supplied object bytes")
    supplied = envelope.get("envelope_sha256")
    payload = dict(envelope)
    payload.pop("envelope_sha256", None)
    if supplied != sha256_value(payload):
        raise ValueError("detached signature envelope SHA-256 mismatch")


def build_release_fingerprint(root: Path, manifest: dict[str, Any]) -> dict[str, Any]:
    paths = manifest.get("release_fingerprint_paths")
    if not isinstance(paths, list) or not paths or not all(isinstance(item, str) for item in paths):
        raise ValueError("manifest.release_fingerprint_paths must be a non-empty string list")
    if len(set(paths)) != len(paths):
        raise ValueError("manifest.release_fingerprint_paths must not contain duplicates")
    if manifest.get("release_fingerprint") in paths:
        raise ValueError("release fingerprint must not include itself")
    records = []
    for relative in sorted(paths):
        path = Path(relative)
        if path.is_absolute() or ".." in path.parts:
            raise ValueError(f"unsafe release fingerprint path: {relative}")
        absolute = root / path
        if not absolute.is_file():
            raise ValueError(f"release fingerprint input missing: {relative}")
        raw = absolute.read_bytes()
        records.append({"path": relative, "bytes": len(raw), "sha256": sha256_bytes(raw)})
    checkpoint = build_ledger_checkpoint(root / manifest["ledger"])
    fingerprint: dict[str, Any] = {
        "protocol": "QSOL-ORACLE-RELEASE/1",
        "scope": manifest.get("release_fingerprint_scope", "oracle-release-identity"),
        "files": records,
        "files_sha256": sha256_value(records),
        "ledger_checkpoint_sha256": checkpoint["checkpoint_sha256"],
        "authority": "integrity-only",
        "truth_claim": False,
    }
    fingerprint["release_fingerprint_sha256"] = sha256_value(fingerprint)
    return fingerprint


def validate_release_fingerprint(fingerprint: dict[str, Any], root: Path, manifest: dict[str, Any]) -> None:
    if fingerprint.get("protocol") != "QSOL-ORACLE-RELEASE/1":
        raise ValueError("release fingerprint protocol mismatch")
    if fingerprint.get("authority") != "integrity-only" or fingerprint.get("truth_claim") is not False:
        raise ValueError("release fingerprint must remain integrity-only")
    if fingerprint != build_release_fingerprint(root, manifest):
        raise ValueError("release fingerprint does not match manifest-declared files")
