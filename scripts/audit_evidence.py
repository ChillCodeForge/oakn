#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from oakn.evidence_audit import audit_evidence  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Verify canonical claim schemas and immutable public evidence."
    )
    parser.add_argument("claims", nargs="?", type=Path, default=Path("knowledge/claims"))
    arguments = parser.parse_args()
    report = audit_evidence(arguments.claims)
    print(json.dumps(report, indent=2, sort_keys=True))
    return int(report["error_count"] > 0)


if __name__ == "__main__":
    raise SystemExit(main())
