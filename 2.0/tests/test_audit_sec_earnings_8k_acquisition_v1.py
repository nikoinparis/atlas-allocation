import hashlib
import tempfile
import unittest
from pathlib import Path

import scripts.audit_sec_earnings_8k_acquisition_v1 as subject


class Earnings8KAuditTests(unittest.TestCase):
    def test_sha256_hashes_exact_file_bytes(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "sample"
            path.write_bytes(b"earnings-event")

            self.assertEqual(subject.sha256(path), hashlib.sha256(b"earnings-event").hexdigest())


if __name__ == "__main__":
    unittest.main()
