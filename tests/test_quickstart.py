import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from oakn.client import KnowledgeClient, build_bundle
from oakn.index import build_index
from oakn.validation import ValidationError

ROOT = Path(__file__).parents[1]
EXPECTED_CLAIM = "9a9c2a7b-4c4c-4a0e-9d84-2e1a6a0c7f31"


class QuickstartIntegrationTests(unittest.TestCase):
    def test_local_bundle_sync_and_mcp_search_from_a_clean_index(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            index = root / "source.sqlite"
            release = root / "release"
            build_index(ROOT / "knowledge" / "claims", index)
            manifest = build_bundle(index, release)
            with self.assertRaisesRegex(ValidationError, "manifest URL must use public HTTPS"):
                KnowledgeClient(root / "default.sqlite").sync(manifest.resolve().as_uri())
            environment = {
                **os.environ,
                "OAKN_ALLOW_FILE_URLS": "1",
                "PYTHONPATH": str(ROOT / "src"),
                "PYTHONDONTWRITEBYTECODE": "1",
            }
            result = subprocess.run(
                [
                    sys.executable,
                    str(ROOT / "scripts" / "demo_local_mcp.py"),
                    "--manifest-url",
                    manifest.resolve().as_uri(),
                    "--query",
                    "unrequested WebSocket subprotocol denial of service",
                    "--purl",
                    "pkg:npm/undici",
                    "--version",
                    "8.10.2",
                    "--expect-claim-id",
                    EXPECTED_CLAIM,
                    "--index-path",
                    str(root / "fresh" / "client.sqlite"),
                ],
                cwd=ROOT,
                env=environment,
                capture_output=True,
                text=True,
                check=False,
                timeout=60,
            )

        self.assertEqual(result.returncode, 0, result.stderr)
        payload = json.loads(result.stdout)
        self.assertEqual(payload["status"], "hit")
        self.assertTrue(payload["untrusted_reference_data"])
        self.assertEqual(payload["results"][0]["claim_id"], EXPECTED_CLAIM)


if __name__ == "__main__":
    unittest.main()
