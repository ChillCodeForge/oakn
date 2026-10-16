from __future__ import annotations

from typing import Any

from .client import KnowledgeClient


def evaluate_search_cases(
    client: KnowledgeClient, cases: list[dict[str, Any]], *, k: int = 3
) -> dict[str, Any]:
    """Measure recall@k, reciprocal rank and hit rate for known-answer searches."""
    if k < 1:
        raise ValueError("k must be positive")
    if not cases:
        raise ValueError("at least one search case is required")

    details: list[dict[str, Any]] = []
    recall_sum = 0.0
    reciprocal_rank_sum = 0.0
    hit_count = 0
    for case in cases:
        expected = case.get("expected_claim_ids")
        if not isinstance(expected, list) or not expected:
            raise ValueError("each case must include at least one expected_claim_id")
        response = client.search(case["query"], case["purl"], case["version"], case.get("topic"))
        actual = [result["claim_id"] for result in response.get("results", [])[:k]]
        relevant_positions = [
            position for position, claim_id in enumerate(actual, start=1) if claim_id in expected
        ]
        retrieved = {claim_id for claim_id in actual if claim_id in expected}
        recall = len(retrieved) / len(expected)
        reciprocal_rank = 1 / min(relevant_positions) if relevant_positions else 0.0
        hit = bool(relevant_positions)
        recall_sum += recall
        reciprocal_rank_sum += reciprocal_rank
        hit_count += int(hit)
        details.append(
            {
                "name": case.get("name", case["query"]),
                "expected_claim_ids": expected,
                "retrieved_claim_ids": actual,
                f"recall_at_{k}": round(recall, 4),
                "reciprocal_rank": round(reciprocal_rank, 4),
                "hit": hit,
            }
        )
    count = len(cases)
    return {
        "case_count": count,
        "k": k,
        f"mean_recall_at_{k}": round(recall_sum / count, 4),
        "mean_reciprocal_rank": round(reciprocal_rank_sum / count, 4),
        "hit_rate": round(hit_count / count, 4),
        "cases": details,
    }
