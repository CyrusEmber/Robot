---
id: record-variant-and-snapshot-specs
title: 记录体系 A1（--variant 语法与一致性）+ B1（快照外置）
scope: ablation_harness, rl_exp/tools/runrecord
status: open
landing: ablation_harness/record.py, ablation_harness/eval.py, rl_exp/tools/runrecord/binding.py
depends_on: record-format-live-checks
next: 按定稿口径实施（**实施前不得改口径**），顺序沿执行链 ④ B1 → ⑥ A1。**A1**：`--variant <token>[+<token>...][-<自由文本>]`，token 取 `record.SUBSTITUTION_CATEGORY` 五类；重复 token、解析不出 token、自由文本带路径分隔符三种都拒；检查做成 `record.py` 纯函数，在 `parse_args()` 之后、`AppLauncher()` 之前调用；已证实的变化类别必须包含在声明里，多写允许但不得被解释为已证实（分 `claimed`/`confirmed` 两列，禁止写成集合相等）；`comparison != compared` 时不做一致性判定；`--overwrite` 不绕过。**B1**：按摘要命名的共享快照 + 记录留摘要与 ref（ref 相对 results 根）；`agent_cfg` 保留 `clip_actions`；已存在的快照必须校验摘要再复用；读侧分"可用 / 缺失 / 损坏或摘要不符"，缺失可回 unknown 但要可见原因；旧内联记录继续可读；不改 `eval.json`；导出单个 run 目录要带上被引用的快照。**一年后最该防的**：基线被 `--overwrite` 改写而旧 `substitutions` 仍指同一路径 ⇒ 必须留"当时"的比较依据
close_when: 执行者按 B1 → A1 实施并各留一次观测：B1 = 一次真 run 后快照落共享位置、记录里的 ref 可解析、把快照改坏后读侧报"损坏或摘要不符"而不是照用；A1 = 五种非法声明各被拒一次、合法声明落成 `claimed`/`confirmed` 两列、`comparison != compared` 时无一致性判定。两条各自观测成立即关；观测不到的那半保持 open
---

## 未覆盖边界

A1/B1 是记录体系剩下未实施的两件（①②已闭、⑤a 离线回归已落）；真跑核对是另一条活跃事项，`depends_on` 指向它——没真跑核过的格式不往上叠。两条小敞口保留：`--variant` 命名靠人；`record.json` 体积主要被 `env_cfg` 快照占据（升级路径 = 内容寻址快照）。单源扫描闸的分工归 `check_record_bindings.py` 与 `terrain_map.check`，导出侧协议校验**已随 `work/closed/2026/distillation-export-checks.md` 取消**（用户 2026-09-22：当前不做蒸馏），本项都不动。
