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

        self.assertEqual(report["case_count"], 5)
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


if __name__ == "__main__":
    unittest.main()
