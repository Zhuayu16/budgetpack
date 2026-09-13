import io
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

import helpers

helpers.force_heuristic_tokens()

from budgetpack import cli  # noqa: E402


class TestCli(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.root = helpers.make_repo(Path(self._tmp.name))

    def tearDown(self):
        self._tmp.cleanup()

    def test_pack_end_to_end(self):
        out = Path(self._tmp.name) / "out.md"
        rc = cli.main(["pack", str(self.root), "-b", "5000", "-o", str(out)])
        self.assertEqual(rc, 0)
        report = out.read_text(encoding="utf-8")
        self.assertIn("# Codebase Pack", report)
        self.assertIn("### README.md", report)
        self.assertIn("### main.py", report)
        # the binary fixture is always reported as omitted
        self.assertIn("`blob.bin`", report)
        self.assertIn("binary file", report)
        self.assertNotIn("notes.log", report)  # .gitignore respected
        self.assertNotIn("node_modules", report)  # default excludes respected

    def test_pack_omits_under_tiny_budget(self):
        out = Path(self._tmp.name) / "tiny.md"
        rc = cli.main(["pack", str(self.root), "-b", "10", "-o", str(out)])
        self.assertEqual(rc, 0)
        report = out.read_text(encoding="utf-8")
        self.assertIn("## Omitted files", report)
        self.assertIn("### README.md", report)  # top priority still wins

    def test_default_subcommand_is_pack(self):
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            rc = cli.main([str(self.root), "--stdout", "-b", "5000"])
        self.assertEqual(rc, 0)
        self.assertIn("# Codebase Pack", buffer.getvalue())

    def test_stats_output(self):
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            rc = cli.main(["stats", str(self.root)])
        self.assertEqual(rc, 0)
        table = buffer.getvalue()
        self.assertIn("README.md", table)
        self.assertIn("total across all files", table)

    def test_missing_path_returns_error(self):
        self.assertEqual(cli.main(["pack", str(self.root / "nope")]), 2)

    def test_version_flag(self):
        with self.assertRaises(SystemExit) as ctx:
            cli.main(["--version"])
        self.assertEqual(ctx.exception.code, 0)


if __name__ == "__main__":
    unittest.main()
