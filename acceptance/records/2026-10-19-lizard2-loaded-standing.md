# lizard2 组合驱动、静站增益修正与失败退出码

## 适用范围

承接小幅跟踪记录和限位 PD 专项步骤 6。先在同一固定基座、无重力候选上做近端组合激励与实际实体姿态核对；再在隔离副本中解除世界固定关节、启用重力，检查自由基座静站。正式资产、原惯量修正文件、配方、网格、关节限位及力矩/速度上限保持不变。

本轮只交短时诊断与增益候选，不交自由行走或完整 B/C/D 验收。自然落地尾段可分担静站载荷；没有把头腹等其它身体接触当支撑。

## 验收条件

- 组合激励沿用原 0.02 rad 幅度、2 s quintic 伸出/1 s 停留/2 s 返回/1 s 停留、0.005 s 物理与目标步长及既有误差判词。逐腿同时命令 swing、abduct、twist；用停留阶段的实际 q 和全体 actor 姿态对照独立 URDF FK，最大矩阵分量差须小于 1e-5。实际数据加参考轴反号后须被拒绝；不得只对目标 q 做 FK。
- 静站入口为 `palm_spatial_standing.py`。仅在新 USD 的世界固定关节增加 `jointEnabled=false`，规范化层文本去掉这唯一属性后须与原层相同。URDF 与网格保持字节内容；按实际中立碰撞网格最低高度确定根高度，再加 0.001 m 初始间隙。运行时须读回自由基座、全体 body 重力开启、原增益或具名修改后的增益、实际限位与上限。
- 运行前固定 5 s 静站窗口，最后 1 s 要求：根下沉不超过 0.02 m、机身倾角不超过 0.1 rad、全部关节偏移不超过 0.1 rad、根竖直速度不超过 0.05 m/s、每足地面法向力至少 5 N，平均总地面支持力与重量相差不超过 20%。根下沉超过 0.15 m、倾角超过 0.35 rad、关节偏移超过 0.35 rad 或非批准身体地面力超过 5 N 时停止。本切片条件不作为 S5/D 最终性能阈值。
- 对实际存在的唯一地面 collider 建每个碰撞 body 到地面的 PhysX contact view；实际 source/filter 路径、行列及形状必须核对。不能用 body 总合力代替地面接触对；脚掌与自然落地尾段列为静站允许集合，其他部位单列禁止。
- 参数按同一阻尼比规则分组调整，保留每次失败。本轮只比较原增益、腿部组频率调整、颈俯仰频率调整三个候选；另重复原失败工况核退出码，不作频率网格扫描或改变目标/阈值。增益改变后只补受影响驱动的跟踪与实体核对。
- 有物理失败或判词失败时，完整失败报告及原因可读，进程必须非零退出；正常完成且通过时退出 0。报告完成不等于判词通过。

## 结果

### 原增益的组合激励

四腿近端组合均通过；最大运动误差 0.0059818211547201915 rad，伸出停留末段误差 0.0001485966891050343 rad，返回末段误差 0.0001494000171078369 rad，其它关节偏移 0.001953192288056016 rad，无接触力。八份实际姿态快照的全体 actor/FK 最大矩阵分量差 8.66699218837752e-7。

同一实际 lf 停留快照对正确 FK 的残差为 5.776632643339497e-7；将参考模型的 shoulder twist 轴反号后变为 0.03702448802373209，超过原条件并被拒绝。这是对真实读回的错误参考对照，不声称又造了一份错轴仿真资产。组合判词扩展后，离线复读原 20 个逐轴工况的全部判词与原报告逐项相同；默认逐轴报告仍保留 `amplitude_rad` 字段。

### 自由基座与基线失败

四掌中立最低高度分别为 −0.602799、−0.602799、−0.602798、−0.602799 m，初始根高度取 0.603799 m。运行时质量为 72.00039672851562 kg，重力 z=−9.81 m/s²，重量 706.3238919067384 N；自由基座及全部 body 重力状态读回符合配置。18 个实际碰撞 body 均绑定到唯一地面 `/World/ground/terrain/GroundPlane/CollisionPlane` 的接触 view。

原 1 Hz、ζ=1 增益在 0.24 s 因关节偏移停止，根已下沉 0.12907591462135315 m；最大偏移为 rf_elbow 的 0.3535451292991638 rad。两前足实际地面法向力约 160/162 N、两后足约 105/106 N，尾段也接触地面；禁止身体部位地面力为零。前五步根高度连续下降，未出现固定关节警告所暗示的瞬间吸回原点；实际 `is_fixed_base=false`，不把禁用关节的导入警告当成功或失败依据。

前肢 shoulder_abduct 的原 Kp 约 52.812 N·m/rad，elbow 约 10.027 N·m/rad。用最后实际状态、逐 link 重力及已测地面合力，在每个接触体完整碰撞网格上取可能作用点的力臂范围，得到 lf shoulder_abduct 的载荷估计区间 [−66.8891,−28.0021] N·m、lf elbow [−9.1661,29.7698] N·m；rl hip_abduct [−49.7332,−24.4088]，rl knee [−18.3450,7.0718] N·m。这是该动态快照及未知接触压力中心下的几何区间，不是实际驱动力或静力解。原 P 在小误差下的恢复量不足以覆盖这些载荷，区间也未要求提高原 180 N·m 上限；因此只调整腿部组的频率初值，不放宽停止线或碰撞过滤。

### 按失败来源分组修正

将 `legs` 组的频率由 1 Hz 调为 6 Hz，ζ 保持 1，即该组 Kp 乘 36、Kd 乘 6；腕踝及躯尾参数不动。该候选撑过完整 5 s，末段根下沉最大 0.006675243377685547 m、倾角 0.006145917822720661 rad、平均地面支持力 706.3228682261795 N；四足持续承重、无禁止部位触地。仍按原判词判失败：只有 neck_pitch 的末段偏移超过 0.1 rad，最大 0.16672086715698242 rad，其余关节均在界内。

随后只将 neck_pitch 频率由 1 Hz 调为 2 Hz，ζ 保持 1，即该轴 Kp 乘 4、Kd 乘 2；保持上述腿部组及其它所有参数。最终候选正常退出 0、`completed=true`、`standing_verified`：

| 最后 1 s 指标 | 实测 |
|---|---:|
| 最大根下沉 | 0.006679117679595947 m |
| 最大机身倾角 | 0.00614033260537749 rad |
| 最大关节偏移 | 0.06092141941189766 rad |
| 最大根竖直速度绝对值 | 0.024116933345794678 m/s |
| 平均总地面支持力 | 706.3244258942295 N |
| lf/rf/rl/rr 最小地面法向力 | 210.8006 / 209.8499 / 120.4218 / 121.9635 N |

原身体位置/速度 targets 保持零，未加重力力矩前馈。真实动力学通过的是短静站，不是误差为零、力矩饱和已验证或动力学解耦。

同一数据中，根 XY 首末变化为 [6.9320e-5,1.2875e-4] m，末段最大水平速度 0.0023257687577439446 m/s；未另设水平滑移性能判据。最大关节速度/读回限速为 0.1559903919696808。最大重建 PD 请求/力矩上限达到 0.9922975540161133，出现在 0.12 s 的 chest_pitch，重建值 −79.38380432128906 N·m、上限 80 N·m。瞬态请求余量很小，后续抬落必须保留该读数及实际驱动力通道的适用边界；不凭短静站通过就称驱动预算充分，也不由重建量直接宣称实际饱和。

最终增益另在固定基座、无重力条件补四腿各自的 swing/abduct/twist/elbow 或 knee 组合及 neck_pitch 单轴，共五个受影响工况，覆盖实际改动的全部 17 个驱动；它们全部通过同一小幅判词。最大运动误差 0.0028802288670375705 rad，伸出停留末段误差 1.5132129192393928e-7 rad，返回末段误差 8.246824734214897e-8 rad，其它关节偏移 0.0028686048462986946 rad，全体 actor/FK 最大分量差 9.172955999225962e-7。两个测试的全部实际 Kp/Kd 读回逐项相等；腕踝与其它躯尾增益未变，不重跑原逐轴全集。无重力组合与有重力静站分别保留各自适用范围。

### 失败退出码修复

基线已落 `standing_failed` 报告且打印原因，原主函数仍因 app.close 提前结束而退出 0；这复现了跨入口事项的已知机制。修正为判词失败时先持久化、flush，再 `os._exit(1)`，不等 close 后再 sys.exit；异常分支仍保留栈和非零退出。相同参数和同样 0.24 s 物理失败重跑后退出 1；腿部组候选末段判词失败也退出 1，最终通过退出 0。跟踪入口的判词失败分支同样加防护；本轮没有额外造其物理失败，不能把静站的真跑对照写成两个入口都已全面覆盖。其余旧入口仍交跨入口事项清点，本轮不关闭该事项。

首次静站准备在 USD 布尔序列化形式检查处停止，尚未造环境；兼容 `0/false` 的规范化拼写后仍严格验证只新增一个 `jointEnabled` 属性，没有放宽实际层差异条件。所有历史失败产物保留。

## 证据引用

- 上游：`acceptance/records/2026-10-19-lizard2-spatial-inertia-repair.md`、`2026-10-19-lizard2-spatial-small-tracking.md`；落点：提交 `22523ae` 的 `rl_exp/tools/diagnose/palm_spatial_tracking.py`、`palm_spatial_standing.py`。该代码提交的仓库预提交闸门通过。
- 原增益组合报告：`rl_exp/out/lizard2_b_combined_tracking_20261019/report.json`，SHA256 `cb166161b05d66ff9456d9e14ebe269cc69d3e6c3b846755432464c8d9781573`；当次源码 `e5fcb458f217f05700f1f243b06a28f8ac11b3e5bb7f34718bfd26b6fd893516`。同目录逐腿文件含原始采样及实际实体快照。
- 基线失败报告：`rl_exp/out/lizard2_b_standing_20261019_run02/report.json`，SHA256 `de280fcdff2cbc23b2e22c8f81eeadaa8482b17834319afaf6e3618fb7e12573`；同条件退出码修复复读：`rl_exp/out/lizard2_b_standing_exitfix_20261019/report.json`。
- 腿部组候选：`rl_exp/out/lizard2_b_standing_legs6_20261019/report.json`；完整原始采样、实际接触路径与读回均在报告中。
- 最终静站：`rl_exp/out/lizard2_b_standing_neck2_20261019/report.json`，SHA256 `f415264793731a71091ed9e167edd6bce1cfe4ad615772b94c080cef579a20e2`；当次源码 `194fd3da8b65fab034c47185c89fca3e9eb15e44ee6c4ccbd56608e23cf55f2d`。
- 最终隔离配置：同目录 `standing_manifest.json`，SHA256 `5942253636b0f3b4006135bcec39c74711f9796afc2f1b47707199ad5f87908b`。同目录保留 USD/URDF/meshes 和源码；本机产物引用不承诺入仓。
- 最终增益跟踪回归：`rl_exp/out/lizard2_b_loaded_pd_regression_20261019/report.json`，SHA256 `002dee654521651070d3405aaddfbf469491d244ca59cb14e762d7264926f8fd`；当次及最终跟踪源码 `8d6f0d9f291fd2dd31b39d40f3f649bbc24f6c56f923277683a062dad412b9d9`；`tracking_manifest.json` SHA256 `6b79740b4e348ecd11b81285995bf00c6c160c0fb65ff67a65e516ad4cc3ce84`。
- 本轮关键报告、分段原始数据、配置、源码快照及静站 USD 的哈希索引：`rl_exp/out/lizard2_b_standing_neck2_20261019/evidence_index.json`，SHA256 `92067c1df34e5ab8921d060e75bf8b9aa5cd6f9cccb2d084ca51ef5b78049a51`。
- 跨入口事项：`work/active/exit-status-swallowed-by-app-close.md`；未将本轮局部修复当该事项整体关闭。

从仓根复读；输出目录必须不存在。去掉全部频率/载荷参数可复读原失败，预期非零退出：

```cmd
"E:\IsaacLab\env_isaaclab\Scripts\python.exe" -B rl_exp/tools/diagnose/palm_spatial_tracking.py --combined --inertia_report rl_exp/out/lizard2_b_inertia_repaired_20261019/report.json --out rl_exp/out/lizard2_combined_reproduce --viz none --device cuda:0
"E:\IsaacLab\env_isaaclab\Scripts\python.exe" -B rl_exp/tools/diagnose/palm_spatial_standing.py --tracking_report rl_exp/out/lizard2_b_combined_tracking_20261019/report.json --leg_frequency_hz 6 --neck_frequency_hz 2 --load_reference rl_exp/out/lizard2_b_standing_exitfix_20261019/report.json --neck_load_reference rl_exp/out/lizard2_b_standing_legs6_20261019/report.json --out rl_exp/out/lizard2_standing_reproduce --viz none --device cuda:0
"E:\IsaacLab\env_isaaclab\Scripts\python.exe" -B rl_exp/tools/diagnose/palm_spatial_tracking.py --combined --gain_reference rl_exp/out/lizard2_b_standing_neck2_20261019/report.json --inertia_report rl_exp/out/lizard2_b_inertia_repaired_20261019/report.json --out rl_exp/out/lizard2_loaded_pd_reproduce --viz none --device cuda:0
```

## 未覆盖边界

尚未验证单腿抬落、整段新 q(c) 的时间映射及承重直行、转向/恢复、实际力矩或有效限速边界，也未证明尾部不拖住行进。静站支持力来自具名地面接触，但未做摩擦、载荷或初始姿态范围扫描，不作稳定域结论。上游惯量转换来源、正式导出接线、其它真实消费者、C 协同、D/S5 判据及独立审核继续在办；本轮不采用、不训练、不关闭总项或专项。
