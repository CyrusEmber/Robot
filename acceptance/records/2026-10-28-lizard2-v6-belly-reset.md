# lizard2 main/v6 腹部触地立即重开

## 适用范围

用户于 2026-10-28 要求“加回来腹部接触地面就重开”。已训 v5 的最终策略收腿后由胸腹和尾部承地，但原 `base_contact` 只检查 `base_link`；实际胸腹外壳属于 `chest_pitch`。本轮建立独立 v6，不改已训 v5 的 YAML、资产锁、配方语义或 tag，不启动训练。

实现为 `rl_exp/tasks/lizard2_recipe.py:lizard2_belly_contact_gate`，在既有 `base_contact` 中加入胸腹外壳。使用既有 `mdp.illegal_contact` 和每物理子步接触历史，未增加内核、依赖或奖励项。独立任务为 `Lizard2-Flat-v6` / `Lizard2-Flat-Play-v6`，日志身份 `lizard2_v6`。

## 验收条件

- 胸腹单独接触超过继承阈值时，旧版漏检、新版 TRAIN/PLAY 都在首次控制步检查终止；无新增持续时间。
- 根部保护保留，足和尾接触不加入腹部终止；阈值边界、历史窗口及跨环境隔离可破坏、可复读。
- 新版除了腹部选择及独立日志身份，与 v5 对应 TRAIN/PLAY 配置逐字段一致；原 v4/v5 行为回归继续成立。
- 原生仿真捕获自动 reset 前的真实接触与终止信号；同源 checkpoint 的趴地轨迹在新版重开，零动作四足站立不误重开。
- 配方声明、资产锁、登记和观测身份可核；通过新上下文对实际落点与证据审核，不用格式闸门代替审核。

## 结果

### 行为与边界

腹部选择为 `base_link`、`chest_pitch`，阈值沿用严格大于 1 N。history=4、dt=0.005 s、控制周期 0.02 s，任一历史子步触发即在当前控制步返回终止并自动 reset。只扩大既有 `base_contact` 的覆盖，不恢复旧的整个胸颈瞬时终止，也不改变 v5 的头部连续 0.5 s 规则。

这是一条刚体接触判据：当前平地、物理自碰撞关闭的配方使用净接触力；不把它描述成任意环境中的仅地面滤波判据，也不区分该刚体网格的腹面、侧面、背面。足、腿与尾保持原许可范围，腹部奖励项仍只按母本读取 `base_link`，未借本轮修改奖励语义。

### 失败对照与回归

`rl_exp/out/v6_belly_legacy.log` 由 `test_lizard2_v5.py --legacy-belly` 复现 `LEGACY_BELLY_FAILURE: chest belly contact did not reset immediately`。同一真实 TerminationManager 输入改用 v6 后通过；具名测试还覆盖足/尾大力不触发、1 N 不触发、超过阈值立即触发、最旧物理子步接触、单环境隔离及原根部保护。

`rl_exp/out/v6_belly_tests.log` 保留完整回归；本轮运行的 11 项均通过，其中 TRAIN/PLAY 对照核对 scene、rewards、actions、observations、events、commands、sim、curriculum 和 PPO 的非目标字段一致。差异声明生成器只发现一项环境路径及独立日志身份；golden 更新工具仅报告新增两个 v6 任务，没有改写其它任务条目。v6 资产锁由仓库工具首次生成，不刷新旧版锁。

### 原生自动 reset 对照

同一最终 v5 checkpoint 的 SHA256 为 `a5024c9256e8f588bf9f280f48d195237587f349b1d912725e3403b8111395ea`。固定 seed=0、1.5 m/s，两个环境分别施加策略和零动作；每臂运行 3 s。诊断在 `TerminationManager.compute` 返回后、环境自动 reset 之前抓取接触历史和 term 信号，不用 reset 后的姿态反推终止原因。

- v5：策略重开 0 次、零动作重开 0 次；策略胸部历史峰值 18232.25 N，说明有真实接触而原选择漏检。峰值是落地冲击，不能解释为持续承重或静态体重。
- v6：策略重开 13 次、零动作重开 0 次。首次重开发生在第 11 控制步（0.22 s）；`base_contact=true`、头部终止与 timeout 均为 false，根部接触 0 N、胸部接触 18232.25 N，确认由新增胸腹选择触发。
- v6 零动作末帧四足接触力约 213.08 / 213.11 / 122.40 / 123.29 N，投影重力 z≈−0.99964；本工况下四足支撑未被误终止。

原生旧版报告 `rl_exp/out/v6_belly_reset_before.json` 为 `passed=false`，新版 `rl_exp/out/v6_belly_reset_after.json` 为 `passed=true`。此处 passed 只表示该诊断的接触与自动 reset 判据，不是策略步态验收。

### 仓库检查与独立审核

首次完整检查发现限速闸门只登记 v4/v5，将相同物理配置的 v6 误判成未审核限速。只将 v6 加入同一严格分支，并将既有 missing/changed/extra 破坏测试同时用于 v4/v6；`v6_configclass_fields.log` 中各破坏均报错，正常基线通过。不改变任何驱动数值或闸门阈值。

第二次检查在 `check_golden_frozen.py` 拒绝新任务黄金文件的旧摘要，未将其当作可忽略告警。此前 `check_cfg_lock.py --update --line lizard2/main --reason ...` 只报告 `2 task(s) added: ['Lizard2-Flat-Play-v6', 'Lizard2-Flat-v6']`，没有 changed/removed 条目；只读 `--diff` 用于核对当前所有任务构造与登记一致。旧摘要 `d53f83788660022b242e69279de4908cd3b03f19f4b98fd14b9c04d8081f1dff`，新摘要 `ccdeea8043f1b8e3d7a50bf9c613c1476cf1cf136d37b19d5f812e748ff71037`。按闸门要求同步更新冻结摘要与 `lizard/ACCEPTANCE.md` 的 B0 路由，原因仅为新增 v6 的 TRAIN/PLAY pair；其余四份基线不动。该轮失败输出保留在 `v6_offline_suite_final.log`，不覆盖失败历史。

第三次套件在 hard A/B 覆盖钉数处明确拒绝尚未登记的 v6：比较集合仍为 10、新版本差异未入表。按生成器实际输出补入 v6 的两条差异（腹部选择及日志身份），覆盖计数改为 12；没有放宽任何旧版差异计数，失败日志保留在 `v6_offline_suite_ready.log`。

原生诊断的 JSON 和终止帧读法不变；输出完成后显式把通过/失败码传给 `SimulationApp.close(exit_code=...)`，避免 Kit 快速关闭丢掉失败退出码。

第四次套件的 37 项功能全部通过，但 `check_obs_protocol.py --self-test --live` 为 32.0 s / 单独确认 27.6 s，超过原有 25 s 单项预算；实际退出为 `OFFLINE_SUITE_COST_REGRESSION`，原日志保留在 `v6_offline_suite_complete.log`。没有放宽预算、删掉任务或破坏测试。

性能剖析 `v6_obs_profile.pstats` 定位同一检查内的 TRAIN/PLAY 对相同路由重复解析 YAML。只在 `assets_on_protocol` 一次调用内按 `(line, version)` 复用资产字符串或未解析结果；没有跨调用缓存，不改运行时读取器，非字符串输入仍交原读取器处理。`v6_obs_repeat_reproduced.log` 为有效旧实现负例，最终 `OBS_PROTOCOL_GATE_FAILED (1)`；`v6_obs_repeat_verified.log` 中共享路由、不同版本、下一次输入变化、非字符串路由及全部原破坏测试均通过，声明/黄金/实时配置覆盖仍为 50/50/12。相同 CLI 的单独复测为 18.4118 s、退出 0，计时保留在 `v6_obs_repeat_verified_timing.json`。带 cProfile 的时长仅用于定位，不作为前后速度比较。

最终完整检查 `rl_exp/out/v6_offline_suite_all_green.log` 返回 `ALL_OFFLINE_CHECKS_PASSED (37/37 in 140.5s, wave 279s/informational, jobs=2)`，观测检查为 21.1 s，所有原预算保持不变。此前失败日志全部保留，没有用部分通过替代完整套件。

独立新上下文审核结论：通过。审核者未参与本轮执笔，按 work-ledger、versioning 与开发规则核对实际落点和原始证据：`lizard2_recipe.py:373` 的选择扩展仅挂入 v6，v6 YAML/base/diff/PLAN/NOTES、任务/runner/观测登记与 v5 隔离一致；实际 USDA 的 `Geometry/chest_pitch` 是刚体，其 `chest_pitch_collision` 子网格挂有碰撞 API（161–193 行），并非凭刚体名称推断归属。已逐项比对 v5/v6 资产锁中的非 YAML 资产哈希，无漂移，实际 checkpoint SHA256 与两份原生报告一致。已读取旧版失败及新版回归日志、两份原生 JSON 和同名日志，并核对真实 `illegal_contact` 的严格阈值/历史峰值算法、环境自动 reset 链及探针在 reset 前采样的位置；这些行为证据支持当前平地配方的腹部接触重开，未以声明一致代替行为验证。限速破坏测试、黄金重锚与 hard A/B 登记均保留原约束；配方锁只据工具输出判定，未直接读取正文。新增观测检查优化仅在一次调用内按完整路由复用不可变路径或 None，非字符串输入仍交原读取器，未共享可变配置或跨调用缓存；有效旧实现负例、四项新回归、原破坏测试及完整套件输出已核，任务覆盖未缩减，原成本预算未变。未发现剩余阻断缺陷，允许主代理按 git-auto-sync 执行本轮明确归属文件的提交和 `lizard2-main-v6` tag，并按 work 关闭条件归档；提交、tag 与推送的实际完成及核验仍由主代理随后落实，本审核不把日志 banner 当作 tag 已存在的证明。审核边界仍为单 seed、双环境、短时平地对照；整刚体净接触力不能区分腹面/侧背面或任意接触来源，不外推粗糙地形、自碰撞开启、大规模训练容量或学习效果。本审核未重新运行重型仿真；先前录像兼容修复不作为腹部行为证据。

## 证据引用

离线回归：`python -B rl_exp/tools/verify/test_lizard2_v5.py --legacy-belly`（预期失败）及不带该开关的修复回归。

原生复读（从仓根，替换 checkpoint 为本机对应路径；`--out` 须使用新文件）：

```powershell
& E:/IsaacLab/env_isaaclab/Scripts/python.exe -u -B rl_exp/tools/diagnose/belly_reset_probe.py --task Lizard2-Flat-Play-v5 --checkpoint E:/IsaacLab/logs/rsl_rl/lizard2_v5/2026-10-26_16-35-11/model_5999.pt --out rl_exp/out/v6_belly_replay_before.json --viz none
& E:/IsaacLab/env_isaaclab/Scripts/python.exe -u -B rl_exp/tools/diagnose/belly_reset_probe.py --task Lizard2-Flat-Play-v6 --checkpoint E:/IsaacLab/logs/rsl_rl/lizard2_v5/2026-10-26_16-35-11/model_5999.pt --out rl_exp/out/v6_belly_replay_after.json --viz none
```

生成与声明：`emit_diff_declaration.py --line lizard2/main --version v6 --out rl_exp/versions/lizard2/main/v6/diff.json`；`check_dr_parity.py --update-locks --version lizard2/main/v6`；`check_cfg_lock.py --update --line lizard2/main --reason <本轮原因>`。这些是本次首次登记命令，不是复读旧锁的更新许可；只读核对用各工具默认模式。

原生 stdout/stderr 位于上述 JSON 同名 `.log`；先前失败姿态和零动作短对照保留在 `rl_exp/out/v5_inversion_diagnostic_20261028.json`，录像矩阵取 `ablation_harness/videos/v5_20261028_5999/matrix.json`。本机产物不入仓，其缺失不允许虚构重现结果。

## 未覆盖边界

本轮没有训练 v6、没有迁移权重开始学习、没有证明策略性能或步态改善。原生仅双环境、单 seed、短时对照，不外推大规模训练容量、粗糙地形或开启自碰撞后的接触来源。原生失败臂与通过臂按同一读取方式采集，不能把接触冲击峰值当作实际持续载荷。
