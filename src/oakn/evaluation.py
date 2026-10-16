from __future__ import annotations

from typing import Any

from .client import KnowledgeClient


def evaluate_search_cases(
    client: KnowledgeClient, cases: list[dict[str, Any]], *, k: int = 3
) -> dict[str, Any]:
    """Measure positive-answer retrieval and the pass rate of expected-empty searches."""
    if k < 1:
        raise ValueError("k must be positive")
    if not cases:
        raise ValueError("at least one search case is required")

    details: list[dict[str, Any]] = []
    positive_count = 0
    negative_count = 0
    negative_pass_count = 0
    recall_sum = 0.0
    reciprocal_rank_sum = 0.0
    hit_count = 0
    for case in cases:
        expected = case.get("expected_claim_ids")
        expected_no_results = case.get("expected_no_results", False)
        if not isinstance(expected_no_results, bool):
            raise ValueError("expected_no_results must be a boolean")
        if expected_no_results is True:
            if expected is not None and expected != []:
                raise ValueError("negative cases cannot include expected_claim_ids")
            expected_ids: list[str] = []
        elif (
            not isinstance(expected, list)
            or not expected
            or not all(isinstance(claim_id, str) for claim_id in expected)
        ):
            raise ValueError("each positive case must include at least one expected_claim_id")
        else:
            expected_ids = expected
        response = client.search(case["query"], case["purl"], case["version"], case.get("topic"))
        results = response.get("results", [])
        actual = [result["claim_id"] for result in results[:k]]
        must_not_return = case.get("must_not_return_claim_ids", [])
        if not isinstance(must_not_return, list) or not all(
            isinstance(claim_id, str) for claim_id in must_not_return
        ):
            raise ValueError("must_not_return_claim_ids must be a list of strings")
        forbidden = sorted(set(actual) & set(must_not_return))
        if expected_no_results:
            passed = not results and not forbidden
            negative_count += 1
            negative_pass_count += int(passed)
            details.append(
                {
                    "name": case.get("name", case["query"]),
                    "expected_claim_ids": [],
                    "retrieved_claim_ids": actual,
                    "expected_no_results": True,
                    "negative_case_passed": passed,
                    "must_not_return_claim_ids": must_not_return,
                }
            )
            continue
        relevant_positions = [
            position
            for position, claim_id in enumerate(actual, start=1)
            if claim_id in expected_ids
        ]
        retrieved = {claim_id for claim_id in actual if claim_id in expected_ids}
        recall = len(retrieved) / len(expected_ids)
        reciprocal_rank = 1 / min(relevant_positions) if relevant_positions else 0.0
        hit = bool(relevant_positions) and not forbidden
        recall_sum += recall
        reciprocal_rank_sum += reciprocal_rank
        hit_count += int(hit)
        positive_count += 1
        details.append(
            {
                "name": case.get("name", case["query"]),
                "expected_claim_ids": expected_ids,
                "retrieved_claim_ids": actual,
                f"recall_at_{k}": round(recall, 4),
                "reciprocal_rank": round(reciprocal_rank, 4),
                "hit": hit,
                "must_not_return_claim_ids": must_not_return,
                "forbidden_claim_ids_retrieved": forbidden,
            }
        )
    if positive_count == 0:
        raise ValueError("at least one positive known-answer case is required")
    return {
        "case_count": len(cases),
        "positive_case_count": positive_count,
        "negative_case_count": negative_count,
        "k": k,
        f"mean_recall_at_{k}": round(recall_sum / positive_count, 4),
        "mean_reciprocal_rank": round(reciprocal_rank_sum / positive_count, 4),
        "hit_rate": round(hit_count / positive_count, 4),
        "negative_case_pass_rate": (
            round(negative_pass_count / negative_count, 4) if negative_count else None
        ),
        "cases": details,
    }
