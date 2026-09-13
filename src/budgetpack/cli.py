"""Command-line interface: `budgetpack pack` and `budgetpack stats`."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from . import __version__
from .packer import pack
from .prioritize import score_file, score_files
from .render import render_markdown, render_stats
from .scanner import git_change_counts, scan

DEFAULT_BUDGET = 100_000
OUTPUT_NAME = "budgetpack-output.md"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="budgetpack",
        description=(
            "Pack a repository into an LLM-ready prompt under a strict token budget: "
            "highest-value files first, omissions reported, nothing wasted."
        ),
    )
    parser.add_argument("--version", action="version", version=f"budgetpack {__version__}")
    sub = parser.add_subparsers(dest="command", required=True)

    p_pack = sub.add_parser("pack", help="pack files under the token budget")
    p_pack.add_argument("path", nargs="?", default=".", type=Path, help="repository to pack")
    p_pack.add_argument(
        "-b", "--budget", type=int, default=DEFAULT_BUDGET, metavar="N",
        help=f"token budget for file contents (default: {DEFAULT_BUDGET:,})",
    )
    p_pack.add_argument(
        "-o", "--output", type=Path, default=None, metavar="FILE",
        help=f"output file (default: ./{OUTPUT_NAME})",
    )
    p_pack.add_argument(
        "--stdout", action="store_true", help="print the pack instead of writing a file"
    )
    p_pack.add_argument("-i", "--include", action="append", default=[], metavar="GLOB",
                        help="only files matching this glob (repeatable)")
    p_pack.add_argument("-e", "--exclude", action="append", default=[], metavar="GLOB",
                        help="skip files matching this glob (repeatable)")
    p_pack.add_argument("--no-gitignore", action="store_true", help="ignore .gitignore files")
    p_pack.add_argument("--no-default-excludes", action="store_true",
                        help="do not apply built-in excludes (node_modules, locks, ...)")
    p_pack.add_argument("--max-file-size", type=float, default=1.0, metavar="MB",
                        help="skip single files larger than this (default: 1.0)")

    p_stats = sub.add_parser("stats", help="show a per-file token breakdown")
    p_stats.add_argument("path", nargs="?", default=".", type=Path, help="repository to analyze")
    p_stats.add_argument(
        "--top", type=int, default=25, metavar="N", help="rows to show (default: 25)"
    )
    p_stats.add_argument(
        "--why", action="store_true", help="also explain each file's priority score"
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    # Make `budgetpack <path>` mean `budgetpack pack <path>`.
    if argv and not argv[0].startswith("-") and argv[0] not in ("pack", "stats"):
        argv.insert(0, "pack")
    args = build_parser().parse_args(argv)

    root = args.path.resolve()
    if not root.is_dir():
        print(f"budgetpack: not a directory: {args.path}", file=sys.stderr)
        return 2

    if args.command == "pack":
        return _cmd_pack(args, root)
    return _cmd_stats(args, root)


def _cmd_pack(args: argparse.Namespace, root: Path) -> int:
    output_name = (args.output or Path(OUTPUT_NAME)).name
    entries = scan(
        root,
        extra_excludes=[*args.exclude, output_name, OUTPUT_NAME],
        extra_includes=args.include,
        respect_gitignore=not args.no_gitignore,
        use_default_excludes=not args.no_default_excludes,
        max_file_size=int(args.max_file_size * 1_000_000),
    )
    if not entries:
        print("budgetpack: no readable files found", file=sys.stderr)
        return 1

    change_counts = git_change_counts(root)
    scored = score_files(entries, change_counts)
    result = pack(scored, args.budget)
    report = render_markdown(result, root)

    if args.stdout:
        sys.stdout.write(report)
        return 0

    output = (args.output or Path(OUTPUT_NAME)).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(report, encoding="utf-8")
    rel_note = ""
    if change_counts:
        rel_note = f", git heat considered for {len(change_counts)} files"
    print(
        f"Packed {len(result.packed)} files "
        f"({result.used:,} / {result.budget:,} tokens{rel_note}) -> {output}"
    )
    if result.omitted:
        print(f"{len(result.omitted)} files omitted - see the report's 'Omitted files' table.")
    return 0


def _cmd_stats(args: argparse.Namespace, root: Path) -> int:
    entries = scan(root)
    if not entries:
        print("budgetpack: no readable files found", file=sys.stderr)
        return 1
    change_counts = git_change_counts(root)
    total = sum(e.tokens for e in entries)
    rows = []
    for e in entries:
        s = score_file(e, change_counts)
        reason = s.reasons[0] if args.why and s.reasons else ""
        rows.append((e.relpath, e.tokens, s.score, reason))
    rows.sort(key=lambda r: -r[1])
    print(render_stats(rows, total, args.top))
    return 0


def run() -> None:
    raise SystemExit(main())


if __name__ == "__main__":
    run()
