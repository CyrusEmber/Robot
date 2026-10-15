# 肩髋三轴增量静态切片

## 适用范围

用户要求继续按复用指南执行，并确认先做两腿共 270 个姿态的小规模增量切片。复用实际五轴 `Leg`、具名骨段读点、已有网格碰撞和输入绑定；未重建 FK 或碰撞算法。关联肩髋重构事项及限位 PD 专项。本记录不是自然步态、完整安全域、动力学或关闭验收。

此前提议沿用旧步长、抬脚与周期尺度被用户质疑，执行者撤回推荐。本次不使用旧步长／周期／速度／安全余量作为目标，也不改机体、限位或驱动。

## 验收条件

- 从同一实际候选及完整具名链取角域；每腿分别采 twist 端点／零位、肘膝和腕踝的离散组合，其余可动关节保持零。
- 固定根朝向，以四掌中立碰撞网格最低顶点设共享根高度；逐姿态记录实际网格地面间隙，不以掌中心代替。
- 实体相交／包含、正间隙、零间隙非实体判词、掌面有向读数分别保留。倾掌本身不是失败，不用旧间隙不足标记冒称实体相交。
- 输入、代码、实际检查／排除网格对与完整姿态可复读；错误链、漏 twist、错误地面变换和错误碰撞口径必须被自检拒绝。

## 结果

### 实现与输入

现有 `rl_exp/tools/diagnose/palm_spatial_probe.py` 增加 `--static_slices` 和不依赖候选的 `--self_check`；历史固定参考点回归模式保持不变。新模式按具名角色读链，不沿用旧 `hinge_boundaries` 或 `sweep_poses` 的肘膝位次。生成前核对自包含候选文件、URDF 网格引用、几何输入契约、两套 FK 及保存的 Blender 快照。

输入为 `rl_exp/out/lizard2_palm_spatial_20261014/checkpoint_v3/build.json` 指向的候选集合；38 个候选文件绑定成立。原始源输入摘要只保留来源，不要求未消费的源文件为新切片重新计算。实际轴／限位、build 摘要及本次直接依赖代码摘要均在新报告 `identity` 中。

固定上下文：全部 30 个可动关节默认零；每次只改变左前 `lf` 或右后 `rr` 的三个具名角色。根旋转为单位阵，统一上移 0.602799 m；四掌中立最低顶点用于摆位，不逐姿态调整体高。

每腿 twist 取 -0.5235987755982988、0、+0.5235987755982988 rad；肘膝在 [-1.2, 1.2] rad 取 9 点；腕踝在 [-0.523598776, 0.523598776] rad 取 5 点，共 270 个姿态。这些范围来自候选诊断 URDF，不是获准解剖范围或策略限位。

保留 139 对实际检查网格、14 对实际排除网格（8 对直接连接、6 对已有批准连接几何迁移）。不额外过滤所发现的相交。精检触发为 1e-9 m，仅用于避免 `clearance=0` 时 AABB 分支跳过重叠；`safety_clearance_m` 为 null。正间隙中可能有 AABB 保守下界，不把它们称为精确表面距离。

### 离散结果

| 腿 | twist [rad] | 实体相交姿态 | 掌最低顶点 z 范围 [m] |
|---|---:|---:|---:|
| lf | -0.523599 | 3 | 0.053893～0.319907 |
| lf | 0 | 3 | -0.087778～0.273447 |
| lf | +0.523599 | 3 | -0.123037～0.206214 |
| rr | -0.523599 | 0 | -0.120216～0.188782 |
| rr | 0 | 0 | -0.087770～0.273475 |
| rr | +0.523599 | 4 | 0.056244～0.303324 |

13 个姿态有实体相交：

- 前腿 9 个均为 `lf_shoulder_twist ↔ lf_wrist`，肘角 1.2 rad、腕角 0／0.261799388／0.523598776 rad，在三档 twist 均出现。在本次三档 twist 均出现，且零位对照也出现；不能将这组干涉归因于新增 twist，也不能因此直接确定肘硬限位。
- 后腿 4 个均为 `base_link ↔ rr_ankle`，只在本次 +0.523599 rad twist、膝角 1.2 rad、踝角 -0.261799388／0／0.261799388／0.523598776 rad 的切片样点出现。说明新增 twist 的非零上下文能暴露零位切片未采到的机身干涉；未采区域是否还有干涉未知。

75 个姿态的掌网格最低顶点低于当前固定地面（汇总时以 -1e-9 m 排除浮点零噪声，不是穿地容许值）。12 个姿态的掌面局部正 z 朝向在世界 z 投影为负；只记录有向状态，不能把所有倾斜或这些孤立姿态当自然相位的最终失败判词。两腿全零样点掌最低顶点 z=0、normal_z=1、未发现保留检查对的实体相交。

热图颜色为掌最低顶点高度、X 为实体相交／包含；浮起、低于固定地面与干涉分别解释。单独提高体高能改变地面读数，不能消除机体内部相交；不据此修改体高、步长或安全阈值。

### 自检与反证

自检通过。五个破坏例均退出 1，分别拒绝链列错配、缺失 twist、漏根地面变换、把正间隙旧 `fail` 当实体相交、把精检触发置零而跳过相交。后两例在同一四面体几何输入上，正常实现检测交叉／包含并将正小间隙分开，错误实现失败，恢复后通过。

补做真实候选摘要破坏：只将 build 的 candidate_sha256 改为错误值，静态入口退出 1，输出目录没有创建。源码内存编译通过；完整离线套件 `offline_suite.py --python E:/IsaacLab/env_isaaclab/Scripts/python.exe --jobs 4` 37/37 通过，48.4 s，波内合计 163 s 仅信息，不修改预算。这些通过数只证明方法与仓库检查，不把 270 个姿态都判为安全。

不带执笔历史的新上下文只读审核新增静态路径及其直接碰撞依赖，未发现阻塞；指出的过滤列表比较无实际冲突，因为行含唯一 pair。该审核输出误称根高度只取两腿；实际 `_static_prepare` 明确遍历四腿，根定义及新报告均按四掌取值，最终结论以代码与实际报告为准。代码级审核不代替对下列结果或整个事项的关闭审核。

## 证据引用与复读

产物：`rl_exp/out/lizard2_palm_spatial_static_20261015/report.json` 和 `static_slices.png`。报告 SHA256 为 `60d5e017c039a89fca5abe52d66b069e22d22c622af2b6ac6e7dc7540bad19dd`，其中每个样点带完整 `q_rad`、网格相交对、固定根及代码／输入绑定。产物为本机诊断，不承诺入仓。

从仓根运行；解释器由 `python -B ablation_harness/host_paths.py --python` 解析。复读输出目录必须不存在，不覆盖本次产物：

```cmd
"E:\IsaacLab\env_isaaclab\Scripts\python.exe" -B rl_exp/tools/diagnose/palm_spatial_probe.py --self_check
"E:\IsaacLab\env_isaaclab\Scripts\python.exe" -B rl_exp/tools/diagnose/palm_spatial_probe.py --self_check --break_test misaligned
"E:\IsaacLab\env_isaaclab\Scripts\python.exe" -B rl_exp/tools/diagnose/palm_spatial_probe.py --self_check --break_test missing_twist
"E:\IsaacLab\env_isaaclab\Scripts\python.exe" -B rl_exp/tools/diagnose/palm_spatial_probe.py --self_check --break_test ground
"E:\IsaacLab\env_isaaclab\Scripts\python.exe" -B rl_exp/tools/diagnose/palm_spatial_probe.py --self_check --break_test solid
"E:\IsaacLab\env_isaaclab\Scripts\python.exe" -B rl_exp/tools/diagnose/palm_spatial_probe.py --self_check --break_test zero_trigger
"E:\IsaacLab\env_isaaclab\Scripts\python.exe" -B rl_exp/tools/diagnose/palm_spatial_probe.py --static_slices --build_report rl_exp/out/lizard2_palm_spatial_20261014/checkpoint_v3/build.json --output_dir rl_exp/out/lizard2_palm_spatial_static_reproduce
```

正常自检和完成探索退出 0；破坏例退出 1。探索退出 0 只说明采集完成，不表示所有姿态合格。代码及本次直接依赖如已变化，应核对报告摘要后解释差异，不能覆盖报告冒认同一次执行。

随后另一个不带执笔历史的新上下文对照实际静态报告、代码与事项指针审核，确认采样轴／数量、四掌根摆位、过滤集合、相交分组及声明边界一致，本轮静态一致性审核通过，无阻塞；它未独立重算地面计数与报告哈希，这两项由执行者上述实际汇总核对，不冒称审核者全量复算。该结论不授权关闭整个重构事项。

## 未覆盖边界与交接

未加密失败转折，未采 swing／abduct 非零上下文、左右镜像切片、两腿同时运动、连续轨迹或全五维角域。URDF 诊断范围不升级为安全角盒。没有力、摩擦、推进、周期、PD、承重与策略证据；地面高度和掌面方向不证明滚动或材料点不滑。

本次只证明在给定切片下出现具体反例，并为进一步局部加密和相位目标提供输入。下一步按复用指南保留前腿旧折叠干涉对照，围绕后腿新增上下文的实际机身／踝反例先定位转折与耦合，随后再讨论动作候选，不从静态最大位移直接选步长。重构与专项保持在办；正式采用、训练和关闭均不在本轮授权内。
