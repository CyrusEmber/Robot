# lizard2 反曲禁区确认与当前文档状态同步（2026-10-09）

## 适用范围

承接本对话用户要求先读取当前情况、随后更新文件的指令，明确限位需求并纠正文档中落后于正式 v3 接入的状态。本轮只更新文档与事项归档，不修改 URDF、USD、网格、配方、锁、协议或验证代码，不启动训练。

## 验收条件

- 用户明确的反曲禁区进入现有评审口径；待量测的边界与余量不得再被混称为是否禁止反曲尚未决定。
- 当前状态以正式采用记录和现有文件为准；旧机体的几何角度、策略行为及临时提案不自动作为当前机体的限位。
- 已完成的 Blender 交付按原关闭条件归档，未完成验证仍有现有活跃事项承接；不新增重复事项。
- 数值与结论只在验收记录保留，活跃事项及版本入口引用记录；不把文档同步写成物理修复或新增仿真验收。

## 结果

### 用户决定与剩余工作

用户原答复为“要根据不能反曲调整限位。已有work”。本轮将这项决定接入 `2026-10-08-lizard2-joint-design-review-contract.md` 的 R4，沿用 `work/active/joint-limit-shape-and-range-pass.md`。明确设计禁区已成立，逐腿伸直边界、屈曲侧、跟踪误差与控制余量尚待当前机体量测和验证；不再重复询问是否禁止反曲。

旧 hfe 事项在 `work/closed/2026/hfe-extension-stop-not-validated.md` 的关闭性质是 superseded，已移交父事项，未代表修复。其旧机体伸直角、越直量与策略影响不能照搬到新零位/新轴向；当前限位仍沿用旧值，尚无新限位方案获验收。

### 当前资产与工程状态核对

本轮读取时仓库 HEAD 为 `949239a`，工作区干净。正式 v3 的采用、动作集合、默认目标、最小运行与离线检查结果引用 `2026-10-08-lizard2-v3-landing.md`；本轮未重跑该记录中的仿真。

只读复算 `main/v3/asset_lock.json` 的 43 个文件，全部存在且 SHA256 匹配；这仅证明当前内容与现有锁一致，不证明碰撞安全或限位合理。复读：在仓根 PowerShell 读取该锁的 `files`，逐项对 `Join-Path (Resolve-Path rl_exp) $entry.Name` 运行 `Get-FileHash -Algorithm SHA256` 并与 `$entry.Value` 比较，预期无 missing/drift。

本地未发现 `E:/IsaacLab/logs/rsl_rl/lizard2_v3`；版本 NOTES 也无训练 run。未训练与未冻结状态沿用版本记录，不因资产锁已建立而混称训练候选已冻结。配置训练预算不在本轮改动；若以后用 6000 迭代，只能报告截至该步的表现，不能称为修复或收敛。多变量探索若无归因设计，不作为单项修复的验收证据；本轮没有批准或启动此类训练。

完整动作周期、真实网格碰撞、旧机体开自碰撞控制组仍未完成；左右命令符号仍保留现约定且待定。姿态角目标尚未验收，不以未经验证角度直接新增 reward 监督。限位实施涉及资产内容，继续按 `.codemaker/rules/versioning.mdc` §A 的新版本、资产采用与锁机制处理，本轮不刷新现有锁。

### 事项与指针同步

Blender 候选接受事实已由正式采用记录证实，Codex 依原 close_when 核对交付与交接后，将 `leg-chain-symmetry-convention` 移至 `work/closed/2026/`，保留 id、去掉 next、补 outcome。其限位、完整运行验证与镜像闸门仍由父事项承接，关闭不表示这些后续动作完成。

候选执行单的用户选择、接入/运行时状态及剩余缺口指向较新的落地记录；R1 的 D2 标记为已有部分答复，其余容差与工况不视作获批。配方事项移除已作废的“待建 v3/待做 v2 冻结”状态，保留部署边界、奖励与新协议交付。版本 PLAN/NOTES 仅补需求与后续工作的记录指针，不变更配方。

### 文档验证

复读命令：`E:/IsaacLab/env_isaaclab/Scripts/python.exe -B rl_exp/tools/verify/offline_suite.py --python E:/IsaacLab/env_isaaclab/Scripts/python.exe --jobs 4`。本轮输出 `ALL_OFFLINE_CHECKS_PASSED (47/47 in 82.9s, wave 307s/informational, jobs=4)`；末次文字勘误后单跑 `check_work_docs.py` 与 `check_version_docs.py` 均通过，`git diff --check` 无空白错误，检索无本次归档事项的旧 active 路径残留。既有日期证据的其它旧路径 HINT 与历史 tag WARN 保留，未据此改写历史记录或冻结候选。离线通过不增加物理验收结论。

## 证据引用

- 本对话用户（2026-10-09）：“要根据不能反曲调整限位。已有work”；后续要求“先读取当前情况”“更新文件”。
- `acceptance/records/2026-10-08-lizard2-v3-landing.md`：正式采用与最小运行结果，完整验收边界。
- `acceptance/records/2026-10-08-lizard2-blender-body-candidate.md`：几何交付与隔离诊断。
- `acceptance/records/2026-10-08-lizard2-joint-design-review-contract.md`：当前 R3/R4 验收口径。
- `acceptance/records/2026-09-29-lizard2-hfe-knee-limit.md`、`work/closed/2026/hfe-extension-stop-not-validated.md`：旧机体证据及归并关系。
- `rl_exp/versions/lizard2/main/v3/asset_lock.json`、`main_params.yaml`、`PLAN.md`、`NOTES.md` 与 `rl_exp/tasks/agents/rsl_rl_ppo_cfg.py`：本轮只读核对落点。
- `.codemaker/rules/versioning.mdc` §A/§B：资产锁与版本修订机制。

## 未覆盖边界

尚未量测当前机体的反曲边界，未实现或验证新硬限位，没有新增碰撞、长期稳定、扰动、完整周期或动力学结果。文档形状检查只能验证结构和指针，不能证明反曲已被物理禁止。其余未答需求仍按 R1 提案处理，本轮不替用户选容差、目标速度或左右符号约定。
