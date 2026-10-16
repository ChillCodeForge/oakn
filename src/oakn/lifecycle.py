from __future__ import annotations

import json
import re
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from .versions import split_purl

_WORD = re.compile(r"[a-z0-9]+")
_IGNORED_WORDS = {"about", "after", "before", "from", "into", "only", "that", "their", "with"}


def audit_claims(
    claims_directory: str | Path, *, today: date | None = None, max_age_days: int = 365
) -> dict[str, Any]:
    """Report stale claims and lifecycle inconsistencies without changing data."""
    if max_age_days < 1:
        raise ValueError("max_age_days must be positive")
    current_date = today or date.today()
    cutoff = current_date - timedelta(days=max_age_days)
    claims: list[dict[str, Any]] = []
    lifecycle_errors: list[dict[str, str]] = []
    stale_claims: list[dict[str, str]] = []
    superseded_by: dict[str, list[str]] = defaultdict(list)
    for path in sorted(Path(claims_directory).glob("*.json")):
        try:
            payload = json.loads(path.read_text())
        except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
            lifecycle_errors.append(
                {"file": path.name, "reason": f"claim file cannot be read: {error}"}
            )
            continue
        if not isinstance(payload, dict):
            lifecycle_errors.append({"file": path.name, "reason": "claim must be a JSON object"})
            continue
        if not isinstance(payload.get("id"), str) or not payload["id"]:
            lifecycle_errors.append({"file": path.name, "reason": "claim id must be a string"})
        elif payload["id"] != path.stem:
            lifecycle_errors.append(
                {"file": path.name, "reason": "claim id does not match its filename"}
            )
        claims.append(payload)
    by_id: dict[str, dict[str, Any]] = {}
    for claim in claims:
        claim_id = claim.get("id")
        if isinstance(claim_id, str) and claim_id:
            if claim_id in by_id:
                lifecycle_errors.append({"claim_id": claim_id, "reason": "duplicate claim id"})
            else:
                by_id[claim_id] = claim

    for claim in claims:
        lifecycle = claim.get("lifecycle", {})
        claim_id = claim.get("id", "")
        claim_id_text = claim_id if isinstance(claim_id, str) else str(claim_id)
        if not isinstance(lifecycle, dict):
            lifecycle_errors.append(
                {"claim_id": claim_id_text, "reason": "lifecycle must be an object"}
            )
            continue
        created_at = lifecycle.get("created_at")
        if not isinstance(created_at, str):
            lifecycle_errors.append(
                {"claim_id": claim_id_text, "reason": "invalid lifecycle.created_at"}
            )
        else:
            try:
                created = date.fromisoformat(created_at)
            except ValueError:
                lifecycle_errors.append(
                    {"claim_id": claim_id_text, "reason": "invalid lifecycle.created_at"}
                )
            else:
                if created > current_date:
                    lifecycle_errors.append(
                        {
                            "claim_id": claim_id_text,
                            "reason": "lifecycle.created_at is in the future",
                        }
                    )
                elif created < cutoff:
                    stale_claims.append(
                        {"claim_id": claim_id_text, "created_at": created.isoformat()}
                    )

        supersedes = lifecycle.get("supersedes")
        if supersedes is not None:
            if not isinstance(supersedes, str):
                lifecycle_errors.append(
                    {"claim_id": claim_id_text, "reason": "lifecycle.supersedes must be a string"}
                )
            elif supersedes == claim_id:
                lifecycle_errors.append(
                    {"claim_id": claim_id_text, "reason": "claim cannot supersede itself"}
                )
            elif supersedes not in by_id:
                lifecycle_errors.append(
                    {
                        "claim_id": claim_id_text,
                        "reason": f"supersedes missing claim {supersedes}",
                    }
                )
            else:
                superseded_by[supersedes].append(claim_id_text)

    for superseded_id, successors in sorted(superseded_by.items()):
        if len(successors) > 1:
            lifecycle_errors.append(
                {
                    "claim_id": superseded_id,
                    "reason": f"multiple claims supersede this claim: {', '.join(sorted(successors))}",
                }
            )

    lifecycle_errors.extend(_supersession_cycles(claims, by_id))
    return {
        "claim_count": len(claims),
        "max_age_days": max_age_days,
        "stale_claims": stale_claims,
        "lifecycle_errors": lifecycle_errors,
        "possible_conflicts": _possible_conflicts(claims),
        "note": "Staleness and possible conflicts are review signals; claims are never modified.",
    }


def _supersession_cycles(
    claims: list[dict[str, Any]], by_id: dict[str, dict[str, Any]]
) -> list[dict[str, str]]:
    errors: list[dict[str, str]] = []
    visited: set[str] = set()
    for claim in claims:
        start = claim.get("id", "")
        if not isinstance(start, str) or not start:
            continue
        current = start
        chain: list[str] = []
        positions: dict[str, int] = {}
        while current in by_id and current not in visited:
            if current in positions:
                cycle = chain[positions[current] :] + [current]
                errors.append(
                    {"claim_id": start, "reason": f"supersedes cycle: {' -> '.join(cycle)}"}
                )
                break
            positions[current] = len(chain)
            chain.append(current)
            lifecycle = by_id[current].get("lifecycle", {})
            if not isinstance(lifecycle, dict):
                break
            next_id = lifecycle.get("supersedes", "")
            if not isinstance(next_id, str):
                break
            current = next_id
        visited.update(chain)
    return errors


def _possible_conflicts(claims: list[dict[str, Any]]) -> list[dict[str, Any]]:
    groups: dict[tuple[str, str, str], list[dict[str, Any]]] = defaultdict(list)
    for claim in claims:
        package = claim.get("package", {})
        if not isinstance(package, dict):
            continue
        purl = package.get("purl", "")
        claim_id = claim.get("id")
        version = package.get("version")
        claim_type = claim.get("claim_type")
        if (
            not isinstance(purl, str)
            or not isinstance(claim_id, str)
            or not isinstance(version, str)
            or not isinstance(claim_type, str)
            or not isinstance(claim.get("summary"), str)
        ):
            continue
        try:
            _, package_base, _ = split_purl(purl)
        except ValueError:
            continue
        groups[(package_base, version, claim_type)].append(claim)

    candidates: list[dict[str, Any]] = []
    for (package, version, claim_type), grouped_claims in sorted(groups.items()):
        ordered = sorted(grouped_claims, key=lambda claim: claim.get("id", ""))
        for index, left in enumerate(ordered):
            left_words = _meaningful_words(left.get("summary", ""))
            for right in ordered[index + 1 :]:
                right_words = _meaningful_words(right.get("summary", ""))
                union = left_words | right_words
                similarity = len(left_words & right_words) / len(union) if union else 0.0
                if len(left_words & right_words) >= 3 and similarity >= 0.6:
                    candidates.append(
                        {
                            "claim_ids": sorted((left["id"], right["id"])),
                            "package": package,
                            "version": version,
                            "claim_type": claim_type,
                            "summary_similarity": round(similarity, 3),
                        }
                    )
    return candidates


def _meaningful_words(text: str) -> set[str]:
    if not isinstance(text, str):
        return set()
    return {word for word in _WORD.findall(text.lower()) if word not in _IGNORED_WORDS}
