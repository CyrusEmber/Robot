# TGS 速度偏差定位与非零策略观测切片

## 适用范围

**用户纠正定案（2026-10-22）**：本次及后续默认驱动、观测与集成验证须保持与训练一致，`enable_external_forces_every_iteration=false`。执行者此前把 true 当作设置候选并接承地复验不符合本次条件；撤回该候选采用路由。已经执行的 true 数据仅保留作机制归因对照，不能作为训练一致的驱动/观测验收结果，不作为训练设置候选，也不据此改变 PD、训练配置或策略输入。训练一致 false 下的速度偏差及其进入策略观测的事实继续保留，不能用 true 的较小偏差替换或消除该边界。后续不再启动 true 工况，除非用户另有明确指示。

承接[RL 分工与通道核对](2026-10-22-lizard2-rl-coordination-handoff.md)，用户要求继续处理速度读数异常及非零观测语义。保持当前全部 PD、力矩/速度上限、资产、重力、目标和原停止条件；仅在隔离诊断中比较 TGS 外力施加时序。没有改 IsaacLab 默认值、正式 v3、配方锁或训练状态，没有增加 PD。

用户追问是否“先检测再施加外力”。两组实际采样顺序完全相同：写入驱动目标 → `sim.step` → `scene.update` → 读取后端/缓存/观测。这里的外力主要是始终存在的重力，没有另加测试推力；对照只改变物理步内部一次计入整步重力影响，还是各位置迭代按对应时间份额计入。不是把重力重复加倍，也不是改变控制器量测/出力顺序或对观测数值做后处理；该求解器选项确实会影响模拟状态，不能当仅显示修正。

用户另问训练使用什么求解器。实际构建当前 `Lizard2-Flat-v3` 得到 `PhysxCfg`、`solver_type=1`（TGS）、外力每迭代选项为 false；已完成正式 run 的 `E:/IsaacLab/logs/rsl_rl/lizard2_v3/2026-10-10_10-14-50/params/env.yaml` 同样保存该设置。物理 dt=0.005 s，decimation=4，策略更新与 TGS 内部迭代是不同层级。用户现明确要求当前候选的验证保持该 false 设置；true 仅属偏离训练条件的诊断对照，不是采用方案，旧配方本轮未改。

物理范围是同一固定根左后膝的两组原 17 s、±0.02 rad 往返，以及诊断对照时序下的一次原 5 s 自由根承地观测，共 7800 步。固定根沿用前序 5 s 静置、两方向各 2 s 伸出/1 s 保持/2 s 返回/1 s 恢复，dt=0.005 s；自由根沿用[原静站预算与判据](2026-10-22-lizard2-standing-joint-force.md)。无增益扫描、无自动重试物理。

## 验收条件

- 从已验实际力矩报告及 manifest 的批准哈希接入，全部 Kp/Kd、effort/speed 上限读回与原值相等。TGS 求解类型和外力时序读实际场景属性；迭代次数字段只保留原配置值，不冒称额外测得迭代行为。
- 固定根两次运行的源代码、输入、基座、全部非时序 physics 配置和读回一致；唯一变量是 `enable_external_forces_every_iteration`。逐步记录后端 q/v 与缓存 q/v，不能由单条警告推断原因。
- 用实际 q 的相邻步差分与同区间两端读回速度平均比较；固定根静置及正/负保持、恢复窗口分开报告。误差只用于诊断归因，不新增“差分等于瞬时速度”的硬性能门槛。
- 运行真实 observation manager，逐项记录 raw、clip、scale 及最终 policy 拼接，独立核对关节列、动作列、重力投影及自由根 COM 速度到 body frame 的变换。七类实际观测函数另用各列不同的非零夹具验证默认值扣除及消费者语义；夹具不写入仿真。
- 复读原始样本、原站姿判词及新切片；缓存错位、错误关节观测、错误根坐标和错误速度消费者须被拒绝。原失败保持失败，诊断有效不等于正式采用求解设置或完成限速/策略验收。

## 结果

### 速度偏差来源

源码 `isaaclab_physx/.../articulation_data.py:joint_vel` 按时间戳直接取得 `root_view.get_dof_velocities()`；实际关节观测直接使用该 data 通道。两组完整逐步后端/缓存 q/v 均逐值相同。旧时序重跑的 q 和 v 与前序左膝实际力矩 case 最大差均为零，排除本轮新增观察动作造成复现差异。

| 固定根静置末段左后膝 | 训练一致 false | 偏离训练的诊断对照 true |
|---|---:|---:|
| q 差分速度最大 rad/s | 1.1641532e-8 | 0 |
| 后端速度平均 rad/s | 0.0511575019 | −5.5265145e-9 |
| 后端速度与差分最大差 rad/s | 0.0511575141 | 8.3568064e-9 |
| 实际步平均保持力矩 N·m | −0.156620930 | −0.157283921 |

诊断对照时序正/负保持的左膝速度差分差异最大约 1.19e-6 / 1.10e-6 rad/s；各静置/保持/恢复窗口全关节最大差约 1.56e-6 rad/s。诊断对照时序左膝正/负保持直接目标角误差分别约 0.00013844 / 0.00134743 rad；这是当前单轴切片读数，不复用为五轴组合或其它膝肘通过。

实际单变量对照支持：本轮固定根驱动静置偏差来自 TGS 的外力/驱动迭代时序，非 Python 缓存或 observation 列错位。不能称所有求解误差都由这一原因解释。[PhysX SDK 的 TGS 稳态速度与位置差异说明](https://nvidia-omniverse.github.io/PhysX/physx/5.8.0/docs/Simulation.html#tgs-steady-state-velocity-and-position-discrepancy)描述整步施加外力与子步施加约束力产生稳态非零速度的机制；该文档用于机制对照，不将文档版本等同本机 SDK 版本。当前本地 `PhysxCfg` 也明确说明该选项用于改善速度更新；根因判断依赖本机实测，而非警告或文档单独推断。

### 非零观测与自由根复验

本节 true 下自由根的数值核对只证明该诊断工况的消费者行为，不向 false 的训练一致工况转移；固定根 false 的实际后端/缓存/策略观测复读及独立非零消费者夹具仍按各自范围保留。

固定根每组采 170 份真实 policy 观测，均为 102 维；末段偏置确实进入 `joint_vel` 观测。真实 raw 关节状态与独立后端值、clip/scale 和拼接复读一致，拼接最大差为零。七类非零夹具调用真实 consumer：base lin/ang velocity、projected gravity、velocity commands、joint position/velocity、actions，全部逐值相等；位置/速度夹具使用非零默认值以检验扣除逻辑，非零列各异以捕获排列错误。

自由根诊断对照时序完成 1000 步、5 s，无停止线触发。与旧静站 USD 字节哈希同为 `721e8a4053c2a6114b5c4607e57ed34f287fe317f8f9abb47a5e857b845e9c0e`；全部 PD 和上限相同，仅隔离场景时序改变。50 份真实非零根/关节观测的独立坐标转换及 raw 最大分量差 `4.0699846604e-7`，102 维 policy 拼接差为零。角速度与线速度均由世界 COM 速度转换到根 actor 的 body frame，重力按归一化方向核对；不把 COM 与 link 原点线速度混比。

自由根最后 1 s，全关节读回速度与 q 区间差分的最大差由旧工况 `0.0612169094 rad/s` 降为 `0.0031143211 rad/s`；根 link 线速度与位置差分最大差由 `0.0220695063 m/s` 降为 `7.2087671e-5 m/s`。诊断对照工况的 COM 线速度差异最大 `0.0001600307 m/s`。接触下仍有小幅差异，不据此认定全部速度精确、连续域一致或限速触边已验；区间平均与末步状态、接触离散及数值分辨率的影响未逐项归因。

原静站判据仍失败：`root_drop`、两侧 elbow，末端下沉约 0.03479415 m。进程如实退出 1；不将速度改善改写成零目标站姿通过，不继续为此加刚度。承重/姿态协调依用户定案交 RL，底层限速及接触/集成边界继续由 B/E/D 承接。

### 执行与拒错

首次固定根准备在构造环境前因注册 `RoughPhysicsCfg` 预设包装停止。按 `SimulationContext` 本身的 default 解包行为修正后运行，不更换该预设的实际字段；保留失败报告，首轮没有物理步。随后固定根两组正常退出 0，自由根完成但原静站判词失败退出 1，无物理重试。

静站既有自检通过；缓存速度加偏置、观测 joint velocity 加偏置、根线速度观测加偏置、将真实 joint velocity consumer 换成 joint position consumer 四类错误均被拒绝，原始文件未改。旧静站读取器默认入口回归通过；事项格式检查通过，仓库离线套件 `ALL_OFFLINE_CHECKS_PASSED (37/37 in 57.5s)`。首轮套件指出本地临时分析脚本重复哈希，改用统一 binding 函数后全套通过，未修改物理或原始证据。上述为执行者复读与受控单变量试验，不是事项关闭所需的新上下文审核。

## 证据引用

- 工具提交 `599d80f`：`rl_exp/tools/diagnose/palm_velocity_probe.py`、`palm_velocity_audit.py`；静站 `palm_spatial_standing.py --velocity_observation_probe` 及 `palm_standing_force_audit.py --velocity_probe` 为显式隔离入口。旧入口默认不采用新时序；新状态有专用前缀，旧读取器不会将其混成旧工况。
- 固定根训练一致 false：`rl_exp/out/lizard2_velocity_legacy_20261022_run02/report.json` SHA256 `798335b96355a631dc498fda6eff2be7eb92bf1c61de628372617d35c9122916`。
- 固定根诊断对照时序：`rl_exp/out/lizard2_velocity_per_iteration_20261022/report.json` SHA256 `6ba4db535973186464eb4e23c4cffc1f739b2ee718bd66cd8c5436dffc77dddb`。
- 两组实际源码 `source.py` 同为 SHA256 `7ac1fc42d6b3a0ba243d39e938bf44bda57bcdf24a444ae1accc91ff800b7055`；依赖快照及哈希在各报告，导入的五个 tracking 帮助函数 AST 与已提交 HEAD 相等，共享 tracking 其它在办修改未纳入提交。
- 自由根诊断对照：`rl_exp/out/lizard2_velocity_standing_20261022/report.json` SHA256 `b5cc951df4640dd98be1fbf34ad3ca3e581f4e3b3104c6581658066b38a85383`；实际 `source.py` SHA256 `e4f74855d5cb94da7ce0c374dd3766e05dbf20000da63c6a3fd17e844fa4dde4`。
- 总复读：`rl_exp/out/lizard2_velocity_comparison_complete_20261022.json` SHA256 `a793755d8d4ed134da22b405f8b003bb5a87dab051920ccb47ddbf905185604c`；反例结果 `rl_exp/out/lizard2_velocity_negative_20261022.json`；旧静站读取器回归、离线套件和提交前日志归同前缀本机输出。
- 原始逐步数据、观测、依赖源码及日志均保留本机，不承诺入仓。启动失败在 `rl_exp/out/lizard2_velocity_legacy_20261022/failure.json`，当次日志同名 `.log`；不覆盖前序报告。

从仓根复读，输出须不存在，不起物理：

```cmd
E:\IsaacLab\env_isaaclab\Scripts\python.exe -B rl_exp/tools/diagnose/palm_velocity_audit.py --legacy rl_exp/out/lizard2_velocity_legacy_20261022_run02/report.json --per_iteration rl_exp/out/lizard2_velocity_per_iteration_20261022/report.json --standing rl_exp/out/lizard2_velocity_standing_20261022/report.json --out rl_exp/out/lizard2_velocity_replay.json
```

历史诊断命令只供追溯；用户纠正后不再自行执行 true。若另有明确指示复读，须另有预算、每次新 out：`palm_velocity_probe.py --reference rl_exp/out/lizard2_b_joint_force_probe_20261021/report.json --approved_reference_sha256 13929c53eccdb51d454ade60cf071c3eaa614bf5c90684dd2e06f4017d2485ef --force_timing legacy|per_iteration --out <新目录> --headless --device cuda:0`。自由根沿原静站命令追加 `--velocity_observation_probe`；未提供该选项时行为保持原义。

## 未覆盖边界

仅核当前有限工况的速度来源、诊断对照时序及非零 policy 语义，不修改或批准正式训练求解器设置。没有重验全部关节当前 PD 的所有受载切片、五轴组合、硬限速行为、极限力矩、其它接触/姿态、gait/终止消费者或正式采用/训练。外力时序改变后，旧时序的保持精度与接触数值不能无条件转移；当前已测单轴与静站各保留原条件，true 结果不接入训练一致验收；后续按 false 条件及已有同条件证据接续。不把差分速度直接替换策略观测，不要求 RL 学习掩盖求解偏置；B/E/D、S5/S6 原未完动作继续在办。
