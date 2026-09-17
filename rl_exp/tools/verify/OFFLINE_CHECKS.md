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

## 3 执行超时与成本预算（两回事，不可互替）

### 3.1 执行超时：保证套件一定会结束

| 常量 | 现值 | 口径 |
|---|---|---|
| `PER_CHECK_TIMEOUT_S` | 180 | 单条检查的墙钟上限，超了**杀掉整棵进程树**并以 `124` 记失败 |

预算是在检查**返回之后**才评估的，所以它救不了"永远不返回"的检查：遍历/循环最终会返回，
预算能事后抓住；卡死则连预算判断都执行不到（用户 2026-09-16 指出）。超时是这条兜底，故意
设得远高于成本预算——让"慢"被报成成本问题，而不是被当成卡死杀掉。

杀的是**整棵树**（Windows `taskkill /F /T`）：只杀直接子进程时，活下来的孙进程会攥着管道，
紧随其后的 `communicate()` 会永久阻塞——套件恰好卡死在它本该放弃的地方。`--self-test` 覆盖了
两种情形：`永不返回` 与 `留下一个活得比它久的子进程`，两者都必须在 ~1s 内结束（1s 超时夹具），
而不是等满 30s 的睡眠。

### 3.2 成本预算：控制退化，按"先复核再定性"走

| 常量 | 现值 | 口径 |
|---|---|---|
| `PER_CHECK_BUDGET_S` | 25 | 单条检查在**安静机器上单独跑**的秒数上限 |
| `SERIAL_BUDGET_S` | 400 | 全部检查各自秒数的**和**（不是墙钟） |

**波内数字只是疑似，不是成本指标。** 一波 6 个并发把"检查成本"和"资源竞争"加进同一个数，
它能在机器仅仅比较忙的时候越线。所以超预算的正确动作是**复核**，不是改阈值：

1. **标记"性能待确认"**：波内超预算先记为待确认，**不归因**给检查。
2. **低负载复核（runner 自动）**：单条 → 同一条检查单独跑（先做最重的 3 条）；总量 →
   `--jobs 1` 把全表重跑一遍，机器安静时得到的才是成本。
3. **只有安静下仍超预算**才算成本退化 ⇒ `OFFLINE_SUITE_COST_REGRESSION` 红。
4. **出口两个**：把检查改便宜（优先）；或已确认新增覆盖值得这个价时，在**同一个 commit** 里
   抬这两个数并写明理由。

**抬阈值不是误报后的默认动作**：为了让红灯变绿而抬数，等于把"套件在变慢"这条信号一起抬掉，
而且教会下一个人再抬一次。复核后落在预算内的波内超标，**什么都不用改**（runner 会打印
"no reason to touch the budget"）。

'和'而不是墙钟：墙钟随核数/`--jobs` 变，用墙钟等于给机器速度设闸；'和'才是版本迭代里
真正在涨的那个数（170s → 232s）。

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
6. 在 `CHECKS` 追加一行；跑 `python rl_exp\tools\verify\offline_suite.py` 一次，看成功行里的
   `wave Ns / quiet Ns` 涨了多少——那才是这条检查的成本，写进 commit message。
7. 若这条检查会让某些既有版本/记录失效，按仓库版本记录纪律补 NOTES/ACCEPTANCE（见
   `.codemaker/rules/versioning.mdc`）。

## 5 什么时候它**不该**进离线套件

- 要起仿真 / 要 GPU / 要 Isaac Sim app（那就不是离线：`smoke_test.py`、`view_terrain.py`、
  `terrain_preflight.py` 这类留在目录里但不进 `CHECKS`）。
- 单次超过 25s 且砍不动：先用 `--json` 落报告 + 窄化断言（`--tasks`、`--only` 那类入口），
  或拆成"快速契约 + 慢速离线"两层，别把 25s 直接抬到 120s。
- "很慢但会返回"的检查：超时**不会**替你优化它，那只是保证套件别卡死；判它贵不贵的地方是预算。
- 只是"顺手也验一下"的弱断言：进套件就要长期付 import 税，别为它加一条。

## 6 谁守这些规则

| 规则 | 看守 |
|---|---|
| 清单唯一来源 / 条目存在且不重复 / 未声明的解释器子进程 | `check_suite_shape.py`（静态，stdlib，venv 坏了也能跑） |
| 成本预算（波内=疑似 → 低负载复核 → 只在安静下超预算才算退化） | `offline_suite.py`（需要计时，只能在 runner 里） |
| 执行超时（永不返回 / 留下存活的子进程，都要被杀掉并让套件结束） | `_run_one` 的整树击杀；`--self-test` 两例夹具 |
| 调度器本身（退出码、fail-fast、坏解释器、负载不背锅、超时） | `python rl_exp\tools\verify\offline_suite.py --self-test` |
| 写路径契约 | **无闸门**，只有 §4.4 的约定 + 本轮一次人工审计（见下）。新增检查要写仓的话，自己核一遍 |
| 冻结 yaml 不被跨 cfg 共享 | `test_params_isolation.py` |

写到"谁守规则"这一栏时要有闸门，否则就是欠账——本仓已有先例：横幅卫生当初只是约定，
`echo ... task -> recipe ...` 把一条横幅写成了仓库根的垃圾文件且套件照样绿，后来才有
`check_suite_banners.py`。

## 7 本轮（2026-09-16）写路径审计结论

套件内检查的写操作只有两类：① 自己的 `tempfile` 目录；② 仅在 `--update` / `--update-locks`
/ `--json` 下写仓，而套件**不传**这些 flag。审计时用 git status + mtime 扫过整仓，
`config` 那类遗留垃圾没有再出现。
