# 腿链几何探测复用指南

用于增轴、改轴、改骨长或改掌形后的几何诊断：先选择已有能力，只补变化影响的覆盖，不另造一套 FK、碰撞或扫描器。本文管复用方法与入口；具体构型、在办动作和结果分别取家族文档、work 与验收记录，不在这里复制读数或参数。

## 先区分三种复用

- **实现复用**：坐标变换、网格判定、边界括号加密等算法可复用，但必须满足输入契约。
- **证据沿用**：输入几何、轴、命名、方法、过滤、配置和覆盖条件仍兼容时，原证据保留原结论；变化只重验受影响部分。文件日期或脚本哈希变化不自动要求全量重跑，须追到实际行为差异。
- **对照复用**：旧机构、旧平掌任务或固定其它轴切片可作为对照，不能把其边界数字迁入新构型，也不能把切片读数扩成完整安全域。

“新轴置零”只证明特定对照姿态或轨迹保留旧运动；不能代替新轴非零、组合运动及动力学验证。

## 入口选择

路径相对仓根；调用前读目标函数的 docstring 与输入校验。

| 需要什么 | 复用入口 | 适用边界 |
|---|---|---|
| 从实际树取关节、根坐标系 FK、骨段夹角 | `rl_exp/tools/verify/check_leg_reachability.py`：`chain_joint_names`、`load_chain`、`chain_frames`、`straight_hfe`、`thigh_shank_angle` | 显式传 naming；共中心承载枢轴不是骨段。`straight_hfe` 的平面角不证明非平面骨段可以完全共线；该文件不是完整可达域扫描器 |
| 实际五轴链端、掌网格、保存的 Blender 快照对照及增量静态切片 | `rl_exp/tools/diagnose/palm_spatial_probe.py`：`Leg`、`check_blender`、`--static_slices` | `Leg` 可复用树、网格和姿态读点；向量须完整对应 `names`。静态模式按具名 twist／肘膝／腕踝取候选端点和零位切片、其它关节零，输出网格地面读数与相交反例，不给安全域判词；`--self_check` 校验口径。`solve` 和默认 CLI 是历史固定参考点／水平掌回归任务，不是自然步态求解入口；掌参考点不是实时材料接触点 |
| 网格距离、表面相交、包含与逐姿态碰撞 | `rl_exp/tools/diagnose/palm_motion_boundaries.py`：`surface_distance`、`surface_crosses`、`inside`、`Collision`、`validate_geometry` | 网格须满足闭合与绕序检查；先验证 FK 支持的 joint rpy、碰撞变换和缩放。`Collision` 继承现有批准对和直接连接排除，须核对新树下实际过滤集合；它不检查地面，也不证明连续域安全 |
| 单关节扫描和失败转折加密 | `rl_exp/tools/diagnose/palm_motion_boundaries.py`：`hinge_boundaries` | 复用采样、逐姿态检查与转折括号方法；现函数按旧位次取肘膝，不可直接喂新链。先按具名角色适配，再声明其它轴固定上下文；未采到转折不证明区间内没有窄失败带 |
| 旧机构的肘—腕耦合切片、平面解析 | `rl_exp/tools/diagnose/palm_recovery_constraints.py`：`coupled_map`、`plane_parameters` | 切片方法可参考；解析要求首轴竖直、其余轴平行。新增长轴 twist 不满足此前提，禁止绕过断言或将旧解析结论推广到新链 |
| 旧自碰撞粗筛与失败姿态 | `rl_exp/tools/verify/check_self_collision.py`：`sweep_poses`、`confirm` | 凸包／网格方法局限见脚本；`sweep_poses` 的 knee 与组合角色仍按旧位次选择。支持新 naming 不等于扫描角色已适配；不能仅换名字运行后称新轴覆盖完整 |

历史四轴 `rl_exp/tools/diagnose/palm_gait_kinematics.py:Leg` 核对真实树并拒绝额外轴。保留它作旧样本对照，不为接新资产而关闭拒错，也不靠补数组长度代替角色、坐标系和任务迁移。

## 最小增量探测

1. **绑定输入**：明确源／候选 URDF、网格、轴／限位、代码、命名与地面／根姿态。摘要复用 `rl_exp/tools/runrecord/binding.py`。先核已有报告身份与覆盖，再决定哪些证据直接沿用；若需新输出，使用隔离的新目录，不覆盖历史产物。
2. **保留对照**：使用相同其余关节、根姿态及判定方法，对比新轴零位与旧机构；无几何或方法变化的尺寸与中立读数不无差别重测。
3. **只扩变化方向**：新增 twist 时，补其非零上下文中的肘膝／腕踝切片，明确 swing、abduct、根姿态和其它腿状态。前后肢分别取真实树，左右按实际镜像验证，不默认同号或同范围；只扫单轴零上下文会漏耦合变化。
4. **分开记录判定**：实体相交、指定间隙不足、反曲、掌面有向状态、最低碰撞顶点地面间隙分别报告。地面检查需显式摆位并变换实际网格，不能以掌中心位置代替；倾掌本身不是失败，滚动与材料接触滑移不能仅由静态几何判定。
5. **保存反例与覆盖**：保留完整具名姿态、固定上下文、网格对、地面、采样间隔与转折括号。报告说明未采区域、共用 FK 假设及过滤范围；离散通过不等于连续轨迹、全维安全域或最终关节限位。
6. **再提出动作输入**：由上述读数提出步长、抬脚候选及依据，交相位目标决策；不继承旧周期、占位限速或 PD。周期与承重能力须另由动态标定支撑。

输入不被方法支持、身份不明或具名角色错配时停止该读点，不换旧资产、旧名表或扩大过滤掩盖问题。新增拒错／行为修复必须用真实失败对照验证；单纯声明一致不能作为行为能力证明。

## 局部转折复读

已有静态切片出现相邻分离／相交样点时，使用 `palm_spatial_probe.py --refine_slices`，显式提供 `--build_report`、`--source_report`、`--angle_resolution` 和全新 `--output_dir`。当前入口定位右后腿机身／踝掌目标对；复用源网格的相邻异态边，不替代通用全域扫描。校验源候选、固定姿态与过滤集合，重新检查完整碰撞对；仅当前 probe 新增模式的摘要允许与源不同，其余依赖变化须先解释，不能悄悄复用旧判词。

二分只收缩两端异态括号；同态边内部窄带未覆盖，非单调边可能存在其它转折。`--angle_resolution` 只约束角宽，不代表机械精度、安全余量或已批准关节限位。报告保留来源角网格、两端完整姿态、网格对及地面读数，结果仍归验收记录。

## 局部路径复读

使用 `palm_spatial_probe.py --local_path --build_report <绑定输入> --output_dir <新隔离目录>` 探测两腿中立附近的闭合路径；数值口径与预算集中于模式配置并写入报告。复用完整五轴、网格最低特征、全体碰撞对和源身份，不调用历史平掌 `solve`。任务达标即停，实际残差调用包含有限差分；端点与关节线性插值中点分别检查。中点偏离接触约束是路径表示的缺口，不能自动归因于机构不可达；失败保留阶段，不放宽容差、跳过中点或声称整条腿能力失败。

`completed_local_loop` 仅指该探索路径的离散点／中点及完整关节分支回归检查，不代表自然步态、连续域、世界无滑移、时间映射或动力学合格。路径失败时先核任务残差、预算停止、几何和分支插值，复用已采姿态定位责任层。

## 自检与结果路由

从仓根运行。先用 `python -B ablation_harness/host_paths.py --python` 取得配置解释器，再以该解释器运行以下入口；这些是方法自检，不会替候选做完整扫描：

```text
<配置解释器> -B rl_exp/tools/diagnose/palm_spatial_probe.py --self_check
<配置解释器> -B rl_exp/tools/verify/check_leg_reachability.py --self-check
<配置解释器> -B rl_exp/tools/verify/check_leg_reachability.py --break-test
<配置解释器> -B rl_exp/tools/diagnose/palm_motion_boundaries.py --self_check
<配置解释器> -B rl_exp/tools/verify/test_baseline_contract.py --binding-only
```

结果与可复读命令唯一归 `acceptance/records/`，work 只留指针和未完路由。不把本指南当候选验收记录、已实现扫描承诺或冻结参数。

本项目实例入口：`work/active/lizard2-palm-spatial-reconfiguration.md`；构型事实取 `rl_exp/versions/lizard2/FAMILY.md`，旧切片、试作和修复证据取该事项及限位 PD 专项的 evidence 指针。
