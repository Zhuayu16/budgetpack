<div align="center">

<img src="assets/logo.svg" alt="budgetpack" width="640" />

**把整个仓库按 token 预算智能打包成一份 LLM 提示词。**

高价值文件优先装填。遗漏如实报告。不浪费一个 token。

[![PyPI version](https://img.shields.io/pypi/v/budgetpack)](https://pypi.org/project/budgetpack/)
[![Python](https://img.shields.io/pypi/pyversions/budgetpack)](https://pypi.org/project/budgetpack/)
[![CI](https://img.shields.io/github/actions/workflow/status/Zhuayu16/budgetpack/ci.yml?branch=main&label=CI)](https://github.com/Zhuayu16/budgetpack/actions)
[![Code style: ruff](https://img.shields.io/badge/code%20style-ruff-261230)](https://github.com/astral-sh/ruff)
[![License: MIT](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![GitHub stars](https://img.shields.io/github/stars/Zhuayu16/budgetpack?style=social)](https://github.com/Zhuayu16/budgetpack/stargazers)

[English](README.md) | 简体中文

</div>

---

把整个代码库一股脑塞给 Claude、ChatGPT 或 Cursor,lock 文件、生成代码和
测试会白白吃掉上下文 —— 甚至在看不见的地方被静默截断。**budgetpack 先问你
有多少预算,再像花钱一样把它花在刀刃上**:README 和入口文件最先装填,
低价值文件垫底,并生成一份报告,明确告诉你哪些文件被装进来了、哪些没有。

```terminal
$ budgetpack pack . --budget 6000
Packed 8 files (5,904 / 6,000 tokens) -> budgetpack-output.md
11 files omitted - see the report's 'Omitted files' table.
```

`budgetpack-output.md` 里面长这样:

```text
## Repository tree

● 已打包 · ◐ 因预算截断 · ○ 已省略

├── src/budgetpack/
│   ├── cli.py  ● 1,290        ← 最高优先级,最先装填
│   ├── gitignore.py  ● 1,114
│   ├── packer.py  ● 729
│   ├── scanner.py  ○ 1,410    ← 装不下了;如实报告,绝不静默丢弃
│   └── ...
├── pyproject.toml  ● 414
└── tests/  ...  ○ 已省略      ← 测试文件优先级本来就低

## Omitted files
| File | Tokens | Reason |
|---|---:|---|
| `src/budgetpack/scanner.py` | 1.4k | needs 1,410 tokens, only 96 left in budget |
```

把这份文件粘贴进任意 LLM 对话框,或直接让 Agent 读它。

## ✨ 特性

- **💸 预算优先的打包** —— 给它 1 万或 20 万 token,它以接近 100% 的
  利用率装满最有用的代码,绝不超过预算。
- **⚡ 惰性读取** —— 扫描阶段完全不解码文件内容,只有真正入选的文件才会
  被读取。在 7000 个文件的仓库上,这意味着最多 **354 倍的磁盘 I/O 节省**
  和 **6~10 倍**的端到端提速(见下方基准测试)。
- **🧠 多信号优先级评分** —— README 和入口文件权重最高,"git 改动热度"
  高的文件加分,测试和深层嵌套降权。每个文件的分数都可解释。
- **📋 没有任何文件会静默消失** —— 装不下的文件全部列在 *Omitted files*
  表里,附上 token 开销和原因。
- **✂️ 智能截断** —— 当只差一个大文件装不下时,budgetpack 会把它截断到
  恰好填满剩余预算,并在报告中明确标注。
- **🪶 零依赖** —— 纯 Python 标准库,单个小体积可执行文件。可选安装
  `budgetpack[tokens]` 启用 tiktoken 精确计数。
- **🤝 尊重你的仓库** —— 解析 `.gitignore`(含 `!` 取反与 `**`),默认
  跳过二进制、lock 文件、`node_modules` 等。
- **🔍 仓库体检** —— `budgetpack stats` 在打包之前先告诉你哪些文件在
  吞噬你的上下文。

## 🚀 快速开始

```bash
pipx install budgetpack      # 或:pip install budgetpack
```

```bash
# 以默认 10 万 token 预算打包当前仓库
budgetpack pack .

# 把大型 monorepo 压进 32k 上下文窗口
budgetpack pack ~/work/monorepo --budget 32000 -o context.md

# 只要源码、不要测试,直接接管道
budgetpack pack . --include "src/**" --exclude "tests/" --stdout
```

然后:打开 `budgetpack-output.md`,粘贴给你喜欢的 LLM,完事。

初来乍到看不懂代码库?先看分布:

```terminal
$ budgetpack stats . --top 5
  TOKENS   SHARE   SCORE  REASON / FILE
------------------------------------------------------------------------
    1,443   11.1%     230
                           src/budgetpack/render.py
    ...
```

## 🧠 工作原理

```mermaid
flowchart LR
    A[扫描<br/>gitignore · 二进制<br/>大小限制] --> B[评分<br/>多信号 + git 热度]
    B --> C[装填<br/>贪心策略,预算优先]
    C --> D[渲染<br/>目录树 · 文件 · 遗漏表]
```

评分信号(分高者优先;完整规则见
[`prioritize.py`](src/budgetpack/prioritize.py)):

| 信号 | 影响 |
|---|---|
| `README*` | +1000 —— 项目概览永远第一 |
| 入口文件(`main.py`、`cli.py`、`index.js`、`main.go`……) | +500 |
| 清单文件(`pyproject.toml`、`package.json`、`go.mod`、`Dockerfile`……) | +400 |
| `src/`、`lib/`、`app/`、`pkg/` 下的源码 | +150 ~ +270 |
| git 改动热度(提交次数) | 最高 +200 |
| 文档(`.md`) | +60 |
| 目录嵌套深度 | 每层 −20 |
| 测试文件 | −250 |
| 超大文件(>2 万 token,疑似生成物) | −100 |

token 计数默认用"字符数 ÷ 4"启发式;装上扩展即可精确计数:
`pip install "budgetpack[tokens]"`。

## 📊 基准测试

在真实仓库上实测(requests、click、fastapi、django;Windows 11、
Python 3.10、NVMe 固态;32k token 预算;取 3 次最优;2026-09-13)。
可用 [`benchmarks/bench_pack.py`](benchmarks/bench_pack.py) 复现。

![基准测试图表](assets/benchmark.png)

| 仓库 | 文件数 | v0.1.0 | v0.2.0 | 提速 | 磁盘 I/O |
|---|---:|---:|---:|---:|---|
| requests | 128 | 325 ms | 116 ms | **2.8×** | 1.57 → 0.13 MB |
| click | 174 | 219 ms | 86 ms | **2.6×** | 1.32 → 0.13 MB |
| fastapi | 3,137 | 2,942 ms | 277 ms | **10.6×** | 22.36 → 0.13 MB |
| django | 7,082 | 6,491 ms | 1,052 ms | **6.2×** | 46.05 → 0.13 MB |

提升来自架构改动:v0.1.0 在决策之前先把所有可读文件全部解码;v0.2.0 只扫
元数据、排名后再读取真正入选的文件。在 django 上,46 MB 的 I/O 被替换成
0.13 MB —— 恰好是最终打包内容的体积。

预算保证在精确计数下同样成立:用 `tiktoken` cl100k_base 对这四个仓库重新
打包,结果为 29,107 / 29,288 / 29,807 / 28,771 token —— 全部落在 32,000
预算之内(利用率 89.9%~93.1%;真实代码的精确计数比"字符÷4"更密,
budgetpack 宁可舍弃文件也绝不超预算)。

为什么要关心单文件的体积?因为最大的 context 杀手往往根本不是代码:

![上下文分布图表](assets/context-fit.png)

fastapi 最大的单个 context 杀手是一张 30.8 万 token 的 SVG 架构图 ——
**是整个 32k 预算的 10 倍** —— 就安静地躺在 `docs/` 里。`budgetpack
stats` 会在打包前揭示这一点,而打包器无论预算多大都能保持 96%~97% 的
利用率。

## 📖 CLI 参考

### `budgetpack pack [PATH]`

| 选项 | 说明 |
|---|---|
| `-b, --budget N` | 文件内容的 token 预算(默认 100,000) |
| `-o, --output FILE` | 输出文件(默认 `./budgetpack-output.md`) |
| `--stdout` | 打印到标准输出而不写文件 |
| `-i, --include GLOB` | 只保留匹配的文件(可重复) |
| `-e, --exclude GLOB` | 跳过匹配的文件(可重复) |
| `--no-gitignore` | 忽略 `.gitignore` |
| `--no-default-excludes` | 连 `node_modules`、lock 文件也扫描 |
| `--max-file-size MB` | 跳过超过该大小的单文件(默认 1 MB) |

### `budgetpack stats [PATH]`

| 选项 | 说明 |
|---|---|
| `--top N` | 显示行数(默认 25) |
| `--why` | 显示每个文件的评分原因 |

直接 `budgetpack .` 也行,等价于 `budgetpack pack .`。

## 🆚 同类对比

| | budgetpack | repomix | gitingest |
|---|---|---|---|
| token 预算控制 | ✅ 核心特性 | ❌ | ❌ |
| 按价值排优先级 | ✅ | ❌(目录树顺序) | ❌(目录树顺序) |
| 遗漏清单 | ✅ | ❌ | ❌ |
| 运行时依赖 | 无 | Node.js | Python |
| Web 界面 / 远程仓库 | 规划中(见 Roadmap) | ✅ | ✅ |

*截至 2026 年 9 月 v0.1.0,最新情况请看它们的文档。*
[repomix](https://github.com/yamadashy/repomix) 与
[gitingest](https://github.com/coderamp-labs/gitingest) 是优秀的"全量打包"
工具;budgetpack 是同一件事的"预算优先"做法。

## ❓ 常见问题

**为什么不直接全部拼接?**
上下文就是钱和注意力。lock 文件和生成代码可能在真正的源码出现之前就吃掉
半个上下文窗口。budgetpack 把窗口花在模型真正需要的东西上。

**token 计数准确吗?**
默认启发式(字符 ÷ 4)对典型代码误差约 10% 以内。安装
`budgetpack[tokens]` 可获得精确的 cl100k_base 计数。预算按当前后端严格执行。

**被排除的东西还能找回来吗?**
可以 —— `--no-default-excludes` 关闭内置规则,`-e`/`-i` 通配完全由你控制。

**输出应该放在哪?**
`budgetpack-output.md` 会写到你当前目录。建议加进 `.gitignore`(本仓库自己
就是这么做的),或者直接用 `--stdout`。

**支持 Windows 吗?**
支持 —— 纯标准库实现,CI 覆盖 Linux、macOS、Windows。

## 🗺️ Roadmap

- [ ] `--git-diff` 模式:只打包某个 ref 以来的改动(做评审提示词绝佳)
- [ ] JSON / XML 输出格式
- [ ] `budgetpack.toml` 项目配置文件
- [ ] 远程仓库支持(`budgetpack pack github://owner/repo`)
- [ ] 基于 tree-sitter 的符号级智能排序

## 🤝 参与贡献

欢迎 Issue 和 PR,见 [CONTRIBUTING.md](CONTRIBUTING.md)。全部代码约一千行、
纯标准库、测试完备 —— 就是要让人读得懂。

## ⭐ Star 历史

[![Star History Chart](https://api.star-history.com/svg?repos=Zhuayu16/budgetpack&type=Date)](https://star-history.com/#Zhuayu16/budgetpack&Date)

## 📄 许可证

[MIT](LICENSE) © budgetpack contributors
