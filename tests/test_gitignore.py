import unittest

import helpers

helpers.force_heuristic_tokens()

from budgetpack.gitignore import (  # noqa: E402
    DEFAULT_EXCLUDES,
    IgnoreStack,
    compile_ignore_line,
)


class TestPatterns(unittest.TestCase):
    def test_star_matches_any_depth(self):
        p = compile_ignore_line("*.log")
        self.assertTrue(p.matches("a.log", False))
        self.assertTrue(p.matches("sub/a.log", False))
        self.assertFalse(p.matches("log.txt", False))
        self.assertFalse(p.matches("a/sub/x.log.txt", False))

    def test_dir_only(self):
        p = compile_ignore_line("build/")
        self.assertTrue(p.matches("build", True))
        self.assertTrue(p.matches("a/build", True))
        self.assertTrue(p.matches("build/x.py", False))
        self.assertFalse(p.matches("build", False))
        self.assertFalse(p.matches("rebuild", False))

    def test_anchored_to_gitignore_dir(self):
        p = compile_ignore_line("/root.txt")
        self.assertTrue(p.matches("root.txt", False))
        self.assertFalse(p.matches("sub/root.txt", False))

    def test_double_star_prefix(self):
        p = compile_ignore_line("**/temp")
        self.assertTrue(p.matches("temp", False))
        self.assertTrue(p.matches("a/b/temp", False))
        self.assertFalse(p.matches("temp2/x", False))

    def test_double_star_middle(self):
        p = compile_ignore_line("src/**/gen.py")
        self.assertTrue(p.matches("src/gen.py", False))
        self.assertTrue(p.matches("src/a/b/gen.py", False))
        self.assertFalse(p.matches("other/gen.py", False))

    def test_double_star_suffix(self):
        p = compile_ignore_line("docs/**")
        self.assertTrue(p.matches("docs/a.md", False))
        self.assertFalse(p.matches("docs", False))

    def test_question_mark(self):
        p = compile_ignore_line("file?.py")
        self.assertTrue(p.matches("file1.py", False))
        self.assertFalse(p.matches("file12.py", False))

    def test_comments_and_blanks_ignored(self):
        self.assertIsNone(compile_ignore_line("# comment"))
        self.assertIsNone(compile_ignore_line("   "))
        self.assertIsNone(compile_ignore_line(""))


class TestIgnoreStack(unittest.TestCase):
    def test_negation_last_rule_wins(self):
        stack = IgnoreStack()
        stack.push("", "*.log\n!keep.log")
        self.assertTrue(stack.ignored("a.log", False))
        self.assertFalse(stack.ignored("keep.log", False))

    def test_deeper_gitignore_overrides_root(self):
        stack = IgnoreStack()
        stack.push("", "*.log")
        stack.push("sub", "!special.log")
        self.assertTrue(stack.ignored("a.log", False))
        self.assertTrue(stack.ignored("sub/other.log", False))
        self.assertFalse(stack.ignored("sub/special.log", False))
        self.assertTrue(stack.ignored("other/deep.log", False))

    def test_patterns_are_relative_to_their_own_directory(self):
        stack = IgnoreStack()
        stack.push("src", "private.py")
        self.assertTrue(stack.ignored("src/private.py", False))
        self.assertFalse(stack.ignored("app/private.py", False))

    def test_default_excludes(self):
        stack = IgnoreStack()
        stack.push("", DEFAULT_EXCLUDES)
        self.assertTrue(stack.ignored("node_modules", True))
        self.assertTrue(stack.ignored("node_modules/pkg/index.js", False))
        self.assertTrue(stack.ignored("package-lock.json", False))
        self.assertTrue(stack.ignored("poetry.lock", False))
        self.assertTrue(stack.ignored(".venv", True))
        self.assertFalse(stack.ignored("src/app.py", False))
        self.assertFalse(stack.ignored("readme.md", False))


if __name__ == "__main__":
    unittest.main()
