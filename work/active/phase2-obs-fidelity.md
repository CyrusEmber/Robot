---
id: phase2-obs-fidelity
title: Phase 2 输入侧两件：特权真值 term 的 event 缓存 + 三噪声模型移植
scope: rl_exp/tasks, rl_exp/versions/lizard
status: open
landing: rl_exp/tasks/teacher_mdp.py, rl_exp/tasks/components.py, rl_exp/tasks/student_networks.py, rl_exp/versions/lizard/OBS.md
next: 两件分别做，都先复现再改。① 摩擦/外力真值 obs term：先认现值取自哪一层（`foot_friction_truth` 的材质桶读回、`base_external_wrench` 的 `permanent_wrench_composer`），复现"DR 在 reset 改过摩擦后现值陈旧"；确认后改成 event 写缓存 + term 只读缓存，并把 `OBS.md` 里那条偏差句换成现行规则。② 三噪声模型（逐点噪声 / 遮挡 / 漂移，参考仓库实现）从 C++ 移植成 Python，接在加噪高度扫描上；动手前点名当前哪一层是 C++（框架侧还是参考实现），并判定与 teacher 侧已有的 Miki S8 噪声（`NoisyFootRing`）是补第二套还是替换第一套——不许两套并行语义
close_when: 执行者在 Phase 2 开工前各跑一次并留观测：① 触发一次改摩擦的 event，同一 run 里 obs 真值随事件变化（不再只在 startup 语义下有效）⇒ 该件成立，仍陈旧 ⇒ 写出实际取值层并保持 open；② 离线跑噪声模型对照，三种模型对同一条干净扫描给出确定输出、且与参考实现逐点比对一致 ⇒ 该件成立，对不上 ⇒ 记差异清单（哪一模型、哪个参数轴）。两件都有观测即关；只做成一件就把另一件拆出去单列
evidence: rl_exp/versions/lizard/OBS.md
---

## 未覆盖边界

student 侧的蒸馏 runner 本身不在本项；obs 维度/布局的声明面归 `versions/obs_protocols.json`，本项不新增或删除 term。教师侧噪声已在用、student 侧还没有 Python 实现，是本项 ② 的起点。
