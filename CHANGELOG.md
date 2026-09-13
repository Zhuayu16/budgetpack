# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [0.2.0] - 2026-09-13

### Added

- Lazy reading pipeline: `scan(read_texts=False)` collects metadata only and
  the new `packer.materialize()` reads just the files that make the pack,
  re-checking the budget with exact token counts. On real repositories this
  removes 12-354x of disk I/O and speeds up end-to-end packing by 2.6-10.6x
  (benchmarks in README; reproducible via `benchmarks/bench_pack.py`).
- Scanner now walks with `os.scandir`, reusing directory-entry stat data
  instead of issuing a second stat per file.
- Ignore rules are matched through bucketed literal/suffix fast paths; a
  brute-force equivalence test pins the fast paths to the regex semantics.
- `pack` reports how many files and bytes it actually read.
- README benchmark charts generated from measured data
  (`benchmarks/make_charts.py`).
- Budget guarantee verified under exact tiktoken cl100k_base counting on
  requests / click / fastapi / django (all within a 32k budget).

### Changed

- `FileEntry.tokens` for metadata-only scans is an estimate (`size // 4`);
  exact counts are computed when files are materialized.
- `stats` still reads everything - it is the deep-inspection command.

## [0.1.0] - 2026-09-13

### Added

- `budgetpack pack` - pack a repository into a single markdown file under a
  strict token budget, highest-value files first.
- `budgetpack stats` - per-file token breakdown with priority scores and
  optional explanations (`--why`).
- Multi-signal prioritization: README/entry-point/manifest boosts, core
  directory boost, git-change heat, depth penalty, test-file penalty.
- Truncation pass: when whole files no longer fit, the best omitted file is
  truncated to use the leftover budget, clearly marked in the report.
- "Omitted files" table so nothing silently disappears from the pack.
- .gitignore subset parser (negation, `**`, anchoring, dir-only rules) plus
  built-in hygiene excludes (`node_modules`, lock files, caches, ...).
- Binary detection by extension and null byte; per-file size limit.
- Optional exact token counting via `pip install budgetpack[tokens]`
  (tiktoken/cl100k_base); zero-dependency chars/4 heuristic otherwise.
- `--include` / `--exclude` globs, `--stdout`, `--no-gitignore`,
  `--no-default-excludes`, `--max-file-size`.
- Cross-platform CI (Linux / Windows / macOS, Python 3.9-3.13).

[Unreleased]: https://github.com/Zhuayu16/budgetpack/compare/v0.2.0...HEAD
[0.2.0]: https://github.com/Zhuayu16/budgetpack/compare/v0.1.0...v0.2.0
[0.1.0]: https://github.com/Zhuayu16/budgetpack/releases/tag/v0.1.0
