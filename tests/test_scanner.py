import tempfile
import unittest
from pathlib import Path

import helpers

helpers.force_heuristic_tokens()

from budgetpack.scanner import scan  # noqa: E402


class TestScan(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = helpers.make_repo(Path(self._tmp.name))
        # extras for binary/large-file handling
        (self.root / "pic.jpg").write_bytes(b"\xff\xd8\xff\xe0fake")
        (self.root / "big.txt").write_text("a" * 5000, encoding="utf-8")

    def tearDown(self):
        self._tmp.cleanup()

    def rels(self, **kwargs):
        return [e.relpath for e in scan(self.root, **kwargs)]

    def test_respects_gitignore_and_defaults(self):
        rels = self.rels()
        self.assertIn("README.md", rels)
        self.assertIn("src/app.py", rels)
        self.assertIn("tests/test_app.py", rels)
        self.assertNotIn("notes.log", rels)  # via .gitignore
        self.assertNotIn("node_modules/pkg/index.js", rels)  # via defaults

    def test_gitignore_can_be_disabled(self):
        self.assertIn("notes.log", self.rels(respect_gitignore=False))

    def test_default_excludes_can_be_disabled(self):
        self.assertIn("node_modules/pkg/index.js", self.rels(use_default_excludes=False))

    def test_binary_detected_by_extension(self):
        entry = next(e for e in scan(self.root) if e.relpath == "pic.jpg")
        self.assertIsNone(entry.text)
        self.assertEqual(entry.skip_reason, "binary file")

    def test_binary_detected_by_null_byte(self):
        entry = next(e for e in scan(self.root) if e.relpath == "blob.bin")
        self.assertEqual(entry.skip_reason, "binary file")

    def test_oversized_file_marked_not_read(self):
        entries = {e.relpath: e for e in scan(self.root, max_file_size=1000)}
        entry = entries["big.txt"]
        self.assertIsNone(entry.text)
        self.assertIn("too large", entry.skip_reason)

    def test_include_filter(self):
        rels = self.rels(extra_includes=["*.py"])
        expected = ["main.py", "src/app.py", "src/util.py", "tests/test_app.py"]
        self.assertEqual(sorted(rels), expected)

    def test_exclude_filter(self):
        rels = self.rels(extra_excludes=["tests/"])
        self.assertNotIn("tests/test_app.py", rels)
        self.assertIn("src/app.py", rels)

    def test_output_file_never_included(self):
        (self.root / "budgetpack-output.md").write_text("stale", encoding="utf-8")
        self.assertNotIn("budgetpack-output.md", self.rels(extra_excludes=["budgetpack-output.md"]))


if __name__ == "__main__":
    unittest.main()
