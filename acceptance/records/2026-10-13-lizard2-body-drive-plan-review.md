# lizard2 机体与驱动候选计划审核（2026-10-13）

## 适用范围

用户请求审核 `work/active/lizard2-body-drive-candidate.md` 相应计划。本上下文未参与该计划执笔；对照当前事项、R1–R5、整体记录、P1/P2 证据、实际导出器及 S5/S6 交接审核可执行性。本次不是 D 集成验收，不批准几何、容差、动力学或采用。

### 审核输入绑定

- `code_rev`：`83c6ead`；审阅时下列两个事项及导出器均无工作树改动。本次仅给主事项增加本记录的 evidence 指针，不修订受审正文。
- `upstream_path`：`work/active/lizard2-body-drive-candidate.md`；`record_date`：当前工作树（内含 2026-10-13 决定）；受审正文文件 SHA256：`71b3efc7449a2b1c45671cbac1af67ddc1725da9fac9959a50aecf673a049676`。
- `upstream_path`：`work/active/lizard2-family-landing.md`；`record_date`：当前工作树；SHA256：`43e1fcd4cb0560ccb3af1ed9e360395d776c3791f60cf508f72e0db8e53ed9ed`。
- `code_digest`：`rl_exp/blender/scripts/generate_urdf.py` SHA256 `6e4fae4243bf92e3783cbd629675d22ec70517d9e3ea8ad8bf81c8ac6fbbcc54`。
- 其它上游记录的路径、日期见“证据引用”；读取版本为上述 `code_rev`。`asset_digest` 不适用：本次未读取或验收二进制候选资产；资产行为仅按历史记录确认其证据边界。

## 验收条件

执行顺序应能在不先正式采用、不跳过真实消费者验证的情况下到达 D；探测入口必须绑定当前无指/趾链；标定与最终比较应有明确、无环的交接；下游实施不能复活已取消的驱动。文档形状检查不能替代这些人工判据。

## 结果

**计划可执行性审核不通过，保留 in_progress。** 发现以下四项；已披露的 P2 碰撞和未执行动力学本身不作为“计划缺陷”，本次不把它们冒充新发现。

### F1 / P1：E 的必需运行时验证被推迟到依赖本项完成的 S6

主事项第 17 行及能力记录追加八将双命名运行验证定为“采用后才能做”；但 E4 第 3 条、第 110 行要求两套隔离目标真实运行，缺第二套目标即第一波未交付。`lizard2-family-landing` 又依赖本项，S5 先读已审设计，S6 才正式采用。按现文字执行会互等，或迫使执行者先采用未经候选运行验证的机体。

配方动作项、默认位姿和 joint_order 写有旧名，只说明诊断配置也需要映射，不能推出隔离配置必须等正式采用。将旧/新样本的 USD 与隔离诊断配置作为 E 的成对交付，明确由谁接通并跑真实动作/传感器路径；正式冻结配方迁移仍交 S6。若决定缩小 E 出口，应显式改判据并保证 D 的实际候选运行不依赖 S6，不能仅在进度叙述中降低出口。

复核方式：沿 E4 → D → S5 → S6 的依赖逐条检查，给出无需修改冻结配方即可加载第二套目标并读回至少一步的精确命令与记录；错配拒绝只能作负例。

### F2 / P1：P4 的开跑前提与 S5 的输入形成另一处闭环

主事项 P4（第 145 行）把预算、幅度、窗口和性能判据交 S5 在比较前确认，并要求缺证停 B/D 开跑前；D 第 3 条也把最终性能阈值交 S5。下游 S5 第 1 条先要求本项真实审核记录，第 3 条又需消费本项标定，才能提出阈值。于是 B/D 需要 S5，而 S5 的阈值需要 B/D 标定及已审交付。

应明确分开“隔离标定的安全预算和设计不变量”与“最终性能比较的冻结阈值”：前者在 B/D 开始前具名确定，允许产出标定；后者消费标定后在最终比较前由 S5 确认。或者明确允许 S5 的阈值子动作消费未关闭的具名标定记录并回送 D，取消它对完整设计已审交付的依赖。二者任选其一形成无环流程，不能让执行者临场解释。

复核方式：逐项列出首次标定和最终比较各自的输入、批准点和输出，确认任何输入都不来自该次比较的通过结论。

### F3 / P2：C2 的命令仍绑定旧五轴候选，不能消费当前 palm 骨架

主事项第 177 行给出 `--robot lizard2_candidate`，并将 C1–C3 描述为已有接口。实际 `generate_urdf.py:76–85` 为该目标保留 shared 命名、旧源角色及合成 hip；第 152–154 行要求骨集合精确匹配。当前四角色 palm 骨架交给该目标会在写前被拒。唯一 palm 目标 `lizard2_palm_contract` 的 axes 为 None，且第 87–88 行禁止实际导出；仅改命令中的目标名也不能解阻。

P3 需要先交付获准几何/轴下的真实 palm 导出目标及完整消费路径，再填 C2 的可执行命令，并同步 C3 的 URDF 文件名。已有 C4/FK 的补线任务不能替代导出器这一前置。

复核方式：同一已核四肢 palm 场景实际隔离导出，核对树、轴、末端网格及惯量；旧源/错绑目标必须在写前拒绝。此次源码核对已足以证明命令绑定不符，未生成资产。

### F4 / P2：下游 S5 仍要求接入已取消的趾根驱动

主事项 A1（第 122 行）和 B 第 2 条明确无指/趾根活动轴、不设置其驱动；`lizard2-family-landing.md:22` 却仍要求接入“趾根驱动”。该条是当前活跃实施指令，不是历史记录。按它落地会寻找不存在的关节、形成空动作组或重新增加用户已取消的自由度。

修订候选计划时须同变更更新这一接收方条款，改为消费获准的实际腕/踝动作与 palm 接触端；已取消的趾根驱动不得作为 S5 交付。检查动作通道和 joint_order 与实际关节集合一致，不以空匹配作为通过。

### 验证

初次沙箱内 Python 启动失败（uv trampoline permission denied）；获工具批准后重跑只读闸门：`check_work_docs.py` 退出 0（86 项），`check_suite_banners.py` 退出 0。记录落地后，提交前完整复跑 hook 对应检查，全部退出 0：

```powershell
& E:/IsaacLab/env_isaaclab/Scripts/python.exe -B rl_exp/tools/verify/framework_pin_check.py --strict --self-test
& E:/IsaacLab/env_isaaclab/Scripts/python.exe -B rl_exp/tools/verify/check_dr_parity.py --strict
& E:/IsaacLab/env_isaaclab/Scripts/python.exe -B rl_exp/tools/verify/check_version_docs.py
& E:/IsaacLab/env_isaaclab/Scripts/python.exe -B rl_exp/tools/verify/check_work_docs.py
& E:/IsaacLab/env_isaaclab/Scripts/python.exe -B rl_exp/tools/verify/check_suite_banners.py
& E:/IsaacLab/env_isaaclab/Scripts/python.exe -B rl_exp/tools/verify/check_obs_protocol.py --live
git diff --check
```

在线配置构建对表覆盖 6 个 live comparisons；没有启动动力学仿真。既有 fork dirty、历史 tag 缺失与限速警告保留。以上检查不验证计划依赖是否无环，不反证 F1–F4。

## 证据引用

- `work/active/lizard2-body-drive-candidate.md`：下一步、E4、A2/P4、C2、D。
- `work/active/lizard2-family-landing.md`：depends_on、S5 第 1–3 条、S6 第 1 条。
- `work/active/lizard2-contact-protocol.md`：样本标定与性能阈值的交接边界。
- `acceptance/records/2026-10-08-lizard2-joint-design-review-contract.md`：R1–R5，日期 2026-10-08。
- `acceptance/records/2026-10-10-lizard2-land-body-drive-overall-work.md`：联动设计修订、审核输入绑定，日期 2026-10-10。
- `acceptance/records/2026-10-12-lizard2-drive-capability-and-name-inventory.md`：追加八的运行时验证延期及追加十的未验范围，日期 2026-10-12。
- `acceptance/records/2026-10-12-lizard2-palm-chain-p1.md`：只读 palm 构建契约与导出阻断，日期 2026-10-12。
- `acceptance/records/2026-10-12-lizard2-palm-p2-sample.md`：P2 诊断与几何接受边界，日期 2026-10-12。
- `acceptance/records/2026-10-13-lizard2-lowered-body-vertical-shanks.md`、`acceptance/records/2026-10-13-lizard2-natural-ground-tail.md`：当前候选范围与未验碰撞，日期 2026-10-13。

## 未覆盖边界

没有运行 Blender、IsaacLab 动力学或全周期碰撞；没有验证二进制产物与历史记录逐位一致；不作 R1–R5 通过或关闭判定。没有改设计正文、资产、驱动、配方和阈值。上述修订建议仍待实施并重审；本记录及 evidence 指针是本轮唯一改动范围。
