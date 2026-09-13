import unittest

import helpers

helpers.force_heuristic_tokens()

from budgetpack.tokens import backend_name, count_tokens, truncate_to_tokens  # noqa: E402


class TestTokens(unittest.TestCase):
    def test_heuristic_estimate(self):
        self.assertEqual(count_tokens("a" * 40), 10)

    def test_empty_text(self):
        self.assertEqual(count_tokens(""), 0)

    def test_short_text_is_nonzero(self):
        self.assertEqual(count_tokens("ab"), 1)

    def test_truncate_respects_budget(self):
        text = "x" * 400
        self.assertEqual(count_tokens(truncate_to_tokens(text, 50)), 50)

    def test_truncate_under_budget_returns_original(self):
        text = "x" * 40
        self.assertEqual(truncate_to_tokens(text, 100), text)

    def test_truncate_zero_budget(self):
        self.assertEqual(truncate_to_tokens("hello", 0), "")

    def test_backend_reports_heuristic(self):
        self.assertIn("heuristic", backend_name())


if __name__ == "__main__":
    unittest.main()
