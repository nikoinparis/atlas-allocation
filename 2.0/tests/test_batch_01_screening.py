from pathlib import Path
import sys
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from screen_batch_01_repositories import (  # noqa: E402
    classify_license_text,
    health_band,
)


class LicenseClassificationTests(unittest.TestCase):
    def test_recognizes_mit_text(self) -> None:
        self.assertEqual(
            ("MIT", "manually_confirmed_permissive"),
            classify_license_text("Permission is hereby granted, free of charge, to any person"),
        )

    def test_recognizes_commons_clause_restriction(self) -> None:
        self.assertEqual(
            ("LicenseRef-Commons-Clause", "source_available_restricted_commercial_use"),
            classify_license_text("Commons Clause License: this does not include the right to Sell"),
        )

    def test_recognizes_gpl_v3(self) -> None:
        self.assertEqual(
            ("GPL-3.0", "manually_confirmed_copyleft_review_obligations"),
            classify_license_text("GNU GENERAL PUBLIC LICENSE Version 3, 29 June 2007"),
        )

    def test_gpl_compatibility_reference_does_not_become_agpl(self) -> None:
        text = (
            "GNU GENERAL PUBLIC LICENSE Version 3, 29 June 2007 "
            + "ordinary terms " * 100
            + "Use with the GNU Affero General Public License"
        )
        self.assertEqual(
            ("GPL-3.0", "manually_confirmed_copyleft_review_obligations"),
            classify_license_text(text),
        )

    def test_health_bands_are_conservative(self) -> None:
        self.assertEqual("strong_screening_signals", health_band(80))
        self.assertEqual("high_risk_or_insufficient_evidence", health_band(39))


if __name__ == "__main__":
    unittest.main()
