---
id: stale-entrypoints-after-prune
title: 清理后遗留的死入口与陈旧指针（默认任务 id / skill 清单 / 一次性脚本 / 记录口径）
scope: rl_exp/tools, .codemaker/skills, acceptance/records
status: done
landing: rl_exp/tools/diagnose, rl_exp/tools/verify, rl_exp/tools/archive, .codemaker/skills, acceptance/records
close_when: (a) 每个默认值要么指向仍注册的任务、要么改为必填，且工具自身的 `--help`/docstring 与之一致；(d) 一次性脚本不再留在 verify/ 主路径；(e) 两处口径与 `offline_suite.py` 的常数一致——判据 = `run_offline_checks.bat` 全绿 + 逐个工具 `--help` 打印的默认值是注册表里的 id；观测 = 清理 commit + 记录
depends_on: rl_exp/tools/verify/offline_suite.py
evidence: acceptance/records/2026-10-09-retired-family-prune-execution, acceptance/records/2026-10-10-stale-entrypoints-after-prune
outcome: 五条全落地——12 处默认值改指活跃任务或改必填、2 个主体已消失的工具删除（direction_probe / time_foot_rings）、2 个一次性脚本移入 archive（_b3 / _a0）、4 个 skill 文件的已删脚本入口改准、2 处 SERIAL_BUDGET_S 口径与常量（160）对齐；判词 `ALL_OFFLINE_CHECKS_PASSED (37/37)`。逐条依据、保留不动的旧 id 与未覆盖边界见执行记录
---

## 当前状态

已关闭（`done`）：退休线清理之后仍留在主路径上的死入口与陈旧指针已处置完毕，判词 = 执行记录里的
`ALL_OFFLINE_CHECKS_PASSED (37/37)`。改了什么、为什么留了几处旧 id 不动、以及没做到哪（未真跑任何
工具）全在执行记录，本项不复述。

## 未覆盖边界

只证"默认值指向注册表里存在的 id / 必填"，未起过仿真验证任何工具跑通；两个删除是我的裁决（
`direction_probe` 已 import 不了、`time_foot_rings` 的被测对象两个 id 都已注销），只有 git 历史与 tag
`lizard-final` 兜底；`diagnose_support` 改了默认值但 case 构造仍是 v10 台阶形状（归
`work/active/floor-contact-attribution.md`）；`terrain_split_env_run` 有工具无被试对象，等 lizard2
接地形课程（`work/active/dr-widening-policy.md`）才复活；`ablation_harness` 侧旧线默认值与
`versions/lizard/**` 历史文档按 10-09 的边界未动。
