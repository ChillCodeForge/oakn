import gzip
import hashlib
import json
import sqlite3
import tempfile
import unittest
from pathlib import Path

from oakn.client import build_bundle
from oakn.index import ClaimIndex, build_index

ROOT = Path(__file__).parents[1]


class ReleaseReproducibilityTests(unittest.TestCase):
    def test_index_bundle_is_reproducible_checksummed_and_integral(self) -> None:
        claims = ROOT / "knowledge" / "claims"
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            index_a = root / "first" / "index.sqlite"
            index_b = root / "second" / "index.sqlite"
            build_index(claims, index_a)
            build_index(claims, index_b)

            release_a = root / "first-release"
            release_b = root / "second-release"
            manifest_a = build_bundle(index_a, release_a)
            manifest_b = build_bundle(index_b, release_b)

            self.assertEqual(index_a.read_bytes(), index_b.read_bytes())
            self.assertEqual(
                (release_a / "index.sqlite.gz").read_bytes(),
                (release_b / "index.sqlite.gz").read_bytes(),
            )
            self.assertEqual(manifest_a.read_bytes(), manifest_b.read_bytes())
            manifest = json.loads(manifest_a.read_text())
            bundle = (release_a / manifest["artifact"]).read_bytes()
            self.assertEqual(manifest["sha256"], hashlib.sha256(bundle).hexdigest())
            self.assertEqual(manifest["index_bytes"], index_a.stat().st_size)
            self.assertEqual(gzip.decompress(bundle), index_a.read_bytes())
            self.assertEqual(ClaimIndex(index_a).count(), len(list(claims.glob("*.json"))))
            with sqlite3.connect(index_a) as connection:
                self.assertEqual(connection.execute("PRAGMA integrity_check").fetchone(), ("ok",))


if __name__ == "__main__":
    unittest.main()
