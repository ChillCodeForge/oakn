import unittest
from pathlib import Path

from scripts.prepare_claim_validation_recovery import validate_pull_request

WORKFLOW = Path(__file__).parents[1] / ".github" / "workflows" / "validate-contribution.yml"
RECOVERY_WORKFLOW = (
    Path(__file__).parents[1] / ".github" / "workflows" / "recover-claim-validation.yml"
)


class WorkflowConfigurationTests(unittest.TestCase):
    def test_validation_workflow_is_pr_only_and_keeps_required_check_name(self) -> None:
        workflow = WORKFLOW.read_text()

        self.assertIn("name: Validate pull request boundary", workflow)
        self.assertIn("  pull_request_target:", workflow)
        self.assertIn("  pull_request_review:", workflow)
        self.assertNotIn("\n  push:", workflow)
        self.assertNotIn("ignore-push:", workflow)

    def test_recovery_workflow_is_manual_main_only_and_uses_a_separate_check_writer(self) -> None:
        workflow = RECOVERY_WORKFLOW.read_text()

        self.assertIn("  workflow_dispatch:", workflow)
        self.assertNotIn("\n  pull_request:", workflow)
        self.assertNotIn("\n  pull_request_target:", workflow)
        self.assertIn('GITHUB_REF" != "refs/heads/main"', workflow)
        self.assertIn("permissions: {}", workflow)
        self.assertIn("checks: write", workflow)
        self.assertIn("needs: validate", workflow)
        self.assertIn("scripts/validate_contribution.py", workflow)
        self.assertIn('name: "validate"', workflow)
        self.assertIn("head_sha: $head", workflow)
        self.assertIn(".app.id == 15368", workflow)
        self.assertNotIn("statuses", workflow)
        self.assertNotIn("branches/main/protection", workflow)

    def test_recovery_pr_guard_rejects_stale_or_non_claim_target_metadata(self) -> None:
        pull_request = {
            "number": 40,
            "state": "open",
            "base": {
                "ref": "main",
                "sha": "a" * 40,
                "repo": {"full_name": "RoYaL69/oakn"},
            },
            "head": {
                "sha": "b" * 40,
                "repo": {"full_name": "RoYaL69/oakn"},
            },
        }

        self.assertEqual(
            validate_pull_request(pull_request, "RoYaL69/oakn", 40, "b" * 40), "a" * 40
        )
        for changed in (
            {"state": "closed"},
            {"base": {**pull_request["base"], "ref": "other"}},
            {"head": {**pull_request["head"], "sha": "c" * 40}},
        ):
            with self.subTest(changed=changed):
                invalid = {**pull_request, **changed}
                with self.assertRaises(ValueError):
                    validate_pull_request(invalid, "RoYaL69/oakn", 40, "b" * 40)

    def test_recovery_pr_guard_requires_the_expected_repository_and_sha(self) -> None:
        pull_request = {
            "number": 40,
            "state": "open",
            "base": {
                "ref": "main",
                "sha": "a" * 40,
                "repo": {"full_name": "RoYaL69/oakn"},
            },
            "head": {
                "sha": "b" * 40,
                "repo": {"full_name": "RoYaL69/oakn"},
            },
        }

        with self.assertRaises(ValueError):
            validate_pull_request(pull_request, "someone/else", 40, "b" * 40)
        with self.assertRaises(ValueError):
            validate_pull_request(pull_request, "RoYaL69/oakn", 40, "not-a-sha")
