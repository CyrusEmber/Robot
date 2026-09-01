# Lizard-Rough-v2 实施计划（存档 · 追溯补录）

> 状态：**冻结待训**——teacher 快照落地 + 冒烟通过（家族 PLAN 更新行记 v2.1），
> 训练 = 家族 PLAN 挂账 #3 关键路径；结果回填走 `NOTES.md`，不改本文。
> 本文件为计划层追溯记录（2026-09-01 补录）。复现：任务 id `Lizard-Rough-v2`
> （obs 308）常驻注册，或 git tag `v2` 整树快照。
> 修订：v2 初稿（追溯补录）

## 1. 目的与假设

v1 特权信息不全。对照 Miki et al. 2022 特权表逐项补齐，抬高 teacher 上限、
补全蒸馏目标。假设：同 DR 对照（v2 vs v1 同协议 eval）能量出特权补全的净增益。

## 2. 当时方案

- **代码级结构变更，yaml 与 v1 逐字相同**（变量隔离：只动 obs 结构，不动扰动）。
- 新增 5 个特权 term，+42 维（266→308）：`foot_contact_forces` /
  `foot_contact_normals` / `foot_friction` / `thigh_shank_contacts` /
  `base_external_wrench`——实现细节表见 NOTES.md，完整 obs 布局 SSOT 在 FAMILY.md。
- 确立版本差异机制：`TEACHER_PRIVILEGED_SPEC` 为代码级版本差异唯一真源，
  基类 wire 全部 term 后按 spec 剥离；**纪律：已发布 term 实现永不改语义，新版本只加 term**。
- **决策 B（用户拍板，2026-08-31）**：存量偏差保留——真值速度 6 + 逐 body 质量 27
  为论文外超集特权；若复现保真度出问题 → 删两 term（obs 269）重开版本。

## 3. 明确不做

- DR 不回调 v0 全量（保持 v1 收窄值）；奖励/终止不动；CPG 继续挂账。

## 4. 验收线

沿用 v1（~1000 iters 内 feet_air_time >0；判死刑信号同）。
冒烟已过（teacher_smoke.py，PLAY）：OBS_SHAPE 308、MASS_SUM≈72、
FOOT_FORCES_Z≈700N、FOOT_NORMAL_Z≈+1、BASE_WRENCH=0。

## 5. 结局

待回填：训练 → `dump_tb.py` 导出曲线 → harness eval（tag=v2）→ NOTES.md 回填；
与 v1 同协议对照判读。

## 6. 修订记录

| 日期 | 版本 | 变更 |
|---|---|---|
| 2026-09-01 | v2 初稿（追溯补录） | 补录本计划文档；内容由 NOTES.md / FAMILY 版本历史 / 家族 PLAN 整理，不改方案实质 |
