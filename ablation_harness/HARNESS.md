# Ablation Harness —— 评测台 SSOT

> 本文件 = 评测台（`ablation_harness/`）**当前事实与规则**的唯一真源：协议版本、记录格式契约、
> 升级触发、与 `rl_exp` 的契约。
> **待办不在这里**（→ `work/`，发现命令见 `AGENTS.md`）；**版本史与修订记录也不在这里**
> （→ `git log -p ablation_harness/HARNESS.md` 与各 commit message）。
> 评测台是共享测量仪器：服务所有机器人家族（换家族后仍在），**不进任何家族的配方版本管理**
> （versioning.mdc「范围边界」）。修订纪律沿用 versioning.mdc B 节（vN.M.K + 版本号开头的 commit
> message），**编号独立于家族配方版本**（冻结 tag：家族叫 `lizard-vN`，这里叫 `harness-vN`）。
> 家族侧对应项 = `work/active/isaac-root-parameterisation.md`（原 `versions/lizard/PLAN.md` 挂账 #12）。

## 当前状态

- **协议**：`locomotion_eval_v3` 当前（`eval.py` 的 `--protocol` 默认值即它；套件 `lizard_suite_v2`
  的 rough 两列是真起伏）。`locomotion_eval_v2` 与 `v1` 冻结封存，旧结果留
  `results/locomotion_eval_v{1,2}/` 原地。**三版任一不得混表**：v1→v2 帧右移一个 `step_dt`（20 ms）
  ⇒ 全指标有系统漂移；v2 的 rough 两列实为均匀抬升平板（已由 v3 换掉）。
- **代码基线**：v1.7.5 —— 几何测量的唯一家 `rl_exp/tasks/terrain_geometry.py`；记录格式见下一节。
- **部署形态**：仓根独立目录，全部自定位。机器本地事实（IsaacLab 树 + venv 解释器）登记在仓根
  `paths.yaml`（模板 `paths.example.yaml`），唯一读者 `host_paths.py`；`E:\IsaacLab\ablation_harness`
  junction 已废，原机可 `rmdir` 摘链接。

## 记录格式（`record_format`，独立于 eval 协议版本）

一次 eval 的**条件**写在 `results/<协议>/[组/]<run_id>/record.json`。格式身份 = `record_format` 字段
（现行 `eval-record-1`）。**版本号独立**：协议语义变化（时间线/阈值/地形/DR/指标/采样帧）才开新
`locomotion_eval_vN`；纯溯源字段补充**不开新协议**，只升这里的版本号。

**四条读侧规则**（`record.read_state`，合规即通过，违规即红，不做兼容）：

1. 无 `record_format` = **legacy**：缺字段一律读作未知，不回写、不补齐、不推导；
2. 有 `record_format` 但缺该格式必需字段 = **记录不完整**：不得按 legacy 放行，也不算通过
   （未知值写 `"unknown"`，**空槽不算记录**）；
3. 可比／不可比／未知分别有测试，缺证据**不得**自动升级为可比；
4. 记录行为不得改变 rollout、随机数消费或指标计算 —— `record.py` 不 import torch/numpy/random，
   由静态闸看守（`test_eval_record.py` 末例）。

**可比性只看绑定面**（`record.BINDINGS`：checkpoint / suite / assets / eval 协议 / obs 协议身份+摘要）：
任一侧 legacy 或不完整、或某绑定读作 unknown ⇒ **未知**；`differences` 只收**真差异**，
`unproven` 另记"两侧同为 unknown"的绑定。其余元数据（run_id、时间戳、分组）不参与比较。

**写侧硬门**：绑定齐备处（`_make_policy` 之后）与 `_persist` 各判一次 —— ①记录不完整 ⇒ **拒绝落盘**；
②同一 `run_id` 已有**可比**记录 ⇒ 重跑自重写，其余一律拒（记录有真差异 / legacy / 不完整 /
目录有结果无记录 / 记录文件不可读）。放行只有 `--variant`（另起身份）或 `--overwrite`（显式替换）。
拒写发生在 rollout **之前**。`record.json` / `eval.json` / `summary.csv` 一律 tmp + `os.replace`
原子落盘：截断的记录会让下一次 run 崩在解析上，而不是崩在一个决定上。

**字段清单与采集点**：格式定义见 `record.py`，四个采集点在 `eval.py`。`metrics.derived`
（`tilt_cos_min` / `clearance_min` / `sustain_steps`）是"指标实际用到的值"，v1.7.2 之前的记录没有它
⇒ 读作未知，不算缺字段。

## 升级触发（防"永远不升"）

harness 代码高频变更 / 多机器人共用 / 再开新协议时 → 目录化 `versions/harness/vN/`（协议 yaml + NOTES
进版本目录，与家族配方同款冻结纪律）。

**跨协议规则（现行约束，不是将来时）**：老跑分留在各自 `results/<协议>/` 原地不迁移；
**禁止跨协议直接对比**（任何表格/图表不得混 v1 / v2 / v3 行）；新协议新起 campaign 目录，
`--report` / `--summarize` 按协议目录天然隔离。

## 与 rl_exp 的契约（单向消费，改动必跑闸门）

- 任务 id：suites 引用 rl_exp 注册的 gym 任务（`import isaaclab_tasks` 触发注册链）
- DR 事件名：`components/dr_controller.py` ↔ rl_exp `play_utils.py` 9 事件清单，`check_dr_parity` 双向看守
- 机器人块：ArticulationCfg parity（family vs teacher）

→ 任何 harness 代码变更后必跑 `rl_exp\tools\verify\run_offline_checks.bat`（闸门红 = 不提交）。

## 挂账（正文已迁 `work/`，本表只留 id 与指针）

**新增待办直接开到 `work/active/`，不要往本表加行**；本表随批次收干。

| # | 事项 | 指针 | 优先级 |
|---|---|---|---|
| 1 | 运行时验收未跑完（跨协议对照 / 基线重跑 / rough 两列分布） | → `work/active/runtime-acceptance-v3.md` | 高 |
| 2 | 记录格式的剩余真跑段（rsl_rl 身份 / num_envs 格子 / 资产 fail 路径待授权） | → `work/active/record-format-live-checks.md` | 中 |
| 3 | 地形随机源两处缺口 + 几何证据归档（已收） | → `work/closed/2026/terrain-suite-v2-rng.md`、`work/closed/2026/terrain-evidence-18b.md` | — |
| 4 | 地形证据归档位置与 `rebuild.py` 角色（已裁决：运行目录 + 材料完整性） | → `work/closed/2026/archive-location-decision.md`；裁决见 `acceptance/records/2026-09-22-terrain-evidence-archive-and-verification.md` | — |
| 5 | 诊断 run 与 campaign 表之间没有闸门 | → `work/active/diagnostic-run-gate.md` | 中 |
| 6 | `--headless` 已弃用而本仓仍在用 | → `work/active/headless-flag-deprecation.md` | 低 |
