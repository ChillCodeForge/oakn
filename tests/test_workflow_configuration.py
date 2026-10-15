import unittest
from pathlib import Path

WORKFLOW = Path(__file__).parents[1] / ".github" / "workflows" / "validate-contribution.yml"


class WorkflowConfigurationTests(unittest.TestCase):
    def test_validation_workflow_is_pr_only_and_keeps_required_check_name(self) -> None:
        workflow = WORKFLOW.read_text()

        self.assertIn("name: Validate pull request boundary", workflow)
        self.assertNotIn("administration:", workflow)
        self.assertIn("  pull_request_target:", workflow)
        self.assertIn("  pull_request_review:", workflow)
        self.assertNotIn("\n  push:", workflow)
        self.assertNotIn("ignore-push:", workflow)

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
