"""Generate the README charts from measured benchmark data.

Uses benchmarks/results-v0.1.0.json and benchmarks/results-0.2.0.json (both
produced by bench_pack.py runs recorded in CHANGELOG.md) plus live
budgetpack runs for the fastapi repository breakdown.

Requires matplotlib (dev-only):  pip install matplotlib
Run from the repository root:    python benchmarks/make_charts.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

import matplotlib  # noqa: E402

import budgetpack.tokens as btokens  # noqa: E402

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from budgetpack.packer import materialize, pack  # noqa: E402
from budgetpack.prioritize import score_files  # noqa: E402
from budgetpack.scanner import git_change_counts, scan  # noqa: E402

ASSETS = ROOT / "assets"
V010 = json.loads((ROOT / "benchmarks" / "results-v0.1.0.json").read_text(encoding="utf-8"))
V020 = json.loads((ROOT / "benchmarks" / "results-0.2.0.json").read_text(encoding="utf-8"))
REPOS = ["requests", "click", "fastapi", "django"]

# Pin the heuristic backend for reproducible numbers.
btokens._encoding = None
btokens._encoding_checked = True

C_V010, C_EAGER, C_LAZY = "#c9d1d9", "#58a6ff", "#1a7f37"
plt.rcParams.update({
    "font.size": 10, "axes.spines.top": False, "axes.spines.right": False,
    "axes.grid": True, "grid.color": "#eaeef2", "axes.axisbelow": True,
})

REPO_ROOT = Path(sys.argv[1]) if len(sys.argv) > 1 else None


def chart_benchmark() -> None:
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10, 4.0))

    x = range(len(REPOS))
    width = 0.27
    v010 = [V010[r]["ms_best"] for r in REPOS]
    eager = [V020[r]["eager_ms"] for r in REPOS]
    lazy = [V020[r]["lazy_ms"] for r in REPOS]
    bars1 = ax1.bar([i - width for i in x], v010, width, label="v0.1.0", color=C_V010)
    bars2 = ax1.bar(list(x), eager, width, label="v0.2.0 (eager read)", color=C_EAGER)
    bars3 = ax1.bar([i + width for i in x], lazy, width, label="v0.2.0 (lazy read)", color=C_LAZY)
    for bars in (bars1, bars2, bars3):
        ax1.bar_label(bars, fmt="%.0f", fontsize=8, padding=1)
    for i, r in enumerate(REPOS):
        ax1.annotate(f"{V010[r]['ms_best'] / V020[r]['lazy_ms']:.1f}x",
                     (i + width, lazy[i]), ha="center", va="bottom",
                     fontsize=9, fontweight="bold", color=C_LAZY, xytext=(16, 14),
                     textcoords="offset points")
    ax1.set_xticks(list(x), REPOS)
    ax1.set_ylabel("end-to-end pack time, best of 3 (ms)")
    ax1.set_title("Pack time on real repositories (32k budget)", fontsize=11)
    ax1.set_ylim(0, max(v010) * 1.22)
    ax1.legend(frameon=False, fontsize=9)

    eager_mb = [V020[r]["eager_read_mb"] for r in REPOS]
    lazy_mb = [V020[r]["lazy_read_mb"] for r in REPOS]
    ax2.bar([i - 0.2 for i in x], eager_mb, 0.38, color=C_V010,
            label="v0.1.0: reads everything")
    ax2.bar([i + 0.2 for i in x], lazy_mb, 0.38, color=C_LAZY,
            label="v0.2.0: reads what ships")
    for i, r in enumerate(REPOS):
        ratio = V020[r]["eager_read_mb"] / V020[r]["lazy_read_mb"]
        lift = (0, 4) if eager_mb[i] > 5 else (0, 4 + 18 * (i % 2))
        ax2.annotate(f"{eager_mb[i]:.2f} \u2192 {lazy_mb[i]:.2f} MB  ({ratio:.0f}x less I/O)",
                     (i, eager_mb[i]), ha="center", va="bottom", xytext=lift,
                     textcoords="offset points", fontsize=8.5, fontweight="bold",
                     color="#1a5c2a")
    ax2.set_xticks(list(x), REPOS)
    ax2.set_ylabel("bytes read from disk (MB)")
    ax2.set_title("Disk I/O per pack (32k budget)", fontsize=11)
    ax2.set_ylim(0, max(eager_mb) * 1.3)
    ax2.legend(frameon=False, fontsize=9)

    fig.tight_layout()
    fig.savefig(ASSETS / "benchmark.png", dpi=200)
    plt.close(fig)


def chart_context_fit(repo: Path) -> None:
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(10, 4.2))

    entries = scan(repo)
    scored = score_files(entries, git_change_counts(repo))
    top = sorted(scored, key=lambda s: -s.entry.tokens)[:10]
    names = ["/".join(s.entry.relpath.split("/")[-2:]) for s in top][::-1]
    tokens = [s.entry.tokens for s in top][::-1]
    ax1.barh(names, tokens, color=C_EAGER)
    ax1.bar_label(ax1.containers[0], fmt="%.0f", fontsize=8, padding=2)
    ax1.set_xlabel("tokens (chars/4)")
    ax1.set_title(f"Where the context budget goes - {repo.name}, top files", fontsize=11)
    ax1.set_xlim(0, max(tokens) * 1.15)
    ax1.tick_params(axis="y", labelsize=8)
    ax1.grid(axis="y", visible=False)

    budgets = [4_000, 8_000, 16_000, 32_000, 64_000]
    utils, packed = [], []
    for budget in budgets:
        entries = scan(repo, read_texts=False)
        plan = pack(score_files(entries, git_change_counts(repo)), budget)
        result, _ = materialize(plan, repo, budget)
        utils.append(result.used / budget * 100)
        packed.append(len(result.packed))
    labels = [f"{u:.1f}%\n{n} files" for u, n in zip(utils, packed)]
    bars = ax2.bar([f"{b // 1000}k" for b in budgets], utils, 0.55, color=C_LAZY)
    ax2.bar_label(bars, labels=labels, fontsize=8.5, padding=2)
    ax2.set_xlabel("token budget")
    ax2.set_ylabel("budget utilization (%)")
    ax2.set_title(f"Budget utilization - {repo.name}", fontsize=11)
    ax2.set_ylim(0, 118)
    ax2.grid(axis="x", visible=False)

    fig.tight_layout()
    fig.savefig(ASSETS / "context-fit.png", dpi=200)
    plt.close(fig)


if __name__ == "__main__":
    if REPO_ROOT is None:
        sys.exit("usage: python benchmarks/make_charts.py path/to/fastapi-checkout")
    ASSETS.mkdir(exist_ok=True)
    chart_benchmark()
    chart_context_fit(REPO_ROOT.resolve())
    print(f"written: {ASSETS / 'benchmark.png'}")
    print(f"written: {ASSETS / 'context-fit.png'}")
