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

## 追加：reset 阶段与实际 collider 归属

### 范围与方法

用户批准先攻 baseline 阻塞，追踪 reset 写入、缓存和物理步，同时核 collider 归属；不改网格、惯量、碰撞过滤或检查阈值。新增 `palm_spatial_runtime.py --reset_probe` 持久入口，消费原注册 manifest，输出新 `attempt02`；实际启动一次仿真，记录九个阶段，诊断 hooks 自动恢复。输入 manifest、固定 USD 与原候选 38 文件摘要未变。

### 阶段实测与判定

| 阶段 | max q-default [rad] | max qd-default [rad/s] |
|---|---:|---:|
| gym.make 返回 | 0.134496257 | 19.841339111 |
| wrapper reset 返回 | 0.134496257 | 19.841339111 |
| 原状态首物理步前 | 0.134496257 | 19.841339111 |
| 原状态首物理步后 | 0.183123186 | 10.115932465 |
| 诊断写绑定默认值并 forward | 0 | 0 |
| 上述写入后的一个物理步 | 0.047132555 | 10.003413200 |

全部阶段缓存与 backend 的位置/速度差为零；`forward()` 不推进物理。本 fork 使用 xyzw，实际 backend root 一直为 [0,0,2,0,0,0,1]，不支持 quaternion 顺序错误或根被旋转的猜测。

`RslRlVecEnvWrapper` 确实调用 `env.reset()`；reset events 全禁用时，scene/articulation reset 仅清 actuator/wrench，实测 wrapper reset 没有调用关节状态 writer。PhysX startup warmup 在 gym.make 返回前推进物理，偏移因此保留到严格 reset 检查。**这不是漏调用 wrapper.reset 或缓存陈旧。**

诊断仅写回已经绑定的零默认关节状态，原严格检查立即通过；下一物理步又失败。该同场景反事实不清除 solver 历史，也不是 baseline 修复或验收。写零后首步 base_link net contact force 范数约 75,814.647 N；不能据净力推出碰撞 pair 或地面接触。self-contact、fixed-world-joint solver 与惯量各自贡献仍未知；fixed joint 的 authored local origin 与实际根保持 z=2 并存，尚未验证 solver-frame 解释，不能据前者宣称根锁错。

### 实际 collider 归属

实际生成场景中读取 18 个 collision prim、18 个 nearest rigid-body owner，未认领 collider 为零；sensor 有 31 个 body。前肢上/下/掌分别归 shoulder_twist、elbow、wrist；后肢分别归 hip_twist、knee、ankle。其它 owner 为 base_link、chest_pitch、neck_pitch、tail1/2/3_pitch。

四个腕/踝体都有实际 collider 与 sensor ID；实际 reward resolved bodies 中无缺 collider 的空处罚对象。报告保存每个完整 prim、nearest owner、approximation、enabled、transform 与 URDF 网格摘要。mesh-local extent 未拿来证明不同坐标系尺寸相等。**本切片补齐静态实际 ownership，不证明地面接触归属、碰撞过滤合理、旧资产问题解除或承重合格。**

### 证据与复读

本机产物为 `rl_exp/out/lizard2_e_registered_20261015/attempt02/`：

| 对象 | SHA256 |
|---|---|
| reset_probe_report.json | `928dd7811619b28b98ba8f49df1e23a1ac1b1ebe6a3c572ed8b5195a4efb7b96` |
| collision_ownership.json | `8329f33e4c9b57a1758aee6bc9825816a12af138cf99540b8ea8a9b0d05facc3` |
| reset_attribution.json | `88889b03313f962682fa1925d8930d84e4ff63a12f865842fe2581f1122268ff` |
| 诊断源码与快照 | `0547df46357033697ce470f474362a2e30d2bd2ebec2a4c66ec27df17285dece` |
| 父目录 reset_probe_attempt02.log | `0707facf651034da9c1bc3516440a8249d2603d24b33d751d05ed3e42eb41add` |

实际命令输出 `RESET_PROBE_COMPLETED blocked`，表示诊断采集完成、baseline 仍被阻塞，不表示性能通过。执行者直接复核报告 completed/status、代码摘要、全部缓存/backend 差与 ownership 计数通过；自检仍核 38 文件、五个破坏案例与两个诊断身份拒绝。baseline 未重跑十步，未改 evaluator/checker 或配方。

```cmd
"E:\IsaacLab\env_isaaclab\Scripts\python.exe" -u rl_exp\tools\diagnose\palm_spatial_runtime.py --reset_probe rl_exp\out\lizard2_e_registered_20261015\attempt01\registered_manifest.json --out rl_exp\out\lizard2_e_registered_20261015\reset_replay01 --viz none --device cuda:0
```

后续接触对采集探索超时，未生成新的 attempt03 或提交任何接触对适配；因此具体 pair 保持未知。超时不当作无 API 或无碰撞的证明。

独立局部复核确认实际 ownership、缓存/backend、未改物理及 counterfactual 边界。审核曾在本仓搜索框架字段后误判 `_sim_step_counter` 不存在；执行者直接查框架 `manager_based_env.py:159` 与报告，九阶段该环境计数实为零而非 None。此环境计数只记录 env.step 推进，不计诊断直接 sim.step 或 warmup，因此不能当累计物理步数；阶段标签和 cache 时间分别记录本次直接步进。具体碰撞对与物理贡献仍未验，不关闭事项。本轮完整离线套件退出 0：37/37、56.5 s；诊断代码提交 `447d922` 的 pre-commit 全部通过。

## 追加：单体观测接触对尝试（2026-10-16）

### 范围与入口

用户批准每 collider owner 单独建立接触观测视图，避免 PhysX 多体 filtered sensor 限制；保持同一资产、零驱动、固定基座、禁重力、物理过滤不变。新增 `--reset_probe ... --contact_pairs`；每个 exact body 单行对目标 owner 列采集法向力，只有列名/行名/shape 对照真实路径通过后才赋予 body 名。路径或 shape 不匹配不得降级猜列。

框架来源为 `isaaclab_physx/sensors/contact_sensor/contact_sensor.py:324` 的 `create_rigid_contact_view` 与 `:380` 的力读点；`isaaclab/sensors/contact_sensor/contact_sensor_cfg.py:83` 明确 filtered 单体限制。接口与 mock 的形状说明仅用于选入口，不能代替实际 PhysX 列映射。`get_contact_data` 未消费，不冒称捕获 collider point、separation 或摩擦。

### 真实尝试与停止点

| 本机尝试 | 观察 | 当前边界 |
|---|---|---|
| attempt03 | 仅到 post_gym_make，退出码 0，但无完成 marker 或主报告 | 当时诊断错误要求容量为 64，实际 backend 默认为 4；关闭应用又吞掉异常。日志没保存 exception，容量原因是源码定位，不伪称已捕获该 live 异常 |
| attempt04（用户追加授权） | 使用实际正整数容量 4；真实退出 1，完成 marker=false，失败 marker=true；`ValueError('contact pair filter binding mismatch')` | 行/列绑定初始化失败，两个 post-step 采力阶段未到达；无 pair 力、sum、reciprocity 或验证通过的 mapping |

actual stage 仍读到 18 个启用 collider/18 owners、31 个 runtime body、原 q/qd 偏差；输入 manifest、USD、URDF 及候选 38 文件保持摘要。**接触对仍全部未知**；不能拿矩阵尚未采集或零结果否认 self-contact，不能据本次失败推定 backend 不支持接触对。

### 诊断修复与测试边界

容量不再硬编码，复用实际 sensor 配置并拒绝非正整数。内部异常先保存 `reset_probe_failure.json`、打印 traceback、flush 并退出 1，避免 finally/app.close 吞掉错误；成功路径仍关闭。

自检通过原 38 文件核对、五个映射/读回/哈希破坏例、两个诊断身份拒错和新增四个接触行列/shape 负例。退出回归执行实际 handler/finally 的 AST 子进程，stub close 退出 0：修复前 code=0，修复后 code=1，成功 code=0；该回归只证明退出分支，真实 PhysX 失败证据另取 attempt04，不混称。

attempt04 修订后增加“每视图 raw mapping 在验证前落盘”：独占文件记录实际 sensor_paths/filter_paths/count 与 API 源摘要，初态 unverified，只有验证通过后才改内存状态为 verified；这是为下一次确定接口语义留证，**该终版改动本轮未再起仿真**。不覆盖 attempt03/04，也不为补证伪造旧 mapping。

### 本机绑定与复读

| 对象 | SHA256 |
|---|---|
| attempt03 运行源码快照 | `0acd5f87906c119685014b37d0f9e94ff3f23a7af34e750bc416e2d34ae202a9` |
| attempt04 运行源码快照 | `befecc4933c10eacb6c4a01c1d826188d16f28d90fa8cad69ff74f335a7e50db` |
| attempt04/reset_probe_failure.json | `7899ba03d5d615d8a526e92a3ea532bb3fc4c3d4c4a9723426c426da1a2d85a4` |
| attempt04/capture_observation.json | `6261093b3ef06d9713f708cf0c5d6e67f91c8f2c6b296fff3a7820966d548353` |
| 父目录 attempt04_capture.log | `6c70329dc68fc761fc736f73552b1aefe4d16d8551de775f190b4141388ca512` |
| raw mapping 留证终版源码 | `15684c7f47641c70d5ef9a7eb8102eb4a6d5e381eeeac2cf419b7adeabb75ba7` |

执行者直接读取并核对本机 observation 的 observed_exit_code、marker、错误阶段与失败工件摘要，自检/AST/空白检查通过。独立审核核代码侧拒错、raw 文件唯一性及测试边界；其上下文未能读取本机 out，不能宣称其完成实测证据审核。实际 attempt04 的失败判定以直接采集的 observation/log/failure 三者为依据，不以源码支持替代。

本轮完整离线套件退出 0：37/37、60.1 s；代码提交 `e66a16b` 的 pre-commit 全部通过。套件通过不代表接触对采集通过。

下一步只读确认实际 TensorAPI filter_paths 返回语义；再次仿真须新获预算并用新目录，不能复用 attempt04 成功身份。复读入口如下，命令用于获准后的新尝试，不表示本轮已经执行：

```cmd
"E:\IsaacLab\env_isaaclab\Scripts\python.exe" -B rl_exp\tools\diagnose\palm_spatial_runtime.py --self_check
"E:\IsaacLab\env_isaaclab\Scripts\python.exe" -B rl_exp\tools\diagnose\palm_spatial_runtime.py --reset_probe rl_exp\out\lizard2_e_registered_20261015\attempt01\registered_manifest.json --contact_pairs --out rl_exp\out\lizard2_e_registered_20261015\pairs_replay01 --viz none --device cuda:0
```

## 追加：真实接触路径修复与采力（2026-10-16）

### 验证对象与根修复

用户批准最多两次短检查：先保存实际路径结构，再最小修复复验；资产、驱动、物理过滤仍保持不变。真实安装入口已定位为 `isaacsim/extscache/omni.physics.tensors-110.1.11+110.1.1.wx64.r.cp312.u7f4/omni/physics/tensors/api.py`。`create_rigid_contact_view` 的单 sensor/多 filter 说明在 :393，`filter_paths` :4898 直接转发 backend，未规定 Python 嵌套形状；不能据框架 mock 猜列。

attempt05 用原 helper 真复现退出 1，raw 文件记录 `sensor_paths=[body]`、`filter_paths=[[18 个 body 路径]]`、counts=1/18。原 helper 将外层 sensor 行误当 singleton filter 列，把十八项行变为 None。新增精确单 sensor 行展开，仍核实际 source、owners 集合、重复与 `(1,18,3)` shape；不递归猜测、没有把不匹配改为默认成功。

实际 raw 输入对旧 helper 真 ValueError，新 helper 返回十八列；固化该结构后旧 self_check 退出 1，新 self_check 退出 0。原四个 pair 拒错保留，新增四个嵌套/歧义/缺列/重复负例通过。CPU 对照仅证明 helper，运行 mapping 另由 attempt06 验证。

### 实际采集与交叉读点

attempt06 实际退出 0，完成 marker 与报告 `completed=true`；报告同时 `status=blocked`，baseline 没有被宣布通过。18 个单体 view 均取得实际路径并 verified，每个力矩阵 `(1,18,3)`，capacity 沿用 4，dt=0.005 s。declared patterns 与 resolved columns 分开保存；raw 文件验证前状态 unverified 与汇总 verified 各自有身份。

以下两阶段共享 solver 历史，不是独立过滤对照。

| unordered body pair | 原状态下一步法向力范数 [kN] | 同历史写绑定零位后下一步 [kN] | URDF 距离 |
|---|---:|---:|---:|
| base_link ↔ tail1_pitch | 46.939 | 52.836 | 2 |
| base_link ↔ rl_hip_twist | 29.482 | 56.709 | 3 |
| base_link ↔ rr_hip_twist | 26.265 | 56.203 | 3 |
| chest_pitch ↔ lf_shoulder_twist | 45.209 | 24.818 | 3 |
| chest_pitch ↔ rf_shoulder_twist | 45.172 | 50.099 | 3 |
| tail1_pitch ↔ tail2_pitch | 本次未报非零聚合值 | 1.617 | 2 |

第一阶段五个 unordered 对，第二阶段六个，不是两个文件 pair 集合完全相同。两阶段所有非零 pair 的互反残差为 0 N，同一步主 sensor 对照残差为 0 N；matrix sum−net 最大分别 0 N 与 0.00208594 N。最大 body net 约 57.803/75.815 kN；与当前净力异常一致，实证这些 body 之间存在强 self-contact，但不证明全部响应只来自它们。

力为 normal aggregate，不含摩擦/接触点/穿透深度；每 owner 一个 collider 的对应依据来自实际 USD nearest RigidBodyAPI，而非字符串猜 collider。零列不证明整个轨迹无碰撞。第二阶段沿用同一 solver 历史，仅写回绑定默认值，不是独立过滤对照。关节状态和 reset 阻塞与 attempt02 相同，下一物理步仍偏离。

### 与已有几何排除的对照

`palm_gait_kinematics.py:43` 的六对 APPROVED 被 `palm_spatial_probe.py:359-372` 明确按 abduct→twist 重映射；上述六对 union 恰好命中当前离线几何排除，不是凭两三层 ancestry 批准。原列表也用于旧四轴 `palm_pd_probe.py:382` 的诊断过滤。

执行者直接读取本机固定 USD 文本并核 SHA，未见 authored `FilteredPairsAPI`/`filteredPairs` 字段。此项只描述该输入层，不拿来推断全部运行时自动相邻过滤。实际非零 pair 另证明本次运行这些 body 接触在报告中存在。**几何排除命中不等于新三轴运行时过滤自动获准**；新载体/实体归属、连接区几何理由、应保留的非相邻及跨腿接触反例仍由限位 PD 专项步骤 4 核验，不在本轮写入过滤。

### 绑定与复读

| 对象 | SHA256 |
|---|---|
| 最终运行源码及快照 | `1588d503e82b1ef70f79c7d3791e23d246295119f636dc26344df6e017535900` |
| attempt06/reset_probe_report.json | `36344c8af1ccf56552c931d252008fb50a9b6951265e8fe083f2079bd340d115` |
| attempt06/contact_pair_mapping.json | `ab36809e2bafdb3b634579ffcb27ae7fd3e8545e58f88fa959d08683dd8fa576` |
| attempt06/post_1_physics_step_contact_pairs.json | `3b784d059d2c9bf6266d4916c3c2b5366c7171275c9feca2eaa28f29ec34ecc4` |
| attempt06/explicit_default_post_1_physics_step_contact_pairs.json | `b0509faa794c8eca0f700addda0cc150a775dcd4c5843fdb81d91f29a328520d` |
| 父目录 attempt06_observation.json | `f4eb3e09893a23bcfc0315bf495fb4b5156b6a519807ebf6532f49afbe10446a` |
| 父目录 attempt06_capture.log | `47d81bea6cfe8511e12aa5d88f45ae889cfd402eb4c20a81f9dfe72f64406a30` |
| 实际 TensorAPI api.py | `be558e31693e0d48a7003134a777c306bc3b080ce5e7ce6ebabc418fb680f9ca` |

这些 attempt 均位于 `rl_exp/out/lizard2_e_registered_20261015/`，与早先专用 runtime 的同名 attempt06 不同，不混用目录。输入 manifest、USD、URDF 与 38 文件摘要仍保持原绑定。执行者直接复核观测退出码、主报告、全部 mapping、两阶段 force/交叉对照及源码快照摘要通过；旧失败产物保留原身份。

复读仍使用上一节 `--reset_probe ... --contact_pairs` 命令，必须新输出目录。当前脚本可采集接触对，不意味着该检查点动力学、baseline 或完整 E 已验收。

独立局部审核直接读取 attempt05 raw 路径、attempt06 observation 及两阶段 pair 产物，确认精确绑定、真实采力、第一五对/第二六对和同历史边界；未替执行者核源码/输入摘要，不冒称总 E 审核。两份 pair 文件均在注册诊断的 `attempt06/` 下，父目录不存在同名 pair 文件。

本轮完整离线套件行为检查全部通过，但成本闸门退出 1：`test_baseline_contract.py` 波内 28.5 s、自动单独复核 25.2 s，超过既有 25 s 预算。当前只改接触诊断 helper，不改该 contract 检查；不能因此直接归为接触修复造成，也不能删测试或抬预算。执行者随后逐测试计时和 profile：最贵为 frozen judge semantics 与四种命名实际绘图 roundtrip，AST/读文件开销很小；未删除测试、mock 绘图或改预算。原脚本再次单独实测 21.262 s，75+5 项通过，期间主机 CPU 仍忙，不能称安静、不能单凭较低读数宣布退化已消失；随后 runner 全套复核行为仍全通过，但再次成本拒绝：波内 28.9 s、自动单独 31.8 s，预算保持 25 s。当前检查点修复和真实采集已留证，提交/推送暂停，不能靠重复跑到绿或预算豁免收尾；下一步需处理该独立成本阻塞。

## 追加：默认回归与完整绘图矩阵成本拆分

### 用户决策与执行范围

用户选择先修成本再提交；随后批准最小拆分：默认闸门保留共享缺陷回归和全部报告拒错，完整绘图矩阵移到显式专项。不改变套件条数、单条预算、冻结协议、生产 reader 或真实数据判词，不跳提交钩子。

线程假设先实测：同一完整脚本默认 8 线程为 22.667 s，单线程为 24.172 s，两者行为均通过，**没有证据支持限制线程更快，未设置线程上限**。前成本超限 25.2/31.8 s 保留原记录，不无痕抹去。

### 最小实现

- 默认 `test_target_binding_report_roundtrip()` 仍对 shared/split/palm/palm_spatial 全四种命名实际 save/load、judge 数值等价、词根/索引选择及缺列/混名/缺来源/重复等负例；检查真实 `at_stop` 数值，不用 mock 绘图代替它。
- `test_baseline_contract.py --render_matrix` 显式执行同一完整矩阵，真实调用四次 `draw_band`、生成八张 PNG，并核文件存在与绘图返回数值等价。不新增默认清单条目；`--binding-only` 继续核轻量绑定，完整渲染须另跑此专项。
- 夹具 `build()` 每帧仍调用真实 `BaselineFrames.add`，只复用输入默认缓冲并逐帧替换 override；`add` 自己 clone 保存，不缓存生产判词、不绕过逐帧契约。新增小测试核可变 override、帧快照和跨次调用隔离。

### 等价与成本证据

取 Git HEAD 旧 build 与当前实现，在同一 scope 通过真实 recorder 比较：三格式 × 一/二环境 × clean/可变 override，共十二组合，计时前后各验一次。所有列、shape、tensor bytes、protocol/meta/axes 与完整 judge 结果全等，零排除字段。累计 48,000 次真实 add 委托原实现；每一千帧 `default_frame()` 调用从 1000 降到 1，不冒称 recorder clone 分配也减少。

同进程八线程微基准三轮交替先后顺序，旧为 0.574035/0.579304/0.664462 s，新为 0.369797/0.360980/0.362726 s；最小值 0.574035→0.360980 s。该比较只证明夹具等价与开销下降，不是修复前行为失败的回归。

默认真实 main 定向运行退出 0，76 个 baseline 加五个 acceptance 测试完成；冻结摘要通过，draw_band 路由 guard 调用为零，wall 14.714 s。显式 `--render_matrix` 退出 0，wall 9.553 s（含短路由负例），四种命名真实四次 draw、八张 PNG，signature/文件存在/数值等价核对通过；专项 raising guard 错误向外传播，不吞异常。

定向计时包含 instrumentation，不能当安静主机稳定成本；随后默认 runner 完整复核退出 0：37/37、63.7 s，baseline contract 波内 19.5 s，不触发单独超限复核；预算/条数均未修改。结构独立审核确认默认共享回归、四命名读写/拒错与真 collector clone 保留，完整画图数值等价只由显式专项保护；该审核不冒称亲自重跑定向计时。

定向运行测试源码为 `3fa1fbdb8418a577a98e0ff3ecc03f286401d673d1fae4ab5bc49ca44a660f67`；随后新选项按 snake_case 改为 `--render_matrix`，不影响默认执行集合，终版另复验专项入口。终版测试源码 SHA256 为 `115469d25f48637935015effbb5ddc335cc4567c0b4e8dd0506ddcb1e00685bd`，专项 CLI 退出 0，确实生成四命名八图。代码提交 `3af140b` 的提交钩子全部通过；不存在成本豁免或跳钩子。生产接触采集源码与上一节绑定不变。复读命令：

```cmd
"E:\IsaacLab\env_isaaclab\Scripts\python.exe" -B rl_exp\tools\verify\test_baseline_contract.py
"E:\IsaacLab\env_isaaclab\Scripts\python.exe" -B rl_exp\tools\verify\test_baseline_contract.py --render_matrix
"E:\IsaacLab\env_isaaclab\Scripts\python.exe" -B rl_exp\tools\verify\offline_suite.py --python E:\IsaacLab\env_isaaclab\Scripts\python.exe --jobs 4
```

## 追加：隔离 reset 与中立首步修复（2026-10-16）

### 授权范围与停止点

用户批准恢复确定性 reset、核六个连接区后做具名过滤对照和跨腿负例；固定基座、禁重力、零增益，一个环境，最多三次短启动。正式资产、网格、惯量、PD、奖励与原检查阈值不变。三次启动包括一次 USD 层生命周期崩溃，预算用尽后用户选择“停在当前证据”，因此没有再启动 baseline 十步采集；不能宣称 baseline writer/reader 已通。

### reset 的实际修复

根因在 `palm_spatial_runtime.py` 注册隔离配置生成处：原实现将全部 events 置 None，连正常 reset 的根状态和关节状态 writer 一起取消。修复只改变新生成的 v2 诊断 manifest，保留 `reset_base` / `reset_robot_joints`，显式钉零根偏移与速度、关节位置缩放 [1,1] 和速度缩放 [0,0]；其余随机事件仍取消。使用框架真实 `reset_root_state_uniform` / `reset_joints_by_scale`，不在 evaluator 里临时写零，不修改冻结母本。旧 manifest 与旧证据不覆盖，仍可用原诊断口径读取。

未过滤对照 `reset_unfiltered_20261016` 退出 0、completed=true、status=blocked：gym.make 后仍偏移 0.134496257 rad / 19.841339111 rad/s；wrapper 的正常 reset 确实调用关节 position/velocity writer，返回后两项误差均为 0，backend/cache 差为 0。随后一个 0.005 s 物理步又偏移 0.047132555 rad / 10.005182266 rad/s。此对照区分“reset 接线已修”和“碰撞响应仍在”，不拿 reset 成功掩盖首步异常。原 attempt02/06 的无 writer、同位置偏移是修复前真实反证。

### 六个连接区与过滤边界

`--connection_geometry` 复用实际 URDF/FK、闭合真实网格的三角面交叉与 solid-angle containment，实扫所有中立非直接连接网格对。扫描连接集合须严格等于现有 APPROVED 经实际 build 的 abduct→twist 映射所得六对；任何额外非相邻干涉拒绝，不仅比较生成列表与写入列表。肩髋新链实际树距为 **3**，并非旧四轴的 2；中间 swing、abduct 两个 link 均无 collider，三轴枢轴共点，实体属于 twist 下游。尾段仍为树距 2、一个无 collider 的 yaw 载体，两个枢轴相隔约 5 mm。逐对真实面交叉与归属保存在 geometry 报告；该机构理由仅授权当前中立诊断的具名连接排除，不推导整个 ROM 无干涉。

实际隔离副本只新增以下六对 `FilteredPairsAPI`：base↔rl/rr hip_twist、chest↔lf/rf shoulder_twist、base↔tail1_pitch、tail1_pitch↔tail2_pitch。去掉新增 relation 并恢复原 apiSchemas listOp 后，USD 整个根层文本与强引用保留的源 stage **逐字相等**，核无其它几何、惯量或物理属性差异；实际运行时全部 authored filters 也须与六对严格相等。源 USD 与 checkpoint 38 文件保持原摘要，自碰撞仍开启。`--repair_connections` 只写新 attempt，不覆盖源件。

第一次过滤启动 `connections_fixed_20261016` 在物理初始化前发生 native fatal：`attempted member lookup on NULL TfWeakPtr<SdfLayer>`，退出 2147483651，**没有成功报告**。错误来自我新增差异核验的 `Usd.Stage.Open(...).GetRootLayer()` 临时 stage 被释放、layer 仅持 weak reference；改为持有 `source_stage` 强引用，并恢复原 schema listOp 后离线核 delta，随后第三次启动复验。失败日志原样保留，不补造 Python exception 报告，也不将该次算物理反例。

### 修复后的真实正反例

`connections_verified_20261016` 退出 0、completed=true、status=reset_and_neutral_first_step_verified。与未过滤对照使用相同候选、根高、默认 q/qd、零驱动、步长和阶段顺序，各自独立进程/solver 历史；仅过滤副本有上述六对差异。gym.make、wrapper reset、正常首物理步及写回默认后的首步，q/qd 最大误差均为 **0**，cache/backend 差均为 0。中立观测的全 18×18 owner 法向力矩阵无非零项；这不是全轨迹无碰撞证明。两阶段在各自运行内部仍共用历史，不冒充四个独立实验。

保留碰撞负例用同一五轴资产：除 `chest_yaw_joint=+0.6 rad` 外其它关节零，离线确认 `lf_wrist↔rl_ankle` 真三角面交叉；运行后该跨腿 pair 实测 **107.647354 N**，两方向大小相同、反向，非祖先关系、树距 12，不在六对过滤中。随后正常 `live.reset()` 将激励后的 q/qd 恢复为零，严格 reset 检查通过。该负例证明没有关闭所有自碰撞或误滤这组跨腿接触，不证明全部非相邻接触均完整保留。

### 验证入口与输入绑定

新增检查留在诊断脚本及显式 `--verify_registered` / `--self_check`，**没有增加默认闸门或默认测试函数**。真实 loader 正例与重复动作、缺 twist、外来末端、错 SHA、缺 reset writer 五类拒错通过；filter 集合缺对、重复、跨腿追加三类 self-check 拒绝。实际 before/after 物理对照承担碰撞修复的行为反证，不将 CPU 集合检查冒充 PhysX 行为。最终源码 `d531bc5293dac6ae42db4a02b3d6f8d4ccbad655203a8e529bdf49acff7665ae` 相比成功启动源码只追加 manifest 缺 reset writer 拒错；物理分支未改，另完成最终 self-check 与 loader 复读。

本机证据都在 `rl_exp/out/lizard2_e_registered_20261015/`，以下摘要逐文件复读；产物本机保存，不承诺 clone 携带资产二进制。

| 文件（相对上述目录） | SHA256 |
|---|---|
| reset_fixed_20261016/registered_manifest.json | `745b6953c10cf2ae4c9a39a13e9020ffc8dc0ed01ce94a286599bc5c56a9c7ac` |
| reset_unfiltered_20261016/reset_probe_report.json | `f2b46799fd391fcf9d8a454b89779923612ba3428a6312bd541cd5678c9ab7da` |
| reset_unfiltered_20261016.log | `72452fdcda7c5a25fbfe0de29824401945059c88ed78150d42c9bc4f08eec0bb` |
| connections_fixed_20261016.log | `0d687ea4af67bda034836e336555d47bc2e6d1befc7d57c6f239c6fce984dc48` |
| connections_verified_20261016/reset_probe_report.json | `923298e61278a9186be1fa202ce6257b333528347ce9f1f32359ad311499083f` |
| connections_verified_20261016.log | `f23ec167f7c43d90106089ca6836b5e946fb3fa03ff8e5218c806747219d2ff2` |
| connections_verified_20261016/registered_manifest.json | `eb58101306a1f27f931a63c6e24f00267946d91596a1c8e55b07f4490bbd9b62` |
| connections_verified_20261016/palm_spatial.usda | `62f430ee78fbfa45bf65d43d34f3f8bd332316cf0e68919511a2a8fb6dbfcb19` |
| connections_verified_20261016/connection_geometry.json | `64023ff37a77dd40f8922aac68a53797a3446ad5c3f965a2ed3611e92baeb7f7` |
| connections_verified_20261016/post_1_physics_step_contact_pairs.json | `5e6ae8fb134400caddfd585de6a1b535482acba62d2cfb936114571e0cb416ae` |
| connections_verified_20261016/cross_leg_post_1_physics_step_contact_pairs.json | `99da9c3123b62180880be31fc55fad5308e234c2e8046b13ee6162aa897f451d` |

未过滤运行源码 `b22b43b33884f7af2215b802fe9f36eef5542ac049017ba610cbf059abc78a48`，成功过滤运行源码 `5de9d720ddc755d712e8c4911852bf109e5479952f3fbb674ea5d2d196bd3299`，各保留 `reset_probe_source.py`。两者之间只修改了输入 pin、额外 USD 差异核验及枢轴集合选择，未改 reset/状态/步进顺序或驱动。原值完整保留，不用最终源码摘要代替采集版本。

最终默认完整离线套件退出 0：37/37、52.4 s，baseline contract 波内 16.3 s；无新增默认条目、无预算调整。新上下文局部审核直接对照代码、两个实际报告、geometry、负例及活跃路由，未发现阻塞矛盾；此审核只覆盖本轮 reset/中立首步切片，不关闭 E，不冒称亲自逐字比较采集源码。执行者随后实际 unified diff 确认成功采集到最终源码仅新增上述缺 reset writer 拒错。

显式复读入口（启动须另获预算，输出用新目录）：

```cmd
"E:\IsaacLab\env_isaaclab\Scripts\python.exe" -B rl_exp\tools\diagnose\palm_spatial_runtime.py --connection_geometry
"E:\IsaacLab\env_isaaclab\Scripts\python.exe" -B rl_exp\tools\diagnose\palm_spatial_runtime.py --prepare_registered --out rl_exp\out\lizard2_e_registered_20261015\reset_repair_replay01
"E:\IsaacLab\env_isaaclab\Scripts\python.exe" -B rl_exp\tools\diagnose\palm_spatial_runtime.py --reset_probe rl_exp\out\lizard2_e_registered_20261015\reset_repair_replay01\registered_manifest.json --contact_pairs --out rl_exp\out\lizard2_e_registered_20261015\unfiltered_replay01 --viz none --device cuda:0
"E:\IsaacLab\env_isaaclab\Scripts\python.exe" -B rl_exp\tools\diagnose\palm_spatial_runtime.py --reset_probe rl_exp\out\lizard2_e_registered_20261015\reset_repair_replay01\registered_manifest.json --contact_pairs --repair_connections --out rl_exp\out\lizard2_e_registered_20261015\filtered_replay01 --viz none --device cuda:0
"E:\IsaacLab\env_isaaclab\Scripts\python.exe" -B rl_exp\tools\diagnose\palm_spatial_runtime.py --verify_registered rl_exp\out\lizard2_e_registered_20261015\connections_verified_20261016\registered_manifest.json
```

## 追加：baseline 十步真实写读闭环（2026-10-16）

用户随后批准一次十步 baseline 短仿真，失败即停；只使用上述 `connections_verified_20261016/registered_manifest.json`（摘要 `eb58101306a1f27f931a63c6e24f00267946d91596a1c8e55b07f4490bbd9b62`），未改正式资产、PD、具名过滤集合或阈值。运行前核 manifest、USD 与 geometry 摘要，读取此前完成的 reset/过滤正反例；输出选全新文件名，不覆盖任何已有采集。没有修改采集、collector 或 reader 源码，也没有新增默认检查。

### 实际消费者与结果

真实 `baseline_eval.py` → 正常 `RslRlVecEnvWrapper` reset → `joint_reset_errors` → `BaselineFrames.add` / `save` → `baseline_metrics.judge` 完成，命令退出 0、报告 `smoke_only`。严格 reset 检查在采集前保持原实现；有记录表明该分支未拒绝，不将其等同于额外采集了 reset 数值。随后独立进程从磁盘 `.frames.pt` 调同一 reader 的 CLI，判定字段与报告内原始 `reader_validation` 全等；函数复读含 axes 也全等。

实际记录为 `baseline-frames-3`，一个环境、十个 0.02 s 控制步（0.2 s），17 列均为十个真实快照，全部有限。`joint_pos` shape=(10,1,30)，实际运行序的 20 个腿关节与 10 个躯尾关节完整、唯一，包含四条 twist；六类足端轴均为 `rl_ankle / rr_ankle / lf_wrist / rf_wrist`。terminated 与 timeout 十帧均零，使用真实 reader `_alive` 核十帧全部在首局内，无 reset-mixed 数据。所有关节位置最大绝对值为 0 rad：固定基座、禁重力、零动作/零 PD 下的中立采集，**不证明驱动跟踪或步态**。

正式协议仍是冻结 `lizard2_flat_v5.json` 的 20 s / 1000 步，reader 原判定为 `invalid`，唯一原因是 `the window is 10 steps x 0.02 s = 0.2 s, but the protocol declares 20 s`。smoke 包装保留原判定，全部性能 gates=None、metrics/diagnostics/per_env 为空；不能据此引用任何成绩。reader 因短时长在契约阶段返回，不会自动执行 `_data_reasons`；执行者另对实际记录调用原 `_data_reasons(artifact, _alive(...))` 得到空列表，并独立核所有列有限、shape 和身份，未改协议缩短窗口“变绿”。

`terminal_frames_captured=0` 且本窗无 done，因此没有应捕获的终止帧；该次**未覆盖终止 hook**，不能证明 hook 存活。这个事实不同于有 done 却捕获 0 的失配，不能拿十帧首局通过解除终止分支的专项验证。

实际记录的内存副本分别破坏来源、twist 声明、关节命名、足端轴后，经真实 `baseline_metrics.judge` 拒绝：缺 source；缺 `lf_shoulder_twist_joint` 声明与实际轴冲突；`lf_hip_joint` 混入 spatial；`lf_ankle` 混入足端。原始 pt/report 完全不改。既有四命名及共享缺陷回归继续由默认测试守护，本轮未因复验新增默认负担。

### 身份与复读

采集版本及工作树来源在报告 `code` 中保存；共享工作树含其它 A 在办改动，不宣称整树 clean。三个实际消费者文件在本轮采集前后无本轮改动，分别 SHA：baseline_eval=`6b4ea3f3868b37fd39e7782b0ca7e3c9f2afa79331199f88b1c383b019fdb3aa`、baseline_frames=`3c2b9adc8949929cdde9a96b0f9a2ec08ccef5f5055238a5a695d9e3e5cbf39d`、baseline_metrics=`fbd63fb5ec784488d568f0dd96e373d10a1f4ad8a4fb4b409c8730f77c1a3929`。协议 SHA=`db5f92ba56586907837f49081ba640d0239ff92a2692277371b3ae8b79aa138a`，内容与 pt 内协议全等。

证据相对 `rl_exp/out/lizard2_e_registered_20261015/`，本机产物不承诺随 clone 入仓：

| 文件 | SHA256 |
|---|---|
| baseline_smoke_20261016.log | `52124ce9bde4baeb6dbab6dc899f709c6962d6573388ca70984f36927c3d3fcf` |
| connections_verified_20261016/baseline_smoke_20261016.json | `c55c1dffaf168a89096bbdfcaed227c08370d3f01252eb1641f3344b2aec83a6` |
| connections_verified_20261016/baseline_smoke_20261016.frames.pt | `34f490be00d64fecdb4946a8875de12b746b44930dda3a26e847faf32cf2eda6` |
| connections_verified_20261016/baseline_smoke_20261016.reader.json | `6e86e2745c070ba1f897935b0aa0e959c52a99bc739986814ee0ff821c8109e7` |

```cmd
"E:\IsaacLab\env_isaaclab\Scripts\python.exe" -B ablation_harness\baseline_eval.py --task Lizard2-Flat-Play-v3 --target_config rl_exp\out\lizard2_e_registered_20261015\connections_verified_20261016\registered_manifest.json --protocol ablation_harness\protocols\lizard2_flat_v5.json --num_envs 1 --smoke_steps 10 --viz none --output rl_exp\out\lizard2_e_registered_20261015\connections_verified_20261016\baseline_smoke_replay01.json
"E:\IsaacLab\env_isaaclab\Scripts\python.exe" -B -m ablation_harness.baseline_metrics rl_exp\out\lizard2_e_registered_20261015\connections_verified_20261016\baseline_smoke_20261016.frames.pt --protocol ablation_harness\protocols\lizard2_flat_v5.json --naming palm_spatial
```

第一条为本次成功采集的同参数复读，输出改新路径；重新起仿真须另获预算。第二条已独立进程执行，仅读盘，不启动仿真。该闭环仅解除先前缺真实 baseline 产物的接线缺口，不解除 E 其它必需链或动力学前提。

新上下文只读审核核对记录、两个 JSON 与 reader/collector 源码，没有报告阻塞矛盾，确认短窗提前返回及终止分支未覆盖；该审核没有加载 pt 或独立复跑四负例，pt 张量与负例的实际核验归执行者直证，不将源码可拒绝代替已执行证据。审核输出误称报告无顶层 verdict；执行者直接读取已确认 `verdict=smoke_only`，不采纳该误读，其余局部范围结论不用于关闭 E。

## 未覆盖边界

- 当前隔离 manifest 的正常 reset、中立首物理步及 baseline 十帧实际 writer/reader 已核；完整 20 s 评测、终止帧 hook 实测和任何性能结论仍未覆盖，不以短窗 smoke 宣布 E 完成。
- 注册在线协议非空足端分支、实际 collider/body-owner 接触归属及 gait 诊断 writer/绘图已核；具名过滤仅核当前中立及一组跨腿负例，不证明全 ROM。baseline 当前十帧均为首局有效采集，但不是运动；逐轴受控驱动、惯量一致性、PD 跟踪、承重、连续安全域和行走均未完成。
- 未接正式 Blender 导出目标或验证其错源/错目标；旧资产 cap/contact ownership 缺口仍由 `floor-contact-attribution` 回交，不用新候选读数解除旧资产前提。
- A 的树/轴/零位/网格/惯量/命名变化后按变化重验受影响链，不外推检查点结果。总事项维持 in_progress，最终仍随 D 由新上下文审核。
