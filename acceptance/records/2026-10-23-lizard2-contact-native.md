# lizard2 原生地面接触点与零动作承重采样

## 适用范围

用户在说明“实际接触采样”的含义后批准继续。本轮交付一个可复读的原生接触采样入口，复用[隔离训练草案](2026-10-23-lizard2-interface-runtime.md)的机体与配置；不修改正式配方、资产、奖励、终止或训练目标。全部动作与位置/速度目标为零，自由根、重力、自碰撞、当前 PD/caps、TGS 与 `enable_external_forces_every_iteration=False` 保持。

本轮只核测量链及短时零动作样本，不要求手工抬腿、卸载、移重或步行成功。COM 算式和版本化 reader 依据[前置校准与审核](2026-10-23-lizard2-contact-com-calibration.md)，旧 reader/协议保持历史语义。

## 验收条件

- 一个环境最多 100 控制步/400 物理步、dt=0.005 s、decimation=4；保留原终止条件，无外力或参考速度。沿用既有 root drop 0.15 m、tilt 0.35 rad、joint motion 0.35 rad、非足非尾地面力 5 N 的局部停止条件，不作策略性能闸门。
- 每个实际碰撞 owner 单独建立精确 body→floor 观察 view，核实际行列路径；不更改物理碰撞过滤。逐物理步记录原生点、法向、力、间隙、count/start、同帧 ground matrix、净力及 actor/COM 状态。
- 按 count/start 切片，逐点法向力求和与同一对的汇总力一致；满容量拒绝，空片和非零偏移另做 CPU 正反例。实际单对样本只有 start=0，不冒称实际覆盖非零偏移。
- 固定世界点序号不当材料身份；将当前原生点变换到 actor 局部，再经前一 actor 位姿重建同一材料点，计算 backward 区间速度，与同帧 COM 速度场对照。区间估计不升级为瞬时真值。
- 零力求解器点与正法向力点分开统计；脚掌、尾、其它地面法向支撑分开。不给正力筛选附加策略通过含义，不由静置样本批准滑移阈值或分类能力。

## 结果

### 执行与实际绑定

永久入口 `rl_exp/tools/diagnose/palm_contact_sample.py`。草案仍为 `training_interface_draft.json`，SHA256 `a120b8907601852e5ca7bf1190f675d75ea7a8ae0fa79e970d887628ed7e8b19`。实际 joint 名表及全部 Kp/Kd/effort/speed 后端读回逐列等于此前承地报告，不只核四个膝肘。全部 body 重力开启、根未固定、solver=TGS/false；实际 physics/control 目标与 raw action 全零。

| 尝试 | 完成情况 | 实际样本 | 解释 |
|---|---|---:|---|
| attempt01 | completed=false/closed=false | 0 | App 启动后错误导入 `isaaclab_physx.PhysxManager`，环境创建与采样前退出；CLI 返回 0 不作完成依据 |
| attempt02 | completed=true/closed=true | 100 控制/400 物理步 | 改用已有入口的 `isaaclab_physx.physics.PhysxManager`，2 s 零动作采样完成；无停止、终止或 timeout |

只有 attempt02 建立实际环境并执行采样，共 400 个物理步，不含框架初始化内部步。失败输出、采集源码与最终复读源码分别保留；后续全部对照均离线执行，没有因审核修改重复物理。

真实 31 个 body 中，18 个带碰撞的 owner 各建一行一列 ground view；四末端为 `lf_wrist/rf_wrist/rl_ankle/rr_ankle`，尾按真实 tail link 分组。每帧完整保存未接地 owner 的零矩阵，不把未接地 body 删除出分母。18 个 view 的行列路径逐项实际核验，与全 body sensor 的名称顺序分开映射。

原生 API 快照说明六个数组依次为力标量、世界点、法向、separation、count、start。9600 个求解器点条目中含大量零力候选；点数不等于承重接触数。所有实际 count≤4、start=0，没有触及每 view 256 条容量。全部 owner/帧的逐点力求和与 ground matrix 最大三维差约 `2.98e-5 N`；正对照非空，五项真实数组破坏均被拒。

### 承重归属与末窗口

最后 100 个物理帧（1.505…2.000 s；0.5 s 窗口）的平均地面法向支撑如下。此处力为法向力，不含剪切/摩擦；“其它”是本场景其余具名碰撞 owner，不能外推所有姿态或训练行为。

| 部位 | 平均垂直法向支撑 [N] |
|---|---:|
| 左前腕 | 213.1234 |
| 右前腕 | 213.1972 |
| 左后踝 | 121.7800 |
| 右后踝 | 122.7168 |
| tail2_pitch | 29.9572 |
| tail3_pitch | 5.5529 |
| 其它 | 0 |

四脚合计约 670.8174 N，尾部约 35.5101 N；记录的机体重力约 706.3239 N，总支撑/重力约 1.000005。占比分别约 94.97%/5.03%。这提供允许尾触地的真实零动作参考，没有据此批准“尾部达到多少算异常主承重”的阈值，也未采异常主承重反例。

### 接触点语义与速度

原生记录是求解器 manifold 位置，不能直接称精确地面材料点真值。全窗口最高点约 z=0.022066 m，对应 separation 约 0.022066 m、法向力为零；这种正间隙候选不作已受载接触。最后窗口前腕点的正间隙可到约 0.000426 m，后踝约微米量级。原生点与 separation 原值都保留，不投影回地面来隐藏差异。

四脚最低网格候选与最近原生 patch 点的距离全窗口最大约 0.09128 m；平掌不同边角及点的选择会影响该量，不能仅据距离宣告几何错误、实际滑动或传感器失效。原生多点和最低单点仍是不同测量对象。本轮没有迁移正式 writer/reader 契约。

以下只选法向力>0 的点，不以任意新载荷阈值判性能；单位均 m/s。每格是晚窗口各接触点的最大切向速度，两个估计可能在不同帧/点取最大，不将二者之差当作同帧误差。

| 部位 | COM 后端速度场 | 同材料点 backward 位姿差分 |
|---|---:|---:|
| 左前腕 | 0.000565 | 0.000166 |
| 右前腕 | 0.000221 | 0.000177 |
| 左后踝 | 0.003831 | 0.000202 |
| 右后踝 | 0.000537 | 0.000141 |

同一材料点的区间重建避免了把接触点切换或最低点跳变算作速度。后端速度与相邻位姿仍有不一致，尤其左后踝；与此前 TGS/false 的已知速度观察边界相容，但本轮没有求解器时序 A/B，不单凭本次样本重新宣告唯一因果。差分含 float32 位姿分辨率和时间区间近似，也不是瞬时无误真值。当前小后端速度不能单独当真实滑移判据，未据此改 PD、奖励或目标速度。

### 自检与失败处理

`--self_check` 对已知平移、滚动相消、反向叠加滑动和带 90° 转动的同材料点重建给手算正例；真实 collector 复用的 `contact_patch` helper 用非零 start=7 验切片，同时拒绝越界、满容量和负有效索引，空 count 允许无效 start。CPU 编码验证不代替 native 非零 start 行为证据。

独立复核指出初版写报告/序列化位于 app.close 保护之外，NaN 或写盘失败可能跳过 app 清理。已把 env.close、序列化、写盘与 audit 全部置于 app.close 的外层 finally 内；持久 self-check 执行实际 collector 的 finally AST，以 stub app.close=SystemExit(0) 核正常、采集失败、NaN 与写盘失败。正常路径在 app.close 前写 report/audit 并 flush，失败保留明确异常，不把进程码替代 completed/closed 和数据核验。此为清理控制流验证，未再次启动物理。

## 证据引用

[独立审核](2026-10-23-lizard2-contact-native-review.md)接受这次有限原生采样，直接复算真实力/点/位姿数组、核原生 API 与新旧清理分支，并执行真实数据破坏检查；不批准运动分类、完整协议或开训。

代码提交 `2edf4ca`，包含诊断入口与 FILEMAP。最终 `--self_check` 通过；完整离线套件 `ALL_OFFLINE_CHECKS_PASSED (37/37 in 52.2s, jobs=6)`，日志在输出根 `self_check_final.log` / `offline_suite.log`。提交前及正常提交的原仓库钩子均通过，日志 `precommit_code.log` / `commit_code.log`；`check_work_docs.py` 与 `git diff --check` 通过。这些检查不代替本记录中的物理样本或独立复核。事项继续 in_progress，未因局部完成关闭任何动作。

本机输出根 `rl_exp/out/lizard2_contact_native_20261023/`，不承诺随仓分发。actual raw/source 不覆盖；`attempt02/audit.json` 是当时初版摘要，最终用 `audit02_verified.json`（新增正力点、晚窗口与候选速度统计，原数组未变）。

| 工件 | SHA256 |
|---|---|
| attempt01/report.json | `99020491eca03d449c3f0846f130729fb9f1a4a4bc48e4e0bd7210052ff8702d` |
| attempt02/report.json | `7d8169117ccea67592d4b27a6c128087929cf91193e71965a0d76f25093106e9` |
| attempt02/source.py | `2b33881768d83c0ebd0074ff414f43c546fb904a353375b82a15b508aaf5d9b2` |
| audit02_verified.json | `dfb09e451bda32a5639429fe4f4f7dbff4c539f874a14d1e5683e1d39d7e01c6` |

报告另绑定实际 USD/URDF/18 个网格摘要、原生 API 源码快照；运行日志为输出根同级的 `lizard2_contact_native_20261023_attempt01.log` / `attempt02.log`。最终源码 SHA256 `9dd3b451b9f4cd803bf28c5cf9dd474974c22b293f5d3fa04957a3c3a331e586`；与采集快照差别为数组切片提取成同义 helper、失败清理及离线复读/自检，不改变已采原数组或物理条件。

从仓根用项目 Python；audit/self-check 不启 Kit，collect 输出必须不存在：

```powershell
& E:/IsaacLab/env_isaaclab/Scripts/python.exe -B rl_exp/tools/diagnose/palm_contact_sample.py --self_check
& E:/IsaacLab/env_isaaclab/Scripts/python.exe -B rl_exp/tools/diagnose/palm_contact_sample.py --audit rl_exp/out/lizard2_contact_native_20261023/attempt02/report.json
& E:/IsaacLab/env_isaaclab/Scripts/python.exe -B rl_exp/tools/diagnose/palm_contact_sample.py --headless --device cuda:0 --out rl_exp/out/contact_native_replay
```

## 未覆盖边界

本次提供原生 body→ground 点/法向力采样和允许尾触地参考；未采受控真实偏转、滚动、滑动的三类动力学标定，也未采异常腹部/头部主承重，不以静置样本替代分类、策略性能阈值或完整新协议。无摩擦力/剪切力测量，无持续材料点身份追踪；求解器点含零力与正间隙，接触面不是单一理想点。

未改旧 baseline 协议、正式配方、动作/观测锚点、资产采用/退休或训练；D/E 整体、S5/S6 及正式协议继续在办。训练预算仍为用户已批的新候选从头 6000 迭代，尚未启动；取消限速/限矩及对称复测、手工运动归 RL 的决定不变。
