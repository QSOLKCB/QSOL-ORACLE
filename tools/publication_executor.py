#!/usr/bin/env python3
"""Replaceable publication executors for QSOL-TIMELOCK/1.

GitHub is merely the current concrete adapter. Plans are deterministic, dry-run by
default, rebound to the validated contract and clearance at execution time, and
credentials are runtime-only.
"""
from __future__ import annotations

import copy
import json
import os
import re
from datetime import datetime, timezone
from typing import Any, Protocol
from urllib import error, request

import timelock as publication_timelock

EXECUTION_PROTOCOL = "QSOL-PUBLICATION-EXECUTION/1"
_OWNER_RE = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?$")
_REPO_RE = re.compile(r"^[A-Za-z0-9._-]{1,100}$")


class PublicationExecutor(Protocol):
    platform: str
    def plan(self, *, contract: dict[str, Any], clearance: dict[str, Any]) -> dict[str, Any]: ...
    def execute(
        self,
        plan: dict[str, Any],
        *,
        contract: dict[str, Any] | None = None,
        clearance: dict[str, Any] | None = None,
        execute: bool = False,
        confirm_current_authority: bool = False,
        token: str | None = None,
    ) -> dict[str, Any]: ...


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _repo_parts(subject: str) -> tuple[str, str]:
    if not isinstance(subject, str) or subject.count("/") != 1:
        raise ValueError("GitHub subject must use OWNER/REPO form")
    owner, repo = subject.split("/", 1)
    if _OWNER_RE.fullmatch(owner) is None or _REPO_RE.fullmatch(repo) is None or repo in {".", ".."}:
        raise ValueError("GitHub subject contains an invalid repository identity")
    return owner, repo


def _not_before(contract: dict[str, Any]) -> datetime:
    raw = contract.get("not_before")
    if not isinstance(raw, str) or not raw:
        raise ValueError("timelock contract not_before missing")
    if raw.endswith("Z"):
        raw = raw[:-1] + "+00:00"
    parsed = datetime.fromisoformat(raw)
    if parsed.tzinfo is None:
        raise ValueError("timelock contract not_before must be timezone-aware")
    return parsed.astimezone(timezone.utc)


def _validate_clearance_for_execution(contract: dict[str, Any], clearance: dict[str, Any]) -> None:
    if contract.get("protocol") != "QSOL-TIMELOCK/1":
        raise ValueError("timelock contract protocol mismatch")
    publication_timelock.validate_clearance_receipt(clearance, contract=contract)
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

    def __init__(self) -> None:
        self._planned_contract: dict[str, Any] | None = None
        self._planned_clearance: dict[str, Any] | None = None

    def plan(self, *, contract: dict[str, Any], clearance: dict[str, Any]) -> dict[str, Any]:
        _validate_clearance_for_execution(contract, clearance)
        self._planned_contract = copy.deepcopy(contract)
        self._planned_clearance = copy.deepcopy(clearance)
        owner, repo = _repo_parts(contract["subject"])
        if contract.get("intent", {}).get("target_visibility") != "public":
            raise ValueError("GitHub executor only supports public target visibility")
        return {
            "protocol": EXECUTION_PROTOCOL,
            "executor_id": self.executor_id,
            "platform": self.platform,
            "contract_id": contract.get("contract_id"),
            "subject": contract["subject"],
            "not_before": contract.get("not_before"),
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
            "postcondition": {"repository": contract["subject"], "visibility": "public"},
            "oracle_execution_authority": False,
            "truth_claim": False,
        }

    def execute(
        self,
        plan: dict[str, Any],
        *,
        contract: dict[str, Any] | None = None,
        clearance: dict[str, Any] | None = None,
        execute: bool = False,
        confirm_current_authority: bool = False,
        token: str | None = None,
        opener=request.urlopen,
    ) -> dict[str, Any]:
        trusted_contract = copy.deepcopy(contract) if contract is not None else copy.deepcopy(self._planned_contract)
        trusted_clearance = copy.deepcopy(clearance) if clearance is not None else copy.deepcopy(self._planned_clearance)
        if trusted_contract is None or trusted_clearance is None:
            raise ValueError("execution requires the validated contract and clearance context")
        _validate_clearance_for_execution(trusted_contract, trusted_clearance)
        expected_plan = self.plan(contract=trusted_contract, clearance=trusted_clearance)
        validate_execution_plan(plan, contract=trusted_contract, clearance=trusted_clearance)
        if plan != expected_plan:
            raise ValueError("publication execution plan does not match validated contract and clearance")

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

        if _utc_now() < _not_before(trusted_contract):
            raise ValueError("real execution is locked by the current trusted runtime clock")
        if not confirm_current_authority:
            raise ValueError("real execution requires explicit current platform authority confirmation")
        runtime_token = token or os.environ.get("GITHUB_TOKEN")
        if not runtime_token:
            raise ValueError("real GitHub execution requires a runtime GITHUB_TOKEN")
        if "\n" in runtime_token or "\r" in runtime_token:
            raise ValueError("runtime GitHub token format invalid")

        owner, repo = _repo_parts(trusted_contract["subject"])
        endpoint = f"https://api.github.com/repos/{owner}/{repo}"
        if plan["request"]["endpoint"] != endpoint:
            raise ValueError("GitHub publication endpoint does not match validated subject")
        headers = {
            "Accept": "application/vnd.github+json",
            "Authorization": f"Bearer {runtime_token}",
            "X-GitHub-Api-Version": "2026-03-10",
            "User-Agent": "QSOL-ORACLE-TIMELOCK/1",
        }

        get_req = request.Request(endpoint, headers=headers, method="GET")
        before = _read_json_response(opener, get_req)
        expected_subject = trusted_contract["subject"]
        if before.get("full_name") != expected_subject:
            raise ValueError("GitHub preflight repository identity mismatch")
        if before.get("visibility") == "public" or before.get("private") is False:
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

        body = json.dumps({"visibility": "public"}, separators=(",", ":")).encode("utf-8")
        patch_headers = dict(headers)
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
            "source_commit": trusted_clearance["source_commit"],
            "clearance_receipt_sha256": trusted_clearance["receipt_sha256"],
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


def validate_execution_plan(plan: dict[str, Any], *, contract: dict[str, Any] | None = None, clearance: dict[str, Any] | None = None) -> None:
    if plan.get("protocol") != EXECUTION_PROTOCOL or plan.get("executor_id") != "github-visibility-v1" or plan.get("platform") != "github":
        raise ValueError("publication execution plan identity mismatch")
    if plan.get("dry_run") is not True or plan.get("current_platform_authority_required") is not True:
        raise ValueError("publication execution plans must be dry-run and require current authority")
    if plan.get("operator_authority_assertion_is_proof") is not False or plan.get("credential_persisted") is not False:
        raise ValueError("publication execution plan authority or credential semantics invalid")
    if plan.get("oracle_execution_authority") is not False or plan.get("truth_claim") is not False:
        raise ValueError("publication execution plan cannot grant ORACLE authority or truth")
    subject = plan.get("subject")
    owner, repo = _repo_parts(subject)
    expected_endpoint = f"https://api.github.com/repos/{owner}/{repo}"
    spec = plan.get("request")
    if not isinstance(spec, dict) or spec.get("method") != "PATCH" or spec.get("body") != {"visibility": "public"}:
        raise ValueError("GitHub publication request is invalid")
    if spec.get("endpoint") != expected_endpoint:
        raise ValueError("GitHub publication endpoint does not match plan subject")
    if plan.get("postcondition") != {"repository": subject, "visibility": "public"}:
        raise ValueError("GitHub publication postcondition does not match plan subject")
    if contract is not None:
        if plan.get("contract_id") != contract.get("contract_id") or subject != contract.get("subject") or plan.get("not_before") != contract.get("not_before"):
            raise ValueError("publication execution plan contract binding mismatch")
    if clearance is not None:
        if plan.get("source_commit") != clearance.get("source_commit") or plan.get("clearance_receipt_sha256") != clearance.get("receipt_sha256"):
            raise ValueError("publication execution plan clearance binding mismatch")


EXECUTORS: dict[str, type[GitHubPublicationExecutor]] = {"github": GitHubPublicationExecutor}


def get_executor(platform: str) -> PublicationExecutor:
    executor_type = EXECUTORS.get(platform)
    if executor_type is None:
        raise ValueError(f"no executor registered for platform {platform!r}; use the versioned future-platform executor interface")
    return executor_type()


def validate_executor_interface(contract: dict[str, Any]) -> None:
    if contract.get("protocol") != "QSOL-PUBLICATION-EXECUTOR-INTERFACE/1":
        raise ValueError("publication executor interface protocol mismatch")
    required = contract.get("required_semantics")
    if not isinstance(required, list):
        raise ValueError("publication executor interface semantics missing")
    for semantic in {"dry_run_default", "no_stored_credentials", "current_authority_required", "fail_closed", "postcondition_verification", "replaceable_adapter", "validated_clearance_recheck", "trusted_runtime_time_recheck", "subject_endpoint_binding", "plan_rederived_at_execution"}:
        if semantic not in required:
            raise ValueError(f"executor interface missing semantic: {semantic}")
    if contract.get("oracle_has_execution_authority") is not False:
        raise ValueError("executor interface must deny ORACLE execution authority")
