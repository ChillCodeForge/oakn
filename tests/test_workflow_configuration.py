import unittest
from pathlib import Path

from scripts.prepare_claim_validation_recovery import validate_pull_request

WORKFLOW = Path(__file__).parents[1] / ".github" / "workflows" / "validate-contribution.yml"
RECOVERY_WORKFLOW = (
    Path(__file__).parents[1] / ".github" / "workflows" / "recover-claim-validation.yml"
)
CI_WORKFLOW = Path(__file__).parents[1] / ".github" / "workflows" / "ci.yml"
EVIDENCE_WORKFLOW = Path(__file__).parents[1] / ".github" / "workflows" / "evidence-audit.yml"


class WorkflowConfigurationTests(unittest.TestCase):
    def test_ci_installs_locked_dependencies_and_pins_actions_to_release_commits(self) -> None:
        workflow = CI_WORKFLOW.read_text()

        self.assertIn("uv sync --locked --all-groups", workflow)
        self.assertNotIn("pip install", workflow)
        self.assertIn("--minimum-negative-case-pass-rate 1.0", workflow)
        for action in ("actions/checkout", "actions/setup-python", "astral-sh/setup-uv"):
            with self.subTest(action=action):
                self.assertRegex(
                    workflow,
                    rf"uses: {action}@[0-9a-f]{{40}} # v[0-9]+\.[0-9]+\.[0-9]+",
                )

    def test_evidence_audit_is_scheduled_read_only_and_uses_locked_tools(self) -> None:
        workflow = EVIDENCE_WORKFLOW.read_text()

        self.assertIn("  schedule:", workflow)
        self.assertIn("  workflow_dispatch:", workflow)
        self.assertIn("  contents: read", workflow)
        self.assertIn("uv sync --locked --all-groups", workflow)
        self.assertIn("scripts/audit_evidence.py", workflow)
        self.assertNotIn("secrets.", workflow)

    def test_validation_workflow_is_pr_only_and_keeps_required_check_name(self) -> None:
        workflow = WORKFLOW.read_text()

        self.assertIn("name: Validate pull request boundary", workflow)
        self.assertNotIn("administration:", workflow)
        self.assertIn("  pull_request_target:", workflow)
        self.assertIn("  pull_request_review:", workflow)
        self.assertNotIn("\n  push:", workflow)
        self.assertNotIn("ignore-push:", workflow)
        self.assertIn("id: author_permission", workflow)
        self.assertIn("admin|maintain|write)", workflow)
        self.assertIn("steps.author_permission.outputs.trusted != 'true'", workflow)
        self.assertIn("steps.contribution.outputs.kind == 'non-knowledge' && success()", workflow)

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

    def test_validation_workflow_supports_manual_main_dispatch_and_ready_prs(self) -> None:
        workflow = WORKFLOW.read_text()

        self.assertIn("ready_for_review", workflow)
        self.assertIn("  workflow_dispatch:", workflow)
        self.assertIn("      pr_number:", workflow)
        self.assertIn("      expected_head_sha:", workflow)
        self.assertIn('GITHUB_REF" != "refs/heads/main"', workflow)
        self.assertIn("head.sha == $head", workflow)
        self.assertIn("report-manual-validation:", workflow)
        self.assertIn("checks: write", workflow)
        self.assertIn('name: "validate"', workflow)
        self.assertIn(".app.id == 15368", workflow)
