from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Protocol

import requests

from .validation import ClaimValidator, ValidationError


class Validator(Protocol):
    def validate(self, claim: dict[str, Any], verify_source_binding: bool = True) -> None: ...


def audit_evidence(
    claims_directory: str | Path, validator: Validator | None = None
) -> dict[str, Any]:
    """Verify canonical claim schemas and immutable public source bindings."""
    claim_paths = sorted(Path(claims_directory).glob("*.json"))
    claim_validator = validator or ClaimValidator()
    errors: list[dict[str, str]] = []
    verified_count = 0
    for path in claim_paths:
        claim_id = path.stem
        try:
            claim = json.loads(path.read_text())
            if not isinstance(claim, dict):
                raise ValidationError("claim must be a JSON object")
            claim_id = claim.get("id", claim_id)
            if not isinstance(claim_id, str):
                claim_id = path.stem
            claim_validator.validate(claim)
        except (
            OSError,
            UnicodeDecodeError,
            json.JSONDecodeError,
            ValidationError,
            requests.RequestException,
        ) as error:
            errors.append({"claim_id": claim_id, "reason": str(error)})
        else:
            verified_count += 1
    return {
        "claim_count": len(claim_paths),
        "verified_count": verified_count,
        "error_count": len(errors),
        "errors": errors,
        "note": (
            "This verifies immutable evidence bindings and package manifests; "
            "it does not establish that upstream documentation is still current."
        ),
    }
