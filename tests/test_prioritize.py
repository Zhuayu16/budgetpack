import unittest
from pathlib import Path

import helpers

helpers.force_heuristic_tokens()

from budgetpack.prioritize import score_file, score_files  # noqa: E402
from budgetpack.scanner import FileEntry  # noqa: E402
from budgetpack.tokens import count_tokens  # noqa: E402


def entry(relpath: str, text: str = "x") -> FileEntry:
    return FileEntry(relpath, Path(relpath), len(text), text, count_tokens(text))


class TestPrioritize(unittest.TestCase):
    def test_readme_outranks_everything(self):
        scored = score_files(
            [entry("main.py"), entry("README.md"), entry("src/app.py")]
        )
        self.assertEqual(scored[0].entry.relpath, "README.md")
        self.assertIn("project overview", scored[0].reasons)

    def test_priority_order(self):
        scored = score_files(
            [
                entry("tests/test_app.py"),
                entry("src/app.py"),
                entry("main.py"),
                entry("README.md"),
            ]
        )
        rels = [s.entry.relpath for s in scored]
        # src/app.py outranks main.py: "app.py" is an entry-point name AND it
        # sits in the core src/ directory, while main.py is at depth 0.
        self.assertEqual(rels, ["README.md", "src/app.py", "main.py", "tests/test_app.py"])

    def test_entry_point_and_manifest_reasons(self):
        s = score_file(entry("cli.py"))
        self.assertIn("entry point", s.reasons)
        s = score_file(entry("pyproject.toml"))
        self.assertIn("project manifest", s.reasons)

    def test_tests_are_penalized(self):
        hot = score_file(entry("app.py"))
        cold = score_file(entry("tests/app.py"))
        self.assertGreater(hot.score, cold.score)
        self.assertIn("tests", cold.reasons)

    def test_shallow_files_outrank_deep_ones(self):
        shallow = score_file(entry("tools.py"))
        deep = score_file(entry("a/b/c/d/tools.py"))
        self.assertGreater(shallow.score, deep.score)

    def test_git_heat_adds_score(self):
        plain = score_file(entry("app.py"))
        hot = score_file(entry("app.py"), {"app.py": 15})
        self.assertGreater(hot.score, plain.score)
        self.assertIn("git heat (15 commits)", hot.reasons)

    def test_git_heat_is_capped(self):
        mild = score_file(entry("app.py"), {"app.py": 20})
        wild = score_file(entry("app.py"), {"app.py": 5000})
        self.assertEqual(mild.score, wild.score)


if __name__ == "__main__":
    unittest.main()
