---
id: lizard2-v2-foot-authority
title: lizard2 v2 配方：取消脚板策略动作（脚板保留固定平放参考的 PD）
scope: rl_exp/tasks, rl_exp/versions/lizard2, ablation_harness/protocols, rl_exp/versions
status: in_progress
landing: rl_exp/tasks/lizard2_recipe.py, rl_exp/versions/lizard2/main/main_params.yaml, rl_exp/versions/recipes.json, rl_exp/tasks/agents/rsl_rl_ppo_cfg.py, rl_exp/versions/lizard2/main/v2/PLAN.md, rl_exp/versions/obs_protocol_anchors.json
next: ① **已交付 2026-09-29（实验臂的评测）**：协议侧新建 `ablation_harness/protocols/lizard2_flat_v3.json`（身份新、判据与 v2 文件逐块相同，由 `test_baseline_contract.py` 的一条检查看守）并锚进 `protocol_anchors.json`；判决报告落 `ablation_harness/results/lizard2_flat_v3/v2/…`；机制读数（20 s 窗口、样本下限达标）与训练曲线落 `v2/tb_scalars.csv`；`v2/NOTES.md` 已回填。读数、判定与边界**全在** `acceptance/records/2026-09-29-lizard2-v2-eval.md`，本项不复述。② **仍缺 = `close_when` (b) 的"两臂"**：本轮只评了实验臂，对照臂不存在 ⇒ 要么补对照臂，要么把 (b) 的口径收成"单臂"，这一条由所有者定，本项不自行改判据。③ 已知偏离随 run 记在 `v2/NOTES.md`（实跑迭代数与 cfg 声明不一致）。
close_when: (a) 两个新任务 id 在 v2 冻结参数上通过启动契约探针（含"脚板目标恒等默认平放位"与新 obs 宽度两项新断言），且旧断言在 v1 上仍绿；(b) 两臂按同一协议产出评测报告并回填 `v2/NOTES.md`，按 PLAN 预写的判据给出结论 —— 正负都关（**当前只有实验臂一侧；收成单臂口径需所有者拍板**）；(c) 若结论只能到"机制"层（对照臂的几何混淆未消），在 NOTES 与记录里写明并把它作为后续动作的输入，不得写作因果结论。三件齐了才关
evidence: acceptance/records/2026-09-29-lizard2-v2-eval, acceptance/records/2026-09-28-lizard2-v2-startup-contract, acceptance/records/2026-09-28-lizard2-v2-cfg-lock-rebaseline
---

## 问题与本次范围

问题：脚板的策略动作权限是否在拖累步态。v1 是"脚板有动作权限"的那一臂，v2 去掉权限、保留固定平放参考的
PD，其余配方逐字不动，作为**动作权限**这一个变量的实验。

范围：配方版本、任务注册、启动契约、评测协议与两臂对照。**不含**脚板增益本身是否合理的判断（那一问由
`work/closed/2026/feet-drive-candidate-probe.md` 的读数答了：候选弱增益被否，脚板沿用 v1 增益）；不含资产
改造；不含奖励变更。

## 当前状态

**配方、注册、差异声明与启动契约都已落地并过闸**（离线 47/47）。v2 与 v1 的差异在 `diff.json` 里是
一条 env 路径（腿组关节表去掉脚板 pattern）+ 两个 agent 叶子（`experiment_name`、`max_iterations`）
—— "其余逐字沿用 v1"因此是机器可查的，不是散文。仍需 `close_when` 的只有 (b)：两臂训练与评测。

三条已知边界（不因上面这些落地而消失）：**v2 不等于"脚板被动"**（去掉通道只去掉调制，PD 仍在，承重期
脚板可能仍整段饱和；⑭ 另给了接口先验：把脚板钉住会让 v1 的策略 1–3 秒倒地 ⇒ 本版从更远处起跑）；
**对照臂带几何混淆**（现有 checkpoint 训练用的脚板 hull 与当前树不同 ⇒ 对照臂重训之前，本版的"改善"只能
叫机制读数）；**交付力矩只能给上界**（implicit 驱动读不到 `applied_torque`）。

## 未覆盖边界

- 两臂若不配对 seed、或不共用同一份 eval 协议，滑移差异不可归因 —— 协议一旦需要新字段，就新开一份协议
  版本并锚定，**两臂共用**。
- 动作维度改变即改变部署接口：接与不接在仓外（UE 侧），本项只把接口变化递过去。
- 训练预算与命令窗口沿用 v1；本项不评估"更长训练是否更好"。
