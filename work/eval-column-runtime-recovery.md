---
id: eval-column-runtime-recovery
title: 套件列间耦合历史仿真运行环境恢复
scope: rl_exp/tools/diagnose/column_coupling_probe.py
status: open
landing: acceptance/records, rl_exp/tools/diagnose/column_coupling_probe.py
next: 追索历史运行环境来源并验证恢复；无法确认的部分保留缺口。
close_when: 新上下文对照历史身份与恢复运行证据审核，未完成不关闭。
evidence: acceptance/records/2026-10-28-eval-column-coupling-repair.md
---

## 当前范围

- 承接列耦合事项中完整历史运行依赖的可恢复位置与恢复验证；现有本机源码、资产和数据归档不是完整仿真环境。
- 已找到额外缓存及同时间窗口日志候选，但不能直接绑定历史进程；详细证据与边界见 `evidence`。
- 不覆盖原始数据，不把当前机器环境冒充历史环境，不用其他日期的运行信息补造缺失身份。

## 下一步

1. 继续追索历史安装日志、包集合或备份；当前环境旁证见 `evidence`，不能视为历史身份。
2. 找到可用来源后在隔离位置恢复并运行历史诊断，核验身份、复读与输出；保留原始数据和失败现场。
3. 完成后置 `pending_review`，由新上下文对照历史证据、来源和恢复结果审核；不可自行放宽为仅离线复算。

## 关闭条件

- **审核者与输入**：新上下文核验历史证据、依赖来源、隔离恢复过程和运行结果。
- **可观察验收**：恢复后的历史仿真环境有可追溯的依赖身份，真实运行诊断并可复读；缺失身份不得臆造。
- **交付与边界**：记录可复读的恢复位置和命令；异地备份与引擎内部状态若未验证须明确说明。
- **结果处理**：通过审核后关闭；可修缺口退 `in_progress`，仅用户能解决的缺口置 `blocked`。
