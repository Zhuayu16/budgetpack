from __future__ import annotations

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


class TestMaterialize(unittest.TestCase):
    """materialize() reads only planned files and enforces exact budgets."""

    def setUp(self):
        import tempfile

        self._tmp = tempfile.TemporaryDirectory()
        self.root = helpers.make_repo(Path(self._tmp.name))

    def tearDown(self):
        self._tmp.cleanup()

    def _lazy_pipeline(self, budget):
        from budgetpack.packer import materialize
        from budgetpack.prioritize import score_files
        from budgetpack.scanner import scan

        entries = scan(self.root, read_texts=False)
        plan = pack(score_files(entries), budget)
        return materialize(plan, self.root, budget)

    def test_lazy_pipeline_matches_eager_results(self):
        from budgetpack.packer import pack as eager_pack
        from budgetpack.prioritize import score_files
        from budgetpack.scanner import scan

        eager_entries = scan(self.root, read_texts=True)
        eager = eager_pack(score_files(eager_entries), 5000)

        lazy, reads = self._lazy_pipeline(5000)
        self.assertEqual(
            [p.entry.relpath for p in eager.packed],
            [p.entry.relpath for p in lazy.packed],
        )
        self.assertEqual(eager.used, lazy.used)
        self.assertEqual(
            {om.entry.relpath for om in eager.omitted},
            {om.entry.relpath for om in lazy.omitted},
        )
        # eager reads all readable files; lazy reads only the packed ones
        self.assertLessEqual(reads.files_read, len(lazy.packed))
        self.assertLess(reads.bytes_read, sum(e.size for e in eager_entries))

    def test_exact_counts_exceeding_estimate_get_omitted(self):
        # Simulate a tokenizer that needs ~len/3 tokens while estimates assumed
        # len/4: the file no longer fits the leftover and is dropped, keeping
        # the exact budget guarantee.
        from unittest import mock

        from budgetpack import tokens as tokens_mod

        (self.root / "big.txt").write_text("a" * 3600, encoding="utf-8")  # est. 900
        with mock.patch.object(
            tokens_mod, "count_tokens", lambda text: round(len(text) / 3)
        ), mock.patch.object(
            tokens_mod, "truncate_to_tokens", lambda text, cap: text[: cap * 3]
        ):
            result, _ = self._lazy_pipeline(1000)
        self.assertLessEqual(result.used, 1000)
        self.assertFalse(any(p.entry.relpath == "big.txt" for p in result.packed))
        dropped = [om for om in result.omitted if om.entry.relpath == "big.txt"]
        self.assertEqual(len(dropped), 1)
        self.assertIn("needs 1,200 tokens", dropped[0].reason)

    def test_truncation_uses_exact_leftover(self):
        from unittest import mock

        from budgetpack import tokens as tokens_mod

        (self.root / "big.txt").write_text("a" * 4000, encoding="utf-8")  # est. 1000
        with mock.patch.object(
            tokens_mod, "count_tokens", lambda text: round(len(text) / 3)
        ), mock.patch.object(
            tokens_mod, "truncate_to_tokens", lambda text, cap: text[: cap * 3]
        ):
            result, _ = self._lazy_pipeline(1100)
        truncated = [p for p in result.packed if p.truncated]
        self.assertEqual(len(truncated), 1)
        self.assertEqual(truncated[0].entry.relpath, "big.txt")
        # truncation fills the budget exactly: what's left after the small
        # files is consumed by the truncated big one
        self.assertEqual(result.used, 1100)
        self.assertGreaterEqual(truncated[0].included_tokens, MIN_TRUNCATE_TOKENS)
        self.assertIn("truncated", truncated[0].note)

    def test_binary_content_omitted_at_read_time(self):
        from budgetpack.packer import materialize
        from budgetpack.prioritize import score_files
        from budgetpack.scanner import scan

        # .dat is not a known binary extension, so the scan plans it as text
        (self.root / "blob.dat").write_bytes(b"ok\x00binary")
        entries = scan(self.root, read_texts=False)
        plan = pack(score_files(entries), 5000)
        result, _ = materialize(plan, self.root, 5000)
        self.assertTrue(
            any(om.entry.relpath == "blob.dat" and om.reason == "binary file"
                for om in result.omitted)
        )
        self.assertFalse(any(p.entry.relpath == "blob.dat" for p in result.packed))


if __name__ == "__main__":
    unittest.main()
