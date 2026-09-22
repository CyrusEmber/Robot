---
id: lizard2-family-landing
title: lizard2 家族落成：两处契约声明 + diff 论证 + 开训前检查
scope: rl_exp/versions/lizard2, rl_exp/tasks, rl_exp/tools/pipeline, rl_exp/tools/verify, ablation_harness
status: open
landing: rl_exp/versions/lizard2/main/v1/PLAN.md, rl_exp/versions/lizard2/main/main_params.yaml, rl_exp/tools/pipeline/emit_diff_declaration.py, rl_exp/tools/verify/check_recipe_build.py
next: ① 冻结本线评测协议（硬前置 1，未动）：在 `baseline_metrics.CRITERION_KINDS` 上加 `tracking_banded_v1`/`displacement_banded_v1`/`non_foot_load_sum_v1`/`gait_swing_v1`（各带反例与自己的 judge id）、写 `protocols/lizard2_flat_v1.json`、接启动闸门"协议缺失或摘要不符即拒绝"、并按正常/异常样本标定阈值——需先读评审期新落的 `loco_judge.py`/`suite_lock.py`/`judge_semantics.json`，避免另造一套判据真源；② 探针（硬前置 2）**已改造并跑过一次**：命令框/观测宽度/终止集合改由任务自己的文档驱动（`recipe_params`+`obs_protocol.recorded_dims`），`resolve_task_cfg` 不再只认 `lizard/baseline`；lizard2 上实测绿（命令逐 env 落在 0–3、obs 102 与批准一致、30 关节各一通道、终止＝yaml 声明）。**差两件**：(a) yaml 的 `head_contact_body_names` 命中两个无碰撞网格的连杆（探针报 FAIL"该部分守卫永不触发"）⇒ 收窄成 `chest_pitch`/`neck_pitch` 并重钉 golden/lock；(b) 零动作落地姿态目视；③ 头守卫触发（硬前置 5 的观测量）**仍未观测到**：`--head-press` 已建，但只降机体会先落在脚上（0.00 N），驱动头链后终止标志在零接触力下立即置位 ⇒ 读数不可信，需改成"复位后逐步下压 + 以 episode 结束为准 + 同时读接触力"；④ **待 owner 判断（不是测量）**：自碰撞要不要开（筛选干净、无确认穿透；若开要重测站立/跟踪/行程）；⑤ 坏 tag `lizard2-main-v1` 留远端但**已标记无效**（正确锚点＝`v1.4`/`v1.5`），删否由 owner 定。已完成：计数钉、obs 声明与 102 宽度实测、`diff.json` 理由、PLAN 写满、命令窗口 0–3、执行器响应曲线、自碰撞筛选＋网格复核（记录均已按评审修正）。
close_when: 离线套件全绿、硬前置 1-5 完成（协议冻结、能力曲线、自碰撞、探针、目视）、`diff.json` 理由有据、tag 已打 ⇒ 可开训；若明示暂不开训，则完成到 ④ 并记"未开训"这一事实即可关闭——未做的动作不许留在已关闭项里。
depends_on: asset-leg-axis-capability-mismatch
evidence: acceptance/records/2026-09-22-lizard2-family-landing, acceptance/records/2026-09-22-family-landing-decoupled, acceptance/records/2026-09-22-lizard2-stride-at-load, acceptance/records/2026-09-22-lizard2-declarations-and-plan, acceptance/records/2026-09-22-lizard2-self-collision-sweep, acceptance/records/2026-09-22-lizard2-actuator-capability
---

## 问题与本次范围

新家族 `lizard2` 已从旧资产落到"可建 env、能过资产/注册/锁三级闸门"。本项收**落成的尾与债**：
契约声明、差异论证、开训前检查。不含训练，不含旧家族的资产或锁。

## 当前状态

2026-09-22 完成（细节见四条 `evidence` 记录，本处不复制数值）：

- **与任何历史家族解耦**：`declare_family.py` 的参照家族依赖整条删除；零漂移保护改为"目标家族之外的全部家族"
  逐字节比对且锁更新限定目标；通用闸门的检查项改由**声明**决定（资产契约只查 yaml 自己声明的键、只查 `active` 线；
  对拍对象搬进 `versions/freeze_parity.json`）。
- **新骨骼的运行时证据**：承重姿态下四腿髋的前后行程一致且远超旧构型；动作覆盖与 obs 宽度均有实测；
  `check_joint_layout.py` 改为按资产推导腿部关节/力臂并新增弦长断言。
- **声明与论证**：`EXPECTED_DIFFS` 等三处计数钉、obs 声明两任务 + 102 宽度按资产键实测批准（缺宽度/缺解析成静态红）、
  9 条 env + 43 条 agent 理由（再生成保留原文，值变化打 REVIEW 标记）。
- **PLAN 写满**：硬前置 5 条、固定窗口、主轴 7 条判据（四个种类待新增）、非足承重两条判据、8 条风险与 4 条判废线；
  所有者的两条决定已落定。**终止条件 2026-09-22 加一条**：`head_contact`（`chest_.*`/`neck_.*` > 1.0 N，框架
  `illegal_contact`，不加 dwell）——旧线 v1 就是被"压着脖子走"拖垮的（66% 的帧压在 10% 体重之上、却从未连续
  超过 0.22 s，dwell 型承重判据拦不住，接触判据可以）；连带重钉 golden/v1 锁、路径 64→65、计数钉 107→108。
  `v1` 未训练、无 tag。

## 未覆盖边界

判据种类与协议文件**都还没写**（`baseline_metrics.py` 仍是旧归一）；执行器能力曲线与自碰撞检查**没跑过**，
现在只有量级估算与风险声明；理由写的是"这版为什么这样"，不是"数值对不对"；
obs 宽度**变了但两边都批准过**的那种只有活体重建能发现；行程是纯运动学读数；
本轮套件的红在 `rl_exp/tools/verify/test_video_matrix.py`（非本项产物），只报告不处理。
