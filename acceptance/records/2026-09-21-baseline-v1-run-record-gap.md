# baseline/v1 记录在案那次 run 的记录缺口

## 适用范围

覆盖 `E:\IsaacLab\logs\rsl_rl\**\run_manifest.json` 的**完整性普查**（88 个 run 目录，2026-09-21 读），
以及 `baseline/v1` 记录在案那次 run 的逐字段读数。不含记录机制本身的设计、修复或重建评级。

## 验收条件（读数前定）

- **完整** = `stages` 同时含 `pre_make` + `env_constructed` + `ready_to_learn`，且 `failures` 为空；
  缺任一即"半截"。
- 以 `python -m rl_exp.tools.runrecord.manifest --verify <run 目录>` 的 BLOCKING 行数为准，
  不以"目录存在、checkpoint 还在"当完整。

## 结果

- 88 个 run 里**半截的只有 2 个**，都属 `lizard_baseline_v1` 的 2026-09-20 12 点窗口（`12-20-22`、
  `12-23-09`），failure 同为 `pre_make recording failed: AttributeError: 'NoneType' object has no
  attribute 'strip'`。
- **不是机制常态**：同任务更早的 run `2026-09-18_18-31-08` 三阶段齐全、0 failure；同日同机制的
  teacher run（`2026-09-20_14-45-09` 起）也齐全。窗口对应 `35e716c`（baseline 线自有 recipe 模块
  与类构造器）前后的代码状态。
- **记录在案那次**（`12-23-09`）实读：`--verify` → `RUN_MANIFEST_DRIFT (3)`；`stages` 只到
  `env_constructed`；**无 `argv`、无 repo rev**（T0 从未落盘）；`checkpoints.json` 119 条
  `t1_sha256` 全为 `null`、`status: incomplete`。仍在的是 `params/env.yaml` + `params/agent.yaml`
  （配方与 seed 的实际值）与 `git/IsaacLab.diff`。
- **baseline 线此后没再起过 run** ⇒ 现状**未复验**；下一次启动是第一次复验，入口见
  `work/active/baseline-pre-make-record-check.md`。

## 证据引用

- 普查方式：遍历 `E:\IsaacLab\logs\rsl_rl\*\*\run_manifest.json` 打印 `stages` / `failures`
  （临时探针脚本，读数抄录在此，不进仓）。
- 逐字段：`python -m rl_exp.tools.runrecord.manifest --verify <上述 run 目录>`；`params/`、`git/`、
  `checkpoints.json` 用目录列举与一次 `json.loads` 读键。
- 相关：`rl_exp/versions/lizard/baseline/v1/NOTES.md` §命令（实跑段照实写了这个缺口）、
  `.codemaker/rules/versioning.mdc` §A-2（实跑引用必须给 run 目录路径，记录不完整时写明缺什么）。

## 未覆盖边界

- **未复现该 AttributeError**：只知它抛在 `manifest.begin` 的外层 `try` 内、发生在那时的代码状态下；
  哪个调用、为何是 `None`，本记录不回答（`prov.code_sources()` 今天实测正常）。
- 未验证 `params/` + `checkpoints.json` 之外还能还原什么；"能不能重建"归 `verified-rebuild-rating`。
- 88 是 2026-09-21 的快照，且只读 `run_manifest.json`：**完全没有记录的 run 目录不在普查内**。
- 未测 `launch_recipe.py` 那条启动链：若 v2 走它，复验的对象不是同一条调用链。
