# 巨蜥动作、接触与行程事项合并（2026-10-08）

## 适用范围

整理巨蜥相关在办事项的责任与验收出口。只调整工作文档与指针，不改变机器人资产、关节限位、配方、协议或冻结锁；不代表参考动作、接触可达性或髋行程验证已完成。

## 验收条件

- 只有共享目标、验证流程和采用决策的事项合并；独立机制与交付仍可单独推进。
- 原事项保留 ID 与历史正文，移到 closed、去掉 next，以 superseded/outcome/superseded_by 指向接收项，不将移交记作验证通过。
- 未完成的检查、需求决定与决策出口在接收项有明确落点；旧证据保持单一来源，不复制读数。
- 当前活跃指针更新；历史记录和冻结版本中的旧路径保留为当时的追踪信息。
- 工作文档及仓库提交前要求的检查通过，不放宽闸门。

## 结果

### 合并与移交

统一入口为 `work/active/joint-limit-shape-and-range-pass.md`，题名改为“巨蜥参考动作、腿链结构与限位：接触、步幅、验证与换代”。该入口先明确目标，再做结构、接触和范围比较，最后验证动力学与采用机体。

| 原事项 | 保留的未完成动作 | 接收落点 |
|---|---|---|
| pad-flat-requirement-and-ankle-axis | 具名接触需求/容差决定，静态四足支撑、支撑轨迹与连续性三段检查，离线/仿真 FK 核对，接触误差与可行步幅曲线、余量和碰撞，改结构/轴/行程或需求取舍 | ①目标、②工具、③接触与可达性、⑤动力学/采用；close_when (e)(h) |
| stride-axis-range-vs-speed | 跨 seed/checkpoint 的按档贴限位复核，扩大行程/收窄命令窗口/接受现状三条出口，历史比较条件与新版本落点 | ④范围与速度预算、⑤采用；close_when (i) |

两份原文件已移至 `work/closed/2026/`，状态为 superseded，未完成动作继续由统一入口承接。原有膝限位事项已在此前并入，本轮不再次搬迁。活跃项中的旧分工指针同步更新；证据内容仍在原记录。

### 随合并纠正的前提

- 接触目标先于候选验收，容差不能按当前链能达到的值倒定。旧事项要求扫描后才定需求的顺序不再沿用；可以保留探索扫描，不能把它当冻结需求的依据。
- 不预设掌面全周期水平或折腿和为零。只有所选阶段确需平放时才验平放；立边是否允许也须有具名决定。折腿和仅适用于当前平面链的诊断，不能代替世界系掌面方向。
- 几何通过不能直接归因于奖励，也不能证明承重、平衡或稳定行走。原脚掌事项不承担动力学；合并后仍分别形成几何与动力学判定，后者由统一入口的⑤承担。
- 髋贴限位只能说明现策略使用到了边界，不能直接推出扩行程有效或最高速度受它限制。因果结论需目标可达性或受控对比；接受现状时只写已证实代价。
- 原正文的“一次锁/快照刷新”保留作历史文字，当前采用流程以 `.codemaker/rules/versioning.mdc` §A 与接收项⑤为准：新机体新路径、退休旧机体冻结消费者，旧锁不刷新。teacher 派生快照同步仍由资产管线依赖承接。

### 保留独立事项

| 事项 | 独立交付与协作边界 |
|---|---|
| large-monitor-skeleton-muscle-literature | 全身肌群与大型个体资料的来源、样本及证据边界；动作入口按需引用，不以补齐全部生物学资料为参考整理的前置 |
| leg-chain-symmetry-convention | 源资产是否应镜像的具名决定及生成器数值约束；目标拟合仍逐腿验证，不默认对称 |
| asset-tree-per-family | 生成器真跑、资产树与多格式一致性，以及旧家族分歧处置；是采用前置，不阻塞动作整理 |
| lizard2-family-landing | 配方、奖励/参考跟踪、部署动作接口与评测协议；消费统一入口的接触及命令窗口决定 |

这些事项有独立完成条件，合并会把源资产意图、通用机制或训练交付绑到尚未定案的结构方案上。共用同一次换代不等于应共用一个在办事项。

### 文档验证

`framework_pin_check.py --strict --self-test`、`check_dr_parity.py --strict`、`check_version_docs.py`、`check_work_docs.py`、`check_obs_layout.py` 均通过，`git diff --check` 通过。工作文档检查提示的本轮新增旧路径均位于此前的日期证据中，保留历史追踪；活跃事项不再指向两份原项。既有 IsaacLab 工作树改动、旧版本 tag 与历史指针提示不属于本轮修复范围。

## 证据引用

- 当前主项：`work/active/joint-limit-shape-and-range-pass.md`。
- 原项：`work/closed/2026/pad-flat-requirement-and-ankle-axis.md`、`work/closed/2026/stride-axis-range-vs-speed.md`。
- 目标与映射：`acceptance/records/2026-10-08-lizard2-reference-motion-v0.md`、`acceptance/records/2026-09-30-lizard2-leg-to-anatomy-mapping.md`。
- 接触与工具：`acceptance/records/2026-09-29-leg-pose-slider-and-pad-clearance.md`、`acceptance/records/2026-09-29-lizard2-pad-leveling-unreachable.md`、`acceptance/records/2026-09-29-lizard2-pad-tilt-is-the-fold-sum.md`、`acceptance/records/2026-09-30-leg-fk-caliber-facing-and-candidate-chains.md`。
- 行程与策略：`acceptance/records/2026-09-29-lizard2-v2-gait-five-claims.md`、`acceptance/records/2026-09-29-lizard2-hfe-knee-limit.md`。
- 换代机制：`.codemaker/rules/versioning.mdc` §A、`acceptance/records/2026-09-30-body-swap-and-lock-freeze.md`。

## 未覆盖边界

本轮没有新增视频量测、参考轨迹、可达性曲线、仿真 FK 对拍、多 seed 读数或动力学结果，也没有替所有者批准接触容差或新增旋转轴。合并后的最大风险是主项变成无法关闭的大总账；本次仅接收同一动作—结构—范围决策链上的两项，配方和通用机制继续独立，后续新增动作须先核对交付边界。
