---
id: teacher-snapshot-asset-sync
title: 资产换代时同步 teacher 快照文件（PLAN #8；同步仍人工）
scope: rl_exp/tasks, rl_exp/tools/verify
status: open
landing: rl_exp/tools/verify/check_dr_parity.py, ablation_harness/HARNESS.md
next: 先核闸门对"漏同步"的实际覆盖，再决定同步要不要机器化：分别改一处资产侧事实（关节名 / 资产路径 / 机器人块某一行）而**不**手工同步 teacher 快照，看 `check_dr_parity` 的 ④robot 块、⑤usda 结构契约、⑥asset_lock 三条各是否报 DRIFT。三条都拦 ⇒ 余下动作只是"把同步从人工改成机制，或明确记为人工纪律"，**由用户拍板走哪条**；有一条拦不住 ⇒ 先补那条闸门，那才是漏同步的真缺口
close_when: 执行者做完三处反向验证并把结果写进本项：三处各报 DRIFT ⇒ 记"闸门覆盖完整"，随后按用户拍的那条落地并复跑 `run_offline_checks.bat` 全绿 ⇒ 关；任一处不报 ⇒ 保持 open，缺口指向该条闸门（补闸门另立实施项）
---

## 当前状态

teacher 快照（`teacher_env_cfg.py`）与家族侧（`lizard_env_cfg.py`）是**手抄冻结**关系：资产换代时两侧要一起改，机器只负责"报警"——`check_dr_parity` 的 ④⑤⑥ 三条（机器人块对称差、usda 结构契约、asset_lock 哈希锁）。**同步动作本身仍是人工**，这是本项的余下部分：漏同步会被离线闸炸出来，但闸门覆盖到什么程度还没做过反向验证。

## 未覆盖边界

本项不改 teacher 的快照纪律（零家族 import 是冻结纪律），也不接管版本目录四件套的机械迁移——那由换代 commit 自己完成；补闸门或改同步方式都另立实施项，本项只负责"覆盖核认 + 选定机制或纪律"。
