# lizard2 掌面动作相位：撤回全程平掌验收（2026-10-14）

## 适用范围

用户在继续 5b 时指出“为什么掌面不能倾斜？实际上就应该拨动”。本记录纠正执行者将平掌诊断条件推广为全动作要求的错误，承接 `work/active/lizard2-restored-limits-pd-validation.md`。既有总项已明确“四掌共面只约束中立站姿，不锁定动作周期”；不是本次新放宽机械要求。

诊断与几何结果保留，不修改正式资产、关节轴、冻结配方或 PD。本记录不代表关闭审核，也没有完成新的拨动/承重验收。

## 验收条件

- 中立共面要求与动作相位约束分开；掌面在拨动、滚动与摆动中允许转动。全程 ≤2° 和固定掌底中心不得默认作为真实动作验收条件。
- 支撑、拨动、离地及重落掌分别记录掌面方向、实际最低网格点、接触点/边、根运动与几何地面间隙。滚动接触变化与真实滑移分开，不把固定网格中心当固定接触点。
- 维持反曲、翻掌及实体干涉禁区，但相位相关的掌面要求必须有目标依据。不能仅删除倾角断言、调大阈值或保持掌底中心固定后宣布拨动通过。
- 先给出相位目标、必要约束及接触/离地判定，再比较完整轨迹；无力、摩擦和承重数据时只交几何结果。需要改轴或增加自由度，必须针对真实目标给出缺失能力证据。

## 结果

### 撤回的执行推断

旧 5b 的 ±3° 俯仰在掌面倾斜约 2.88° 时失败，失败的是执行者所选的全程平掌样本。用户对工程诊断配置的确认不能替代已有“共面仅中立”设计边界。继续要求在固定四掌落点下满足 ≤2°，并据此提出改轴/换落足点三选一，采用了错误的验收前提；该执行路由撤回。

恢复动作是否成立仍需按相位重做接触和几何验证。倾斜的掌面若仍把网格中心固定在地面上，可能把部分网格压到地面以下；因此不能把旧求解器的倾角目标去掉就称已修复。

### 已完成但限定适用的补充诊断

`rl_exp/tools/diagnose/palm_recovery_constraints.py` 分析历史平掌条件，并绘出中立其它关节下的肘—腕二维切片；入口显式标明它不是全周期验收。输入沿用旧 5b 的隔离 URDF 和网格。

本机 `rl_exp/out/lizard2_palm_motion_5b_20261014/constraints_v1/` 有完成报告及 `coupled_boundaries.png`。四肢每腿 64 个关节状态对照 URDF FK，轴投影与法线不变式残差不超过 2.23e-16（投影为 m，法线点积无量纲，旧汇总取两者数值最大值）。相位澄清前运行版本的代码快照保留在该目录，不将新注释冒充旧报告身份。

解析下界覆盖固定参考点位置误差 ≤0.1 mm 内的全部首关节区间：俯仰必要倾斜下界为 2.7402–2.8822°。它只证明历史平掌条件冲突，不能证明允许拨动后的目标不可达；“四自由度必然不足”并非本次结论。把解析 yaw 符号反向后，真实候选的 FK 对照以约 0.777 的残差拒绝，输出目录尚未创建，无成功报告。

左右肘—腕切片各 81×21 个样本，其它关节固定零。每侧实体相交样本 43 个；满足旧平掌 ≤2° 的 47 个样本未触发 5 mm 余量失败。这仅描述该切片，不能作为真实拨动相位的安全集合或独立关节盒。

中立腕角为零时，两侧肘的实体相交边界加密为 [1.157461, 1.157520] rad，与旧记录的 5 mm 余量边界 [1.141230, 1.141289] rad 明确分开。扫描全部腕角时，5 mm 转折约覆盖 1.04889–1.18910 rad，实体相交转折约覆盖 1.06857–1.19215 rad。腕角会改变干涉边界，不能凭单一固定腕角拍定肘硬限位。

## 证据引用

- 设计原要求：`work/active/lizard2-body-drive-candidate.md` 的“后肢恢复要求”，明确共面仅约束中立；本次用户补充动作中掌面应拨动。
- 历史样本：`acceptance/records/2026-10-14-lizard2-5b-motion-boundaries.md`，已经追加适用性纠正，原数值与失败读数保留。
- 补充原始报告：`rl_exp/out/lizard2_palm_motion_5b_20261014/constraints_v1/report.json`、`lf_coupled.json`、`rf_coupled.json`，输入/源码摘要在 `identity.files`，快照为 `.py.txt`。产物本机保存，不承诺已入仓。
- 复读入口：`rl_exp/tools/diagnose/palm_recovery_constraints.py`；参数取 `--source_report_dir` 所指历史 5b 报告。新报告增加 `assumption_scope`，物理计算与旧结果相同。
- 入口提交：`464f632`。解析自检、yaw 错号拒错、工作账本和单一 binding 检查通过；代码提交钩子的框架、资产、版本、工作及观测协议闸门通过。新的真实拨动判据尚未执行，不能由这些检查代替。

```powershell
& 'E:/IsaacLab/env_isaaclab/Scripts/python.exe' rl_exp/tools/diagnose/palm_recovery_constraints.py --self_check
& 'E:/IsaacLab/env_isaaclab/Scripts/python.exe' rl_exp/tools/diagnose/palm_recovery_constraints.py --source_report_dir rl_exp/out/lizard2_palm_motion_5b_20261014/final --output_dir rl_exp/out/lizard2_palm_motion_5b_20261014/constraints_reproduce
& 'E:/IsaacLab/env_isaaclab/Scripts/python.exe' rl_exp/tools/diagnose/palm_recovery_constraints.py --source_report_dir rl_exp/out/lizard2_palm_motion_5b_20261014/final --output_dir rl_exp/out/lizard2_palm_motion_5b_20261014/constraints_bad_sign --break_yaw
```

输出必须换成不存在的目录；自检和正常诊断退出 0，yaw 破坏例退出 1。几何不可达标记仅指历史全程平掌条件，不是机器人总体能力判词。

## 未覆盖边界

按用户意图的拨动/滚动、实际接触边切换和新的完整恢复周期尚未执行；未做承重、推进、受推恢复或新的最终策略范围。轴调整和新增自由度没有得到必要性证据，不作为当前下一步。

执行者先按真实动作相位重建几何判据，再检查足网格与地面的关系、动作连续性及四肢组合碰撞。动力学仍按专项步骤 1–4 的前提和步骤 6 推进；本项不因修订约束而关闭。
