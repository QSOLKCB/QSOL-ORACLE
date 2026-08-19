#!/usr/bin/env python3
"""Replaceable publication executors for QSOL-TIMELOCK/1.

GitHub is merely the current concrete adapter. The interface is platform-neutral,
dry-run by default, and never persists credentials.
"""

from __future__ import annotations

import json
import os
from typing import Any, Protocol
from urllib import error, request

EXECUTION_PROTOCOL = "QSOL-PUBLICATION-EXECUTION/1"


class PublicationExecutor(Protocol):
    platform: str

    def plan(
        self,
        *,
        contract: dict[str, Any],
        clearance: dict[str, Any],
    ) -> dict[str, Any]: ...

    def execute(
        self,
        plan: dict[str, Any],
        *,
        execute: bool = False,
        confirm_current_authority: bool = False,
        token: str | None = None,
    ) -> dict[str, Any]: ...


def _repo_parts(subject: str) -> tuple[str, str]:
    if not isinstance(subject, str) or subject.count("/") != 1:
        raise ValueError("GitHub subject must use OWNER/REPO form")
    owner, repo = subject.split("/", 1)
    if not owner or not repo:
        raise ValueError("GitHub subject must use OWNER/REPO form")
    return owner, repo


def _validate_clearance_for_execution(
    contract: dict[str, Any], clearance: dict[str, Any]
) -> None:
    if contract.get("protocol") != "QSOL-TIMELOCK/1":
        raise ValueError("timelock contract protocol mismatch")
    if clearance.get("protocol") != "QSOL-PUBLICATION-CLEARANCE/1":
        raise ValueError("publication clearance protocol mismatch")
    if clearance.get("contract_id") != contract.get("contract_id"):
        raise ValueError("publication clearance contract mismatch")
    if clearance.get("subject") != contract.get("subject"):
        raise ValueError("publication clearance subject mismatch")
    if clearance.get("clearance_state") != "cleared":
        raise ValueError("publication execution requires cleared publication receipt")
    if clearance.get("timelock_state") != "eligible":
        raise ValueError("publication execution requires eligible timelock state")
    if clearance.get("execution_authorized") is not False:
        raise ValueError("publication clearance cannot itself grant execution authority")
    if contract.get("platform_binding", {}).get("executor_is_replaceable") is not True:
        raise ValueError("timelock contract must preserve executor replaceability")


class GitHubPublicationExecutor:
    platform = "github"
    executor_id = "github-visibility-v1"

    def plan(
        self,
        *,
        contract: dict[str, Any],
        clearance: dict[str, Any],
    ) -> dict[str, Any]:
        _validate_clearance_for_execution(contract, clearance)
        owner, repo = _repo_parts(contract["subject"])
        if contract.get("intent", {}).get("target_visibility") != "public":
            raise ValueError("GitHub executor only supports public target visibility")
        plan: dict[str, Any] = {
            "protocol": EXECUTION_PROTOCOL,
            "executor_id": self.executor_id,
            "platform": self.platform,
            "subject": contract["subject"],
            "source_commit": clearance["source_commit"],
            "clearance_receipt_sha256": clearance["receipt_sha256"],
            "target_visibility": "public",
            "dry_run": True,
            "current_platform_authority_required": True,
            "operator_authority_assertion_is_proof": False,
            "credential_source": "runtime-only",
            "credential_persisted": False,
            "request": {
                "method": "PATCH",
                "endpoint": f"https://api.github.com/repos/{owner}/{repo}",
                "body": {"visibility": "public"},
            },
            "postcondition": {
                "repository": contract["subject"],
                "visibility": "public",
            },
            "oracle_execution_authority": False,
            "truth_claim": False,
        }
        return plan

    def execute(
        self,
        plan: dict[str, Any],
        *,
        execute: bool = False,
        confirm_current_authority: bool = False,
        token: str | None = None,
        opener=request.urlopen,
    ) -> dict[str, Any]:
        validate_execution_plan(plan)
        if not execute:
            return {
                "protocol": EXECUTION_PROTOCOL,
                "executor_id": self.executor_id,
                "platform": self.platform,
                "state": "dry-run",
                "executed": False,
                "plan": plan,
                "credential_used": False,
                "credential_persisted": False,
                "oracle_execution_authority": False,
                "truth_claim": False,
            }

        if not confirm_current_authority:
            raise ValueError("real execution requires explicit current platform authority confirmation")
        runtime_token = token or os.environ.get("GITHUB_TOKEN")
        if not runtime_token:
            raise ValueError("real GitHub execution requires a runtime GITHUB_TOKEN")
        if "\n" in runtime_token or "\r" in runtime_token:
            raise ValueError("runtime GitHub token format invalid")

        endpoint = plan["request"]["endpoint"]
        common_headers = {
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {runtime_token}",
            "X-GitHub-Api-Version": "2026-03-10",
            "User-Agent": "QSOL-ORACLE-TIMELOCK/1",
        }

        get_req = request.Request(endpoint, headers=common_headers, method="GET")
        before = _read_json_response(opener, get_req)
        expected_subject = plan["subject"]
        if before.get("full_name") != expected_subject:
            raise ValueError("GitHub preflight repository identity mismatch")
        current_visibility = before.get("visibility")
        if current_visibility == "public" or before.get("private") is False:
            return {
                "protocol": EXECUTION_PROTOCOL,
                "executor_id": self.executor_id,
                "platform": self.platform,
                "state": "already-public",
                "executed": False,
                "subject": expected_subject,
                "platform_reported_visibility": "public",
                "credential_used": True,
                "credential_persisted": False,
                "oracle_execution_authority": False,
                "truth_claim": False,
            }

        body = json.dumps(plan["request"]["body"], separators=(",", ":")).encode("utf-8")
        patch_headers = dict(common_headers)
        patch_headers["Content-Type"] = "application/json"
        patch_req = request.Request(endpoint, data=body, headers=patch_headers, method="PATCH")
        after = _read_json_response(opener, patch_req)
        if after.get("full_name") != expected_subject:
            raise ValueError("GitHub postcondition repository identity mismatch")
        if after.get("visibility") != "public" and after.get("private") is not False:
            raise ValueError("GitHub did not report public visibility after execution")

        return {
            "protocol": EXECUTION_PROTOCOL,
            "executor_id": self.executor_id,
            "platform": self.platform,
            "state": "executed",
            "executed": True,
            "subject": expected_subject,
            "source_commit": plan["source_commit"],
            "clearance_receipt_sha256": plan["clearance_receipt_sha256"],
            "platform_reported_visibility": "public",
            "operator_asserted_current_authority": True,
            "operator_authority_assertion_is_proof": False,
            "credential_used": True,
            "credential_persisted": False,
            "oracle_execution_authority": False,
            "truth_claim": False,
        }


def _read_json_response(opener, req: request.Request) -> dict[str, Any]:
    try:
        with opener(req, timeout=30) as response:
            raw = response.read()
    except error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")[:1000]
        raise ValueError(f"platform executor HTTP error {exc.code}: {detail}") from exc
    except error.URLError as exc:
        raise ValueError(f"platform executor network error: {exc.reason}") from exc
    try:
        decoded = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("platform executor returned invalid JSON") from exc
    if not isinstance(decoded, dict):
        raise ValueError("platform executor response must be a JSON object")
    return decoded


def validate_execution_plan(plan: dict[str, Any]) -> None:
    if plan.get("protocol") != EXECUTION_PROTOCOL:
        raise ValueError("publication execution plan protocol mismatch")
    if plan.get("dry_run") is not True:
        raise ValueError("publication execution plans must default to dry-run")
    if plan.get("current_platform_authority_required") is not True:
        raise ValueError("publication execution must require current platform authority")
    if plan.get("operator_authority_assertion_is_proof") is not False:
        raise ValueError("operator authority assertion must not be treated as proof")
    if plan.get("credential_persisted") is not False:
        raise ValueError("publication executor must not persist credentials")
    if plan.get("oracle_execution_authority") is not False:
        raise ValueError("ORACLE must not gain execution authority")
    if plan.get("truth_claim") is not False:
        raise ValueError("publication execution plan must not claim semantic truth")
    request_spec = plan.get("request")
    if not isinstance(request_spec, dict):
        raise ValueError("publication execution request missing")
    if request_spec.get("method") != "PATCH":
        raise ValueError("GitHub publication plan must use PATCH")
    if request_spec.get("body") != {"visibility": "public"}:
        raise ValueError("GitHub publication plan target must be public visibility")


EXECUTORS: dict[str, type[GitHubPublicationExecutor]] = {
    "github": GitHubPublicationExecutor,
}


def get_executor(platform: str) -> PublicationExecutor:
    executor_type = EXECUTORS.get(platform)
    if executor_type is None:
        raise ValueError(
            f"no executor registered for platform {platform!r}; use the versioned future-platform executor interface"
        )
    return executor_type()


def validate_executor_interface(contract: dict[str, Any]) -> None:
    if contract.get("protocol") != "QSOL-PUBLICATION-EXECUTOR-INTERFACE/1":
        raise ValueError("publication executor interface protocol mismatch")
    required = contract.get("required_semantics")
    if not isinstance(required, list):
        raise ValueError("publication executor interface semantics missing")
    for semantic in {
        "dry_run_default",
        "no_stored_credentials",
        "current_authority_required",
        "fail_closed",
        "postcondition_verification",
        "replaceable_adapter",
    }:
        if semantic not in required:
            raise ValueError(f"executor interface missing semantic: {semantic}")
    if contract.get("oracle_has_execution_authority") is not False:
        raise ValueError("executor interface must deny ORACLE execution authority")
