# ISAAC_ROOT 参数化收尾：执行探针记录（2026-10-10）

## 适用范围

`work/active/isaac-root-parameterisation.md` 的执行记录。对象 = 该事项 `close_when` 的两半：
① 三处参数化调用点在**无 junction 布局**下确实生效；② 摘掉 `E:\IsaacLab\ablation_harness` 之后，
一条 train/eval 命令能起来且日志目录的 glob 落在真实 IsaacLab 树。

本记录只写这两半的现场读数与落点。`paths.yaml` / `RL_ISAAC_ROOT` 的解析口径归 `host_paths.py`
与其闸门，不复述；一次性探针 spec 在仓外，不作复读路径（见「未覆盖边界」）。

## 验收条件

- (a) `E:\IsaacLab\ablation_harness` 不存在（junction 已摘）。
- (b) 三处调用点读的是同一个来源，且**在无 junction 下**各自给出真实 IsaacLab 树：
  `eval.py` 的 `_ISAAC_ROOT`、`run_ablation.py` 的 `_ISAAC_ROOT`、`_log_dir_for_tag` 的 glob。
- (c) `rl_exp\tools\verify\run_offline_checks.bat` 全绿。
- (d) 一条 train/eval 命令能走完（`sweep done, failures=0`），日志目录落在 `E:\IsaacLab\logs\rsl_rl\`
  下的真实树而不是本仓。
- 判据形状：全绿按套件自己的收尾行判；train/eval 那半按进程真的起了、真的写了产物判，不看声明。

## 结果

### (a) junction 已摘

`dir /AL "E:\IsaacLab" | findstr /I "ablation_harness"` 无输出（无重解析点），
`if exist "E:\IsaacLab\ablation_harness"` → `MISSING`。`HARNESS.md` 部署形态段那句"可 rmdir"已是既成事实。

### (b) 三处调用点（代码面）

| 落点 | 形态 |
|---|---|
| `ablation_harness/eval.py:109-111` | `_find_isaac_root()` 直接委托 `host_paths.isaac_root()` |
| `ablation_harness/eval.py:122` | `_ISAAC_ROOT = _find_isaac_root()` |
| `ablation_harness/run_ablation.py:44` | `_ISAAC_ROOT = host_paths.isaac_root()`（模块级，唯一来源） |
| `ablation_harness/run_ablation.py:47-59` | `_isaac_root()` 在 `None` 时硬停并指名 `paths.yaml` / `RL_ISAAC_ROOT`，不回落父目录 |
| `ablation_harness/run_ablation.py:62-74` | `_log_dir_for_tag` 在 `_isaac_root().glob("logs/rsl_rl/*/*")` 上匹配，不再拿"harness 的父目录" |

### (c) 离线闸

`rl_exp\tools\verify\run_offline_checks.bat` → `ALL_OFFLINE_CHECKS_PASSED (37/37)`
（改动前、改动后各跑一次；两次同一行）。

### (d) 真跑：探针一（新训）+ 探针二（复用路径）

两条探针都从本仓根用 `paths.yaml` 记录的解释器发起，spec 在仓外（一次性，见「未覆盖边界」）。

| 探针 | 形态 | 现场读数 |
|---|---|---|
| 一 | 新训 `max_iterations=2`（`Lizard2-Flat-v3`） | 训练完成，日志目录真落在 `E:\IsaacLab\logs\rsl_rl\lizard2_v3\2026-10-10_11-41-26_isaac_root_probe`；harness 的 glob 打印的就是这个绝对路径 ⇒ **glob 半成立**。随后 `[ABLATION] ERROR: expected model_2.pt not found under <同路径>`（缺陷二，见下） |
| 二 | 复用探针一的 checkpoint（`max_iterations=1`，`model_1.pt` 已在）→ 跳过训练，直接打 eval 半 | 修复后：`[EVAL] protocol=Locomotion-Eval-v3 … run_id=Lizard2-Flat-v3_isaac_root_probe_it1_nominal_seed123` 起并有终局读数，`[EVAL] wrote results/…/{eval.json,record.json}`，`[ABLATION] sweep done, failures=0` ⇒ **eval 半成立** |

### 本次修掉的一处（进本项 landing）

`run_ablation.py:117` 的 eval 子进程原用相对路径 `"ablation_harness/eval.py"`，而 `cwd=_ISAAC_ROOT`
⇒ 只有 `E:\IsaacLab\ablation_harness` junction 在时才成立。摘掉 junction 后实测：

```
cd /d E:\IsaacLab && E:\IsaacLab\env_isaaclab\Scripts\python.exe ablation_harness/eval.py --help
→ python.exe: can't open file 'E:\IsaacLab\ablation_harness\eval.py': [Errno 2] No such file or directory
```

改为 `str(_HARNESS_DIR / "eval.py")`（`_HARNESS_DIR` 是模块级绝对路径）。`eval.py` 自定位
`_HARNESS_DIR`/`_RESULTS_ROOT`（`eval.py:91-92`），命令其它部分不依赖 cwd，故绝对路径是充分修法。
**不加模块、不改测量语义 ⇒ 按 `work/active/harness-version-anchor-missing.md` 立下的分类不进编号**
（与其中"评测启动的 `--viz none` 取代 `能走通。
判据、口径与修法归另立事项，本项不动。

## 证据引用

- 事项：`work/active/isaac-root-parameterisation.md`。
- 代码：`ablation_harness/run_ablation.py`（`:44`、`:47-59`、`:62-74`、`:117`）、
  `ablation_harness/eval.py`（`:109-111`、`:122`）、`ablation_harness/host_paths.py:76-97`。
- 文档：`ablation_harness/HARNESS.md` 的「部署形态」bullet —— 原句只写到 junction "已废、可 rmdir"，
  本次补上"不以它为前提（子进程入口一律绝对路径）"这个代码侧事实；机器本地的"已摘"不写进该文件。
- 训练器侧命名：`rsl_rl/runners/on_policy_runner.py:112`、`:127-134`（机器本地 site-packages）。
- 复读命令（都在本仓根跑，除标注外）：
  - 离线闸：`rl_exp\tools\verify\run_offline_checks.bat`
  - junction 已摘：`if exist "E:\IsaacLab\ablation_harness" (echo EXISTS) else (echo MISSING)`
  - 修掉的那处（等价最小复现，任选一个不存在的相对路径即可）：
    `cd /d E:\IsaacLab && E:\IsaacLab\env_isaaclab\Scripts\python.exe ablation_harness/eval.py --help`
- 探针产物：探针一的日志目录留在 `E:\IsaacLab\logs\rsl_rl\lizard2_v3\2026-10-10_11-41-26_isaac_root_probe`
  （机器本地，不进仓）；探针二写在 `results/locomotion_eval_v3/smoke/` 的那一行与目录**已删除**（见下）。

## 未覆盖边界

- 探针 spec 是一次性文件（仓外 `%TEMP%`），不留仓、也不作复读路径；本记录里可复读的只有离线闸、
  junction 检查与那条 `can't open file` 最小复现。
- 探针二按 `group=smoke` 落产物后**已删除**并回滚 `smoke/summary.csv`：未训策略的读数进任何表都是噪声，
  且它会把该组既有行判成条件冲突。删掉的东西只承担"eval 半能起"这一个证明，本记录不据此声称任何分数。
  要重看这条路径，任何一条**需要真训**的 spec 都行 —— 但会先被上面那处缺陷挡住。
- 探针用的是 `Lizard2-Flat-v3` 一个任务、一条 nominal eval，不覆盖其它任务 id、robust 模式与多 checkpoint
  排程；`--summarize`/`--by-terrain` 两态本次未碰（它们不调 `_isaac_root()`）。
- 本项不评价 `paths.yaml` 的解析口径（归 `host_paths.py` 与其闸门），也不动 `paths.yaml` 的机器本地事实。
- 缺陷二只登记不修，其判据与取舍（是改凭据命名还是改"预算已用完"的判据）归另立事项。
