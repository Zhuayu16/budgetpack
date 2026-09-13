import unittest

import helpers

helpers.force_heuristic_tokens()

from budgetpack.gitignore import (  # noqa: E402
    DEFAULT_EXCLUDES,
    IgnoreStack,
    compile_ignore_line,
    parse_gitignore_text,
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


def _regex_reference(pattern, relpath: str, is_dir: bool) -> bool:
    """The original regex-based semantics that fast paths must reproduce."""
    m = pattern.regex.search(relpath)
    if m is None:
        return False
    if pattern.dir_only and not is_dir:
        return m.end() < len(relpath)
    return True


class TestFastPathEquivalence(unittest.TestCase):
    """Fast string matching must agree with the regex on every input."""

    LINES = [
        "*.log", "!keep.log", "build/", "node_modules/", "/root.txt", "**/temp",
        "src/**/gen.py", "docs/**", "file?.py", "*.min.js", "package-lock.json",
        "*.egg-info/", "sub/", "*.lock", "main.py", "temp", "a*",
    ]
    PATHS = [
        "a", "a/b", "build", "build/x.py", "a/build", "a/build/x.py", "rebuild",
        "x.log", "a/x.log", "a.b.log/c.txt", "node_modules", "node_modules/pkg/i.js",
        "src/gen.py", "src/a/b/gen.py", "other/src/gen.py", "temp", "a/temp",
        "a/temp/b/c.py", "docs/a.md", "docs", "docs/a/b.md", "file1.py", "file12.py",
        "root.txt", "sub/root.txt", "keep.log", "a/keep.log", "sub", "sub/keep.log",
        "app.min.js", "vendor/app.min.js/map", "pkg.egg-info", "pkg.egg-info/x.py",
        "requirements.lock", "main.py", "deep/nest/ed/main.py", "tempname", "xtemp",
    ]

    def test_fast_matches_agree_with_regex(self):
        for line in self.LINES:
            pattern = compile_ignore_line(line)
            self.assertIsNotNone(pattern, line)
            for relpath in self.PATHS:
                for is_dir in (True, False):
                    self.assertEqual(
                        pattern.matches(relpath, is_dir),
                        _regex_reference(pattern, relpath, is_dir),
                        f"pattern {line!r} path {relpath!r} is_dir={is_dir}",
                    )


def _stack_reference(stack_lines, relpath: str, is_dir: bool) -> bool:
    """Old stack algorithm (sequential, last-match-wins) with regex semantics."""
    for base, text in reversed(stack_lines):
        if base:
            prefix = base + "/"
            if not relpath.startswith(prefix):
                continue
            sub = relpath[len(prefix) :]
        else:
            sub = relpath
        for pat in reversed(parse_gitignore_text(text)):
            if _regex_reference(pat, sub, is_dir):
                return not pat.negated
    return False


class TestStackBucketEquivalence(unittest.TestCase):
    """The bucketed IgnoreStack must agree with sequential regex matching."""

    STACKS = [
        [("", "*.log\nbuild/\n!keep.log\nnode_modules/\n*.min.js\n")],
        [("", "build/\n*.log"), ("sub", "!build\n!special.log")],
        [("src", "private.py\ngen.py"), ("", "**/temp\n/docs/**")],
    ]
    PATHS = TestFastPathEquivalence.PATHS + [
        "src/private.py", "src/x/private.py", "app/private.py",
        "sub/build", "sub/build/x.o", "sub/special.log", "docs/a.md",
        "x/temp/y", "a/temp", "build", "build/z", "keep.log", "sub/other.log",
    ]

    def test_bucketed_stack_matches_sequential_reference(self):
        for stack_lines in self.STACKS:
            stack = IgnoreStack()
            for base, text in stack_lines:
                stack.push(base, text)
            for relpath in self.PATHS:
                for is_dir in (True, False):
                    self.assertEqual(
                        stack.ignored(relpath, is_dir),
                        _stack_reference(stack_lines, relpath, is_dir),
                        f"stack {stack_lines} path {relpath!r} is_dir={is_dir}",
                    )


if __name__ == "__main__":
    unittest.main()
