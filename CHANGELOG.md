# Changelog

All notable changes to this project are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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

[Unreleased]: https://github.com/Zhuayu16/budgetpack/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/Zhuayu16/budgetpack/releases/tag/v0.1.0
