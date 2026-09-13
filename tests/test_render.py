import unittest
from pathlib import Path

import helpers

helpers.force_heuristic_tokens()

from budgetpack.packer import pack  # noqa: E402
from budgetpack.prioritize import ScoredFile  # noqa: E402
from budgetpack.render import human_tokens, render_markdown, render_stats  # noqa: E402
from budgetpack.scanner import FileEntry  # noqa: E402
from budgetpack.tokens import count_tokens  # noqa: E402


def scored(relpath: str, text: str, score: float) -> ScoredFile:
    entry = FileEntry(relpath, Path(relpath), len(text), text, count_tokens(text))
    return ScoredFile(entry, score)


class TestRenderMarkdown(unittest.TestCase):
    def test_full_report_structure(self):
        files = [
            scored("README.md", "# demo\n\ncontent with `ticks`\n", 100),
            scored("main.py", "print('hi')\n", 50),
            scored("big.py", "x" * 600, 10),
        ]
        result = pack(files, budget=100)
        report = render_markdown(result, Path("/tmp/demo"))

        self.assertIn("# Codebase Pack", report)
        self.assertIn("## Repository tree", report)
        self.assertIn("● 7", report)  # README packed marker (29 chars -> 7 tokens)
        self.assertIn("○ 150", report)  # big.py omitted marker
        self.assertIn("## File contents", report)
        self.assertIn("### README.md", report)
        self.assertIn("```python", report)
        self.assertIn("print('hi')", report)
        self.assertIn("## Omitted files", report)
        self.assertIn("`big.py`", report)
        self.assertIn("only 90 left in budget", report)

    def test_fence_grows_around_backtick_blocks(self):
        tricky = "```\nnot a real fence\n```\n"
        files = [scored("weird.md", tricky, 10)]
        result = pack(files, budget=1000)
        report = render_markdown(result, Path("/tmp/demo"))
        self.assertIn("````markdown", report)
        self.assertIn("````", report)

    def test_language_hint_for_common_extensions(self):
        files = [scored("src/app.go", "package main\n", 10)]
        report = render_markdown(pack(files, budget=1000), Path("/tmp/demo"))
        self.assertIn("```go", report)


class TestHelpers(unittest.TestCase):
    def test_human_tokens(self):
        self.assertEqual(human_tokens(999), "999")
        self.assertEqual(human_tokens(12_340), "12.3k")


class TestStatsTable(unittest.TestCase):
    def test_render_stats(self):
        rows = [
            ("README.md", 6000, 1000.0, "project overview"),
            ("main.py", 40, 500.0, "entry point"),
        ]
        table = render_stats(rows, total=6040, top=10)
        self.assertIn("REASON / FILE", table)
        self.assertIn("README.md", table)
        self.assertIn("total across all files", table)


if __name__ == "__main__":
    unittest.main()
