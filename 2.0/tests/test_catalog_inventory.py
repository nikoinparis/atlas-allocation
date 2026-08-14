from pathlib import Path
import sys
import unittest


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from build_catalog_inventory import (  # noqa: E402
    build_entries,
    github_slug,
    normalize_url,
    parse_catalog_links,
    parse_markdown_links,
)


class MarkdownLinkTests(unittest.TestCase):
    def test_ignores_image_badges_and_keeps_regular_links(self) -> None:
        text = "- [Project](https://example.com) ![badge](https://badge.test/x)"
        self.assertEqual(
            [("Project", "https://example.com")],
            [(label, url) for label, url, _, _ in parse_markdown_links(text)],
        )

    def test_parses_balanced_parentheses_in_url(self) -> None:
        text = "- [Book](https://example.com/a_(book))"
        self.assertEqual(
            "https://example.com/a_(book)", parse_markdown_links(text)[0][1]
        )

    def test_normalizes_github_subpaths_for_duplicate_detection(self) -> None:
        self.assertEqual(
            normalize_url("https://github.com/Owner/Repo/tree/main"),
            "https://github.com/owner/repo",
        )
        self.assertEqual(github_slug("https://github.com/Owner/Repo/tree/main"), "Owner/Repo")

    def test_finds_supplemental_github_repository(self) -> None:
        self.assertEqual(
            github_slug("https://project.example", "https://github.com/Owner/Repo"),
            "Owner/Repo",
        )

    def test_parses_angle_bracket_url(self) -> None:
        text = "- Source Code: <https://github.com/example/project>"
        self.assertEqual(
            "https://github.com/example/project", parse_catalog_links(text)[0][1]
        )


class CatalogFixtureTests(unittest.TestCase):
    def test_builds_entries_and_marks_cross_file_duplicates(self) -> None:
        fixture = Path(self._testMethodName)
        fixture.mkdir(exist_ok=True)
        self.addCleanup(lambda: self._remove_fixture(fixture))
        (fixture / "Readme.md").write_text(
            "# Catalog\n- [TOC](#toc)\n## Backtest\n- [One](https://github.com/o/r) | `Python` | - A test\n",
            encoding="utf-8",
        )
        (fixture / "crypto_focus.md").write_text(
            "# Crypto\n- [One again](https://github.com/o/r/tree/main) | `Python`\n",
            encoding="utf-8",
        )
        entries = build_entries(fixture, "abc")
        self.assertEqual(2, len(entries))
        self.assertEqual("", entries[0].duplicate_of)
        self.assertEqual("ast-0001", entries[1].duplicate_of)
        self.assertNotIn("TOC", [entry.name for entry in entries])

    @staticmethod
    def _remove_fixture(fixture: Path) -> None:
        for child in fixture.iterdir():
            child.unlink()
        fixture.rmdir()


if __name__ == "__main__":
    unittest.main()
