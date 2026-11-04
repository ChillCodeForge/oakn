import json
import tempfile
import unittest
from pathlib import Path
from typing import Any

from oakn.evidence_audit import audit_evidence
from oakn.validation import ValidationError


class RejectingValidator:
    def validate(self, claim: dict[str, Any], verify_source_binding: bool = True) -> None:
        raise ValidationError("invalid claim")


class EvidenceAuditTests(unittest.TestCase):
    def test_reports_each_invalid_claim_without_stopping_the_audit(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            claims = Path(directory)
            (claims / "first.json").write_text(json.dumps({"id": "first"}))
            (claims / "second.json").write_text("{")

            report = audit_evidence(claims, RejectingValidator())

        self.assertEqual(report["claim_count"], 2)
        self.assertEqual(report["verified_count"], 0)
        self.assertEqual(report["error_count"], 2)
        self.assertEqual([error["claim_id"] for error in report["errors"]], ["first", "second"])
        self.assertIn("immutable evidence bindings", report["note"])


if __name__ == "__main__":
    unittest.main()
