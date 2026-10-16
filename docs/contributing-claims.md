# Contributing a claim: practical guide

`docs/agent-rule.md` states the protocol. This document collects the concrete,
ecosystem-specific pitfalls that are easy to hit the first time you actually
build and stage a claim, regardless of which agent or tool you use.

## Before opening a pull request

Public claim contributions and trusted code changes follow different paths:

- A **claim PR** must add exactly one new
  `knowledge/claims/<uuid>.json` file. Do not include formatting-only changes,
  workflow edits or source changes in the same PR. The contribution validator
  checks the file as untrusted data and does not execute code from the branch.
- A **control-plane PR** changes trusted paths such as `.github/`, `scripts/`,
  `src/`, `schemas/` or repository policy. Collaborators with administrator,
  maintainer or write permission run the trusted tests directly without the
  external-approval gate. Other contributors may propose control-plane changes,
  but the tests require two independent collaborator approvals for the current
  commit. New commits or a later `CHANGES_REQUESTED` review require approval
  again.
- Control-plane validation runs without repository secrets and without write
  tokens. A green `validate` check means the relevant path passed the trusted
  boundary; it does not replace required CODEOWNER review.
- Claims are immutable after merge. Run `python scripts/audit_claims.py` to
  identify claims that may need a freshness review, invalid supersession links
  or near-duplicate same-version statements. The report is advisory and never
  rewrites claim files; submit a new claim with `lifecycle.supersedes` when a
  correction should replace an older claim.

If a claim PR is rejected as a control-plane change, inspect the changed-path
list first. A claim PR with more than the one new claim JSON file must be split
before it can pass the data-only gate.

## Recovering a missing validation check

Maintainers can rerun validation when a claim PR is still open but its required
`validate` check was never reported. In Actions, run **Recover claim
validation** with the `main` branch selected, the PR number, and the exact
40-character head SHA shown on that PR. The workflow refuses a closed PR, a PR
not targeting this repository's `main`, a changed head or base, or a run
dispatched from a stale/non-main revision.

The recovery fetches the validator from `main`, compares the PR head with its
base, and runs the normal contribution validator against the fetched PR tree as
data. It accepts exactly one newly added `knowledge/claims/<uuid>.json` file;
it does not run code from the PR. Only after successful validation does a
separate job use the built-in GitHub Actions token to create a `validate` check
on that exact head SHA. A failed, stale, or non-claim contribution creates no
successful required check. No repository secrets, branch-protection settings,
review requirements, or PR contents are changed; only the workflow's ephemeral
GitHub Actions token is used for API access.

After a successful run, verify the `validate` check is successful on the same
head SHA. The main-branch required-check policy must continue to show
`validate` from GitHub Actions app `15368`; the workflow does not modify that
policy. Do not use recovery to validate code changes or to override a failed
check.

## 1. Pick evidence that is actually version-provable

Every claim binds a package version to a manifest file's content hash
(`package_manifest` in the evidence entry). That only works if the manifest
at your chosen commit actually contains the version string.

- **npm** (`package.json`), **maven** (`pom.xml`/`build.gradle`), **cargo**
  (`Cargo.toml`), **golang** (`go.mod`, module path only — see below) are
  generally reliable.
- **pypi** is the ecosystem most likely to trip you up: many popular packages
  declare `dynamic = ["version"]` in `pyproject.toml`'s `[project]` table and
  resolve the actual version at build time via a plugin (hatch-vcs,
  setuptools_scm, etc.). A claim cannot be manifest-verified against a
  dynamic version field. Examples that will NOT work: `requests`, `httpx`,
  `click`, `packaging`, `black`, `more-itertools`, `python-dotenv`,
  `tabulate`, `pytest-dev/iniconfig`, `pyyaml`, `Django`. Before picking a
  package, check:
  ```sh
  grep -A8 '^\[project\]' pyproject.toml
  ```
  and confirm there is a literal `version = "x.y.z"` line, not a `dynamic`
  entry naming `"version"`. `flask` (>=3.x) and `cryptography` (>=42.x) are
  reliable examples of static-version pypi packages.
- **golang** is a special case: `go.mod` never carries a version at all
  (only the module path). OAKN verifies golang claim versions against the
  public Go module proxy (`proxy.golang.org`'s `@v/<version>.info` endpoint)
  as a second trust root beyond GitHub, rather than the manifest. No action
  needed on your part beyond picking a real tagged version — just be aware
  the verification path is different from every other ecosystem.

### Declare the affected range for a fix-version claim

The evidence proves one version, usually the fix. Agents search with the
version their project has, which for a security fix is the vulnerable one.
Add `package.affected` as a [VERS](https://github.com/package-url/purl-spec/blob/main/VERSION-RANGE-SPEC.rst)
range in the purl's own scheme, copied from the advisory:

```json
"package": {
  "purl": "pkg:maven/org.apache.commons/commons-text@1.10.0",
  "version": "1.10.0",
  "affected": "vers:maven/>=1.5|<1.10.0"
}
```

Without it, only a project already on 1.10.0 finds the claim. The validator
rejects a range that does not parse or whose scheme differs from the purl type.

## 2. Use the live network fetch to compute hashes, not your local clone

The validator's default `fetch` hits `raw.githubusercontent.com` for the
exact commit SHA you cite. Compute your evidence `content_sha256` values
against that same live endpoint, not just a local `git clone` (they should
match, but the network fetch is what's authoritative, and computing it this
way catches encoding/line-ending mismatches early):

```python
import hashlib, urllib.request

url = f"https://raw.githubusercontent.com/{owner}/{repo}/{commit_sha}/{path}"
content = urllib.request.urlopen(url).read()
hashlib.sha256(content).hexdigest()
```

## 3. Validate before you write anything to `knowledge/claims/`

```python
from oakn.validation import ClaimValidator

ClaimValidator().validate(
    claim
)  # real network verification; raises ValidationError on any mismatch
```

## 4. Stage through `KnowledgeClient.contribute()`, not a hand-written file

Writing a claim JSON directly into `knowledge/claims/` works, but skips the
duplicate-detection and canonical formatting `contribute()` gives you for
free, and doubles as a second independent validation pass:

```python
from oakn.client import KnowledgeClient

KnowledgeClient(".oakn/index.sqlite").contribute(claim, "knowledge/claims")
```

## 5. Rebuild and search locally before opening a PR

```sh
PYTHONPATH=src python3 -m oakn.cli build-index knowledge/claims .oakn/index.sqlite
```

Then run a real `search()` (via the CLI, the MCP server, or
`KnowledgeClient.search()`) for your claim's purl/topic and confirm it comes
back as a hit before spending a PR review cycle on it.

## 6. One claim per PR

Keeps review focused and keeps `_reject_duplicate` (package + overlapping
summary terms) meaningful — it only compares against claims already on disk
when you stage, not against other claims in the same PR.
