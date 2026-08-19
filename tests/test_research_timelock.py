import copy
import json
import os
import subprocess
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
TOOLS = ROOT / "tools"
if str(TOOLS) not in sys.path:
    sys.path.insert(0, str(TOOLS))

import publication_executor
import research
import timelock


class ResearchContinuationTests(unittest.TestCase):
    def _requirements(self):
        return [
            {"id":"current-state","kind":"current_state","satisfied":False,"detail":"current repository visibility has not been directly observed"},
            {"id":"identity","kind":"identity","satisfied":True,"detail":"canonical repository identity is known"},
        ]

    def test_missing_evidence_classifier_is_structural_and_deterministic(self):
        left = research.classify_missing_evidence(self._requirements())
        self.assertEqual(left, research.classify_missing_evidence(self._requirements()))
        self.assertEqual(left[0]["class"], "current-state-unverified")

    def test_primary_targets_and_searches_are_explicitly_non_evidence(self):
        targets = research.generate_primary_source_targets("QSOLKCB/QSOL-CONTEXT", research.classify_missing_evidence(self._requirements()))
        searches = research.generate_suggested_searches(targets)
        self.assertFalse(targets[0]["is_evidence"])
        self.assertEqual(targets[0]["status"], "target-only")
        self.assertFalse(searches[0]["is_evidence"])
        self.assertFalse(searches[0]["admissible_as_evidence_without_observation"])

    def test_unknown_preferred_to_plausible_invention(self):
        envelope = research.build_unknown_response(subject="QSOLKCB/QSOL-CONTEXT", question="Public?", requirements=self._requirements(), plausible_answer="Probably private")
        research.validate_unknown_response(envelope)
        self.assertIsNone(envelope["answer"])
        self.assertFalse(envelope["plausible_completion_used"])

    def test_unknown_rejects_search_laundering(self):
        envelope = research.build_unknown_response(subject="example", question="What happened?", requirements=[{"id":"primary","kind":"primary_source","satisfied":False,"detail":"no primary source"}])
        envelope["suggested_searches"][0]["is_evidence"] = True
        payload = dict(envelope); payload.pop("envelope_sha256")
        envelope["envelope_sha256"] = research.sha256_value(payload)
        with self.assertRaisesRegex(ValueError, "non-evidence"):
            research.validate_unknown_response(envelope)

    def test_unknown_rejects_primary_target_laundering(self):
        envelope = research.build_unknown_response(subject="example", question="What happened?", requirements=[{"id":"primary","kind":"primary_source","satisfied":False,"detail":"no primary source"}])
        envelope["primary_source_targets"][0]["is_evidence"] = True
        payload = dict(envelope); payload.pop("envelope_sha256")
        envelope["envelope_sha256"] = research.sha256_value(payload)
        with self.assertRaisesRegex(ValueError, "target-only non-evidence"):
            research.validate_unknown_response(envelope)

    def _conflict(self):
        return research.build_conflict_bundle(subject="repo", dimension="visibility", observations=[
            {"receipt_sha256":"1"*64,"source_locator":"https://example.invalid/a","value":{"visibility":"private"}},
            {"receipt_sha256":"2"*64,"source_locator":"https://example.invalid/b","value":{"visibility":"public"}},
        ])

    def test_conflict_bundle_preserves_incompatible_observations(self):
        bundle = self._conflict(); research.validate_conflict_bundle(bundle)
        self.assertEqual(bundle["state"], "conflict")

    def test_conflict_bundle_rejects_identical_values(self):
        with self.assertRaisesRegex(ValueError, "incompatible"):
            research.build_conflict_bundle(subject="repo", dimension="visibility", observations=[
                {"receipt_sha256":"1"*64,"source_locator":"a","value":"same"},
                {"receipt_sha256":"2"*64,"source_locator":"b","value":"same"},
            ])

    def test_conflict_validator_requires_provenance(self):
        bundle = self._conflict()
        bundle["observations"][0]["source_locator"] = ""
        payload = dict(bundle); payload.pop("bundle_sha256")
        bundle["bundle_sha256"] = research.sha256_value(payload)
        with self.assertRaisesRegex(ValueError, "provenance"):
            research.validate_conflict_bundle(bundle)

    def test_conflict_validator_recomputes_distinct_digest_list(self):
        bundle = self._conflict()
        bundle["distinct_value_sha256"] = ["0" * 64, "f" * 64]
        payload = dict(bundle); payload.pop("bundle_sha256")
        bundle["bundle_sha256"] = research.sha256_value(payload)
        with self.assertRaisesRegex(ValueError, "distinct-value"):
            research.validate_conflict_bundle(bundle)


class TimelockPublicationTests(unittest.TestCase):
    SUBJECT = "QSOLKCB/QSOL-CONTEXT"

    def _git(self, repo: Path, *args: str) -> str:
        env = dict(os.environ)
        env.update({"GIT_AUTHOR_NAME":"Test","GIT_AUTHOR_EMAIL":"test@example.invalid","GIT_COMMITTER_NAME":"Test","GIT_COMMITTER_EMAIL":"test@example.invalid"})
        proc = subprocess.run(["git", "-C", str(repo), *args], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=env)
        return proc.stdout.decode().strip()

    def _make_repo(self, temp: str, content: bytes = b"public material\n") -> tuple[Path, str]:
        repo = Path(temp) / "repo"; repo.mkdir()
        self._git(repo, "init", "-b", "main")
        (repo / "README.md").write_bytes(content)
        self._git(repo, "add", "-A"); self._git(repo, "commit", "-m", "initial")
        return repo, self._git(repo, "rev-parse", "HEAD")

    def _commit(self, repo: Path, message: str) -> str:
        self._git(repo, "add", "-A"); self._git(repo, "commit", "-m", message)
        return self._git(repo, "rev-parse", "HEAD")

    def _classification(self, source_commit: str, files):
        return {"protocol":"QSOL-PUBLICATION-CLASSIFICATION/1","subject":self.SUBJECT,"source_commit":source_commit,"entries":[
            {"path":path,"classification":level,"sha256":timelock.sha256_bytes(raw) if raw is not None else None} for path,raw,level in files
        ]}

    def _contract(self):
        return {"protocol":"QSOL-TIMELOCK/1","contract_id":"qsol-context-publication-2056","subject":self.SUBJECT,"not_before":"2056-08-18T00:00:00+09:30","intent":{"target_visibility":"public"},"fail_closed":True,"credential_policy":{"store_long_lived_credentials":False},"platform_binding":{"executor_is_replaceable":True}}

    def _clean_scan(self):
        temp = tempfile.TemporaryDirectory(); self.addCleanup(temp.cleanup)
        repo, commit = self._make_repo(temp.name)
        classification = self._classification(commit, [("README.md", b"public material\n", "public")])
        scan = timelock.scan_repository(repo, classification, subject=self.SUBJECT, source_commit=commit)
        return repo, commit, classification, scan

    def _cleared_receipt(self):
        _, _, _, scan = self._clean_scan()
        return timelock.build_clearance_receipt(scan, self._contract(), evaluated_at="2056-08-18T00:00:00+09:30", provenance_requirements_passed=True)

    def test_local_classification_scan_can_clear_fully_classified_repository(self):
        _, commit, _, report = self._clean_scan()
        timelock.validate_scan(report)
        self.assertTrue(report["publishable_from_classification"])
        self.assertEqual(report["git_scope"]["head_commit"], commit)
        self.assertGreaterEqual(report["counts"]["git_refs"], 1)

    def test_source_commit_must_match_resolved_head(self):
        with tempfile.TemporaryDirectory() as temp:
            repo, commit = self._make_repo(temp)
            wrong = "b" * 40
            classification = self._classification(wrong, [("README.md", b"public material\n", "public")])
            with self.assertRaisesRegex(ValueError, "resolved Git HEAD"):
                timelock.scan_repository(repo, classification, subject=self.SUBJECT, source_commit=wrong)

    def test_dirty_or_untracked_worktree_is_rejected(self):
        with tempfile.TemporaryDirectory() as temp:
            repo, commit = self._make_repo(temp)
            (repo / "UNTRACKED.txt").write_text("not scanned commit", encoding="utf-8")
            classification = self._classification(commit, [("README.md", b"public material\n", "public")])
            with self.assertRaisesRegex(ValueError, "clean working tree"):
                timelock.scan_repository(repo, classification, subject=self.SUBJECT, source_commit=commit)

    def test_secret_in_older_commit_blocks_publication(self):
        secret = b"github_pat_" + b"A" * 30 + b"\n"
        with tempfile.TemporaryDirectory() as temp:
            repo, _ = self._make_repo(temp, secret)
            (repo / "README.md").write_bytes(b"public material\n")
            commit = self._commit(repo, "remove secret")
            classification = self._classification(commit, [("README.md", None, "public")])
            report = timelock.scan_repository(repo, classification, subject=self.SUBJECT, source_commit=commit)
            self.assertFalse(report["gates"]["zero_sensitive_findings"])
            self.assertGreaterEqual(report["counts"]["git_commits"], 2)

    def test_secret_on_other_branch_blocks_publication(self):
        secret = b"github_pat_" + b"B" * 30 + b"\n"
        with tempfile.TemporaryDirectory() as temp:
            repo, main_commit = self._make_repo(temp)
            self._git(repo, "checkout", "-b", "secret-branch")
            (repo / "SECRET.txt").write_bytes(secret); self._commit(repo, "branch secret")
            self._git(repo, "checkout", "main")
            classification = self._classification(main_commit, [("README.md", b"public material\n", "public")])
            report = timelock.scan_repository(repo, classification, subject=self.SUBJECT, source_commit=main_commit)
            self.assertFalse(report["gates"]["zero_sensitive_findings"])
            self.assertGreaterEqual(report["counts"]["git_refs"], 2)

    def test_unclassified_material_blocks_publication(self):
        with tempfile.TemporaryDirectory() as temp:
            repo, _ = self._make_repo(temp)
            (repo / "UNREVIEWED.txt").write_text("unknown", encoding="utf-8")
            commit = self._commit(repo, "add unreviewed")
            classification = self._classification(commit, [("README.md", b"public material\n", "public")])
            report = timelock.scan_repository(repo, classification, subject=self.SUBJECT, source_commit=commit)
            self.assertFalse(report["gates"]["zero_unclassified_material"])

    def test_permanent_deny_material_blocks_publication(self):
        with tempfile.TemporaryDirectory() as temp:
            repo, commit = self._make_repo(temp)
            classification = self._classification(commit, [("README.md", b"public material\n", "permanent-deny")])
            report = timelock.scan_repository(repo, classification, subject=self.SUBJECT, source_commit=commit)
            self.assertFalse(report["gates"]["zero_permanent_deny_material"])

    def test_classification_hash_mismatch_becomes_unclassified(self):
        with tempfile.TemporaryDirectory() as temp:
            repo, commit = self._make_repo(temp)
            classification = self._classification(commit, [("README.md", b"different bytes\n", "public")])
            report = timelock.scan_repository(repo, classification, subject=self.SUBJECT, source_commit=commit)
            self.assertFalse(report["gates"]["zero_unclassified_material"])

    def test_sensitive_detector_reports_path_not_secret_value(self):
        secret = b"github_pat_" + b"C" * 30 + b"\n"
        with tempfile.TemporaryDirectory() as temp:
            repo, commit = self._make_repo(temp, secret)
            classification = self._classification(commit, [("README.md", secret, "public")])
            report = timelock.scan_repository(repo, classification, subject=self.SUBJECT, source_commit=commit)
            self.assertNotIn(secret.decode().strip(), json.dumps(report))
            self.assertFalse(report["gates"]["zero_sensitive_findings"])

    @unittest.skipUnless(hasattr(os, "symlink"), "symlinks unavailable")
    def test_symlink_in_git_history_blocks_publication(self):
        with tempfile.TemporaryDirectory() as temp:
            repo, _ = self._make_repo(temp)
            os.symlink("README.md", repo / "alias"); commit = self._commit(repo, "add link")
            classification = self._classification(commit, [("README.md", b"public material\n", "public"), ("alias", None, "public")])
            report = timelock.scan_repository(repo, classification, subject=self.SUBJECT, source_commit=commit)
            self.assertFalse(report["gates"]["zero_unsafe_symlinks"])

    def test_validate_scan_derives_counts_and_gates_from_findings(self):
        _, _, _, report = self._clean_scan()
        tampered = copy.deepcopy(report)
        tampered["records"][0]["classification"] = "permanent-deny"
        tampered["gates"] = {name: True for name in timelock.SCAN_GATE_NAMES}
        tampered["publishable_from_classification"] = True
        payload = dict(tampered); payload.pop("scan_sha256")
        tampered["scan_sha256"] = timelock.sha256_value(payload)
        with self.assertRaisesRegex(ValueError, "counts|gates"):
            timelock.validate_scan(tampered)

    def test_clearance_before_deadline_is_blocked(self):
        _, _, _, scan = self._clean_scan()
        receipt = timelock.build_clearance_receipt(scan, self._contract(), evaluated_at="2026-08-19T00:00:00Z", provenance_requirements_passed=True)
        timelock.validate_clearance_receipt(receipt, scan=scan, contract=self._contract())
        self.assertEqual(receipt["clearance_state"], "blocked")

    def test_clearance_after_deadline_separates_execution_authority(self):
        receipt = self._cleared_receipt()
        timelock.validate_clearance_receipt(receipt, contract=self._contract())
        self.assertEqual(receipt["clearance_state"], "cleared")
        self.assertFalse(receipt["execution_authorized"])

    def test_executor_rejects_tampered_clearance_before_plan(self):
        _, _, _, scan = self._clean_scan()
        blocked = timelock.build_clearance_receipt(scan, self._contract(), evaluated_at="2026-08-19T00:00:00Z", provenance_requirements_passed=True)
        blocked["clearance_state"] = "cleared"
        executor = publication_executor.get_executor("github")
        with self.assertRaises(ValueError):
            executor.plan(contract=self._contract(), clearance=blocked)

    def test_github_executor_defaults_to_dry_run(self):
        clearance = self._cleared_receipt(); contract = self._contract(); executor = publication_executor.get_executor("github")
        plan = executor.plan(contract=contract, clearance=clearance)
        publication_executor.validate_execution_plan(plan, contract=contract, clearance=clearance)
        result = executor.execute(plan)
        self.assertEqual(result["state"], "dry-run")

    def test_real_executor_rechecks_current_clock(self):
        clearance = self._cleared_receipt(); contract = self._contract(); executor = publication_executor.get_executor("github")
        plan = executor.plan(contract=contract, clearance=clearance)
        with mock.patch.object(publication_executor, "_utc_now", return_value=datetime(2026, 8, 19, tzinfo=timezone.utc)):
            with self.assertRaisesRegex(ValueError, "runtime clock"):
                executor.execute(plan, execute=True, confirm_current_authority=True, token="runtime-token")

    def test_execution_plan_endpoint_cannot_be_redirected(self):
        clearance = self._cleared_receipt(); contract = self._contract(); executor = publication_executor.get_executor("github")
        plan = executor.plan(contract=contract, clearance=clearance)
        plan["request"]["endpoint"] = "https://attacker.invalid/steal"
        with self.assertRaisesRegex(ValueError, "endpoint|does not match"):
            executor.execute(plan)

    def test_real_executor_requires_authority_and_runtime_token_after_deadline(self):
        clearance = self._cleared_receipt(); contract = self._contract(); executor = publication_executor.get_executor("github")
        plan = executor.plan(contract=contract, clearance=clearance)
        future = datetime(2056, 8, 18, 1, 0, tzinfo=timezone.utc)
        with mock.patch.object(publication_executor, "_utc_now", return_value=future):
            with self.assertRaisesRegex(ValueError, "current platform authority"):
                executor.execute(plan, execute=True, token="runtime-token")
            old = os.environ.pop("GITHUB_TOKEN", None)
            try:
                with self.assertRaisesRegex(ValueError, "GITHUB_TOKEN"):
                    executor.execute(plan, execute=True, confirm_current_authority=True, token=None)
            finally:
                if old is not None: os.environ["GITHUB_TOKEN"] = old

    def test_future_platform_interface_is_explicit_and_fail_closed(self):
        contract = json.loads((ROOT / "contracts" / "publication-executor-interface.json").read_text(encoding="utf-8"))
        publication_executor.validate_executor_interface(contract)
        with self.assertRaisesRegex(ValueError, "no executor registered"):
            publication_executor.get_executor("future-2056-platform")

    def test_ark_recovery_and_archive_plan_validate(self):
        contract = self._contract()
        recovery = json.loads((ROOT / "recovery" / "ark-timelock-executor.json").read_text(encoding="utf-8"))
        archive = json.loads((ROOT / "release" / "2056-archive-plan.json").read_text(encoding="utf-8"))
        timelock.validate_recovery_instructions(recovery, contract)
        timelock.validate_archive_plan(archive, contract)


if __name__ == "__main__":
    unittest.main()
