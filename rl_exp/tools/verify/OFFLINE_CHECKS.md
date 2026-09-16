# 离线套件规范（OFFLINE_CHECKS.md）

本文件是 `rl_exp\tools\verify\` 下离线检查的**规则与成本口径**。改这套东西之前先读它；
新增一条检查按 §4 走。规则不是建议——每条都有一个闸门在看，见 §7。

## 1 入口与清单

- 唯一入口：`run_offline_checks.bat`（只做主机 python 引导：`paths.yaml` → `host_paths.py`
  → `RL_ISAAC_ROOT` 兜底，然后把参数透传给 runner）。
- **唯一检查清单**：`offline_suite.py` 的 `CHECKS`。bat 不再逐条列检查——两份清单必然
  漂移成"跑的不是写的那份"，`check_suite_shape.py` 会拦。
- 加一条 = 在 `CHECKS` 里加一行（标签，argv）。顺序即 `[i/N]` 编号，版本记录/ACCEPTANCE
  引用它，所以**只追加，不重排**。

## 2 成本模型（为什么它会越来越卡）

一条检查 = 一个独立进程。它的固定开销是解释器 + `torch`/`isaaclab` import，**实测 ~2.5s**，
而现行检查里约 2/3 是这种"import 税"型检查（第一句断言之前就先付 2.5s）。所以套件成本是：

```
总成本 ≈ (检查条数 × 2.5s) + Σ(每条检查自己做的事)
```

真实踩过的两个坑（v0.20 那一轮，170s → 35s）：

1. **冻结数据被反复解析**：`__post_init__` 链每个方法都 `_load_params()` 一次，一次 cfg
   构造解析 9 遍同一份冻结 yaml（~50ms/遍，单个 manifest 用例 210 遍）。冻结的是**文件**，
   不是解析出来的 Python 对象 ⇒ 解析结果缓存 + 每次 `deepcopy` 给调用方
   （`test_params_isolation.py` 看守"不共享同一棵树"）。
2. **进程内重复打主机树**：`combination()` 每次跑 4 个 git 子进程（IsaacLab 树 / rsl_rl），
   而 golden 检查每任务问一次、`--verify` 每次问一次 ⇒ 进程内缓存，ceiling 写在
   `check_cfg_lock.py` 的 docstring 里（测试要伪造 git 时调 `combination.cache_clear()`）。

结论（写新检查前先问自己）：**这个检查有没有在重复付已经付过的钱？**（重复解析、重复
git/子进程、重复构造同一个 cfg。）

## 3 预算（谁看守、怎么合法提高）

两个数写在 `offline_suite.py` 顶部，故意放代码里：提高预算是一次**可 review 的动作**。

| 常量 | 现在的值 | 口径 |
|---|---|---|
| `PER_CHECK_BUDGET_S` | 25 | 单条检查**单独跑**的秒数上限 |
| `SERIAL_BUDGET_S` | 400 | 全部检查各自秒数的**和**（不是墙钟） |

- 单条超预算先**单独重跑一次**再定罪：一波 6 个并发时它和别人抢机器，直接判红会变成
  一条"机器忙就红"的闸，第一次误报就会被人关掉（`--self-test` 覆盖了"只有单独跑也超时才
  算超预算"这条）。
- **和**而不是墙钟：墙钟随核数/`--jobs` 变，用墙钟等于给机器速度设闸；"和"才是
  版本迭代里真正在涨的那个数（170s → 200s+）。
- 超预算的出口只有两个：把检查改便宜（优先），或在**同一个 commit 里**抬这两个数并说明
  理由。`OFFLINE_SUITE_BUDGET_EXCEEDED` 的输出里就写了这句话。

## 4 加一条离线检查

1. 文件放 `rl_exp/tools/verify/`，命名 `check_<被看守的东西>.py`（闸门）或
   `test_<被测的东西>.py`（负测试/falsifier）；stdlib 优先，能不起 isaaclab 就不起。
2. 通过：打印自己的判词（末行），`sys.exit(0)`；失败：打印**具体**问题（不是"assert failed"），
   `sys.exit(1)`。runner 会把末行当作 summary，失败时回放全量输出。
3. **不要**在检查里再 spawn 解释器（每个子进程重付 2.5s）。确需进程边界（例如"两个
   `PYTHONHASHSEED` 下摘要必须一致"）时，在 `check_suite_shape.py` 的 `SPAWN_ALLOWED` 里
   声明个数 + 理由；声明的数会和代码里的实际数比对，长了就要显式改。
4. **写路径契约**：只许读仓，或只写自己 `tempfile` 的目录。**不要在并行下写仓内共享路径**——
   顺序跑时那只是互相覆盖，并行跑就是要写仓的（golden 更新、`--json` 落盘）必须
   挂在显式 flag 后面，且**不许**把那个 flag 加进 `CHECKS`。
5. 负测试（falsifier）的标准：先证明"把修复还原回去它必失败"。写法参考
   `test_cfg_lock_gate.py` / `test_configclass_fields_gate.py` / `test_run_manifest.py`
   的 `negative/*`，或临时脚本钉住被绕过的分支（本轮用过一次：钉死 `combination_key`
   看 `verify/another-combination` 是否真红）。
6. 在 `CHECKS` 追加一行；跑 `python rl_exp\tools\verify\offline_suite.py` 一次看
   `serial` 涨了多少——那行数字就是这条检查的成本，写进 commit message。
7. 若这条检查会让某些既有版本/记录失效，按仓库版本记录纪律补 NOTES/ACCEPTANCE（见
   `.codemaker/rules/versioning.mdc`）。

## 5 什么时候它**不该**进离线套件

- 要起仿真 / 要 GPU / 要 Isaac Sim app（那就不是离线：`smoke_test.py`、`view_terrain.py`、
  `terrain_preflight.py` 这类留在目录里但不进 `CHECKS`）。
- 单次超过 25s 且砍不动：先用 `--json` 落报告 + 窄化断言（`--tasks`、`--only` 那类入口），
  或拆成"快速契约 + 慢速离线"两层，别把 25s 直接抬到 120s。
- 只是"顺手也验一下"的弱断言：进套件就要长期付 import 税，别为它加一条。

## 6 谁守这些规则

| 规则 | 看守 |
|---|---|
| 清单唯一来源 / 条目存在且不重复 / 未声明的解释器子进程 | `check_suite_shape.py`（静态，stdlib，venv 坏了也能跑） |
| 预算（单条 + 总和） | `offline_suite.py`（需要计时，只能在 runner 里） |
| 调度器本身（退出码、fail-fast、坏解释器、预算只怪单独也慢的） | `python rl_exp\tools\verify\offline_suite.py --self-test` |
| 写路径契约 | **无闸门**，只有 §4.4 的约定 + 本轮一次人工审计（见下）。新增检查要写仓的话，自己核一遍 |
| 冻结 yaml 不被跨 cfg 共享 | `test_params_isolation.py` |

写到"谁守规则"这一栏时要有闸门，否则就是欠账——本仓已有先例：横幅卫生当初只是约定，
`echo ... task -> recipe ...` 把一条横幅写成了仓库根的垃圾文件且套件照样绿，后来才有
`check_suite_banners.py`。

## 7 本轮（2026-09-16）写路径审计结论

套件内检查的写操作只有两类：① 自己的 `tempfile` 目录；② 仅在 `--update` / `--update-locks`
/ `--json` 下写仓，而套件**不传**这些 flag。审计时用 git status + mtime 扫过整仓，
`config` 那类遗留垃圾没有再出现。
