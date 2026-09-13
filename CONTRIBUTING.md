# Contributing to budgetpack

Thanks for your interest! budgetpack is a small, dependency-free CLI, and we
try to keep it that way.

## Development setup

```bash
git clone https://github.com/Zhuayu16/budgetpack
cd budgetpack
pip install -e .[dev]

# run the tests (stdlib unittest - no pytest needed)
python -m unittest discover -s tests -v

# lint
ruff check src tests

# try your changes
budgetpack pack . --budget 5000 --stdout
```

## Project layout

```
src/budgetpack/
  gitignore.py    # .gitignore subset parser (also powers --include/--exclude)
  scanner.py      # filesystem walk, binary detection, git heat
  prioritize.py   # importance scoring
  packer.py       # greedy budget packing + truncation
  render.py       # markdown report and stats table
  tokens.py       # token counting (tiktoken optional, chars/4 fallback)
  cli.py          # argparse CLI
tests/            # stdlib unittest, deterministic (heuristic backend pinned)
```

## Ground rules

- **Zero required dependencies.** The standard library only. Optional extras
  (`[tokens]`) must fail soft when absent.
- **Tests are mandatory** for behavior changes; pin the heuristic token backend
  via `helpers.force_heuristic_tokens()` so numbers stay deterministic.
- **Windows-friendly.** No shell assumptions, always pass `encoding=` to file
  reads/writes, keep CLI output ASCII.
- **No tracking, no network calls** except the optional tiktoken BPE load.

## Release checklist (maintainers)

1. Replace every `Zhuayu16` placeholder (READMEs, pyproject, logo
   links inside `render.py`).
2. Bump `__version__` in `src/budgetpack/__init__.py` and update CHANGELOG.md.
3. `python -m unittest discover -s tests` and `ruff check src tests`.
4. `python -m build && twine upload dist/*`.
5. Tag the release: `git tag vX.Y.Z && git push --tags`.
