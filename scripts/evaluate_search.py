#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from oakn.client import KnowledgeClient  # noqa: E402
from oakn.evaluation import evaluate_search_cases  # noqa: E402
from oakn.index import build_index  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Evaluate OAKN retrieval against known answers.")
    parser.add_argument("cases", type=Path)
    parser.add_argument("--claims", type=Path, default=Path("knowledge/claims"))
    parser.add_argument("-k", type=int, default=3)
    parser.add_argument("--minimum-recall-at-k", type=float)
    parser.add_argument("--minimum-negative-case-pass-rate", type=float)
    arguments = parser.parse_args()
    if arguments.minimum_recall_at_k is not None and not (
        0.0 <= arguments.minimum_recall_at_k <= 1.0
    ):
        parser.error("--minimum-recall-at-k must be between 0 and 1")
    if arguments.minimum_negative_case_pass_rate is not None and not (
        0.0 <= arguments.minimum_negative_case_pass_rate <= 1.0
    ):
        parser.error("--minimum-negative-case-pass-rate must be between 0 and 1")
    cases = json.loads(arguments.cases.read_text())
    with tempfile.TemporaryDirectory() as directory:
        index_path = Path(directory) / "evaluation.sqlite"
        build_index(arguments.claims, index_path)
        report = evaluate_search_cases(KnowledgeClient(index_path), cases, k=arguments.k)
    print(json.dumps(report, indent=2, sort_keys=True))
    metric = f"mean_recall_at_{arguments.k}"
    if arguments.minimum_recall_at_k is not None and report[metric] < arguments.minimum_recall_at_k:
        print(
            f"{metric} {report[metric]:.4f} is below {arguments.minimum_recall_at_k:.4f}",
            file=sys.stderr,
        )
        return 1
    negative_rate = report["negative_case_pass_rate"]
    if (
        arguments.minimum_negative_case_pass_rate is not None
        and negative_rate is not None
        and negative_rate < arguments.minimum_negative_case_pass_rate
    ):
        print(
            "negative_case_pass_rate "
            f"{negative_rate:.4f} is below "
            f"{arguments.minimum_negative_case_pass_rate:.4f}",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
