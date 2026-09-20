---
id: headless-flag-deprecation
title: `--headless` 已弃用而本仓仍在用（HARNESS 挂账 #6）
scope: ablation_harness
status: open
landing: ablation_harness/run_ablation.py#83, ablation_harness/run_ablation.py#115, README.md#223, .codemaker/skills/tool/isaaclab-task-creator/references/runtime_facts.md
next: 先做证据分级，再决定删或留：① 查 **task cfg 整条继承链**是否声明 visualizer —— 本仓 `rl_exp/tasks/` 的 cfg 加上它继承的**框架侧基座 cfg**（在 `<ROOT>`，不在本仓；2026-09-20 实测本仓零声明，只查本仓会得到"没有 visualizer"的假结论，只算第一步）；② 核该声明在配置解析后是否真的启用；③ 核 `--viz none` 是否影响 `run_ablation.py` 这条调用链（透传之后有没有别的覆盖）。把三步结论按"已核到行为 / 仅读到声明"写进本项，再执行下面的关闭动作
close_when: 执行者按 ①→②→③ 做完后观察启动行为——带与不带 `--headless` 各起一次同 task 训练命令，比对启动日志与 visualizer 相关输出。行为等价 ⇒ 删除两处透传并同步 README / skill / vN NOTES 的命令示例，观测 = 命令仍能起训且不再出现弃用告警；行为不等价（例如启用 visualizer 的 task 需 `--viz none` 才真 headless）⇒ 保留透传，并在本项写明保留理由与必须用 `--viz none` 的场合。两种终局都以 ① 的观测为准，写回本项后即关
---

## 问题与本次范围

IsaacLab 现为 "omit `--viz` for default headless"，但 `run_ablation.py` 仍在 train/eval 两条命令里
透传 `--headless`，命令示例侧（README、若干 skill、vN NOTES）也这么写。跑起来只多一条弃用告警，
所以它躺得住——躺得住的代价是没人知道删了算不算等价。

## 落点的三分（不要混成一句）

- **实际调用点**：`run_ablation.py` 的 train / eval 两处透传 —— 改行为只改这里。
- **需要核对的配置来源**：被调用 task 的 env cfg 是否声明 visualizer，以及解析后是否真的启用。
  **这是本项最容易被跳过的一步**：读到"声明了 visualizer"不等于"实际启用了"。
- **参考示例（不是落点）**：README 与 skill 里的命令行示例 —— 它们只是文档复述，改了不影响行为，
  但不改就会继续教后人写弃用参数。

## 未覆盖边界

本项只管本仓两处透传与示例；IsaacLab 侧的弃用时间表不在本仓可控范围。也不在迁移批次里顺手改
（试点只迁移事项、核对落点、测量读取成本）——功能修复另行实施与验收。
