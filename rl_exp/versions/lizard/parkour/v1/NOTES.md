# Parkour v1 — NOTES

> 骨架（versioning.mdc §A）：目的 / 假设 / 相对上版 diff / 训练命令 / 结果回填 / 结论。
> 本版为支线首版，无上版——"相对上版 diff" 记相对家族主线 v5 的关系。

## 目的

在 lizard 上复现 Parkour in the Wild 核心范式：跑/爬/跳三专家（位置任务，
特权高程感知）→ DAgger 蒸馏成深度感知学生 → RL 微调恢复并超越专家。
切片验证管线，不含 9 技能全量与扫描地形。

## 假设

- H-A：位置任务 (r\*,ψ\*,t\*) + 防趴窝三件套可在 lizard 上稳定训练（M2 首专家验证）
- H-B：lizard 跑跳物理可行（M1.5 probe 裁决；不可行则双专家管线）
- H-C：蒸馏掉点 −10% 量级、RL 微调恢复到专家 ±5%（论文对标）
- H-D：height_scanner 特权可承载专家训练（论文 elevation map 映射）

## 相对上版 diff（vs 家族主线 v5）

- 命令：velocity → 位置任务（新 command term + S_L 判定）
- reward：v5 反划脚包 → 论文 Table 2 移植（正则数值论文初值）
- 感知：教师特权沿用，学生侧引入深度图路线（Q2 终裁前不实施）
- 训练范式：单 teacher → 多专家 + 蒸馏 + 微调三阶段
- 共用：机体/assets/DR 框架/eval harness/SplitEncoderModel/StagedCurriculumTerm

## 训练命令

（待 M1 注册后回填：`--task Lizard-Parkour-Climb-v1` 等）

## 结果回填

（待训练）

## 结论

（待结果）
