---
id: lizard2-family-landing
title: lizard2 家族落成：两处契约声明 + diff 论证 + 开训前检查
scope: rl_exp/versions/lizard2, rl_exp/tasks, rl_exp/tools/pipeline, rl_exp/tools/verify, ablation_harness
status: open
landing: rl_exp/versions/lizard2/main/v1/PLAN.md, rl_exp/versions/lizard2/main/main_params.yaml, rl_exp/tools/pipeline/emit_diff_declaration.py, rl_exp/tools/verify/check_recipe_build.py
next: ① 评测协议**已冻结且已出首次判决**（2026-09-22 冻结、2026-09-23 判决）：`ablation_harness/protocols/lizard2_flat_v2.json`（`Lizard2-Flat-v2` v2、`judge: baseline-criteria-banded-settled-1`、命令箱 0–3、20 s、plane、`settle_s 1.5`）+ 两种带 settle 的新 kind + 新 reader id 的冻结块 + 反例；首次判决 `pass` 八条全过（零命令带 `|v|` 0.045／最差 env 漂移 0.155 m／三带误差 0.006–0.036／位移比 0.988–1.006），记录 `acceptance/records/2026-09-23-lizard2-v1-first-eval.md`。**该轮修掉三处**：分带位移闸门假定 `meta` 的设备（GPU 上第一次判决直接 `RuntimeError ... cuda:0 and cpu`，冻结点从未在 GPU 上跑通过）、零命令带在命令阶跃那一帧取样、零命令带位移读数在全部 env 上求和却比米限值（读数随批量大小变）。**② 步态实测：判据侧缺项已暴露（所有者目视录像触发）**——承重脚滑移中位 0.65–1.54 m/s（p95 至 3.1）、摆动相离地仅 2–8 cm（本仓 `foot_clearance` 标准 0.2 m），八条判据**没有一条看得见**；根因两侧：奖励侧删了 `feet_slide`/`foot_clearance`（旧线 `lizard/baseline/v1/PLAN.md:125` 预注册的取舍，现已到期），判据侧把 PLAN 验收要求的 `min_lift_m` 丢了、`foot_slip_mps` 声明而未计算。数值/对照/出处见 `acceptance/records/2026-09-23-lizard2-v1-gait-skate.md`；**所有者已定方向：先修尺子**（帧记录加足端高度/滑移两列 + 补回 `min_lift_m` + 真正算出 `foot_slip_mps` ⇒ 新协议版本），奖励侧改动与重训另议。**余项（都写明归属）**：(a) 开训**启动闸门**（"协议缺失/摘要不符 ⇒ 拒训"）**未建**——`manifest.begin` 现只拒 lifecycle 与脏树，形态归 `work/active/eval-protocol-before-training.md`；(b) `min_swing_feet` 现填 **2**，实测 4 足里最少 3 只完成摆动、1 只脚 20 s 内一次都没有 ⇒ 待所有者给产品口径；(c) `no_non_foot_carrier.fraction=0.05` 缺"持续部分承重"档标定样本；(d) 协议 `report_only` 声明 15 项、报告只产出 8 项（无人计算的 6 项列在判决记录里）⇒ 与 (②) 的尺子修复合并做（补计算或收窄清单）；(e) 逐带判据的零命令带覆盖率仍依赖环境的 10 s 重采样（本次 15/256 env 落进该带）。
② 探针（硬前置 2）**已改造并两次收口**，见 `acceptance/records/2026-09-22-lizard2-probe-observer-fixes.md`：压头经部署动作接口真的下发、头链另**用关节状态钉住**（只下发动作时驱动饱和、链回缩 0.3 m）、力与项值在复位前同帧读取、终止集合由 yaml `terminations.terms` 点名且等号判、死条目（无碰撞网格的 yaw 连杆）单独清理并重钉 golden/lock、零动作出帧目视（末帧已看：8 台平地站姿、四足平贴、无可见穿地）；③ 头守卫触发（硬前置 5 的观测量）**已完成，边界两半齐全**：站立 0.00 N 静默 / 下巴离地 50 mm 起降、前 18 帧静默、触地那帧 1108.12 N 同帧触发（`terminated=True`、`base_contact` 不在其中）；实测接触刚度 ≈4×10⁶ N/m ⇒ 该阈值是**接触检测器**，"从下方穿过 1 N 的温和下压"**撤回**（不存在该读数）；④ **自碰撞：所有者 2026-09-22 决定本版不开**（0 条确认穿透、24/24 凸包过近似会造出假接触、按单变量留给下一版），理由与改判条件已入 PLAN 硬前置 5；⑤ tag 事实（2026-09-22 已核并**已处理**）：裸锚点 `lizard2-main-v1`（9c257e3，那笔提交里只有 3 份 record + 本事项、**不含任何配方**）已**本地与远端一并删除**（`git tag -d` + `git push origin :refs/tags/lizard2-main-v1`，结果 `- [deleted] lizard2-main-v1`）；它所指的提交仍在 main 历史里（`merge-base --is-ancestor 9c257e3 main` 通过），故这是**只摘标签**、不改历史。v1 的锚点现由 `lizard2-main-v1.4`=9dcbf12 / `-v1.5`=7387031 / `-v1.6`=24757e0 承担（仓规的 `[.minor]` 形态），`check_version_docs` 复查 `VERSION_DOCS_OK`。连带改动：`work/active/harness-version-anchor-missing.md` 里"照 `lizard2-main-v1` 的先例"已改为 `lizard2-main-v1.5`（原先例已不存在）。**开训后本线又晚于 `-v1.6` 两批改动**（判决那批还没打锚点）。
close_when: 离线套件全绿、硬前置 1-5 完成（协议冻结、能力曲线、自碰撞、探针、目视）、`diff.json` 理由有据、tag 已打 ⇒ 可开训；若明示暂不开训，则完成到 ④ 并记"未开训"这一事实即可关闭——未做的动作不许留在已关闭项里。
depends_on: asset-leg-axis-capability-mismatch
evidence: acceptance/records/2026-09-23-lizard2-v1-gait-skate, acceptance/records/2026-09-23-lizard2-v1-first-eval, acceptance/records/2026-09-22-lizard2-family-landing, acceptance/records/2026-09-22-family-landing-decoupled, acceptance/records/2026-09-22-lizard2-stride-at-load, acceptance/records/2026-09-22-lizard2-declarations-and-plan, acceptance/records/2026-09-22-lizard2-self-collision-sweep, acceptance/records/2026-09-22-lizard2-actuator-capability, acceptance/records/2026-09-22-lizard2-probe-observer-fixes
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
- **探针的观测口径收口**（2026-09-22，评审后）：压头真的下发 + 头链用关节状态钉住、力/项值复位前同帧读、
  终止集合改为 yaml 点名 + 等号判、死条目（无碰撞网格的 yaw 连杆）单独清理并重钉 golden/lock、零动作出帧供目视；
  头守卫触发的**边界两半**已测（离地 18 帧静默 → 触地帧 1108.12 N 同帧触发），并由接触刚度（≈4×10⁶ N/m）
  得出该阈值是**接触检测器**而非力门限。读数与边界见 `evidence` 的 probe-observer-fixes 记录。
- **PLAN 写满**：硬前置 5 条、固定窗口、主轴 7 条判据（四个种类待新增）、非足承重两条判据、8 条风险与 4 条判废线；
  所有者的两条决定已落定。**终止条件 2026-09-22 加一条**：`head_contact`（`chest_.*`/`neck_.*` > 1.0 N，框架
  `illegal_contact`，不加 dwell）——旧线 v1 就是被"压着脖子走"拖垮的（66% 的帧压在 10% 体重之上、却从未连续
  超过 0.22 s，dwell 型承重判据拦不住，接触判据可以）；连带重钉 golden/v1 锁、路径 64→65、计数钉 107→108。
  `v1` 已于 2026-09-22 开训（`--max_iterations 14000`，4096 envs，跑满）并于 2026-09-23 出首次判决
  （`model_13999`，256 envs/seed123：**pass 八条全过**）；锚点为 `lizard2-main-v1.6`。

## 未覆盖边界

判定口径**已写、已冻结、已出判决**（记录见 `2026-09-23-lizard2-v1-first-eval`），但判决是**开训之后**做的，
且那一轮改了尺子（两处缺陷 + 一处 GPU 专用 bug）；协议 `report_only` 的清单仍大于实际产物；
执行器能力曲线与自碰撞检查有读数（硬前置 4/5），但都是**估算 + 静态姿态**口径，不是承重动态；
理由写的是"这版为什么这样"，不是"数值对不对"；obs 宽度变化的活体重建只覆盖**声明过的键**；
行程是纯运动学读数。本轮离线套件全绿。
