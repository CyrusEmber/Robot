# lizard2 恢复模型限位与 PD 验证交接（2026-10-14）

## 适用范围

用户要求 compact 前保留交接记录。本轮只核对既有文件、日志、报告与哈希，不运行新仿真、不继续标定。执行计划唯一归 `work/active/lizard2-restored-limits-pd-validation.md`；总项为 `work/active/lizard2-body-drive-candidate.md`。既有问题基线见 `acceptance/records/2026-10-13-lizard2-restored-limits-pd-open-issues.md`；本记录补后续进展，不修改历史失败读数。

用户已选择“前提通过后继续动作标定”。但低速直行、转向与恢复的工程包线尚未确认：上一问的低速最小包线与较宽工程包线均未获选择，不能当批准配置。用户此前明确不使用 subagent，后续执行者直接处理。正式资产、reward、冻结配方和训练保持不变。

## 验收条件

- 本记录是施工交接，不是新上下文审核，不表示步骤 1–4 全部完成；事项维持 `in_progress`。
- 先落实代码归属、版本和完整输入绑定；本机报告存在不等于干净提交可复现。
- 相同根姿态、实际关节状态、actor/质心 frame 与物理时点对应后再比较；真实负例须非零退出且不产生成功报告。
- 归一化惯量和具名连接过滤只存在独立运行场景，未写回资产。完成对应最终正反例与资产验证后才能进入动作/PD 结论。

## 结果

### 步骤状态及最先续办动作

| 步骤 | 当前落点 | 仍需执行 |
|---|---|---|
| 1 输入与失败判定 | 新验证入口有输入/代码哈希、完整日志及非零退出分支 | 代码尚未提交，整理归属后落版本；当前最终代码再跑成功/失败各一例，确认报告身份与 completed；将入口证据交退出码事项 |
| 2 中立位置与坐标 | 初始化已运动状态误比零位的根因已定位；显式零位、实际 q 的运动快照与三类负例已跑 | 固定最终代码复验；补 Blender→URDF→USD 的全链坐标/网格核对，解释误差预算；不能仅凭运行时 FK 宣布全部资产前提通过 |
| 3 质量与惯量 | 已验证主惯量循环方向错配；URDF 同张量身份主轴对照恢复一致 | 修复应落隔离转换/资产责任层，尚未落地；同姿态、约束下复验逐 link 与关节矩阵，补运动姿态和破坏测试；不修改 IsaacLab fork 或正式资产 |
| 4 连接区碰撞 | 六对跨无网格短轴连接过滤后，所测接触对读数归零；有真实跨腿接触反例 | 当前六对最终版本尚缺同条件跨腿负例复验与过滤精确读回；补合法连接几何理由、其它相交未知边界，不把净力或一物理步当完整碰撞域证明 |
| 5 动作能力与限位 | 原宽范围扫描反例仍有效 | 先确认工程速度/转向/恢复包线，再验证脚位置、掌面与肢段姿态及组合碰撞；机械范围、策略目标范围、阶段约束分开，不拍定角度 |
| 6 PD 与行为复验 | 旧三档 PD 报告仅历史诊断，最终参数未定 | 1–4 前提通过且 5 有可行目标后再静站/摆腿/转向/受扰恢复；触边检验有效限速，结合实际跟踪余量回验范围 |

### 2：原“运行时位置不一致”主要是检查时序错误

未过滤场景 `sim.reset()` 后已发生初始化运动。`coordinates_unfiltered_v3.json` 的首快照最大关节角约 `0.221134692 rad`，根 quaternion 也非 identity；旧方法直接减 base 平移后与 URDF 零位比较，最大位置差约 `0.106536544 m`。同一快照按实际根旋转与实际 q 构造 FK，最大残差约 `1.088288190e-6 m`。

显式写 root pose/velocity、joint position/velocity，刷新缓存但不推进物理步后，关节零位读回为 0。随后写全关节 `0.03 rad` 并检查，再推进一物理步按实际 q 检查；未过滤完整报告最大位置残差 `1.382232314e-6 m`、旋转矩阵 Frobenius 残差 `1.333522283e-6`。这解除的是旧检查误比，不证明完整网格、驱动或步态一致性。

真实 USD pivot 改 `0.01 m`、实际旋转轴改错、FK 使用错误读取关节状态三例都拒绝 `lf_shoulder_abduct/lf_elbow/lf_wrist`；旧零位检查对照也真实失败。失败均退出 1、无对应成功 JSON。成功坐标例退出 0。预算在实现中按小数输出精度、float32、链深及世界尺度计算；这是工程算术预算，尚须审核其推导，不能用它替代机械公差。

### 3：主惯量表示方向差异已解释，但未修入隔离资产

原 URDF 对角张量通过 USD 主轴排序/旋转表示后，在部分循环置换 link 上实际方向不同。原模型质量、质心和惯量特征值接近并不证明惯量张量朝向一致。

`inertia_basis_verified.json` 验证全部 link：USD 正向 `R D R^T` 对应运行时原始张量，最大元素差 `3.273039419e-7 kg·m²`；逆向 `R^T D R` 对应 URDF 张量，最大元素差 `7.784720757e-8 kg·m²`。肘膝与 tail1 的非自逆循环置换暴露差异；不要再次把完整张量当主惯量对角表重复旋转。

在独立运行场景中显式用 URDF 对角张量与 identity 主轴建立对照，`inertia_normalized_verified.json` 最大逐 link 张量差 `8.774948124e-8 kg·m²`，实际质量矩阵关节对角与同姿态锁定下游平行轴投影最大绝对差 `2.051542461e-5 kg·m²`，既有实现的相对/绝对预算断言通过。该操作未保存进磁盘 USD，当前资产仍是原错配表示；原 PD 数据因此不得用于最终选值。质量仍是表面积分配、惯量仍是 AABB 箱体近似，不是实物辨识。

### 4：由 14 对过滤收窄到六对，最终负例仍需补

运行时直接 parent/child 对在中立接触对读取中为零，不必再额外列入过滤。最终六对均为已测中立连接区相交、树距离 2、祖先相连、中间 link 无 collider：

- `tail2_pitch ↔ tail1_pitch`
- `tail1_pitch ↔ base_link`
- `base_link ↔ rr_hip_abduct`
- `base_link ↔ rl_hip_abduct`
- `rf_shoulder_abduct ↔ chest_pitch`
- `lf_shoulder_abduct ↔ chest_pitch`

尾 yaw/pitch pivot 相隔约 5 mm，不能要求两个轴完全共点再误拒合法双轴连接。肩髋双轴共点；需要保留实际几何和接触点理由，而非只按树距离过滤。

`pair_unfiltered.json` 同条件真实接触对包含尾根约 `82.186 kN` 及肩髋/尾段大作用力；`pair_six_final.json` 所测接触对最大读数为 0 N，全身 self-collision 仍开。这是一物理步的局部对照，不是完整周期通过。

此前 `pair_cross_leg_verified.json` 在胸 yaw=`+0.6 rad` 下，`lf_wrist ↔ rl_ankle` 仍有约 `513–538 N` 接触，证明当时 14 对过滤未关闭全身碰撞。**该报告用的是旧 14 对清单，不是当前六对最终版本**；不能引用它作为六对最终负例已经复验。最初误选 `lf_elbow ↔ rl_ankle` 的负例无接触，仅是错误探测对，不可引用为通过。

### 在办代码与版本归属

记录时 HEAD=`fa48465`。以下文件均未完成本项代码版本落地；尤其新脚本仍为 untracked，compact 不会删除磁盘文件，但换机/clean checkout 不包含它。

| 路径 | 记录时 SHA256 |
|---|---|
| `rl_exp/tools/diagnose/palm_pd_probe.py` | `a1a1112f3ca557a69bbddf9f4e0b54fd8967f78fe89c614180c36144753356d2` |
| `rl_exp/blender/scripts/generate_urdf.py` | `b6f67578e493a942ed15632eabecc7b2348fde22bb9d54c2f3d33dc9db347bf8` |
| `rl_exp/blender/scripts/lizard2_stance_candidate.py` | `1552583d6044c36010f4499050dabdc11b34ba5d326bd34827cc81cd900fd80b` |
| `rl_exp/tools/verify/check_leg_reachability.py` | `5ce3c54c0712b40edd56803b1aa854a292f8a495de16753c696046632b60efb2` |
| `rl_exp/tasks/joint_names.py` | `262030343b8d379388e8011892673ddff0e6df024c2e464a0fb2239f78f980e5` |

新脚本只允许 coordinates/inertia/collision 三种前提验证模式；旧 PD 主循环已从在办入口移除，尚无最终动作标定实现。退出分支复用现有 `gait_probe` 的打印栈、flush、`os._exit(1)`，成功分支保留 `app.close()`。部分 App 启动/顶层导入还在 main 的异常处理外，不能称所有入口异常都已覆盖。

生成器的 palm diagnostic 导出、源绑定、完整骨树核对与限位精度，以及限位脚本的 `--blend/--boundary_samples` 属本会话在办改动；同文件还有其它任务的 split 接线、哈希复用等修改。`check_leg_reachability.py` 与 `joint_names.py` 有其它接线工作，不能整文件盲目提交。先分清片段及依赖，禁止 `git add -A`，本轮只提交交接文档，不提交这些代码。

## 证据引用

### 唯一输入

- Blender：`rl_exp/blender/lizard2_hindlimb_restored/sample_neutral.blend`；SHA256 `2caf7e17fb327c6fb424ea8eaf7fbedc7e7766a308d70c0cdc93bddd52f33560`。
- 原宽扫描：`rl_exp/blender/lizard2_palm_limit_probe_restored_20261013/measurements.json`；细扫：`rl_exp/blender/lizard2_palm_limit_probe_restored_boundary_20261013/measurements.json`。
- 隔离目录：`rl_exp/out/lizard2_palm_pd_restored_20261013/`。
- 同目录 URDF：`lizard2_palm_diagnostic.urdf`；SHA256 `ec247886a6512e8cc70ba86261970eed8f205e92de98a70eba1dc577f3ce7cc2`。
- 同目录 USD：`lizard2_palm_diagnostic.usda`；SHA256 `d6d7d8afbca1c2a44b2899dded797a7a1a2cc87e1489df5d0b8cd46bc051d661`。

### 报告身份（同隔离目录，各有同 stem `.log`）

| 报告 | SHA256 |
|---|---|
| `coordinates_unfiltered_v3.json` | `289446268e5caa6be4974bc1dc691c2ca83ee786d91ec53715f437b717261ca1` |
| `coordinates_bound_v4.json` | `94d74d65f483a26fc982d6ac2be86238930fd6acc658a444cfbab286b76f5c27` |
| `inertia_basis_verified.json` | `c3cdf17e1fb1d9e26ff2e26cc6009d873cce0185022f561cba6ade843401d4e3` |
| `inertia_normalized_verified.json` | `8c619f760bd1d4474f9c672bb3a14d5087a07e550e2689515b256fe255e69de7` |
| `pair_unfiltered.json` | `4e3da03d0c9009086e4cd1a6a7ffaf6a3f20e6062d4864b8f630883e2859de3a` |
| `pair_six_final.json` | `529ae7cce2c96eecdc10b85e00cf2bbd8475f736884db907fe9c9cdeb0f7beba` |
| `pair_cross_leg_verified.json`（旧14对） | `87421e44676eac5ec2dec0c24d4bdf9aaa065bc35b223c5b3dfdfbc8e75e62d0` |

坐标早期报告没有 `identity.completed`，应结合日志的完成标记与其代码哈希判读，不能伪称已有最终 completed 契约；惯量及接触报告有 `identity.completed=true`。最后在办代码已变更，多数历史报告不是当前代码生成，恢复后必须选新输出名称复验，不覆盖历史。

失败日志：同目录 `legacy_zero_negative.log`、`pivot_negative.log`、`axis_negative.log`、`state_negative.log`、`exception_exit.log`；对应失败没有成功 JSON，异常例拟输出名为 `exception_must_not_exist.json`。原时序失败见 `pd_unfiltered_final.log`。所有产物只在本机，文档记录不承诺原始文件已进仓。

### 续办命令形状

使用现存隔离输入、不传 `--convert`，输出选新的同目录文件。先核代码及输入哈希；当前入口是未提交在办代码，不承诺历史结果逐字节重复。

```cmd
"E:\IsaacLab\env_isaaclab\Scripts\python.exe" -B -u rl_exp/tools/diagnose/palm_pd_probe.py --urdf E:/Robot/rl_exp/out/lizard2_palm_pd_restored_20261013/lizard2_palm_diagnostic.urdf --probe_report E:/Robot/rl_exp/blender/lizard2_palm_limit_probe_restored_20261013/measurements.json --output E:/Robot/rl_exp/out/lizard2_palm_pd_restored_20261013/handoff_coordinate_recheck.json --coordinates_only --viz none
```

同一入口切换模式：

- 坐标旧逻辑回归：加 `--legacy_zero_check`（未过滤）应失败；三个负例分别加 `--inject_error pivot/axis/state`，选新输出。
- 异常退出：`--inject_error exception`；期望栈可见、状态 1、无成功报告。
- 原惯量机制：`--inertia_only --filter_connections`；归一化对照再加 `--normalize_inertia`，各自新输出。
- 连接区对照：`--collision_only --normalize_inertia`，有/无 `--filter_connections` 分开新输出。
- 六对最终跨腿负例：`--collision_only --normalize_inertia --filter_connections --collision_negative`；明确核对 `lf_wrist ↔ rl_ankle` 实际接触、六对精确清单与 self-collision 状态，不能只看退出 0。

## 未覆盖边界

步骤 1 的干净代码版本、全链资产坐标验证、隔离惯量修复落地、六对最终碰撞负例、目标工程包线、动作能力/连续组合碰撞域、最终 PD/力矩/速度边界、GUI 终验和独立审核未完成。未扩大旧正式 `velocity_limit` 的适用结论；隔离 `velocity_limit_sim` 读回不代表触边行为已验。

本次未跑新仿真。记录内 12 个代码/报告表格哈希逐项复查一致；输入 Blender/URDF/USD 哈希复查未变。提交前 `check_suite_banners`、`framework_pin_check --strict --self-test`、`check_dr_parity --strict`、`check_version_docs`、`check_work_docs`、`check_obs_protocol --live` 与 `git diff --check` 通过。保留框架 dirty、历史 tag 与正式配方限速警告；这些检查不是实验验收。

事项保留全部六步，未置 pending_review、未关闭。交接保存不等于代码或动力学交付完成；优先避免把运行场景修订、不同代码版本和旧14对反例拼成同一份“通过”证据。
