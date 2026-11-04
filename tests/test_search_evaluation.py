import json
import tempfile
import unittest
from pathlib import Path

from oakn.client import KnowledgeClient
from oakn.evaluation import evaluate_search_cases
from oakn.index import build_index

ROOT = Path(__file__).parents[1]


class SearchEvaluationTests(unittest.TestCase):
    def test_repository_known_answers_meet_recall_and_ranking_targets(self) -> None:
        cases = json.loads((ROOT / "evaluation" / "search-cases.json").read_text())
        with tempfile.TemporaryDirectory() as directory:
            index_path = Path(directory) / "index.sqlite"
            build_index(ROOT / "knowledge" / "claims", index_path)
            report = evaluate_search_cases(KnowledgeClient(index_path), cases, k=3)

        self.assertEqual(report["case_count"], 8)
        self.assertEqual(report["positive_case_count"], 6)
        self.assertEqual(report["negative_case_count"], 2)
        self.assertEqual(report["negative_case_pass_rate"], 1.0)
        self.assertEqual(report["mean_recall_at_3"], 1.0, report["cases"])
        self.assertEqual(report["hit_rate"], 1.0, report["cases"])
        self.assertEqual(report["mean_reciprocal_rank"], 1.0, report["cases"])

    def test_rejects_empty_cases_and_nonpositive_cutoff(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            client = KnowledgeClient(Path(directory) / "index.sqlite")
            with self.assertRaisesRegex(ValueError, "at least one"):
                evaluate_search_cases(client, [])
            with self.assertRaisesRegex(ValueError, "k must be positive"):
                evaluate_search_cases(client, [{"query": "query"}], k=0)

    def test_negative_case_fails_when_a_claim_is_retrieved(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            index_path = Path(directory) / "index.sqlite"
            build_index(ROOT / "knowledge" / "claims", index_path)
            report = evaluate_search_cases(
                KnowledgeClient(index_path),
                [
                    {
                        "name": "positive control",
                        "query": "unrequested WebSocket subprotocol denial of service",
                        "purl": "pkg:npm/undici",
                        "version": "8.10.2",
                        "expected_claim_ids": ["9a9c2a7b-4c4c-4a0e-9d84-2e1a6a0c7f31"],
                    },
                    {
                        "name": "unexpected positive",
                        "query": "unrequested WebSocket subprotocol denial of service",
                        "purl": "pkg:npm/undici",
                        "version": "8.10.2",
                        "expected_no_results": True,
                    },
                ],
            )

        self.assertEqual(report["negative_case_pass_rate"], 0.0)


if __name__ == "__main__":
    unittest.main()
