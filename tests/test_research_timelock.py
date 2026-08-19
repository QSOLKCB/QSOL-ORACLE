import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

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
            {
                "id": "current-state",
                "kind": "current_state",
                "satisfied": False,
                "detail": "current repository visibility has not been directly observed",
            },
            {
                "id": "identity",
                "kind": "identity",
                "satisfied": True,
                "detail": "canonical repository identity is known",
            },
        ]

    def test_missing_evidence_classifier_is_structural_and_deterministic(self):
        left = research.classify_missing_evidence(self._requirements())
        right = research.classify_missing_evidence(self._requirements())
        self.assertEqual(left, right)
        self.assertEqual(len(left), 1)
        self.assertEqual(left[0]["class"], "current-state-unverified")

    def test_primary_targets_and_searches_are_explicitly_non_evidence(self):
        missing = research.classify_missing_evidence(self._requirements())
        targets = research.generate_primary_source_targets("QSOLKCB/QSOL-CONTEXT", missing)
        searches = research.generate_suggested_searches(targets)
        self.assertEqual(targets[0]["status"], "target-only")
        self.assertFalse(targets[0]["is_evidence"])
        self.assertFalse(searches[0]["is_evidence"])
        self.assertFalse(searches[0]["admissible_as_evidence_without_observation"])
        self.assertEqual(searches[0]["purpose"], "discovery-only")

    def test_unknown_preferred_to_plausible_invention(self):
        envelope = research.build_unknown_response(
            subject="QSOLKCB/QSOL-CONTEXT",
            question="Is the repository public right now?",
            requirements=self._requirements(),
            plausible_answer="Probably private.",
        )
        research.validate_unknown_response(envelope)
        self.assertEqual(envelope["state"], "unknown")
        self.assertIsNone(envelope["answer"])
        self.assertFalse(envelope["plausible_completion_used"])
        self.assertFalse(envelope["plausible_completion_allowed"])

    def test_unknown_rejects_search_laundering(self):
        envelope = research.build_unknown_response(
            subject="example",
            question="What happened?",
            requirements=[
                {
                    "id": "primary",
                    "kind": "primary_source",
                    "satisfied": False,
                    "detail": "no primary source",
                }
            ],
        )
        envelope["suggested_searches"][0]["is_evidence"] = True
        payload = dict(envelope)
        payload.pop("envelope_sha256")
        envelope["envelope_sha256"] = research.sha256_value(payload)
        with self.assertRaisesRegex(ValueError, "non-evidence"):
            research.validate_unknown_response(envelope)

    def test_conflict_bundle_preserves_incompatible_observations(self):
        observations = [
            {
                "receipt_sha256": "1" * 64,
                "source_locator": "https://example.invalid/a",
                "value": {"visibility": "private"},
            },
            {
                "receipt_sha256": "2" * 64,
                "source_locator": "https://example.invalid/b",
                "value": {"visibility": "public"},
            },
        ]
        bundle = research.build_conflict_bundle(
            subject="repo",
            dimension="visibility",
            observations=observations,
        )
        research.validate_conflict_bundle(bundle)
        self.assertEqual(bundle["state"], "conflict")
        self.assertEqual(bundle["resolution"], "unresolved")
        self.assertIsNone(bundle["consensus_value"])
        self.assertTrue(bundle["averaging_forbidden"])

    def test_conflict_bundle_rejects_identical_values(self):
        observations = [
            {
                "receipt_sha256": "1" * 64,
                "source_locator": "a",
                "value": "same",
            },
            {
                "receipt_sha256": "2" * 64,
                "source_locator": "b",
                "value": "same",
            },
        ]
        with self.assertRaisesRegex(ValueError, "incompatible"):
            research.build_conflict_bundle(
                subject="repo", dimension="visibility", observations=observations
            )


class TimelockPublicationTests(unittest.TestCase):
    SOURCE_COMMIT = "a" * 40
    SUBJECT = "QSOLKCB/QSOL-CONTEXT"

    def _classification(self, files):
        entries = []
        for path, raw, level in files:
            entries.append(
                {
                    "path": path,
                    "classification": level,
                    "sha256": timelock.sha256_bytes(raw),
                }
            )
        return {
            "protocol": "QSOL-PUBLICATION-CLASSIFICATION/1",
            "subject": self.SUBJECT,
            "source_commit": self.SOURCE_COMMIT,
            "entries": entries,
        }

    def _contract(self):
        return {
            "protocol": "QSOL-TIMELOCK/1",
            "contract_id": "qsol-context-publication-2056",
            "subject": self.SUBJECT,
            "not_before": "2056-08-18T00:00:00+09:30",
            "intent": {"target_visibility": "public"},
            "fail_closed": True,
            "credential_policy": {"store_long_lived_credentials": False},
            "platform_binding": {"executor_is_replaceable": True},
        }

    def _make_repo(self, temp, content=b"public material\n"):
        repo = Path(temp) / "repo"
        repo.mkdir()
        (repo / "README.md").write_bytes(content)
        return repo

    def test_local_classification_scan_can_clear_fully_classified_repository(self):
        with tempfile.TemporaryDirectory() as temp:
            repo = self._make_repo(temp)
            classification = self._classification(
                [("README.md", b"public material\n", "public")]
            )
            report = timelock.scan_repository(
                repo,
                classification,
                subject=self.SUBJECT,
                source_commit=self.SOURCE_COMMIT,
            )
            timelock.validate_scan(report)
            self.assertTrue(report["publishable_from_classification"])
            self.assertEqual(report["counts"]["unclassified"], 0)

    def test_unclassified_material_blocks_publication(self):
        with tempfile.TemporaryDirectory() as temp:
            repo = self._make_repo(temp)
            (repo / "UNREVIEWED.txt").write_text("unknown", encoding="utf-8")
            classification = self._classification(
                [("README.md", b"public material\n", "public")]
            )
            report = timelock.scan_repository(
                repo,
                classification,
                subject=self.SUBJECT,
                source_commit=self.SOURCE_COMMIT,
            )
            self.assertFalse(report["gates"]["zero_unclassified_material"])
            self.assertFalse(report["publishable_from_classification"])

    def test_permanent_deny_material_blocks_publication(self):
        with tempfile.TemporaryDirectory() as temp:
            repo = self._make_repo(temp)
            classification = self._classification(
                [("README.md", b"public material\n", "permanent-deny")]
            )
            report = timelock.scan_repository(
                repo,
                classification,
                subject=self.SUBJECT,
                source_commit=self.SOURCE_COMMIT,
            )
            self.assertFalse(report["gates"]["zero_permanent_deny_material"])
            self.assertFalse(report["publishable_from_classification"])

    def test_classification_hash_mismatch_becomes_unclassified(self):
        with tempfile.TemporaryDirectory() as temp:
            repo = self._make_repo(temp)
            classification = self._classification(
                [("README.md", b"different bytes\n", "public")]
            )
            report = timelock.scan_repository(
                repo,
                classification,
                subject=self.SUBJECT,
                source_commit=self.SOURCE_COMMIT,
            )
            self.assertEqual(report["records"][0]["classification"], "unclassified")
            self.assertFalse(report["gates"]["zero_unclassified_material"])

    def test_sensitive_detector_reports_path_not_secret_value(self):
        secret = b"github_pat_" + b"A" * 30 + b"\n"
        with tempfile.TemporaryDirectory() as temp:
            repo = self._make_repo(temp, secret)
            classification = self._classification(
                [("README.md", secret, "public")]
            )
            report = timelock.scan_repository(
                repo,
                classification,
                subject=self.SUBJECT,
                source_commit=self.SOURCE_COMMIT,
            )
            serialized = json.dumps(report)
            self.assertIn("github-token-shape", serialized)
            self.assertNotIn(secret.decode().strip(), serialized)
            self.assertFalse(report["gates"]["zero_sensitive_findings"])
            self.assertFalse(report["secret_values_in_report"])

    @unittest.skipUnless(hasattr(os, "symlink"), "symlinks unavailable")
    def test_symlink_blocks_publication(self):
        with tempfile.TemporaryDirectory() as temp:
            repo = self._make_repo(temp)
            os.symlink("README.md", repo / "alias")
            classification = self._classification(
                [("README.md", b"public material\n", "public")]
            )
            report = timelock.scan_repository(
                repo,
                classification,
                subject=self.SUBJECT,
                source_commit=self.SOURCE_COMMIT,
            )
            self.assertFalse(report["gates"]["zero_unsafe_symlinks"])

    def test_clearance_before_deadline_is_blocked(self):
        with tempfile.TemporaryDirectory() as temp:
            repo = self._make_repo(temp)
            classification = self._classification(
                [("README.md", b"public material\n", "public")]
            )
            scan = timelock.scan_repository(
                repo,
                classification,
                subject=self.SUBJECT,
                source_commit=self.SOURCE_COMMIT,
            )
            receipt = timelock.build_clearance_receipt(
                scan,
                self._contract(),
                evaluated_at="2026-08-19T00:00:00Z",
                provenance_requirements_passed=True,
            )
            timelock.validate_clearance_receipt(
                receipt, scan=scan, contract=self._contract()
            )
            self.assertEqual(receipt["timelock_state"], "locked")
            self.assertEqual(receipt["clearance_state"], "blocked")
            self.assertFalse(receipt["execution_authorized"])

    def test_clearance_after_deadline_separates_clearance_from_execution_authority(self):
        with tempfile.TemporaryDirectory() as temp:
            repo = self._make_repo(temp)
            classification = self._classification(
                [("README.md", b"public material\n", "public")]
            )
            scan = timelock.scan_repository(
                repo,
                classification,
                subject=self.SUBJECT,
                source_commit=self.SOURCE_COMMIT,
            )
            receipt = timelock.build_clearance_receipt(
                scan,
                self._contract(),
                evaluated_at="2056-08-18T00:00:00+09:30",
                provenance_requirements_passed=True,
            )
            timelock.validate_clearance_receipt(
                receipt, scan=scan, contract=self._contract()
            )
            self.assertEqual(receipt["clearance_state"], "cleared")
            self.assertFalse(receipt["execution_authority_included"])
            self.assertFalse(receipt["execution_authorized"])

    def _cleared_receipt(self):
        with tempfile.TemporaryDirectory() as temp:
            repo = self._make_repo(temp)
            classification = self._classification(
                [("README.md", b"public material\n", "public")]
            )
            scan = timelock.scan_repository(
                repo,
                classification,
                subject=self.SUBJECT,
                source_commit=self.SOURCE_COMMIT,
            )
            return timelock.build_clearance_receipt(
                scan,
                self._contract(),
                evaluated_at="2056-08-18T00:00:00+09:30",
                provenance_requirements_passed=True,
            )

    def test_github_executor_defaults_to_dry_run(self):
        clearance = self._cleared_receipt()
        executor = publication_executor.get_executor("github")
        plan = executor.plan(contract=self._contract(), clearance=clearance)
        publication_executor.validate_execution_plan(plan)
        result = executor.execute(plan)
        self.assertTrue(plan["dry_run"])
        self.assertEqual(result["state"], "dry-run")
        self.assertFalse(result["executed"])
        self.assertFalse(result["credential_persisted"])

    def test_real_executor_requires_current_authority_and_runtime_token(self):
        clearance = self._cleared_receipt()
        executor = publication_executor.get_executor("github")
        plan = executor.plan(contract=self._contract(), clearance=clearance)
        with self.assertRaisesRegex(ValueError, "current platform authority"):
            executor.execute(plan, execute=True, token="runtime-token")
        old_token = os.environ.pop("GITHUB_TOKEN", None)
        try:
            with self.assertRaisesRegex(ValueError, "GITHUB_TOKEN"):
                executor.execute(
                    plan,
                    execute=True,
                    confirm_current_authority=True,
                    token=None,
                )
        finally:
            if old_token is not None:
                os.environ["GITHUB_TOKEN"] = old_token

    def test_future_platform_interface_is_explicit_and_fail_closed(self):
        contract = json.loads(
            (ROOT / "contracts" / "publication-executor-interface.json").read_text(
                encoding="utf-8"
            )
        )
        publication_executor.validate_executor_interface(contract)
        with self.assertRaisesRegex(ValueError, "no executor registered"):
            publication_executor.get_executor("future-2056-platform")

    def test_ark_recovery_and_archive_plan_validate(self):
        contract = self._contract()
        recovery = json.loads(
            (ROOT / "recovery" / "ark-timelock-executor.json").read_text(
                encoding="utf-8"
            )
        )
        archive = json.loads(
            (ROOT / "release" / "2056-archive-plan.json").read_text(
                encoding="utf-8"
            )
        )
        timelock.validate_recovery_instructions(recovery, contract)
        timelock.validate_archive_plan(archive, contract)


if __name__ == "__main__":
    unittest.main()
