"""Source-specific normalization for QSOL-ORACLE feed collectors."""

from __future__ import annotations

from typing import Any

def _require_mapping(payload: Any, label: str) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError(f"{label} payload must be a JSON object")
    return payload


def _github_repository(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "full_name": payload.get("full_name"),
        "default_branch": payload.get("default_branch"),
        "visibility": payload.get("visibility"),
        "private": payload.get("private"),
        "archived": payload.get("archived"),
        "fork": payload.get("fork"),
        "open_issues_count": payload.get("open_issues_count"),
        "updated_at": payload.get("updated_at"),
        "pushed_at": payload.get("pushed_at"),
    }


def _github_commit(payload: dict[str, Any]) -> dict[str, Any]:
    commit = payload.get("commit") if isinstance(payload.get("commit"), dict) else {}
    verification = commit.get("verification") if isinstance(commit.get("verification"), dict) else {}
    return {
        "sha": payload.get("sha"),
        "html_url": payload.get("html_url"),
        "commit_date": (commit.get("committer") or {}).get("date") if isinstance(commit.get("committer"), dict) else None,
        "tree_sha": (commit.get("tree") or {}).get("sha") if isinstance(commit.get("tree"), dict) else None,
        "verification": {
            "verified": verification.get("verified"),
            "reason": verification.get("reason"),
        },
    }


def _github_release(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": payload.get("id"),
        "tag_name": payload.get("tag_name"),
        "target_commitish": payload.get("target_commitish"),
        "draft": payload.get("draft"),
        "prerelease": payload.get("prerelease"),
        "published_at": payload.get("published_at"),
        "created_at": payload.get("created_at"),
        "html_url": payload.get("html_url"),
    }


def _github_tag(payload: dict[str, Any]) -> dict[str, Any]:
    target = payload.get("object") if isinstance(payload.get("object"), dict) else {}
    return {
        "ref": payload.get("ref"),
        "node_id": payload.get("node_id"),
        "target_type": target.get("type"),
        "target_sha": target.get("sha"),
        "target_url": target.get("url"),
    }


def _github_actions(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": payload.get("id"),
        "name": payload.get("name"),
        "event": payload.get("event"),
        "status": payload.get("status"),
        "conclusion": payload.get("conclusion"),
        "head_sha": payload.get("head_sha"),
        "run_attempt": payload.get("run_attempt"),
        "created_at": payload.get("created_at"),
        "updated_at": payload.get("updated_at"),
        "html_url": payload.get("html_url"),
        "validation_receipt_semantics": "workflow-reported-result-only",
    }


def _zenodo_record(payload: dict[str, Any]) -> dict[str, Any]:
    metadata = payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {}
    files = []
    for item in payload.get("files", []) if isinstance(payload.get("files"), list) else []:
        if not isinstance(item, dict):
            continue
        checksum = item.get("checksum")
        files.append(
            {
                "key": item.get("key"),
                "size": item.get("size"),
                "checksum": checksum,
            }
        )
    files.sort(key=lambda item: (item.get("key") or ""))
    return {
        "id": payload.get("id"),
        "doi": payload.get("doi") or metadata.get("doi"),
        "conceptdoi": payload.get("conceptdoi"),
        "title": metadata.get("title"),
        "version": metadata.get("version"),
        "publication_date": metadata.get("publication_date"),
        "resource_type": metadata.get("resource_type"),
        "files": files,
    }


def _qsol_substrate(payload: dict[str, Any]) -> dict[str, Any]:
    files = payload.get("files") if isinstance(payload.get("files"), list) else []
    return {
        "type": payload.get("type"),
        "schema_version": payload.get("schema_version"),
        "scope": payload.get("scope"),
        "snapshot_date": payload.get("snapshot_date"),
        "substrate_sha256": payload.get("substrate_sha256"),
        "file_count": len(files),
        "authority_semantics": "observed-substrate-fingerprint-not-oracle-semantic-authority",
    }


def _qsol_ark(payload: dict[str, Any]) -> dict[str, Any]:
    manifest = payload.get("manifest") if isinstance(payload.get("manifest"), dict) else payload
    recovery = payload.get("recovery_contract") if isinstance(payload.get("recovery_contract"), dict) else {}
    entrypoints = manifest.get("entrypoints") if isinstance(manifest.get("entrypoints"), dict) else {}
    return {
        "protocol": manifest.get("protocol"),
        "schema_version": manifest.get("schema_version"),
        "status": manifest.get("status"),
        "implemented_recovery_tiers": sorted(manifest.get("implemented_recovery_tiers", [])),
        "recovery_contract_path": entrypoints.get("recovery_contract"),
        "implemented_interface": manifest.get("implemented_interface"),
        "recovery_contract_status": recovery.get("status"),
        "recovery_stage_count": len(recovery.get("stages", [])) if isinstance(recovery.get("stages"), list) else None,
        "authority_semantics": "observed-recovery-capability-not-oracle-recovery-authority",
    }


def _qsol_int(payload: dict[str, Any]) -> dict[str, Any]:
    parents = payload.get("parents") if isinstance(payload.get("parents"), dict) else {}
    normalized_parents: dict[str, Any] = {}
    for name in sorted(parents):
        parent = parents[name]
        if isinstance(parent, dict):
            normalized_parents[name] = {
                "protocol": parent.get("protocol"),
                "repository": parent.get("repository"),
                "pinned_commit": parent.get("pinned_commit"),
            }
    live_freshness = payload.get("live_parent_freshness")
    if live_freshness in {"fresh", "current"}:
        drift_state = "no-drift-observed"
    elif live_freshness in {"stale", "drifted"}:
        drift_state = "drift-observed"
    else:
        drift_state = "untested"
    return {
        "protocol": payload.get("protocol"),
        "version": payload.get("version"),
        "scope": payload.get("scope"),
        "compatibility": payload.get("compatibility"),
        "fingerprint_sha256": payload.get("fingerprint_sha256"),
        "live_parent_freshness": live_freshness,
        "drift_state": drift_state,
        "summary": payload.get("summary"),
        "parents": normalized_parents,
        "authority_semantics": "observed-int-compatibility-not-oracle-composition-authority",
    }


NORMALIZERS = {
    "github.repository": _github_repository,
    "github.commit": _github_commit,
    "github.release": _github_release,
    "github.tag": _github_tag,
    "github.actions": _github_actions,
    "zenodo.record": _zenodo_record,
    "qsol.substrate": _qsol_substrate,
    "qsol.ark": _qsol_ark,
    "qsol.int": _qsol_int,
}


def infer_source_time(kind: str, payload: dict[str, Any]) -> str | None:
    if kind == "github.repository":
        return payload.get("pushed_at") or payload.get("updated_at")
    if kind == "github.commit":
        commit = payload.get("commit") if isinstance(payload.get("commit"), dict) else {}
        committer = commit.get("committer") if isinstance(commit.get("committer"), dict) else {}
        return committer.get("date")
    if kind == "github.release":
        return payload.get("published_at") or payload.get("created_at")
    if kind == "github.actions":
        return payload.get("updated_at") or payload.get("created_at")
    if kind == "zenodo.record":
        metadata = payload.get("metadata") if isinstance(payload.get("metadata"), dict) else {}
        return metadata.get("publication_date") or payload.get("updated")
    if kind == "qsol.substrate":
        return payload.get("snapshot_date")
    return None


