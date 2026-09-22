---
id: lizard2-family-landing
title: lizard2 家族落成：两处契约声明 + diff 论证 + 开训前检查
scope: rl_exp/versions/lizard2, rl_exp/tasks, rl_exp/tools/pipeline, rl_exp/tools/verify, ablation_harness
status: open
landing: rl_exp/versions/lizard2/main/v1/PLAN.md, rl_exp/versions/lizard2/main/main_params.yaml, rl_exp/tools/pipeline/emit_diff_declaration.py, rl_exp/tools/verify/check_recipe_build.py
next: ① **等 owner 决策**：执行器能力曲线实测把 0–3 的上界判为超出这条关节轨迹（0.5 Hz 就 163 N·m、干净跟踪只到 0.5 Hz、按步幅约 1.1 m/s；见 `2026-09-22-lizard2-actuator-capability.md`）——改窗口 / 改执行器（effort 180→更高或降 Kd）/ 接受并重述问题，三选一；同一记录的处置选择还有自碰撞（新族 24 判定、最坏 164.7 mm 把脚板折进躯干，训练期 `enabled_self_collisions=False` 不惩罚）。② 冻结本线评测协议（硬前置 1）：新增 `tracking_banded_v1`/`displacement_banded_v1`/`non_foot_load_sum_v1`/`gait_swing_v1`（各带反例与自己的 judge id），并按正常/异常样本标定 `non_foot_carrier_v1` 与总量那条，接启动闸门"协议缺失或摘要不符即拒绝"；③ `baseline_probe.py` 按 v1 接口改造后复测（命令 `[0.0,3.0]` 逐 env / 横向与转向恒 0 / 10 s 重采样 / 动作 30 维全覆盖 / 102 维 / 未改写下发命令）+ 零动作落地姿态目视；④ 头守卫触发未观测过（1.0 N 是类比继承），要么用一条"逐渐下压"的指令测它，要么在边界里一直标明。已完成：计数钉、obs 声明与 102 宽度实测、`diff.json` 理由、PLAN 写满、命令窗口 0–3、**自碰撞扫描**、**执行器能力曲线**。
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
