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

## 追加：E 执行情况核查（2026-10-13）

### 适用范围

用户追问 E 的执行情况。复核基于 `88c7121`，相关 Python 与主事项正文无后续改动；工作树中其它会话改动不归本次。资产未重新生成或验收，`asset_digest` 不适用。本次仅追加本记录，不修 E 实现，不将本次离线检查冒充运行时或候选验证。

### 验收条件

按 E1–E4 原出口区分代码接入、真实消费者证据和缺口；shared/split 的同几何改名样本不得替代四角色 palm；整套错配被拒不得代替缺项、跨肢及混合命名校验。

### 结果

**E 部分执行，尚未达到第一波出口。** 下表的历史真跑指 2026-10-12 能力/名表记录追加六–十一，不是本轮重跑仿真。

| 面 | 已有交付 | 仍缺 |
|---|---|---|
| E1 / 名表核心 | 纯标准库；shared、split、palm 三种稳定命名；保留旧接口 | 不构成完整 E2 绑定 |
| E2 / 入口与拒错 | 消费者传递 naming；部分核末端、空匹配或键名 | 多数入口仍需另给 `--naming`（默认 shared），不是从所选目标/报告声明取得；精确集合及混合命名拒绝未完成，见下方内存反例 |
| E3 / URDF → FK、碰撞 | shared/split 同几何消费者及错配负例有记录；本次重跑 FK 孪生通过 | 当前 palm 的实际 URDF/碰撞未验；现有链位次与 CLI 的旧链假设仍需处理 |
| E3 / Blender | P1 真实 Blender/export consumer 校验 palm 骨树；P2 有隔离几何 | 只有写前契约；完整 palm 导出阻断，见 F3 |
| E3 / 运行时 | check_joint_layout、stance_step_probe 在旧名资产真跑，错误绑定被拒 | 第二套运行时配置/资产正例、当前 palm 动作与传感器全链未验；gait_probe 未接线 |
| E3 / 接触面 | diag_metrics、check_contact_ownership、baseline_probe 有接入及记录 | obs_protocol_live 改动分支未实际执行；diagnose_support 仍有旧 `_foot`，归 floor-contact-attribution 的接线未完成 |
| E3 / 报告 | plot_joints、baseline_metrics 已消费真实旧产物和数值不变的改名副本 | gait_probe 和 baseline_eval writer 未携带完整目标绑定；没有新目标运行 → 写报告 → 读取的闭环 |
| E4 / 出口 | 部分同几何对照、负例和自检 | 双命名运行时、完整导出与 writer、旧基线同条件复跑；不能按现有记录宣告交付 |

**E2 的可复现缺口：**

1. `joint_names.py:156–167` 的接触模式由末端后缀生成，`is_contact_body` 因而把 split 下 `lf_toe` / `alien_finger`、palm 下 `lf_ankle` / `alien_wrist` 均判为 True；这些名称不属于声明的逐腿精确末端。E2 第 6–7 条要求精确集合、跨前后肢错误拒绝，当前名表谓词不满足。部分消费者另做四末端核对，但不能据此宣称所有消费者都安全。
2. `baseline_metrics.py:885–905` 的 `_record_naming` 仅在所有列均不匹配时拒绝。传入 `lf_hip_joint`、`rf_shoulder_swing_joint`、`rl_hip_swing_joint`、`rr_hip_swing_joint` 四列，以 shared 绑定调用，函数正常返回。这是混合命名通过前置校验的证据，不宣称完整 judge 已跑出错误通过判决。
3. `gait_probe.py:817,826,849` 仍存在模块 `joint_names` 被 main 内同名局部 list 遮蔽；运行到前面的模块访问将遇到局部变量未赋值。源码已核，本次没有起仿真复现该分支；这是名表记录追加五已指出但尚未修掉的问题。

**本次实际复跑：**

- `python -B rl_exp/tasks/joint_names.py`：退出 0，含 palm 四角色名表自检。
- `python -B rl_exp/tools/verify/check_leg_reachability.py --self-check`：退出 0，含 shared/split 孪生的真实 FK 消费。
- 同工具 `--break-test`：退出 0，9 个扰动均检出。
- `python -B rl_exp/tools/diagnose/plot_joints.py --self-check`：退出 0；此入口只检 at-stop 数学，不是双报告绘图复验。
- `python -B rl_exp/tools/diagnose/gait_probe.py --self-check`：退出 1，`self_check_sole_area` 的 lizard2 壳 cap 断言失败：实读 `0.11928214877843857`，期望 `0.013352`。这是已有资产前提红项，未删断言或放宽判据。

上述 python 均使用仓库 `E:/IsaacLab/env_isaaclab/Scripts/python.exe`；可从仓根以此解释器 `-B -c` 复读内存反例：

```python
import sys
sys.path.insert(0, 'rl_exp/tasks')
import joint_names as n
for key, names in [('split', ['lf_finger', 'rl_toe', 'lf_toe', 'alien_finger']),
                   ('palm', ['lf_wrist', 'rl_ankle', 'lf_ankle', 'alien_wrist'])]:
    print(key, [(name, n.is_contact_body(name, n.naming_for(key))) for name in names])
from ablation_harness import baseline_metrics as b
sample = {'axes': {'joint_pos': ['lf_hip_joint', 'rf_shoulder_swing_joint',
                                'rl_hip_swing_joint', 'rr_hip_swing_joint']},
          'meta': {'task': 'mixed-naming-probe'}}
b._record_naming(sample, n.naming_for('shared'))
print('mixed record passed _record_naming(shared)')
```

### 证据引用

既有实施证据为上文所列 `2026-10-12-lizard2-drive-capability-and-name-inventory.md` 追加六–十一及 palm-chain-p1；计划判据为主事项 E2 第 2/3/6/7 条、E3、E4。源码绑定为 `88c7121` 下的 `joint_names.py`、`check_leg_reachability.py`、`check_self_collision.py`、`check_joint_layout.py`、`stance_step_probe.py`、`plot_joints.py`、`baseline_metrics.py`、`gait_probe.py`、`baseline_eval.py`、`diag_metrics.py`、`baseline_probe.py`、`check_contact_ownership.py`、`obs_protocol_live.py`、`diagnose_support.py` 与 `generate_urdf.py`（本次均未修改）。

### 未覆盖边界

本次不重复历史全碰撞扫描、报告绘图或 IsaacLab 仿真，不修复资产/代码、不推进 P3、不验收候选。建议下一步先补 E2 的目标绑定和精确拒错、修 gait_probe 名称遮蔽，再按 F1 解除隔离运行配置的错误延期；资产前提和 writer 归属交接仍须完成。新候选路径只有在 A 的前置成立后才能真跑，名表通过不能绕过该前置。

## 追加：审核意见回写计划与 work（2026-10-13）

### 适用范围

用户要求“把审核记录的覆盖到 plan 里面，修改之前的 plan 和 work”。以 `7d0eca2` 为修订起点，直接替换活跃计划中的失效指令，不将历史审核正文改写为已通过。受影响文件为机体候选、S5/S6 交付、接触协议和统筹四项，以及 `rl_exp/versions/lizard2/PLAN.md` 的候选入口；该入口指向的已训 v3 方案未改。`asset_digest` 不适用；未修改 Python、资产、配方或锁。

### 验收条件

F1–F4 和 E 执行核查的未完动作必须有当前计划落点及接收方；阶段依赖不再互等关闭；保留用户确认、几何前置、采用前运行验证和最终独立审核。只改执行顺序与交接，不虚构通过证据、有效 CLI 或新的数值批准。

### 结果

| 审核输入 | 本轮计划回写 |
|---|---|
| F1：运行验证延期到 S6 | E3/E4 明确成对 USD/隔离 cfg、实际动作和传感器、真实报告链由 E 交付；S6 保留正式采用与冻结版本迁移 |
| F2：P4/S5 循环 | B/C 先按安全预算和设计不变量标定；S5 阈值前置动作消费具名标定与接触口径，不等上游关闭；用户固定判据后 D 新跑最终比较；设计已审才做 S5 正式接入 |
| F3：C2 使用旧链目标 | 撤掉旧 C2 命令，补真实 palm 导出目标、轴/网格/惯量和写前拒错的实现任务；C3 只接 C2 实际输出，驱动不匹配先补隔离转换入口 |
| F4：下游趾根驱动残留 | S5 接入实际腕/踝与 palm 末端，并核动作/关节/默认位姿/传感器集合，不设置被取消的指趾根驱动或空动作组 |
| E2 绑定与拒错缺口 | 补目标/报告声明来源、旧 CLI 兼容边界、精确逐腿集合和完整列校验；负例覆盖跨肢、外来末端、混合命名、缺项、重名及空集，回归需验证修复前失败 |
| E3/E4 必需链缺口 | 明写 gait_probe 遮蔽修复、真实 writer → reader、在线协议非空分支、隔离运行正例及旧基线同条件复跑；接触协议项承接 writer 字段契约；diagnose_support 仍交原负责项并由 E 收交付 |
| 当前候选与审核路由 | C1 取最新尾贴地/body75 隔离记录；P2 执行者自检和用户确认后继续，独立审核仍统一在 D 后；版本 PLAN 只链接当前候选正文，不复制方案 |

手工核对的交付链为：A/P3 与 E 实际候选接线 → B/C 标定 → S5 阈值确认 → D 最终比较/审核 → S5 正式配方接入 → S6。接触口径与 writer 契约可按各自前置提前交付，不依赖机体事项关闭；`depends_on` 的完整交付语义在 S5 和统筹路由均已说明。既有在办动作保留，没有关闭事项。

回写后的 `framework_pin_check --strict --self-test`、`check_dr_parity --strict`、`check_version_docs`、`check_work_docs`、`check_suite_banners`、`check_obs_protocol --live` 均退出 0，调用方式沿用本记录“验证”节；`git diff --check` 通过。既有 fork dirty、历史 tag 与限速警告保留。文档闸门只验证形状/声明和配置构建，执行依赖及审核覆盖为本轮手工自检，不作为 E 行为通过依据。

### 证据引用

- 当前动作与判据：`work/active/lizard2-body-drive-candidate.md` E2–E4、A2–A4、B、C、D。
- 接收方：`work/active/lizard2-family-landing.md` S5 阈值前置/正式接入；`work/active/lizard2-contact-protocol.md` 动作 5–8。
- 路由与入口：`work/active/joint-limit-shape-and-range-pass.md`、`rl_exp/versions/lizard2/PLAN.md`。
- 修订依据：本记录 F1–F4 及“追加：E 执行情况核查”。

### 未覆盖边界

这是计划回写自检，不是新上下文重新审核通过，也不是 E 代码修复、P3 实现、B/C 标定或 D 验收。实际缺口与运行红项仍待执行；用户没有在此批准新数值、机体采用或训练。其它会话工作树修改未纳入本次。

## 追加：E 双目标实际消费者执行（2026-10-13）

### 适用范围

按主事项更新后的 E2–E4 执行。shared 旧链和 split 同几何改名样本用于验证命名、运行接线及真实 writer → reader；palm 仅验证四角色声明与拒错，不证明当前候选几何/动力学。不训练、不采用、不改冻结配方、协议、锁或资产断言。用户要求不再开子代理后，后续修改、复跑和本段回填均直接执行。

工作树存在并行修改。本轮起点为 `acd5c59bd2fefe699b3381e58da1b002d5d1c9b8`；回填时 HEAD 为 `fa48465ae702cc25f3390b7ba804d63a388c7219`，**不是本轮代码已提交的证明**。本轮代码仍为 dirty 工作树，以下文件摘要才绑定实际实现；早期真跑与末段复跑分开记述。Blender 两个共用脚本另含其它会话 palm 工作，不将整份 diff 或 `lizard2_palm_diagnostic` 当本轮已审交付。

实际源码 SHA256（由 `rl_exp/tools/runrecord/binding.py:sha256_file` 取得）：

| 路径 | SHA256 |
|---|---|
| `rl_exp/tasks/joint_names.py` | `262030343b8d379388e8011892673ddff0e6df024c2e464a0fb2239f78f980e5` |
| `rl_exp/tasks/obs_protocol.py` | `b64108dd2156fb1508e04eab0b06271a1d8589dcbeff6fb9df628831d268f967` |
| `rl_exp/tools/verify/baseline_probe.py` | `ff1564679f3a04709dbc73896a8156206e5abc68f89fa070b3d6b8ee0489a0ba` |
| `rl_exp/tools/verify/check_leg_reachability.py` | `5ce3c54c0712b40edd56803b1aa854a292f8a495de16753c696046632b60efb2` |
| `rl_exp/tools/verify/check_self_collision.py` | `3425518c66192b60fad9edc44a586adf8b7b2dedcf9f73d27d792e9b6d8d7bf6` |
| `rl_exp/tools/verify/test_baseline_contract.py` | `4287205c9f8f3e894bb66e78015fb5c27c198d5a65fd6987df81c834bd7ae741` |
| `rl_exp/tools/diagnose/diagnose_support.py` | `68f550123f98b82d4f2fc1d28a6b80dca36578d5e92a9bc16c7ea03269655464` |
| `rl_exp/tools/diagnose/gait_probe.py` | `0acaff8ee7f02ffd0590614e2b5170ea4cfe89f2b67bdc653432ec6f6a16075e` |
| `rl_exp/tools/diagnose/plot_joints.py` | `b8d4e2576fc66d2f4f8c48bab2db2b14c049871a0ce46976c2c7f31cc694f25a` |
| `ablation_harness/baseline_eval.py` | `5dad0f0d0564b546c2efbb68367a29405b27f83e837a075fcc1b512eefbe9a5b` |
| `ablation_harness/baseline_metrics.py` | `fbd63fb5ec784488d568f0dd96e373d10a1f4ad8a4fb4b409c8730f77c1a3929` |
| `rl_exp/blender/scripts/generate_urdf.py` | `b6f67578e493a942ed15632eabecc7b2348fde22bb9d54c2f3d33dc9db347bf8` |
| `rl_exp/blender/scripts/lizard2_stance_candidate.py` | `1552583d6044c36010f4499050dabdc11b34ba5d326bd34827cc81cd900fd80b` |
| `rl_exp/tools/verify/check_contact_ownership.py` | `0b8168c14eef0f0e7d7ef7713508e380cd17e0d10b467e7473246324287e8e7c` |
| `rl_exp/tools/verify/check_joint_layout.py` | `330e0565b9f5038b5df4a0d16206431b14b2493f8d5c341ee9f0f198e1a940d4` |
| `rl_exp/tools/verify/obs_protocol_live.py` | `c86b82fc88f584f2b3e05322ba164fe65674234e5eb48122213f222f6e402057` |
| `rl_exp/tools/diagnose/diag_metrics.py` | `a8e71e08b7cb333a92f9f6d1eaae31054cfb1d635e94c8f352393f8164bca9ef` |
| `rl_exp/tools/diagnose/stance_step_probe.py` | `ffdf52e13fcf4321ff0bbd1e66ec0d249e2a4fc4546f1275ae709f35d684ba0f` |

### 验收条件

沿用主事项 E2–E4，不降低出口：入口声明随实际目标传递；逐腿角色/末端、URDF 树、runtime joint order、动作和传感器精确核对；同几何改名经过同一实际消费者数值一致；错误绑定、混合/重名/缺项/空集拒绝；两套实际 writer 输出均经实际 reader。旧资产红项不放宽，受阻必需链不能凭“旧红”豁免。E 自检不是 D 后独立审核。

### 结果

**E 的双命名接线已大幅推进，但仍未达到第一波完整出口。** 两套旧几何样本的实际布局、站姿、步态、基线、在线协议和支撑测量均已运行；当前 palm 真实候选仍受 A 前提约束，接触所有权/资产自检及全仓闸门仍红，不宣布交付、不关闭事项、不提交未闭环代码。

#### 1. 输入与隔离样本

本机目录 `rl_exp/out/lizard2_e_20261013_final/`；其中 `shared.json` / `split.json` 为唯一目标来源，各有目标 USD/URDF、逐腿角色、精确末端、动作列表、URDF 顺序及实际运行测得的 `runtime_joint_order`。二者 task 都是 `Lizard2-Flat-Play-v3`。默认姿态、PD/动作尺度等由 deepcopy 后的诊断配置映射；不写冻结 yaml 或 runtime registry。

| 本机输入 | SHA256 |
|---|---|
| `shared.json` | `3a6cea0372668b5a5b72f7b61bf306d9c307e851293de1ddcecd0ba521a9cbec` |
| `split.json` | `743c0a489c6913b9053580421083515213f1bd1927ca1632a0dc8b38b0b3dc1b` |
| `lizard2_candidate_shared.urdf` | `9c57fbb7af1558c7da86d19650c5a6bd28fdaafcd27b1517f0ff31db09baf1c7` |
| `lizard2_candidate_shared.usda` | `cce0989b30fb642138aa8a20752a1d5042ed6499417ee70319135dc40c1fde6d` |
| `lizard2_candidate_split.urdf` | `d758c56f69f7eb3d65684db37ca49f249630777c2757448ec47f3ae385e7aecd` |
| `lizard2_candidate_split.usda` | `dc41586cf31eb89a38f69e2157804b78c8b009a823de6a212e47e22db9ac95a6` |

`identity.json` 记录两份 USD 各 104 prim、2289 属性（1722 数值属性）、215 relationship，经名称/路径映射后已 authored 数据全等。复读 adopted 源摘要仍为 URDF `da05432efd5d3c3dd9302682286825869b289d5f912cb5703bd0d32642e0c52b`、USD `fceaf55be1f045572121c464cb32e1eb0ae7d5d0ba63dfbe9a0d943f84df3b6c`，未被本轮改写。

真实 Blender 导出落在该目录 `blender_shared/lizard2_candidate.urdf` 与 `blender_split/lizard2_candidate_split.urdf`，分别 31 link / 30 joint；SHA256 分别 `da05432efd5d3c3dd9302682286825869b289d5f912cb5703bd0d32642e0c52b` / `e69b0290ee93d47a987d9ce5c6fa34c5f80b7c35de69ad75c35bd232af78ce5b`。各 80 个 OBJ/STL，摘要多重集合相同，树/轴/惯量按角色映射等值。源 `rl_exp/blender/lizard2_stance_candidate.blend` 摘要 `0a503c7069d665779392f7f8997c3839e807def9787df97cd0d1b2eb4cf41deb`。末段真实 Blender `--contract_self_check` 通过：旧消费者 3、split 1、memory-only palm 1、负例 10，388 个保护文件未变；此处 palm 正例明确 `geometry_proven=False`。

#### 2. 实际消费者与最终补洞

- `joint_names.py` 保留旧接口语义，新增精确 bound 接触接口、普通 binding 数据和校验；`PLANNED_ACTIVE` 不进入新选择路径。显式 `--naming` 仅作一致性检查，不能覆盖所选目标。
- `obs_protocol.load_diagnostic_target` 复用既有路径解析，验证来源、目标 task、摘要、角色/父关节/连通、重 link/多父关节、明确 URDF 顺序及动作列表。默认入口来源改为实际参数文档。`validate_diagnostic_runtime` 对 actual robot/sensor/action 名称和顺序核对；最后补上 active term 空动作拒绝，取消整个动作项用显式 null，不把空匹配作为合法通道。
- `gait_probe` 局部关节列表遮蔽模块的问题修复；shank 取真实末端父 link，网格取实际 URDF。不凭五轴链补 palm 不存在的 finger/toe。
- `check_leg_reachability.compare` 原 shared/split 文本交集为空，实际只读 1 个零姿态。现先将局部 chain token 对齐稳定角色，真实双入口 lf/rl 各比较 32 个非零极值组合；两侧位置跨度、有向掌面及 hinge 读数相同，不冒充目标动作通过。
- `baseline_probe` 原隔离入口主动不取 frozen approved width，却继续硬要求 approved，造成必红。现隔离分支核正式 term 顺序、每项正宽度及真实 observation tensor 总宽；明确打印 `not protocol approval`。正式无 approved 的原断言仍红。四环境而非单环境复跑，避免用 1 个样本证明 per-env 随机差异。
- `diagnose_support` 精确选四端，保留 sensor 返回顺序，按名称映射 robot 几何索引；全 body 力与位置也同序。网格来自实际目标 URDF，非足排序使用 bound 谓词；无 collider 显示从实际 mesh 集合取得，不再输出旧 `_kfe` 名。
- `check_self_collision` 使用各自声明和实际树，报告的姿态数改为此次实际 `poses` 长度，附目标/来源/命名，避免 split 报告又按 shared 重新计数。

早期真实布局两目标 `LAYOUT_GATES PASSED`：30 actual joints、22 action channels，其余为该 cfg 显式未命令关节；站姿探针在每个目标完成 20 settle 与三段各 10 step，0.15 rad，根角色实际 action column 5 / scale 0.5，shared 为 `lf_hip_joint`、split 为 `lf_shoulder_swing_joint`。两目标 `obs_protocol_live` 都真实进入 `BOUND_FEET` 分支并退出 0，不是无 extero 造成空循环。

末段最终源码两目标 `baseline_probe --num_envs 4 --steps 10` 均 `BASELINE_PROBE_OK`；实际 policy 宽 94，per-env sampled 检查通过。两目标 `diagnose_support --phases 0` 使用真实检查点 `E:/IsaacLab/logs/rsl_rl/lizard2_v3/2026-10-10_10-14-50/model_950.pt`，摘要 `16cb99de784fc2fde41736ca3358009ce14546fcf256d28ed2dab31bd89da3e0`，均退出 0。policy 与 zero-action 两个测量窗口全 body 承重比各为 1.001 / 1.0001；标量和具名 mesh 读数一致，非足列表名称随各自绑定不同，未把整份 JSON 宣称逐字相同。该旧检查点只用于同几何命名影响诊断，不作候选性能批准。

#### 3. writer → reader 交接

四份新 writer 均写 `target_binding` 与 `target_binding_required=True`，source 是各自 manifest。读者从报告取命名，拒绝缺来源/角色/列、混合名称、重名、冲突和 marked 新报告缺整个 binding；没有 marker/binding 的历史报告只走原历史分支。marker 不是防篡改签名，二者均被删除时无法单独证明产物不是历史报告。

| 实际 writer 产物（样本目录内） | SHA256 |
|---|---|
| `shared_gait_final.json` | `25813c16f59f373bd541cd617b66d13a63be1b5640c485bc356e7181d55bd00e` |
| `split_gait_final.json` | `df10fc6d207bd5baf4e8d5f6f38a0d24cb06703bd5ecf24a29a398843c415f63` |
| `shared_baseline.json` | `e05a28042830ba90621a7fa730226e04c4931768a9becc44d58a4a655ad355dd` |
| `split_baseline.json` | `b130e0a0668c438e6274cddcd71aa62fb43efca97bd7fb3e8c6f37688922dd79` |
| `shared_baseline.frames.pt` | `951eb48437fb6b2bc19ba4390a605e5b5b1f6a0eeb803d18067b6c0d7bd116b0` |
| `split_baseline.frames.pt` | `33e2301e15e0acdf7131791cffda8c776bd13a1f3012b5bea5e49a3fbc07fdf6` |

gait 两目标均实际 zero policy 10 个控制步，两份 `series` 相同；末段 `plot_joints` 实读两份输出并绘图，退出 0。baseline writer 使用冻结 `ablation_harness/protocols/lizard2_flat_v5.json`；两份无 checkpoint 报告的判词是 **smoke_only**，不是 pass。两份 frames 都经实际 `baseline_metrics` 复读退出 0；复读输出的性能判词不作为该无策略 smoke 的批准。

最终支撑产物 `rl_exp/tools/diagnose/out/lizard2_e_shared_final_20261013/p0_measure_check.json` / `lizard2_e_split_final_20261013/p0_measure_check.json`，摘要分别 `e5ec338360d03b2efb6155b677b882167e611d1caae00db93ac690d8edc9e746` / `8139af7cd49c893a73e107c4606d04dcb6546b8acc0a4da00fcd3bae25214d05`，同样写入目标 binding。

#### 4. 回归及真实红项

- `test_baseline_contract.py` 整套通过，含 shared/split/palm 同数据报告 roundtrip、真实 judge/plot 数值一致及混合、缺列、缺来源、重名等负例；原 acceptance metrics 5 项仍通过。
- loader self-check 最终 44 个负例通过，含空 active action、缺/重复/foreign action。支撑自检 shared/split/palm 与 sensor 置换通过，旧四筛选在 split/palm 共 RED 8 次。
- 修复前失败验证在内存中撤去对应修复，不改共用工作树：角色对齐撤去后 `32 poses` 断言失败（旧结果只有 1 pose）；隔离 observation 分支撤去后实际测试得到 `obs/policy-width-approved=False` 而失败；空动作检查撤去后 loader 测试报 `malformed manifest accepted`。恢复实现后三者通过。持久复读方法见下方。
- 最终双碰撞实际各跑 132 pose、136 pair，40 个 hull 反例、32 个 mesh 确认，最差 hull margin -222.86016620166515 mm；二者都退出 1 / `SELF_COLLISION_COUNTEREXAMPLE`。按真实角色归一且消除名称排序后 pairs、overlaps、confirmed 全等。**数值同义验证通过，碰撞设计验收不通过**；不修改 clearance、姿态或网格抹红。产物 `shared_collision_final.json` / `split_collision_final.json` 摘要 `b2a782ec4b1c350f62fd6a336396715c044db1eafee97cb5c88b65de818845b2` / `70e7e2792b9bedee25aa92870ad29344353f084fe55882774b11072952e88ba4`。
- 原 `gait_probe --self-check` 末段同条件仍退出 1：lizard2 cap 实读 `0.11928214877843857`，原断言 `0.013352`；交 `floor-contact-attribution`，未删或放宽。
- 两目标真实 `check_contact_ownership` 都 `CONTACT_OWNERSHIP_FAILED (1)`：shared 罚选四个 `_kfe`、split 对应腕/踝 link 均无 collider。保留原罚选和同几何资产；这不是命名失败，但阻止该必需链按完整通过交付。
- 最终 `offline_final.log`：37 项中 36 通过、1 失败、0 skipped。失败是 `check_record_bindings`，落在其它会话 `lizard2_specimen_proportions.py:61` 与 `palm_pd_probe.py:433` 的重复文件摘要实现；本轮 E 自有重复实现已复用单点，不替其它会话改稿、不绕 hook。`git diff --check` 通过。闸门红与共用脚本归属未闭环，未 stage/commit/push。

### 证据引用

所有命令从仓根运行，解释器为 `E:/IsaacLab/env_isaaclab/Scripts/python.exe`。本机样本和日志不承诺入仓。下面的 reader 与 self-check 可原样复读；writer 重采集须使用未存在的输出名，不能覆盖本段已绑定报告。

```cmd
set "PY=E:\IsaacLab\env_isaaclab\Scripts\python.exe"
set "ECASE=rl_exp\out\lizard2_e_20261013_final"
"%PY%" -B rl_exp\tools\verify\check_leg_reachability.py --self-check
"%PY%" -B rl_exp\tools\verify\check_leg_reachability.py --break-test
"%PY%" -B -c "import sys;sys.path.insert(0,'rl_exp/tasks');import obs_protocol;obs_protocol.diagnostic_target_self_check()"
"%PY%" -B rl_exp\tools\verify\test_baseline_contract.py
"%PY%" -B rl_exp\tools\diagnose\diagnose_support.py --self_check_bindings
"E:\SteamLibrary\steamapps\common\Blender\blender.exe" --background --factory-startup --python-exit-code 1 --python rl_exp\blender\scripts\lizard2_stance_candidate.py -- --contract_self_check
"%PY%" -B rl_exp\tools\verify\check_leg_reachability.py --target_config %ECASE%\shared.json --compare_target_config %ECASE%\split.json --leg lf --samples 2
"%PY%" -B rl_exp\tools\verify\check_leg_reachability.py --target_config %ECASE%\shared.json --compare_target_config %ECASE%\split.json --leg rl --samples 2
"%PY%" -B rl_exp\tools\verify\baseline_probe.py --task Lizard2-Flat-Play-v3 --target_config %ECASE%\shared.json --num_envs 4 --steps 10 --headless
"%PY%" -B rl_exp\tools\verify\baseline_probe.py --task Lizard2-Flat-Play-v3 --target_config %ECASE%\split.json --num_envs 4 --steps 10 --headless
"%PY%" -B rl_exp\tools\diagnose\plot_joints.py --report %ECASE%\shared_gait_final.json --out_dir %ECASE%\shared_plots_final
"%PY%" -B rl_exp\tools\diagnose\plot_joints.py --report %ECASE%\split_gait_final.json --out_dir %ECASE%\split_plots_final
"%PY%" -B -m ablation_harness.baseline_metrics %ECASE%\shared_baseline.frames.pt
"%PY%" -B -m ablation_harness.baseline_metrics %ECASE%\split_baseline.frames.pt
"%PY%" -B rl_exp\tools\diagnose\gait_probe.py --self-check
"%PY%" -B rl_exp\tools\verify\offline_suite.py --python "%PY%" --jobs 4
```

真实重采集形状（shared 与 split 分别执行；以下 `_replay` 输出必须未存在）：

```cmd
"%PY%" -B rl_exp\tools\diagnose\gait_probe.py --task Lizard2-Flat-Play-v3 --target_config %ECASE%\split.json --policy_mode zero --speeds 0.5 --seconds 0.2 --headless --out %ECASE%\split_gait_replay.json
"%PY%" -B ablation_harness\baseline_eval.py --task Lizard2-Flat-Play-v3 --target_config %ECASE%\split.json --protocol ablation_harness\protocols\lizard2_flat_v5.json --num_envs 1 --headless --output %ECASE%\split_baseline_replay.json
"%PY%" -B rl_exp\tools\diagnose\diagnose_support.py --task Lizard2-Flat-Play-v3 --target_config %ECASE%\split.json --checkpoint "E:\IsaacLab\logs\rsl_rl\lizard2_v3\2026-10-10_10-14-50\model_950.pt" --phases 0 --headless --label lizard2_e_split_replay
"%PY%" -B rl_exp\tools\verify\check_self_collision.py --family lizard2 --target_config %ECASE%\shared.json --json %ECASE%\shared_collision_replay.json
"%PY%" -B rl_exp\tools\verify\check_self_collision.py --family lizard2 --target_config %ECASE%\split.json --json %ECASE%\split_collision_replay.json
```

两条碰撞命令分别跑；上一条红不得用 `&&` 使第二条漏验。重制双样本入口是 `check_leg_reachability.py --prepare_diagnostic_twins <新rl_exp/out目录>`，随后真实 runtime order 从新产物读回，不借 frozen registry。Blender 原样本导出命令为 `generate_urdf.py -- --robot lizard2_candidate` / `lizard2_candidate_split`，均带 `--blend rl_exp/blender/lizard2_stance_candidate.blend --out_dir <新隔离目录>`；错源/错目标、缺 out/已存在 out/隔离外写均须写前拒绝，palm contract 仍不可导出。

修复前回归的持久复读：加载上述实际模块源码到内存，保留新增测试，分别撤去 `compare` 中 `for chain, bound ...` 到 `tokens_a` 前的角色对齐块、把 baseline AST 中 `if args_cli.target_config: manager = ...` 对应分支条件置 False、撤去 loader/runtime 的非空动作条件，再运行 `_naming_twin_check` / `test_probe_isolated_observation_contract` / `diagnostic_target_self_check`。本轮三次都实测非零；此操作只执行内存源码，不能覆盖共用工作树。正常代码复读同测试必须退出 0。

早期日志为样本目录 `*_layout.log`、`*_stance.log`、`*_live.log`、`*_gait_final.log`、`*_baseline.log`、`*_contact.log`；末段最终复跑为 `*_probe_final.log`、`*_support_final.log`、`*_collision_final.log`、`offline_final.log`、`blender_contract_final.log`。接收方为 `lizard2-contact-protocol` 动作 7（字段契约及双报告）与 `floor-contact-attribution`（支撑绑定和未消除的资产前提），不等待 S6。

### 未覆盖边界

1. 当前恢复后肢的 palm 实际候选、P2/P3 几何/惯量/运动连接及后续承重标定仍未由本轮批准；其它会话的诊断导出不解除主事项 A 的停止条件。shared/split 孪生不是该四角色新几何。
2. 资产 cap 与 contact ownership 红项仍阻止完整 E 出口；碰撞极值同义不证明动作周期无碰撞。不得借本段将旧红豁免或将第一波标为完成。
3. `load_diagnostic_target` 对 deepcopy 配置的字段名递归映射仍有维护上限：未来新字段可能漏接或误接，本轮不扩张为通用转换框架；新增配置需显式声明并复跑 actual runtime。这一风险未被编译/声明一致检查消除。
4. B 的有效限速和线性承重对照、C 协同标定、S5 用户阈值与 D 最终比较/独立审核均未完成。本段只为 E 实施自检，不提供完成整个事项或训练/采用的授权。
5. 最终完整离线闸门仍红，代码和共用文件归属未形成可安全提交的闭环；未提交、未推送。解除真实缺口后须重跑受影响消费者及闸门，D 就绪后才按原流程独立审核。

## 追加：E 双目标执行记录复核（2026-10-14）

### 适用范围

用户要求更新 E 双目标执行记录。本次复核上段源码/产物摘要、真实报告绑定并复跑离线自检及全仓套件；不修改实现，不重采集 Blender 或 IsaacLab 动力学，不覆盖既有日志。上段 2026-10-13 的结果保留为历史快照；当前闸门状态以本段为准。

复核时 HEAD 为 `3f6dba3a73c5fad592b13672d3e2c01e8d352246`。上段列出的 18 份 E 源码仍有工作树改动，摘要逐一相同；HEAD 前进不表示这些代码已提交。主事项与两个接收方已引用本记录，本次不重复回写读数或改变 work 状态。

### 验收条件

沿用主事项 E2–E4 与第一波出口：源码及产物可复读，双目标报告绑定与数值一致；资产前提、必需消费者和完整闸门缺口不得豁免。离线复核不替代新候选实际运行或 D 后独立审核。

### 结果

**E 仍未达到第一波完整出口。** 当前确认如下：

| 复核面 | 本次结果 | 证据边界 |
|---|---|---|
| 源码与已绑定产物 | 上段 18 份源码、6 份双样本输入、6 份 writer 产物，以及 2 份碰撞、2 份 Blender URDF、2 份支撑产物，摘要全部相同 | 共 18 份产物未变，不代表本次重跑物理或完整检查所有 mesh |
| 正式资产保护 | adopted URDF/USD 摘要仍分别为 `da05432efd5d3c3dd9302682286825869b289d5f912cb5703bd0d32642e0c52b` / `fceaf55be1f045572121c464cb32e1eb0ae7d5d0ba63dfbe9a0d943f84df3b6c` | 未改正式资产、冻结配方、协议或锁 |
| 双 writer 绑定 | 两份 gait 与两份 baseline JSON 均有 `target_binding_required=True`，source 分别指向实际 shared/split manifest；两份 gait 的 `envs[*].series` 全等 | 对既有实际 writer 产物复核，不是手工改名报告或新采集 |
| 名表、FK、反证 | `joint_names.py`、FK `--self-check`、`--break-test` 均退出 0 | 纯模块与几何口径，不证明候选动力学 |
| 入口与支撑绑定 | loader 自检退出 0，44 个负例；支撑自检退出 0，shared/split/palm、sensor 置换与负例通过，旧筛选 RED=8 | palm 仍仅声明/拒错覆盖，不证明真实四角色几何 |
| 双报告 reader | 两份 `.frames.pt` 经实际 `baseline_metrics` 复读均退出 0，`binding_validation=target_binding`，分别识别 shared/split | 使用产物内嵌协议；原无 checkpoint writer 的 `smoke_only` 不因 reader 成功升格为 pass |
| 原资产 cap | `gait_probe --self-check` 仍退出 1：实读 `0.11928214877843857`，原断言 `0.013352` | 未删除或放宽；继续交 `floor-contact-attribution` |
| 当前完整离线套件 | 37 项中 36 通过、1 失败、0 skipped；退出 1，49.6 s，jobs=4。baseline 契约项通过，含 acceptance metrics 5 项；work 形状检查覆盖 87 项 | 唯一失败仍为 `check_record_bindings`，见下方；全套未绿 |

**闸门缺口更新：** 当前 `check_record_bindings` 只报告 `rl_exp/blender/scripts/lizard2_specimen_proportions.py:61` 的文件摘要重复实现。上段历史日志还报告的 `rl_exp/tools/diagnose/palm_pd_probe.py:433` 已不在本次告警中；当前该探针调用 `binding.sha256_file`。这只证明该重复实现告警消失，不代表 palm 验证前提、PD 标定或候选验收完成。本次不改另一路实现以消红。

当前套件相关源码绑定（摘要由 `rl_exp/tools/runrecord/binding.py:sha256_file` 取得）：

| 路径 | SHA256 |
|---|---|
| `rl_exp/tools/diagnose/palm_pd_probe.py` | `9a8791baa79a1a090138932285253002ab00f801cb9e958636bcf7c7e5a274ad` |
| `rl_exp/blender/scripts/lizard2_specimen_proportions.py` | `302e24cd0a86ec2b0286316dc7f5a86ec6e7740cd42365d4966c3836e3300cb9` |
| `rl_exp/tools/verify/offline_suite.py` | `805d4d2eda33300741e33e892fb054568684092981bfd152041d3b5674db4dad` |
| `rl_exp/tools/verify/check_record_bindings.py` | `8f537f1d7b92fadd78242677f8d57875002802365ea98d5ddf51477df4295268` |

### 证据引用

- 历史真跑、全部 E 源码与双样本/报告摘要：本记录“追加：E 双目标实际消费者执行”。本段只复核，不改其采集日期与判词。
- 历史完整套件日志：`rl_exp/out/lizard2_e_20261013_final/offline_final.log`，SHA256 `c7d8a992bbd76d047b8e92d0c6e0ece6c455f4821009301682ae44dbab5a6f59`，仍包含当时两个重复实现告警；未用本次输出覆盖它。本次完整复跑输出来自命令终端，未另存日志，可按下方命令复读。
- 当前动作与出口：`work/active/lizard2-body-drive-candidate.md` E2–E4；writer 契约接收方为 `work/active/lizard2-contact-protocol.md` 动作 7；cap/接触前提接收方为 `work/active/floor-contact-attribution.md`。
- 所有命令从仓根运行；样本和日志仍为本机证据，不承诺入仓。

```cmd
set "PY=E:\IsaacLab\env_isaaclab\Scripts\python.exe"
set "ECASE=rl_exp\out\lizard2_e_20261013_final"
"%PY%" -B rl_exp\tasks\joint_names.py
"%PY%" -B rl_exp\tools\verify\check_leg_reachability.py --self-check
"%PY%" -B rl_exp\tools\verify\check_leg_reachability.py --break-test
"%PY%" -B -c "import sys;sys.path.insert(0,'rl_exp/tasks');import obs_protocol;obs_protocol.diagnostic_target_self_check()"
"%PY%" -B rl_exp\tools\diagnose\diagnose_support.py --self_check_bindings
"%PY%" -B -m ablation_harness.baseline_metrics %ECASE%\shared_baseline.frames.pt
"%PY%" -B -m ablation_harness.baseline_metrics %ECASE%\split_baseline.frames.pt
"%PY%" -B rl_exp\tools\diagnose\gait_probe.py --self-check
"%PY%" -B rl_exp\tools\verify\offline_suite.py --python "%PY%" --jobs 4
```

命令逐条执行，预期 cap 与完整套件仍非零，不能用 `&&` 隐去后续检查。摘要复核用既有 `binding.sha256_file` 与上段表逐项比较；gait 数值比较应取 `envs[*].series`，不是不存在的顶层 `series`。

### 未覆盖边界

1. 本次没有重跑双目标布局、站姿、在线传感器、writer、支撑动力学、全碰撞扫描或 Blender 导出；这些仅按上段真跑和未变产物引用。原 contact ownership 与碰撞红项未被解除。
2. 当前恢复后肢的真实 palm 候选仍须完成 A/P2/P3 前提及 E/D 实际消费；B 的有效限速/线性承重、C 标定、S5 阈值与 D 比较/新上下文审核未由本次完成。
3. 本次仅更新该记录；既有 work evidence 指针继续有效，不关闭事项。完整闸门仍红，E 实现与共用文件归属仍未闭环；本轮未 stage/commit/push，也不宣布交付、训练或采用。
