import json
import tempfile
import unittest
from datetime import date
from pathlib import Path

from oakn.lifecycle import audit_claims


def claim(claim_id: str, summary: str, created_at: str, supersedes: str | None = None) -> dict:
    lifecycle = {"state": "active", "created_at": created_at}
    if supersedes is not None:
        lifecycle["supersedes"] = supersedes
    return {
        "id": claim_id,
        "package": {"purl": "pkg:npm/example@1.0.0", "version": "1.0.0"},
        "claim_type": "API_BEHAVIOR",
        "summary": summary,
        "lifecycle": lifecycle,
    }


class ClaimLifecycleAuditTests(unittest.TestCase):
    def test_reports_stale_claims_missing_supersedes_and_possible_conflicts(self) -> None:
        first_id = "11111111-1111-4111-8111-111111111111"
        second_id = "22222222-2222-4222-8222-222222222222"
        missing_id = "33333333-3333-4333-8333-333333333333"
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            claims = [
                claim(first_id, "example returns padded text at requested width", "2024-01-01"),
                claim(
                    second_id,
                    "example returns padded text at requested width exactly",
                    "2026-01-01",
                    missing_id,
                ),
            ]
            for item in claims:
                (root / f"{item['id']}.json").write_text(json.dumps(item))

            report = audit_claims(root, today=date(2026, 10, 16), max_age_days=365)

        self.assertEqual(
            report["stale_claims"], [{"claim_id": first_id, "created_at": "2024-01-01"}]
        )
        self.assertIn(missing_id, report["lifecycle_errors"][0]["reason"])
        self.assertEqual(report["possible_conflicts"][0]["claim_ids"], [first_id, second_id])
        self.assertIn("never modified", report["note"])

    def test_detects_supersession_cycles_and_future_dates(self) -> None:
        first_id = "11111111-1111-4111-8111-111111111111"
        second_id = "22222222-2222-4222-8222-222222222222"
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            first = claim(first_id, "first summary", "2027-01-01", second_id)
            second = claim(second_id, "second summary", "2026-01-01", first_id)
            for item in (first, second):
                (root / f"{item['id']}.json").write_text(json.dumps(item))

            report = audit_claims(root, today=date(2026, 10, 16))

        reasons = [item["reason"] for item in report["lifecycle_errors"]]
        self.assertTrue(any("future" in reason for reason in reasons))
        self.assertTrue(any("cycle" in reason for reason in reasons))

    def test_rejects_invalid_age_threshold(self) -> None:
        with (
            tempfile.TemporaryDirectory() as directory,
            self.assertRaisesRegex(ValueError, "max_age_days must be positive"),
        ):
            audit_claims(directory, max_age_days=0)

    def test_reports_unreadable_json_and_malformed_lifecycle_without_crashing(self) -> None:
        claim_id = "11111111-1111-4111-8111-111111111111"
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "broken.json").write_text("{")
            malformed = claim(claim_id, "example summary", "2026-01-01")
            malformed["lifecycle"] = []
            (root / f"{claim_id}.json").write_text(json.dumps(malformed))

            report = audit_claims(root, today=date(2026, 10, 16))

        self.assertEqual(report["claim_count"], 1)
        self.assertTrue(
            any(error.get("file") == "broken.json" for error in report["lifecycle_errors"])
        )
        self.assertTrue(
            any(
                "lifecycle must be an object" in error["reason"]
                for error in report["lifecycle_errors"]
            )
        )


if __name__ == "__main__":
    unittest.main()
