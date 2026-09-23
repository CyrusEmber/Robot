# 两份形态拍板：开训前协议绑定 / 教师快照（2026-09-23）

## 适用范围

- 本记录只落 **owner 2026-09-23 的两个形态决定**，以及实施前必须满足的前置。**本轮未改代码、未改事项状态。**
- 将来落点：`rl_exp/versions/obs_protocols.json`（加 `eval_protocol` 绑定）、`rl_exp/tools/runrecord/manifest.py`（拒绝点）、
  `rl_exp/tasks/teacher_env_cfg.py` 与教师侧字面量的声明、`rl_exp/tools/verify/check_dr_parity.py`（C4 的静态校验）。
- **不覆盖**：A 与 B 的**实施**（A 等 v2 首跑验收完成；B 待实施）。

## 验收条件

1. 决定本身与它的约束要能照做：载体、摘要口径、覆盖范围、override、读点与报错五项都在。
2. 前置必须可判：不能拿"盘上有产物"顶"验收已完成"。
3. 记录的是形态，不是进度；不得据此把任何事项标为已完成。

## 结果

### A. 开训前协议绑定（形态已定，闸门暂不实施）

1. **载体**：用 `rl_exp/versions/obs_protocols.json` 现有的 **task 路由声明**加 `eval_protocol` 绑定；按 **task id** 查找，
   并核对路由的 `(line, version)` 与本次配方一致。**不放进配方 YAML、不放进 PLAN**。复用的是声明与校验形态；
   验收协议本体仍指向 `ablation_harness/protocols/`。
2. **摘要**：对协议文件调用**唯一的** `binding.sha256_file`。声明中写**路径 + 预期 SHA-256**；若该文件列在
   `protocol_anchors.json`，还须与**批准锚一致**。协议自身的 `digest` 字段与评测记录里的 `eval_protocol.digest`
   **都不充当**开训声明。
3. **覆盖**：闸门上线后**所有新启动的训练**都须绑定，**包括旧版本再次启动**。**不能采用"有声明才检查"**——
   删掉声明就能绕过"无协议拒绝"。上线前须给仍允许开训的版本补绑定，或接受它们被拒；历史 run 不补证，
   已在跑的进程不受影响。
4. **override：不设**。协议缺失或摘要不符＝验收口径未定，写理由放行会让这条硬闸失效。
5. **读点与报错**：`begin` 在 **T0 写盘前**记录本次 task、配方路由、协议路径、预期与实算摘要、判定理由；
   **写盘后**在现有拒绝集合中执行拒绝。文案分别点名"缺少哪个 `(line, version)` 的绑定""哪份文件缺失"
   "预期与实算摘要不符"，沿用 `refused to start` 形状。

**前置未满足（owner 核对）**：`baseline-eval-protocol-gap` 要求的**首跑判定与回填**未完成——活跃事项与 v2 NOTES
尚未写首跑结论。盘上确有 v2 产物（`model_9999.pt`、`ablation_harness/results/baseline_flat_v3/v2-trained-9999/eval.json`），
但**仅凭产物不能宣布前置满足**，且按 `eval-protocol-before-training:29-31`，现有 v2 产物**不能**充当闸门放行证据。
⇒ 顺序不变：v2 首跑验收完成 → 实施闸门 → 另起"缺协议拒绝"与"有协议放行"两次真启动取证。

**owner 点名的最大实施风险**：补绑定时把"**盘上已有协议**"误当成"**这版曾在开训前承诺过它**"。
旧版本的绑定必须标清"这是对未来启动的要求"，**不能反写为历史 run 的证据**。

### B. 教师快照：选 ① 声明式

- **保留**教师代码里的独立冻结值。
- 声明必须给出**可执行的关系**（资产事实、取值规则或边界），**不能只有"依据某资产"的注释**——
  否则 C3（把冻结地形尺寸改成 `0.99`）仍无法被可靠判错。
- **只覆盖已声明、确有可验证关系的量**；**不把教师值强制等同家族当前配置**（③ 对照式仍不选）。
- **C4 单独加静态校验**：教师的 `_VERSION_FAMILY` 必须与登记的教师 subject 所属家族一致；
  同时**修正** `teacher_env_cfg.py` 那句"写错必在构造时抛错"的注释（矩阵记录实测该断言不成立）。
- 随后**C3/C4 变红、C1/C2 保持原判**，再跑离线套件。

## 证据引用

- A 的落点与先例：`rl_exp/tools/runrecord/manifest.py:418-421`（资产 vs 冻结锁已是"冻结物不符即拒"的同类先例）、
  `:425-427`（目录/生命周期答案）、`:428-431`（脏树，含 `refused to start` 形状）、`:422-424`（T0 先写盘的注释）、
  `:432-436`（脏树唯一 override —— 协议这条按本次决定**不设**）；
  `eval-protocol-before-training:23`（排序决定：v2 先开训、本闸门后补）、`:29-31`（两分支要新的真跑证据，不得回溯）。
- B 的缺口读数：`acceptance/records/2026-09-22-teacher-snapshot-parity-matrix.md:46`（C3 三条全静默）、
  `:49-55`（C4 报了但诊断错）、`:57-63`（④⑤⑥ 都不验证"两侧已同步"）；被点名的注释在 `rl_exp/tasks/teacher_env_cfg.py:56-63`。
- 盘上 v2 产物（**不等于**验收）：`ablation_harness/results/baseline_flat_v3/v2-trained-9999/eval.json`。

## 未覆盖边界

- A、B 都**未实施**；本轮不改代码、不改事项状态（owner 指示）。
- 我看过 `eval.json` 在仓里，但**没有**核它是否就是那次"首跑"、也没有判它的 `verdict`——首跑判定与 NOTES 回填
  属 `baseline-eval-protocol-gap`，本记录照 owner 的说法记为"未完成"。
- **未核的牵连面**（实施 A 前先看）：往 `obs_protocols.json` 加字段会动到**声明面自己的闸门**——
  套件 `[42]`（`check_obs_protocol`：声明 vs golden，`--live` 时 vs 构出的 cfg）与
  `rl_exp/versions/obs_protocol_anchors.json` 的摘要锚，字段变化可能触发重钉。本次未验证，未列入决定。
- B 的"可执行关系"具体写法（资产事实／取值规则／边界三选几）未定稿；C4 静态校验落在哪条闸未定
  （候选：扩 `check_dr_parity` 的 subject 校验，或 `framework_pin_check` 一类静态闸）。
