#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from oakn.lifecycle import audit_claims  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Report potentially stale or inconsistent claims without modifying them."
    )
    parser.add_argument("claims", nargs="?", type=Path, default=Path("knowledge/claims"))
    parser.add_argument("--max-age-days", type=int, default=365)
    arguments = parser.parse_args()
    report = audit_claims(arguments.claims, max_age_days=arguments.max_age_days)
    print(json.dumps(report, indent=2, sort_keys=True))
    return int(bool(report["lifecycle_errors"]))


if __name__ == "__main__":
    raise SystemExit(main())
