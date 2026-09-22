---
id: lizard2-family-landing
title: lizard2 家族落成：两处契约声明 + diff 论证 + 开训前检查
scope: rl_exp/versions/lizard2, rl_exp/tasks, rl_exp/tools/pipeline, rl_exp/tools/verify, ablation_harness
status: open
landing: rl_exp/versions/lizard2/main/v1/PLAN.md, rl_exp/versions/lizard2/main/main_params.yaml, rl_exp/tools/pipeline/emit_diff_declaration.py, rl_exp/tools/verify/check_recipe_build.py
next: ① 冻结本线评测协议（PLAN 硬前置 1）：新增四个判据种类 `tracking_banded_v1`/`displacement_banded_v1`/`non_foot_load_sum_v1`/`gait_swing_v1`（各带反例与自己的 judge id），并按正常/异常样本 + 噪声标定 `non_foot_carrier_v1`/总量那条的阈值，接启动闸门"协议缺失或摘要不符即拒绝"；② 执行器能力曲线实测（硬前置 4）：层一悬空正弦跟踪（0.5/1.0/1.5/2.0 Hz，记超调/稳定时间/饱和占比/时间步敏感性）+ 层二承重协调运动；先测运行时真正生效的限幅（`velocity_limit` 被本 fork 丢弃）；③ 自碰撞检查（硬前置 5）：交叠/有符号穿透 + 相邻关节允许重叠，粗网格找反例 + 覆盖实际动作轨迹；④ `baseline_probe.py` 按 v1 接口改造后复测 + 零动作落地姿态目视；⑤ 开训前打 tag `lizard2-main-v1`。
close_when: 离线套件全绿、硬前置 1-5 完成（协议冻结、能力曲线、自碰撞、探针、目视）、`diff.json` 理由有据、tag 已打 ⇒ 可开训；若明示暂不开训，则完成到 ④ 并记"未开训"这一事实即可关闭——未做的动作不许留在已关闭项里。
depends_on: asset-leg-axis-capability-mismatch
evidence: acceptance/records/2026-09-22-lizard2-family-landing, acceptance/records/2026-09-22-family-landing-decoupled, acceptance/records/2026-09-22-lizard2-stride-at-load, acceptance/records/2026-09-22-lizard2-declarations-and-plan
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
