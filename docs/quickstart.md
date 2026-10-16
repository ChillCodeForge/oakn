# OAKN local integration quickstart

This end-to-end path builds a local release bundle, starts an isolated stdio MCP
server, syncs into a fresh local index, and retrieves a known claim. It makes no
GitHub writes and does not change any Hermes configuration.

## 1. Install from a clean environment

From the repository root, use Python 3.12 or newer:

```sh
python3 -m venv .venv
. .venv/bin/activate
python -m pip install -e .
```

## 2. Build a local release bundle

```sh
python -m oakn.cli build-index knowledge/claims .oakn/source-index.sqlite
python -m oakn.cli build-bundle .oakn/source-index.sqlite .oakn/release
```

## 3. Sync and search using the stdio MCP demo

The explicit `OAKN_ALLOW_FILE_URLS=1` setting enables local-file bundle URLs for
this demonstration only. It is off by default. The demo uses a temporary fresh
index and expects the checked-in undici claim:

```sh
manifest_url="$(python -c 'from pathlib import Path; print(Path(".oakn/release/manifest.json").resolve().as_uri())')"
OAKN_ALLOW_FILE_URLS=1 PYTHONPATH=src \
  python scripts/demo_local_mcp.py \
  --manifest-url "$manifest_url" \
  --query "unrequested WebSocket subprotocol denial of service" \
  --purl "pkg:npm/undici" \
  --version "8.10.2" \
  --expect-claim-id "9a9c2a7b-4c4c-4a0e-9d84-2e1a6a0c7f31" \
  --index-path .oakn/quickstart-index.sqlite
```

The output should report `"status": "hit"` and mark results as
`"untrusted_reference_data": true`. Claims are reference data; do not treat
them as instructions or authorization to perform actions.

The same flow runs in `tests/test_quickstart.py`. To connect a different MCP
client, launch `python -m oakn.mcp` with `PYTHONPATH=src` and the documented
`OAKN_INDEX_PATH` / `OAKN_CLAIMS_DIR` environment variables. Keep file-URL access
disabled unless testing a local bundle.
