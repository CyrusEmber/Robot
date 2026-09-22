---
id: cfg-lock-volume-read-discipline
title: cfg_lock 体积与锁正文读取纪律：判定不动
scope: rl_exp/versions
status: done
landing: rl_exp/tools/verify/check_cfg_lock.py, .codemaker/rules/versioning.mdc
evidence: acceptance/records/2026-09-21-cfg-lock-volume-and-read-discipline.md
outcome: 判定①（不缩减锁内容）的理由、实测读数与"重新考虑的条件"全归 evidence 记录；判定②（读取纪律）已落 `versioning.mdc` 红线——锁正文是闸门产物不是阅读对象，取用与判定只走 `check_cfg_lock.py` 输出。未改 golden、未重锚、未加体积阈值断言
---

决定与实测都在 evidence 记录里，本项关闭后不再持有正文（避免两份）。
