#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import subprocess
from pathlib import Path
from typing import Any

_SHA_RE = re.compile(r"[0-9a-f]{40}")
_REPOSITORY_RE = re.compile(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+")


def validate_pull_request(
    pull_request: Any, repository: str, number: int, expected_head_sha: str
) -> str:
    if number < 1 or not _SHA_RE.fullmatch(expected_head_sha):
        raise ValueError("PR number or expected head SHA is invalid")
    if not isinstance(pull_request, dict):
        raise ValueError("GitHub returned an invalid pull request")

    base = pull_request.get("base")
    head = pull_request.get("head")
    if not isinstance(base, dict) or not isinstance(head, dict):
        raise ValueError("GitHub returned incomplete pull request metadata")
    base_repo = base.get("repo")
    head_repo = head.get("repo")
    if not isinstance(base_repo, dict) or not isinstance(head_repo, dict):
        raise ValueError("pull request repository metadata is unavailable")

    base_sha = base.get("sha")
    if (
        pull_request.get("number") != number
        or pull_request.get("state") != "open"
        or base.get("ref") != "main"
        or base_repo.get("full_name") != repository
        or head.get("sha") != expected_head_sha
        or not isinstance(base_sha, str)
        or not _SHA_RE.fullmatch(base_sha)
        or not isinstance(head_repo.get("full_name"), str)
    ):
        raise ValueError(
            "PR must be open, target this repository's main, and match the expected head"
        )
    return base_sha


def _git(repository: Path, *arguments: str) -> str:
    result = subprocess.run(
        ["git", "-C", str(repository), *arguments],
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout.strip()


def prepare(
    repository: str,
    number: int,
    expected_head_sha: str,
    trusted_root: Path,
    contribution: Path,
    changes_file: Path,
    output_file: Path,
) -> None:
    if not _REPOSITORY_RE.fullmatch(repository):
        raise ValueError("repository name is invalid")
    pull_request_result = subprocess.run(
        ["gh", "api", f"repos/{repository}/pulls/{number}"],
        check=True,
        capture_output=True,
        text=True,
    )
    base_sha = validate_pull_request(
        json.loads(pull_request_result.stdout), repository, number, expected_head_sha
    )

    _git(trusted_root, "fetch", "--no-tags", "--depth=1", "origin", base_sha)
    if _git(trusted_root, "rev-parse", "FETCH_HEAD") != base_sha:
        raise ValueError("fetched PR base does not match the GitHub API")

    pull_ref = f"refs/pull/{number}/head"
    _git(trusted_root, "fetch", "--no-tags", "--depth=1", "origin", pull_ref)
    if _git(trusted_root, "rev-parse", "FETCH_HEAD") != expected_head_sha:
        raise ValueError("fetched PR head does not match the expected head SHA")

    changes = _git(
        trusted_root,
        "diff",
        "--no-renames",
        "--name-status",
        base_sha,
        expected_head_sha,
    )
    changes_file.write_text(f"{changes}\n", encoding="utf-8")

    if contribution.exists():
        raise ValueError("temporary contribution directory already exists")
    _git(trusted_root, "worktree", "add", "--detach", str(contribution), expected_head_sha)
    output_file.write_text(f"base_sha={base_sha}\n", encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repository", required=True)
    parser.add_argument("--pr-number", required=True, type=int)
    parser.add_argument("--expected-head-sha", required=True)
    parser.add_argument("--trusted-root", required=True, type=Path)
    parser.add_argument("--contribution", required=True, type=Path)
    parser.add_argument("--changes-file", required=True, type=Path)
    parser.add_argument("--output-file", required=True, type=Path)
    arguments = parser.parse_args()
    prepare(
        arguments.repository,
        arguments.pr_number,
        arguments.expected_head_sha,
        arguments.trusted_root,
        arguments.contribution,
        arguments.changes_file,
        arguments.output_file,
    )


if __name__ == "__main__":
    main()
