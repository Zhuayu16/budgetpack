"""A/B benchmark: eager vs lazy reading of budgetpack on real repositories.

The eager pipeline reads every readable file during the scan (v0.1.0
behavior); the lazy pipeline scans metadata only and materializes the pack by
reading just the chosen files. Both are timed with the chars/4 heuristic so
the comparison isolates the I/O change. When `tiktoken` is installed, a final
pass re-packs with the exact cl100k_base backend to verify the budget
guarantee holds under exact counting.

Usage:
    python benchmarks/bench_pack.py path/to/repoA path/to/repoB \
        [--budget 32000] [--runs 3] [--json out.json]
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

SRC = Path(__file__).resolve().parents[1] / "src"
sys.path.insert(0, str(SRC))

import budgetpack.tokens as btokens  # noqa: E402
from budgetpack.packer import materialize, pack  # noqa: E402
from budgetpack.prioritize import score_files  # noqa: E402
from budgetpack.render import render_markdown  # noqa: E402
from budgetpack.scanner import git_change_counts, scan  # noqa: E402


def run_eager(repo: Path, budget: int):
    t0 = time.perf_counter()
    entries = scan(repo)
    scored = score_files(entries, git_change_counts(repo))
    result = pack(scored, budget)
    render_markdown(result, repo)
    ms = (time.perf_counter() - t0) * 1000
    return ms, sum(e.size for e in entries if e.text is not None), result


def run_lazy(repo: Path, budget: int):
    t0 = time.perf_counter()
    entries = scan(repo, read_texts=False)
    scored = score_files(entries, git_change_counts(repo))
    plan = pack(scored, budget)
    result, reads = materialize(plan, repo, budget)
    render_markdown(result, repo)
    ms = (time.perf_counter() - t0) * 1000
    return ms, reads.bytes_read, result


def best(fn, repo: Path, budget: int, runs: int):
    best_run = None
    for _ in range(runs):
        run = fn(repo, budget)
        if best_run is None or run[0] < best_run[0]:
            best_run = run
    return best_run


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("repos", nargs="+", type=Path, help="checkouts to benchmark")
    ap.add_argument("--budget", type=int, default=32_000)
    ap.add_argument("--runs", type=int, default=3)
    ap.add_argument("--json", type=Path, default=None, help="write results here")
    args = ap.parse_args(argv)

    # Pin the heuristic backend so the A/B isolates the I/O change.
    btokens._encoding = None
    btokens._encoding_checked = True

    out: dict = {}
    for repo in args.repos:
        repo = repo.resolve()
        e_ms, e_bytes, e_res = best(run_eager, repo, args.budget, args.runs)
        l_ms, l_bytes, l_res = best(run_lazy, repo, args.budget, args.runs)
        out[repo.name] = {
            "budget": args.budget,
            "files_found": len(scan(repo, read_texts=False)),
            "eager_ms": round(e_ms, 1),
            "lazy_ms": round(l_ms, 1),
            "speedup": round(e_ms / l_ms, 2),
            "eager_read_mb": round(e_bytes / 1e6, 2),
            "lazy_read_mb": round(l_bytes / 1e6, 2),
            "packed": len(l_res.packed),
            "heuristic_used": l_res.used,
        }
        r = out[repo.name]
        print(
            f"{repo.name:12s} eager {r['eager_ms']:8.1f} ms | lazy {r['lazy_ms']:7.1f} ms "
            f"| {r['speedup']:5.2f}x | read {r['eager_read_mb']:6.2f} MB -> "
            f"{r['lazy_read_mb']:5.2f} MB | packed {r['packed']}"
        )

    try:
        import tiktoken

        btokens._encoding = tiktoken.get_encoding("cl100k_base")
        btokens._encoding_checked = True
    except Exception as exc:  # noqa: BLE001
        print(f"\ntiktoken unavailable ({exc}) - exact-backend verification skipped")
    else:
        print(f"\ncl100k_base verification (budget {args.budget:,}):")
        for repo in args.repos:
            repo = repo.resolve()
            entries = scan(repo, read_texts=False)
            scored = score_files(entries, git_change_counts(repo))
            plan = pack(scored, args.budget)
            result, _ = materialize(plan, repo, args.budget)
            ok = result.used <= args.budget
            out[repo.name]["cl100k_used"] = result.used
            out[repo.name]["cl100k_ok"] = ok
            print(
                f"  {repo.name:12s} packed {result.used:,} / {args.budget:,} tokens "
                f"({result.used / args.budget * 100:.1f}%) within budget: {ok}"
            )
    finally:
        btokens._encoding = None
        btokens._encoding_checked = True

    if args.json:
        args.json.write_text(json.dumps(out, indent=2), encoding="utf-8")
        print(f"\nsaved {args.json}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
