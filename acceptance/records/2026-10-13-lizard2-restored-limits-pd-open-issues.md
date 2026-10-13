# lizard2 恢复后肢候选：限位与 PD 当前问题（2026-10-13）

## 适用范围

用户要求先记录当前问题。本轮仅落问题记录，不继续执行标定。本记录对应恢复原后肢尺寸的当前模型，不对应已撤销的放大后肢或旧正式机体。所属事项：`work/active/lizard2-body-drive-candidate.md`。本轮检查由执行者直接完成，未委托。

输入：`rl_exp/blender/lizard2_hindlimb_restored/sample_neutral.blend`，SHA256 `2caf7e17fb327c6fb424ea8eaf7fbedc7e7766a308d70c0cdc93bddd52f33560`；记录时复查源哈希未变。模型身份及恢复几何验收只取 `acceptance/records/2026-10-13-lizard2-hindlimb-restored.md`。

执行基线为 `629aea7` 加未提交工作树改动。新增 `rl_exp/tools/diagnose/palm_pd_probe.py` 与原 Blender 生成器修改仍属在办代码；本次只提交问题记录与事项路由，不宣称干净提交可复现全部实验。原始 JSON、日志和隔离资产仅在本机。

## 验收条件

- 区分真实模型几何、导出声明、运行时读回与动力学行为；进程退出 0 不等于检查通过。
- 区分机械硬限位、策略位置目标范围、力矩与速度边界。策略范围须覆盖目标步态并留实测跟踪/恢复余量，不能直接取扫描最大角度或拍定统一余量。
- 具名连接区过滤对照与未过滤原候选分开；不关闭全身自碰撞、不用过滤后的静站证明原候选安全。
- 导出到运行时的中立位、pivot、轴、网格和质量惯量一致性未成立前，PD 读数只作诊断，不定稿、不采用、不训练。

## 结果

**当前结论：限位重测与 PD 诊断已执行，但正式机械限位、策略目标范围和最终 PD 均未确定。最新运行时位置对照断言失败，是恢复施工时的优先阻断项。**

### 1. 限位组合仍有明确几何反例

绑定当前恢复模型，原宽范围扫描 169 姿态；另按每轴正负方向各 40 档细扫，共 2249 姿态。四肢实际 Blender 转动与独立刚体变换最大顶点残差为 `1.9120576403682606e-6 m`，仅证明所测运动构造一致，不证明导出或完整活动域安全。

- 原宽范围仍有 16 个翻掌姿态、12 个树距离大于 2 的远距表面交叉姿态。中立位交叉是连接区，不应把所有交叉都叫远距碰撞。
- 细扫首次胸 yaw 跨腿表面交叉出现在正负 `0.54 rad`；相邻的 `0.525 rad` 采样未发现该类交叉。这是采样区间，不是精确机械边界，更不是可直接采用的限位。
- 肘/膝伸直位置约为前肢 `−80.1576°`、后肢 `−80.1648°`。原 `±1.2 rad` 范围未跨伸直侧，但跟踪与受扰余量未验证。
- 三段尾 pitch 的第一档负向 `−0.0125 rad` 已使实体进入固定地面。该反例约束当前贴地动作阶段，不足以把机械限位统一改成单侧。
- 单关节细扫不代表组合安全；未完成低速直行、转向及受扰恢复的可行轨迹，不能据此确定策略范围。原先提出的收窄角度没有作为已批准实施值写入正式配置。

### 2. 未过滤连接区产生大冲量，PD 标定被污染

隔离 URDF/USD 包含 27 link、26 活动关节，关节球仍排除于碰撞；实体小腿、掌体与其它碰撞网格保留。`lizard2_palm_contract` 只读保护未解除，另建诊断导出目标，不代表 A/P3 验收通过。

按 URDF 实际足底确定根初高的未过滤诊断，三档增益均在第一物理步触发“接触峰值超过 5 倍体重”停止条件；base、胸、尾根和肩上段等出现大作用力，最大量级约 `73 kN`。不能通过继续加大 PD 掩盖这些冲量。

仅在独立运行场景中，为中立已相交、祖先相连且树距离不超过 2、中间 link 无碰撞的 14 个具名连接对建立过滤对照；全身自碰撞仍开，未过滤跨腿对。该对照支持连接区过滤是关键因素，但不能证明所有物理碰撞归属正确，也没有采用到正式资产。

### 3. 三档 PD 小幅测试跑完，但性能与力矩代价未定稿

具名连接过滤对照下，每档 5800 物理步：3 秒静站，加 26 个关节逐一 `±0.05 rad`、1 秒正弦目标，共 29 秒。阻尼使用实际 PhysX 关节空间质量矩阵对角投影调整；PD、角度、力矩和 `velocity_limit_sim` 有运行时读回。没有策略、reward 改动或训练。

| Kp 相对初值 | 全步最大关节目标误差 [rad] | PD 请求超过力矩边界的关节-步数 | 本轮停止条件 |
|---|---:|---:|---|
| 0.5 | 0.157274 | 46 | 未触发 |
| 1.0 | 0.096779 | 58 | 未触发 |
| 2.0 | 0.069033 | 82 | 未触发 |

加大增益改善部分静态偏移和跟踪，却增加超力矩请求，不能把 2 倍档直接宣布为最终 PD。请求量是 `Kp*(target-q)-Kd*qd` 重建，不是实际求解器输出力矩；表中计数不是实测力矩饱和次数。小幅单轴动作也不是正常步态验证。

### 4. 新增中立运行时位置对照失败，既有 PD 结论须降级

最后一次未过滤复验日志 `pd_unfiltered_final.log` 命中 `palm_pd_probe.py` 中“运行时 body 相对 base 位置等于 URDF 零位累加位置”的 `torch.allclose(..., atol=1e-5)` 断言，未生成 `pd_unfiltered_final.json`。该检查晚于前述已完成的 PD 对照，因此前述运行没有证明导出与运行时零位一致。

根因尚未定位：可能涉及初始化已发生物理步、根/link frame 解释、数据更新时间或导出/导入差异，不能先认定仅是数值容差，也不能先认定资产确实漂移。应定位逐 body 残差和读取时点，再判明重跑范围；禁止放宽断言充当通过。

此外，URDF 下游锁定惯量投影与运行时质量矩阵对角存在最高约 `2.98%` 差异。曾尝试用实时主惯量姿态重建仍未通过；原因未解决。后续改为明确记录差异并使用实际质量矩阵选诊断阻尼，不等于一致性问题已修复。质量仍是表面积分配、惯量仍是 AABB 箱体近似，不是实际物理辨识。

### 5. 执行记录与机制缺口

- 首轮直接拿 Blender 世界地面高度作 URDF 根初高，混淆世界坐标与相对根坐标，已改为读取 URDF 碰撞网格最低点；旧 `pd_measurements.json` 只作失败历史，不用作承重通过。
- 转换器实际嵌套输出目录与最初路径断言不符；已在隔离树内拍平并归位，正式资产未动。
- Isaac Sim 关闭过程可能使脚本异常仍表现为命令退出 0：最后位置断言失败时命令也返回 0。必须同时核对日志、报告是否生成及报告内容；脚本退出传播尚未修复。
- 隔离执行器通过 `velocity_limit_sim` 写入并读回速度边界；正式配方原 `velocity_limit` 对 implicit 被忽略的问题仍未修复。未做触边激励和有/无限速行为对照，不宣称有效限速能力已完成验收。

## 证据引用

全部路径相对仓根；本机产物不进仓。

- 原宽范围报告：`rl_exp/blender/lizard2_palm_limit_probe_restored_20261013/measurements.json`。
- 细扫报告：`rl_exp/blender/lizard2_palm_limit_probe_restored_boundary_20261013/measurements.json`。
- 隔离资产与报告目录：`rl_exp/out/lizard2_palm_pd_restored_20261013/`；URDF SHA256 `ec247886a6512e8cc70ba86261970eed8f205e92de98a70eba1dc577f3ce7cc2`，USD SHA256 `d6d7d8afbca1c2a44b2899dded797a7a1a2cc87e1489df5d0b8cd46bc051d661`。
- 未过滤冲量报告：同目录 `pd_ground_bound.json`；较早过滤对照：`pd_connection_control.json`；全关节对照：`pd_all_joints_verified.json`，实际运行日志 `pd_final.log`。
- 惯量不一致诊断：同目录 `pd_inertia_details.log`、`pd_inertia_state.log`、`pd_live_inertia.log`；最新位置失败：`pd_unfiltered_final.log`，对应 JSON 不存在。

细扫复读命令，输出须使用新的独立同级目录：

```cmd
"E:\SteamLibrary\steamapps\common\Blender\blender.exe" --background --factory-startup --python-exit-code 1 --python rl_exp/blender/scripts/lizard2_stance_candidate.py -- --limit_probe --blend E:/Robot/rl_exp/blender/lizard2_hindlimb_restored/sample_neutral.blend --boundary_samples 40 --output_dir rl_exp/blender/lizard2_palm_limit_probe_restored_boundary_recheck
```

当前在办脚本的物理复读形状如下。当前代码带新增中立位置断言，复读可能停于该断言，不能承诺重新生成前述完成报告；先处理该阻断，不覆盖历史报告。

```cmd
"E:\IsaacLab\env_isaaclab\Scripts\python.exe" -B -u rl_exp/tools/diagnose/palm_pd_probe.py --urdf E:/Robot/rl_exp/out/lizard2_palm_pd_restored_20261013/lizard2_palm_diagnostic.urdf --probe_report E:/Robot/rl_exp/blender/lizard2_palm_limit_probe_restored_20261013/measurements.json --output E:/Robot/rl_exp/out/lizard2_palm_pd_restored_20261013/pd_recheck.json --filter_connections --viz none
```

旧放大源配新报告的真实导出负例退出 1，命中 `palm diagnostic source/report binding mismatch`，错源输出目录未创建。代码编译及当时 `git diff --check` 通过，不代表动力学或资产一致性通过。

问题记录落地时，`check_suite_banners`、`framework_pin_check --strict --self-test`、`check_dr_parity --strict`、`check_version_docs`、`check_work_docs`、`check_obs_protocol --live` 均通过。保留框架未提交改动、历史 tag 与正式配方限速警告；这些检查不证明本记录中的失败已修复。

## 未覆盖边界

未完成中立位置失败定位、导入惯量差异解释、退出码传播、完整步态/转向/恢复轨迹、连续组合碰撞域、真实力矩测量、速度触边行为验证、GUI 动作终验或新上下文审核。有限 BVH 表面交叉扫描可能漏纯包含；净接触力不能单独识别碰撞对。

最大隐藏风险是将“过滤连接区后能站住”的诊断资产，误当原模型及正式配方通过；另一风险是把过程退出 0 当实验绿灯。上述前提未解决，不定稿限位/PD，不将本项置 pending_review，不改正式资产或冻结配方。
