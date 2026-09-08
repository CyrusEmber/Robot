# v9 —— ghost 断腿鲁棒性（截肢近似 DR + damage flag obs + v8 checkpoint 微调）

> 状态：提案（未冻结——训练启动时补打 tag `lizard-v9`，versioning.mdc §A）。
> 修订：v9.0（2026-09-08 初稿——提案自 v7 迁入并重基 v8（用户拍板"按顺序
> 开 v9"）；limp 档弃训，mid-episode 断腿/损伤分级/多腿同断不做）。
> 本版变更 = DR 新组 + obs 加一项 + reward 豁免一项 + 训练源一项；方案细节
> 与验收判据继承 `../v8/PLAN.md`（及 v5 反划脚 KPI）全文，此处只记 v9
> 特有内容。

## 目的

怪物断腿不宕机：UE 战斗断腿事件后仍能爬行/追击，瘸法生物学合理（三足 +
躯干/尾代偿——代偿通道正是 v6.1 解锁的 10 个脊柱/尾关节）。同时验证
"微调扩技能"配方（Parkour in the Wild 的"加地形→继续微调"：旧技能不掉点、
新能力小遗忘）。

## 为什么是 ghost，不是真删 / limp

- **真删（摘 link）两条硬墙**：PhysX articulation 拓扑 spawn 时固定；预烤
  4 个截肢 USD 变体则关节数 26→22，obs/action 维度契约崩，单策略吃不下异构维度
- **ghost = 维度契约全不变，物理上"弄没"**：断腿 4 关节 stiffness→0（无电机）+
  整腿 link 质量 ×0.001（残肢惯性消失）。策略照常输出 26 维动作，断腿关节的
  分量成废话但不破契约
- **limp（软腿有质量拖着晃）弃用**：残肢近零质量动力学干净，塌缩风险低；
  档位存档于 v9 yaml 注释，训练期发现 ghost 表现不足再议
- **不做 mid-episode 断腿**：部署端（UE 游戏逻辑）直喂 damage flag，
  "从历史推断损伤"的问题在游戏里不存在——flag obs 使其无必要

## 变更（相对 v8）

1. **DR 新组 `v9.broken_leg`（reset 事件，代码待实施）**：每 env 每 reset
   p=0.3 抽签，命中均匀选 lf/rf/rl/rr，整腿 4 关节 stiffness→0、damping→1.0，
   腿 link 质量 ×0.001（复用 limb mass DR 机制扩下界 + 整腿联动）
2. **obs：`damage_flags` 4 维 one-hot 进 actor 本体组**（90→94；全 0 = 健康）。
   结构变更 → OBS.md 版本差异声明开工时补。**结构变更 → 新任务 id**：
   `Lizard-Rough-v9` + V9 cfg 常驻注册（仅新增子类，v1–v8 类零改动——红线：
   已发布 term 语义不动）
3. **reward 豁免（V9 新 term/子类覆盖，不回改旧类）**：断腿 env 豁免断腿
   hfe/kfe 的 r_co（undesired contact）罚——近零质量残肢拖蹭不可避，不豁免
   = 无解惩罚。`.*_foot` 不豁免：断脚被动撑地合法（野外三足蜥蜴残肢当支点）。
   断脚接触力 ≈0 → r_fc/脚接触 term 视其为悬空，策略学会忽略断脚 = 预期
4. **训练源：v8 checkpoint 初始化微调**（前置依赖：v8 已训）。obs 90→94 形状
   不匹配，不能直接 resume——**weight surgery**：actor 输入层权重扩 4 列
   `damage_flags` 零初始化（t=0 策略行为与 v8 逐位相同，从健康步态起步，
   flag 用法学起——PITW"蒸馏当初始化"的等价物）；新 optimizer + 微调降 LR；
   obs normalizer 统计量（如有）pad mean 0/std 1。防遗忘三件套
   照 PITW：健康样本占大头（p=0.3 即天然配比）+ DR 不收窄 + 先冻结 policy
   只训 critic 的预热（若 resume 机制不支持则从零训——DR 混训本身自洽，
   微调只是省时，作 fallback 记入 NOTES）

## 不做（防蔓延）

- limp 档、损伤分级（severity）、多腿同断、断腿课程化（p 爬坡——固定 0.3
  起步；健康步态被三足补偿污染/塌缩时再上课程，触发信号记 NOTES）
- ablation_harness 之外的评测协议变更

## 验收（继承 v8 全部 KPI + 新增）

1. **健康 env：v8 反划脚 KPI 不掉档**（防"永远瘸"塌缩，主判据——
   塌缩症状 = 健康回放出现三足步态特征）
2. **断腿 eval suite**（ablation_harness 新增：固定 LF/RF/RL/RR × 命令网格）：
   位移/跟踪达健康档 ≥60%（初值可调，首跑后校）
3. **GUI 肉眼**：断腿回放三足步态 + 躯干/尾代偿可见；健康回放无代偿特征

## 结论

（一句话，训练后补）
