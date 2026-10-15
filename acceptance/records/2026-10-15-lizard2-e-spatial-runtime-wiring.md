# E：palm_spatial 无承重运行接线切片

## 适用范围

承接 `work/active/lizard2-body-drive-candidate.md` E5。用户选择本轮只处理 E 运行接线，A 保留生成器、名表与 FK/碰撞核心修改归属；另批准一个环境、固定基座、禁重力、零增益，逐关节 ±0.05 rad 状态注入、动作目标及观测/传感器读回。不做 PD 跟踪、承重、训练或正式采用。

输入固定为 `rl_exp/out/lizard2_palm_spatial_20261014/checkpoint_v3/build.json` 所绑定的只读候选。A 后续产物不得自动继承本次结果。新增持久入口 `rl_exp/tools/diagnose/palm_spatial_runtime.py`，输出仅在新的隔离目录；共用生成器、正式机体、冻结配方和历史协议均未修改。

## 验收条件

- 候选源件和相对网格引用保持原身份；新 USD 与诊断配置单独绑定，禁止覆盖检查点。
- 实际关节、动作通道、默认位姿、零增益、限位、观测切片、精确腕/踝末端及传感器顺序核对。实际状态对应 actor/FK，不能拿物理步后状态与注入零位混比。
- 逐关节真实采集写出完整具名列；同一绘图 reader 读取，缺 twist、混名或缺来源拒绝。展示三列与原始五角色完整性分开检查。
- 专用诊断不得伪称已验证注册任务，`load_diagnostic_target` 应拒绝专用身份及将其当 v3 加载。失败非零并留下 completed=false，不能产生成功报告。

## 结果

### 已完成的切片

最终 `attempt06` 正常完成、命令返回成功：38 个候选文件哈希核对，30 个可动关节；20 个腿动作加 10 个躯尾动作，各自名称与真实运行时 ID 精确对应。31 个 robot body 与 31 个 sensor body 按具名映射核对，足端精确为 lf/rf_wrist、rl/rr_ankle，近端载体不作为足端。

独立 `ManagerBasedEnv` 使用固定基座、禁重力、零 stiffness/damping/armature，无 reset 随机事件。policy 宽度 99；位置切片 [9:39]、速度 [39:69]、动作 [69:99]。30 个关节分别 ±0.05 rad，每次注入后仅推进一个物理步，共 60 个实际样本，动作目标缓存与注入目标一致，观测按实际框架顺序与实际状态/动作读回核对。actor/FK 使用物理步后的真实 q，通过报告所列精度预算，不证明状态保持或动力学解耦。

专用 writer 实际生成完整五角色记录；`plot_joints.report_naming` 与 `draw_band` 成功消费，真实缺 twist/混名/缺 source 三例均拒绝。缺列与混名由同一完整列集合断言拒绝，未冒称不同分类能力。绘图仍只展示 swing、肘膝、腕踝三个既有面板；twist 原始列必须存在。此专用 writer 不等于 `gait_probe` 或 `baseline_eval` 已闭环。

最终自检通过：38 个文件核对、5 个映射/读回/摘要破坏负例；真实 loader 对专用 task 无 family、对 v3 task 身份不符分别拒绝。实际最终 manifest 同样拒绝两种注册加载尝试。`manifest.json` 的 format/scope 与 `PalmSpatial-Wiring-Diagnostic` 明确其未注册属性，config 仅部分测量元数据，不能用来重建 v3 配方。

### 固定基座根问题与修复前失败

`attempt04` 使用浮基转换、原生 flatten、spawn 固定根，真实退出 1：Geometry 和 base_link 同时携带 ArticulationRootAPI。框架已删除显式 Physics API，但 importer 的 `NewtonArticulationRootAPI` 又包含该 API，留下第二个根。

最终入口只在隔离 USD 先调用框架固定基座方法，再移除 base 上残留的 Newton 根 schema；保留 RigidBody/Mass，scope 不加 RigidBodyAPI。固定 world joint 目标核对为 base_link，唯一父 root 与实际 `is_fixed_base=True` 均读回；spawn 不再次设置固定根。最终 `fixed_root_adapter.json` 记录前后 schema、固定连接、源码及 USD 摘要。

最终同输入执行中，未清理残留 schema 的真实内存 USD 状态在唯一 root 断言失败，修复后只剩父 root；没有 mock 空函数加人为失败来冒充回归。更早 attempt01/02/03 的转换布局与固定根失败保留在各自 failure.json，不覆盖。

### 仓库检查

最终运行源码下完整离线套件退出 0：37/37，通过耗时 53.7 s；波内 180 s 仅信息。随后证据与 work 指针回填后 `check_work_docs.py`、`git diff --check` 通过。套件通过不代表 E 完整出口、候选物理或关闭审核通过。

### 实际异常读数与交接

物理步后最大状态漂移为 0.2313874513 rad、速度绝对值最大 42.18108368 rad/s；sensor 最大力范数 166921.0038 N、最大分量 163682.84375 N。零驱动、自碰撞开启，初始干涉仍产生很大响应。**成功只表示运行接线/读回检查完成，不是候选物理合格。** 力与漂移归因、连接区碰撞过滤和虚拟载体惯量继续交恢复限位 PD 专项步骤 3/4；未借 E 改网格、滤掉碰撞或加 PD 压掉异常。

E5 五项均不宣布完整完成：导出目标仍归 A/共用生成器执行者；五角色已完成本专用映射切片，逐轴受控驱动仍未验；实际末端/传感器集合已核，但接触归属和在线协议分支未完成；专用真实 writer/绘图已核，gait/baseline 实际消费者未完成；完整出口清点仍需上述链与旧资产负责项回交。

## 证据引用

本机产物不承诺入仓。最终目录：`rl_exp/out/lizard2_e_spatial_20261015/attempt06/`，主报告、manifest、reader_report、fixed_root_adapter、源码快照和两个诊断图均在该目录。

| 对象 | SHA256 |
|---|---|
| 输入 build.json | `59473f8c345dce48e8ee379c0972c928184f768be85afca948ac812a666fa6f8` |
| 只读候选 URDF | `2c78117020458d5e7934219a2064bf7241430b81c2a736acd8cc0761c7a1461f` |
| 只读候选 blend | `beeac4c09726260bf392a6ecc81a04ebcf9b54a210416493bbb2689c4909cdea` |
| 最终运行脚本 | `b70bc2895ba8eb78c7c9cb00fd08373da0e1d1782acc4991f9c4898129a79b8d` |
| 最终 runtime_report.json | `0b5e3b259223fa79b9d4b807b0da7bf826f81bb5051663787e87925f12e89058` |

其它工件摘要取主报告 artifacts；报告 code.sha256 与源码快照相符，输入与全部列出工件已实际核对。复读从仓根运行，必须换未存在的输出目录：

```cmd
"E:\IsaacLab\env_isaaclab\Scripts\python.exe" -B rl_exp\tools\diagnose\palm_spatial_runtime.py --self_check
"E:\IsaacLab\env_isaaclab\Scripts\python.exe" -B rl_exp\tools\diagnose\palm_spatial_runtime.py --viz none --out rl_exp\out\lizard2_e_spatial_20261015\replay01
"E:\IsaacLab\env_isaaclab\Scripts\python.exe" -B rl_exp\tools\diagnose\plot_joints.py --report rl_exp\out\lizard2_e_spatial_20261015\attempt06\reader_report.json --out_dir rl_exp\out\lizard2_e_spatial_20261015\replay_plots
```

独立只读核查发现 attempt05 manifest 曾可能被误当 v3 输入且不携零 PD 配置；最终改成独立身份并真实验证 loader 拒绝。后续新上下文核对终版代码/记录/未完交接，身份问题消除；其 glob 未命中本机产物，未独立读到 attempt06，不能冒称完整实测审核。执行者随后直接复核本机主报告、专用 task、60 样本、源码摘要及 artifacts 全部摘要，退出 0；直接复核不是独立审核。总事项不关闭。

用户于 2026-10-15 确认提交本轮 E 代码、证据与已有 E5 共用暂存，按代码/文档分组；其他 A 在办改动和本机输出不纳入。此同步不代表 E 完整交付或事项关闭。

## 追加：注册消费者短窗（2026-10-15）

### 范围与配置

用户批准同只读候选、一个环境、固定基座、禁重力、零增益，在线协议及 gait/baseline 各十个控制步；异常仅记录，不借接线修改碰撞或给性能判定。新增持久准备/复读入口为 `palm_spatial_runtime.py --prepare_registered` / `--verify_registered`，保留此前专用诊断身份及产物。

新注册诊断 manifest 位于 `rl_exp/out/lizard2_e_registered_20261015/attempt01/registered_manifest.json`。`Lizard2-Flat-Play-v3` 仅用于实例化母本配置，loader 在 deepcopy 上绑定候选 USD/URDF；不是新配方、正式采用或已批准策略宽度。驱动组为非末端腿、腕踝、躯尾三个不重叠集合，全部 stiffness/damping/armature 为零，effort/velocity 显式逐关节取 URDF；20 个腿动作与 10 个躯尾动作、单位尺度、零默认关节状态、z=2 m、禁重力、自碰撞与全部 events=null 显式声明。旧 shared 角色槽不负责猜新链 PD。

### 实际完成与失败

| 消费者 | 真实结果 | 边界 |
|---|---|---|
| 注册 loader | 准备前两次局部验证比较 dict/tuple 错误退出 1，修复后正例及重复动作/缺 twist/外来末端/错摘要四负例核对通过 | 复读不覆盖已存在负例；不同内容拒绝。manifest 仍是隔离诊断，不是冻结配方 |
| 在线协议 | 正例退出 0，实际进入 `BOUND_FEET` 分支核四个腕/踝体；20+10 动作，policy=102(unapproved) | 观测宽度未授权训练；不是承重或接触所有权证明 |
| 在线协议负例 | 同外来末端真实 CLI 修复前打印 FAILED 但退出 0；修复后退出 1 | 修复 Kit close 吞失败码，不把被拒输入当成功 |
| gait | 初次固定基座 Jacobian 索引失败，修复后采集结束又因逐关节 effort 字典转 scalar 失败；两处修复后实际 CLI 完成十步并写报告，最终 writer/reader/绘图通过 | 首帧即 done，没有有效首局采样；只完成诊断写读链 |
| baseline | 实际启动后在采集前被 reset 检查拒绝，退出 1；位置偏差 0.1344962567 rad、速度 19.84133911 rad/s | 无真实 frames/report；未跳过、放宽检查，未追加完整 20 s 运行 |

在线正例日志为 `live_positive.log`，前后负例为 `live_negative_before.log` / `live_negative_after.log`。`execution_record.json` 保留首轮失败历史；其中 gait 未验项属于修复前状态，不能用它否定后续真实 `gait_final.log` / `gait_final_report.json`，也不无痕改写旧记录。`execution_gait_record.json` 绑定中间 effort 修复报告；终版首局语义以 `gait_final_report.json` 为准。

### 修复与真实反证

1. **固定基座 Jacobian**：fixed root 不占 body 行，DoF 无六个浮基列；浮基保持原布局。新测试执行实际采集代码块，旧代码对包含最后 body 的 CPU 输入真实 IndexError，修复后 fixed/floating 编码列、线性/旋转分量与错误 shape 拒错通过；实际 CLI 已越过该位置并最终写报告。
2. **逐关节 effort**：删除 cfg group 的 scalar 假设，从实际 `joint_effort_limits` 的 env/joint 列读取。旧代码对逐关节 dict 真实 TypeError；修复后 scalar/dict 配置对应真实张量读点、不同肢体/env/列测试通过。报告面板读到摆动/肘膝 180 N·m、腕踝 70 N·m，与模拟器表相符。
3. **首帧终止掩码**：中间报告的全死 fallback 把 `frames_alive` 错写成十帧。用最终真实 done 序列执行旧 writer 块真实失败；修复后保留严格首次终止前的 alive，不复活。独立 recorded 序列仅保留诊断采集，并写明无效首局及 reset-mixed scope，不伪称捕获到 pre-reset terminal 姿态。
4. **baseline 十步预算**：新增 `--smoke_steps` 默认 None，保持旧运行；有 checkpoint 的实际 CLI 在启动前退出 2。短窗保留冻结协议及原 reader 判词，仅诊断 report/artifact 携带 smoke 元数据。原实现会把采集 invalid 洗成 smoke_only，真实回归先失败，修复后采集错误/非时长 reader invalid 保持 invalid；只有正常采集且原判词可用或唯一短时长拒绝才标 smoke_only。测试实际 recorder 保存/加载 fixture 元数据通过，不是本候选真实采集能力证明。

### 最终真实 gait 写读链

最终命令退出 0，`steps=10`、`frames_alive=0`、`frames_recorded=10`、`done_frames=6`、`invalid_for_first_episode=true`，valid 全 false。60 个腿具名序列（20 关节 × target/actual/vel）均为十条采集值，包含 twist；躯尾列单独保留。四足体为 rl/rr_ankle、lf/rf_wrist；raw 足力全零、最低点离地约 1.259–1.620 m。**这是固定基座零驱动、含自动 reset 的诊断数据，不是有效步态或足力合格证据。**

原 `plot_joints` reader 与实际 CLI 出图通过，终版真实报告 deep-copy 的缺 twist/外来词根/空来源均拒绝。三面板展示不等于五角色原始列缩减。最终报告和源码摘要由执行者再次直接核验，不借旧日志或 fixture 宣称真实 writer 通过。

### 绑定与复读

| 对象 | SHA256 |
|---|---|
| 注册诊断 manifest | `30209cfc6237f8d0a6b1a3cbce6d5911c5c5a5e66113cb7473b204f561dab68f` |
| 注册输入固定 USD | `40f37d124d17f69b201c06f49173681367370a66a38431bcbda3d5e1192f3f79` |
| 最终 gait 报告 | `ce041c5831f33ef99ed7575876a662cdce7fb5e926a85539d6d874c280309092` |
| runtime 源码 | `ba5ad7872051dc6839b40b14b95c8607e1eadb36ebbbd1f57cf063a9cd260013` |
| live 源码 | `c4c8e5df486db33ccb1d50c47229dca4d30ebe1a28a772f163284410c53090a0` |
| gait 源码 | `ae3addafe300aa86d7dc3656302c07cc6f596a6dbaf54817d5a86463d7501d8f` |
| baseline 源码 | `6b4ea3f3868b37fd39e7782b0ca7e3c9f2afa79331199f88b1c383b019fdb3aa` |
| 采集时 contract 测试源码 | `9baad8af0c7871baac391ac5905aed974a7b16e4276403d1107e55ab8e51becd` |
| 提交时 contract 测试源码 | `c0e6294bc34b0c0b99bfd4d5b44434f06f15d869dc2d9e86f235914517956392` |

本机 attempt01 下保留各次失败、终版日志与报告；不可拿后改源码摘要冒充之前 baseline 失败运行的源码，首次执行快照与摘要在 `artifact_hashes.json` 中。复读从仓根，报告和图必须用新路径；baseline 命令预期仍可能在 reset 前提拒绝，不使用 `&&` 隐掉后续测试。

```cmd
"E:\IsaacLab\env_isaaclab\Scripts\python.exe" -B rl_exp\tools\diagnose\palm_spatial_runtime.py --verify_registered rl_exp\out\lizard2_e_registered_20261015\attempt01\registered_manifest.json
"E:\IsaacLab\env_isaaclab\Scripts\python.exe" -B rl_exp\tools\verify\obs_protocol_live.py --tasks Lizard2-Flat-Play-v3 --envs 1 --target_config rl_exp\out\lizard2_e_registered_20261015\attempt01\registered_manifest.json --viz none
"E:\IsaacLab\env_isaaclab\Scripts\python.exe" -B rl_exp\tools\diagnose\gait_probe.py --task Lizard2-Flat-Play-v3 --target_config rl_exp\out\lizard2_e_registered_20261015\attempt01\registered_manifest.json --policy_mode zero --speeds 0 --seconds 0.2 --viz none --out rl_exp\out\lizard2_e_registered_20261015\attempt01\gait_replay_report.json
"E:\IsaacLab\env_isaaclab\Scripts\python.exe" -B rl_exp\tools\diagnose\plot_joints.py --report rl_exp\out\lizard2_e_registered_20261015\attempt01\gait_final_report.json --out_dir rl_exp\out\lizard2_e_registered_20261015\attempt01\plots_replay
"E:\IsaacLab\env_isaaclab\Scripts\python.exe" -B ablation_harness\baseline_eval.py --task Lizard2-Flat-Play-v3 --target_config rl_exp\out\lizard2_e_registered_20261015\attempt01\registered_manifest.json --protocol ablation_harness\protocols\lizard2_flat_v5.json --num_envs 1 --smoke_steps 10 --viz none --output rl_exp\out\lizard2_e_registered_20261015\attempt01\baseline_replay_report.json
"E:\IsaacLab\env_isaaclab\Scripts\python.exe" -B rl_exp\tools\verify\test_baseline_contract.py
```

最终完整离线套件退出 0：37/37、51.5 s。新增真实缺陷均有修复前失败/修复后通过的回归；不新增闸门，不用套件绿解除 baseline reset 前提。

提交前发现新增两个回归测试直接读取本机诊断报告，换机无法复读；已改为内置捕获 done 序列与名表生成的 per-joint fixture，保留真实代码块执行，删除重复报告 roundtrip。本机真实 CLI 证据仍取上述报告，不用 fixture 冒充实测。改后完整 contract 与 binding-only 均退出 0，测试源码摘要另列，不改采集时身份。提交前完整套件再跑退出 0：37/37、51.0 s；代码提交的 pre-commit 全部通过，提交为 `84fc797`。

独立局部审核核代码和实际产物；首轮曾把修复前 `execution_record.json` 当成最新状态、漏读最终日志，并误判已存在负例会覆盖。随后新上下文直接读取 `gait_final.log` 与终版报告，确认实际 writer 输出、首局零有效帧与无 traceback；核 `if path.exists(): require(equality) else: write` 后撤回覆盖判定。日志本身不含退出码，exit 0 仍依据执行命令结果，不伪称日志可单独证明它。此局部审核不关闭 E 或总事项，baseline reset 仍按独立实际失败日志留在办。

## 未覆盖边界

- baseline 实际十帧 writer/评测 reader 仍受 reset 位置/速度拒绝；先交限位 PD 专项步骤 3/4 定位源候选自碰撞、惯量及加载状态，不为完成 E 绕过检查。
- 注册在线协议非空足端分支及 gait 诊断 writer/绘图已核；实际 collider 所有权、逐轴受控驱动、非零有效首局、PD 跟踪、承重、连续安全域和行走均未完成。
- 未接正式 Blender 导出目标或验证其错源/错目标；旧资产 cap/contact ownership 缺口仍由 `floor-contact-attribution` 回交，不用新候选读数解除旧资产前提。
- A 的树/轴/零位/网格/惯量/命名变化后按变化重验受影响链，不外推检查点结果。总事项维持 in_progress，最终仍随 D 由新上下文审核。
