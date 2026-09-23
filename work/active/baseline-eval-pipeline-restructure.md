---
id: baseline-eval-pipeline-restructure
title: baseline / Lizard2 eval 解耦机制计划
scope: ablation_harness, rl_exp/tools/verify
status: open
landing: ablation_harness/baseline_frames.py, ablation_harness/baseline_metrics.py, ablation_harness/baseline_eval.py, rl_exp/tools/verify/test_baseline_contract.py, ablation_harness/HARNESS.md
next: P0 由 baseline-eval-persist-before-judge 独立实施；本项按 P1→P3 落机制并完成 P4 验收。协议版本与产品口径消费 lizard2-family-landing 的决定，不在本项另定。
close_when: 执行者核验 P1–P4 的格式兼容、离线复判、报告声明和场景覆盖；P0、baseline-eval-measurement-trust、floor-contact-attribution 均关闭，家族项完成本轮新协议发布与口径验收后，本总项关闭。家族项的其他落成工作不阻挡本项关闭。
depends_on: baseline-eval-persist-before-judge, baseline-eval-measurement-trust, floor-contact-attribution, lizard2-family-landing
evidence: acceptance/records/2026-09-21-baseline-eval-measurement-contract.md, acceptance/records/2026-09-23-lizard2-v1-first-eval.md, acceptance/records/2026-09-23-lizard2-v1-gait-skate.md
---

## 归属与边界

**机制归本项；新协议版本、报告清单、产品阈值及标定样本归 `work/active/lizard2-family-landing.md`。**
本项负责足端采集、指标实现、声明检查和固定命令驱动；家族项只引用这些交付，不再重复实施步骤。
`depends_on` 表达最终验收所需输入，不要求家族项先整体关闭；家族协议可在机制交付后发布。

P0 的实施与验收已移至 `work/active/baseline-eval-persist-before-judge.md`，本项只消费结果。
地面接触归因归 `floor-contact-attribution`，真实早终止取证归 `baseline-eval-measurement-trust`；
开训闸门归 `eval-protocol-before-training`。不改训练配方、奖励、资产或 rough 入口，不建通用采集框架。

## 机制边界

流水线为：采集条件与字段 → 保存记录 → 离线指标 → 判据 → 报告；默认命令可顺序编排，并提供仅采集路径。
记录保留实际条件和来源，复判只更换判据，不能覆盖原采集身份。报告绑定帧摘要、条件和 reader/协议身份。
条件不兼容、必需数据未测或采样能力不足须显式说明；存了更多字段不代表测到了所需场景。

默认采集范围由格式声明，不随本次门槛裁剪：

| 基础量 | 复算用途 |
|---|---|
| 基座位置/完整姿态/线角速度，生效命令，终止/超时 | 跟踪、位移、姿态、有效区间与命令对齐 |
| 逐 body 接触合力向量，逐 env 质量与重力来源，部位轴标 | 接触、承重、占空比；合力不等同于地面专属力 |
| 足端姿态/线角速度，足底几何参考，地面高度/法向来源 | 离地高度与参考点切向运动 |
| 现有非足网格诊断所需量及实际资产来源 | 保留诊断能力，避免用当前或旧家族网格补历史几何 |

地面专属接触对、摩擦归因、关节力矩与录像维持专项采集。常规协议对力矩报告项的取舍只在家族项登记。
测量参数、单位、坐标系、采样周期及轴标随记录保存；先测开销再决定缓存/传输优化，不预建分块存储系统。

## P1：按格式分派与冻结采集契约

落点：`baseline_frames.load`、`BaselineFrames`、`_expected_shape`、`baseline_metrics._contract_reasons`。

- 契约按记录 `format` 选择。尤其替换 `_contract_reasons` 对模块级 `REQUIRED_META` 和 `COLUMNS` 的直接依赖；
  必需 meta、合法列、形状/轴标校验均读所选格式。遍查其他全局读取处，不能只改 `load()`。
- 旧格式使用旧契约；新 writer 发新格式，未知格式拒绝。保留既有公共入口与旧字段语义，旧记录缺新量不得补零。
- 新建按 format 索引的 `frame_semantics.json` 冻结表，沿判据表的形状钉列集合、形状种类、单位、坐标/时序语义、
  必需 meta、固定用例和预期结果；摘要由显式批准写入，检查时只比较，不自动重钉。
- `test_baseline_contract.py` 增加独立旧格式 fixture，不能从当前 `COLUMNS` 动态生成全部基准。破坏旧列/单位/
  必需 meta 必须红，新增格式不改变旧块摘要；语义用例补足“摘要只能守声明”的边界。
- 按默认范围采集并保存独立 CPU 帧/meta；命令配对驱动该步的输入，终止帧取物理步后/复位前。核验短接触采样
  能力、实际资产几何来源与轴对应，开销和参照测量写入验收记录。

出口：旧格式经 `load` 和 `judge` 都可复读；新旧格式交叉、未知格式、缺 meta、轴置换、命令阶跃与复位均有反例。
新判据读取旧记录缺失量时明确不可判，不能改变旧 reader 的既有判决。

## P2：离线指标及新 reader 的完整性检查

落点：`baseline_metrics` 计算函数、`CRITERION_KINDS`、`JUDGE_KINDS` 与 `judge_semantics.json`。

- 指标显式声明列依赖、单位、适用条件，返回数值及有效样本量；报告与判据共用计算结果。足端测量机制在此实现，
  哪些指标进入协议及其阈值由家族项消费。参考点速度含 `v + ω × r`；未经接触参照验证须标近似。
  **诊断侧已先行（2026-09-23）**：`rl_exp/tools/diagnose/diag_metrics.py` 的 `mesh_lowest_point` / `contact_point_velocity`（参考点取 COM：`body_lin_vel_w` 是 `body_com_lin_vel_w` 的别名）/ `yaw_frame_offset`，驱动为 `gait_probe.py`，已按上述口径在同一检查点上跑通（读数见 `acceptance/records/2026-09-23-lizard2-v1-gait-skate` 的 ⑤）⇒ P1 的帧列与 P2 的指标**复用这三个函数**，不在 `baseline_metrics` 里另写一份。
- **报告项完整性仅由新 reader id 强制**：沿 `JUDGE_KINDS` 身份绑定声明能力，未知/未实现的名称拒绝；缺数据或
  无样本显式不可用。必需判据缺证据给 `invalid`，可选诊断缺证据保留原因。旧 reader 沿旧路径，不追溯加严。
- 测试同时钉两侧：旧 `lizard2_flat_v2` 与旧帧复判维持原判决；新 reader 遇未实现项必须拒绝，新家族协议的清单
  必须全有实现。先核对已有报告映射，不照历史缺项描述重复实现。
- 报告分测量有效性、任务表现、行为有效性；工具异常与策略失败可区分。公式/聚合/失败帧语义变更用新 kind/reader，
  产品阈值变化由家族项发布新协议，禁止修改旧块消除失败。

出口：静止、平移、纯转动、摆动落地、持续滑行、失败复位的合成反例与正常参照能区分；完整性检查不作废旧判决。

## P3：执行并核验声明的固定场景

落点：`baseline_eval` 命令驱动与现有命令/帧契约测试；场景序列、速度带、等待窗及覆盖要求只读家族新协议。

核对注入坐标和时序，阻止环境重采样覆盖评测命令，保证策略观察对应实际命令。分别报告场景分配数、执行数和
有效样本数；区分采集漏执行与策略提前失败，不能把失败策略一律归为采集无效。环境数不足或空带明确暴露。
同表核对采集条件、格式/测量身份与判据；旧随机采样帧不能冒充新场景。

出口：固定 seed/映射的命令可复现；阶跃与策略输入对齐；纯阈值复判保持帧摘要；改变场景或缺所需量必须重采。

## P4：集成验收

同一检查点新采集后，默认全流程与同帧离线复判一致；测量反证、早终止与接触参照消费各负责事项的证据。
按仓规做故障回归的修复前失败证明，再跑相关测试和全量离线闸门。更新 `HARNESS.md` 的机制契约，按其版本纪律
发布 harness；协议发布由家族项完成，既有锚点问题归 `harness-version-anchor-missing`。
实测与结论进 `acceptance/records/`，事项只留指针。未定产品口径只可交付诊断，不宣称正式步态验收完成。
