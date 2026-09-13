import unittest
from pathlib import Path

import helpers

helpers.force_heuristic_tokens()

from budgetpack.packer import MIN_TRUNCATE_TOKENS, pack  # noqa: E402
from budgetpack.prioritize import ScoredFile  # noqa: E402
from budgetpack.scanner import FileEntry  # noqa: E402
from budgetpack.tokens import count_tokens  # noqa: E402


def scored(relpath: str, text: str, score: float, skip_reason: str | None = None) -> ScoredFile:
    entry = FileEntry(relpath, Path(relpath), len(text), text, count_tokens(text), skip_reason)
    return ScoredFile(entry, score)


class TestPack(unittest.TestCase):
    def test_everything_fits(self):
        files = [scored("README.md", "a" * 400, 100), scored("main.py", "b" * 800, 50)]
        result = pack(files, budget=1000)
        self.assertEqual(len(result.packed), 2)
        self.assertEqual(len(result.omitted), 0)
        self.assertEqual(result.used, 300)

    def test_priority_fills_budget_first(self):
        files = [scored("README.md", "a" * 2400, 1000), scored("notes.txt", "b" * 800, 10)]
        result = pack(files, budget=700)
        self.assertEqual([p.entry.relpath for p in result.packed], ["README.md"])
        self.assertEqual([om.entry.relpath for om in result.omitted], ["notes.txt"])
        self.assertEqual(result.used, 600)

    def test_omission_reason_explains_shortfall(self):
        files = [scored("big.py", "x" * 2400, 10)]
        result = pack(files, budget=100)
        self.assertEqual(len(result.omitted), 1)
        self.assertIn("needs 600 tokens", result.omitted[0].reason)
        self.assertIn("only 100 left", result.omitted[0].reason)

    def test_skipped_files_are_omitted_with_reason(self):
        files = [scored("logo.png", "", 10, skip_reason="binary file")]
        result = pack(files, budget=1000)
        self.assertEqual(len(result.packed), 0)
        self.assertEqual(result.omitted[0].reason, "binary file")

    def test_leftover_budget_truncates_best_omitted_file(self):
        # 2500 + 300 + 400 = 3200 tokens of content, budget 2000:
        # big.py cannot fit whole, the two smaller files fill 700,
        # leaving 1300 >= MIN_TRUNCATE_TOKENS for a truncated big.py.
        files = [
            scored("big.py", "a" * 10_000, 100),
            scored("small.py", "b" * 1_200, 50),
            scored("mid.py", "c" * 1_600, 40),
        ]
        result = pack(files, budget=2000)
        self.assertEqual(result.used, 2000)
        truncated = [p for p in result.packed if p.truncated]
        self.assertEqual(len(truncated), 1)
        self.assertEqual(truncated[0].entry.relpath, "big.py")
        self.assertEqual(len(result.omitted), 0)
        self.assertIn("truncated", truncated[0].note)

    def test_no_truncation_when_leftover_too_small(self):
        files = [scored("big.py", "a" * 10_000, 100), scored("small.py", "b" * 1_200, 50)]
        result = pack(files, budget=MIN_TRUNCATE_TOKENS - 1)
        packed_rel = [p.entry.relpath for p in result.packed]
        self.assertNotIn("big.py", packed_rel)
        self.assertEqual([om.entry.relpath for om in result.omitted], ["big.py"])

    def test_packed_output_stays_in_priority_order(self):
        files = [scored("zz.py", "x" * 40, 900), scored("aa.py", "y" * 40, 10)]
        result = pack(files, budget=1000)
        self.assertEqual([p.entry.relpath for p in result.packed], ["zz.py", "aa.py"])

    def test_zero_budget_omits_all(self):
        files = [scored("a.py", "x" * 40, 10)]
        result = pack(files, budget=0)
        self.assertEqual(len(result.packed), 0)
        self.assertEqual(len(result.omitted), 1)


if __name__ == "__main__":
    unittest.main()
