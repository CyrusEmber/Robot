# 肩髋三轴隔离试作检查点

## 适用范围

用户要求将未完成模型试作提交，或先做收尾。本轮保存可打开的 Blender 模型、自包含 URDF/网格、生成与探测代码及有限几何证据；对应 `work/active/lizard2-palm-spatial-reconfiguration.md`。这是在办检查点，不是模型正式采用、动力学验收或关闭审核。

## 验收条件

- 试作在隔离目录生成并保存重开，三个近端轴共中心；长轴指向肩至肘或髋至膝，实体及子链随 twist 转动。
- Blender 实际枢轴和网格抽样与 URDF 独立 FK 对照；新旧名表保持各自语义，锁轴与错误轴对照须失败。
- 提交模型的 URDF 网格引用为相对路径，源和候选身份可核对；不覆盖采用资产。
- 当前检查只覆盖所列离散诊断，不宣称完整 A–E 或重构事项已经完成。

## 结果

采用 `swing → abduct → twist → elbow/knee → wrist/ankle` 的五轴链。上段实体移到 twist 下游；原近端理想化载体的质量/各向同性惯量拆给共中心载体。twist 的 ±30° 和继承的 effort/velocity 仅为诊断占位，未标定驱动。保存后重开 Blender，再取得中立、四腿分别 ±10° twist 和组合运动的实际快照。

最终检查点为 `rl_exp/out/lizard2_palm_spatial_20261014/checkpoint_v3/`：含 `palm_spatial.blend`、`palm_spatial.urdf`、`meshes/` 和 `build.json`。输出网格按内容哈希命名、相对引用；生成报告绑定源 blend/URDF/测量输入、来源网格、生成脚本及候选文件哈希。源文件保持原样。

中立网格抽样最大位移为 3.734220292e-7 m；保存重开后的 Blender/FK 最大枢轴差 1.228082272e-6 m、网格样点差 1.962326758e-6 m，低于本诊断依据六位小数导出与 float32 运算设定的 1e-5 m 比对阈值。四腿纯 twist 的肘膝中心保持在轴上，下游掌段确实移动；镜像和两套 FK 对照通过。总质量读数保持 72.0004 kg；不据此声称动态惯量近似准确。

历史固定参考点/水平掌面诊断对 pitch、roll、yaw 分别取 ±3° 闭合采样，每腿共 51 帧。旧链最大倾角 2.882392895°；新链最大倾角约 1.207418270e-6°，最大参考点残差约 3.55e-16 m。此为数值求解的离散残差，不是机械精度；历史平掌要求只用于能力对照，不重新成为自然步态约束。

锁住真实新增 twist 的对照退出码为 1，恢复 2.882392895° 倾角缺口；放开轴的同条件诊断退出码为 0。错误轴注入将左前 twist 轴改为竖直，Blender/FK 对照拒绝，枢轴/网格样点误差分别约 0.08616/0.07987 m。中立和俯仰/横滚正负极值共五个全身姿态的抽样碰撞检查未报失败；此项保留原有连接排除及其名称迁移，不证明全域无碰撞。

完整离线套件首次运行 37 项，36 项通过、1 项失败：两个新脚本重复实现文件哈希。已改用 `tools/runrecord/binding.py:sha256_file`，原失败的 `check_record_bindings.py` 复跑通过，随后重新生成最终候选并复验正例和锁轴负例。名表自检通过。Blender 的系统缩略图缓存写入有告警，模型保存、重新打开和运动取样均成功；不把缩略图缓存失败当模型失败。

最终完整套件复跑 `offline_suite.py --python E:/IsaacLab/env_isaaclab/Scripts/python.exe --jobs 4`：37/37 通过，58.8 s。最终包复制到系统临时目录后，38 个候选文件哈希及 URDF 全部相对网格引用通过核对；相同引用检查对修复前 candidate_v1 的绝对路径引用真实拒绝。最终脚本的错轴反例仍退出 1。记录的是本机隔离包验证；跨机历史对照重跑仍受下列原始输入前提约束。

暂存时另发现 Git 换行规范化会改变 URDF 字节、破坏报告哈希：修复前逐项对照 `git show :<文件>` 与 build.json，真实报告 `palm_spatial.urdf` 不匹配。已在试作目录的 `.gitattributes` 对本次三个输出目录设置 `-text`；重新暂存后，38 个候选文件以及 build/正反例报告、两个脚本的索引字节均与实测版本一致。此设置只保存检查点字节，不改变全仓换行约定；复读可用 `git show HEAD:<文件>` 的字节经统一 `binding.sha256_bytes` 与对应报告哈希比较。

实际提交和索引共 43 个已绑定文件均通过字节核对。该包的空白检查显式认可原有 CRLF 行尾（`cr-at-eol`），仍检查尾随空格、文件末尾空行和 tab 前空格；全组提交的 `git diff --check` 通过。

## 证据引用

- 生成与实际快照：`rl_exp/out/lizard2_palm_spatial_20261014/checkpoint_v3/build.json`。
- 正例轨迹、碰撞样本及代码身份：`rl_exp/out/lizard2_palm_spatial_20261014/checkpoint_v3_probe/report.json`；同目录 `comparison.png` 为诊断图。
- 锁轴反例：`rl_exp/out/lizard2_palm_spatial_20261014/checkpoint_v3_locked/report.json`。
- 错轴拒绝用下方命令复读，不产生成功报告。
- 实施代码：`rl_exp/blender/scripts/lizard2_palm_spatial_candidate.py`、`rl_exp/tools/diagnose/palm_spatial_probe.py`、`rl_exp/tasks/joint_names.py`。

从仓根运行；输出目录必须不存在。下列原始输入位于本机，身份取 build.json；试作模型包本身可单独打开，新旧对照复跑仍需这些原始输入，不承诺所有上游历史资产已入库。

```powershell
& 'E:/SteamLibrary/steamapps/common/Blender/blender.exe' --background --factory-startup --python-exit-code 1 --python rl_exp/blender/scripts/lizard2_palm_spatial_candidate.py -- --urdf rl_exp/out/lizard2_palm_pd_restored_20261013/lizard2_palm_diagnostic.urdf --probe_report rl_exp/blender/lizard2_palm_limit_probe_restored_20261013/measurements.json --output_dir rl_exp/out/lizard2_palm_spatial_replay/candidate
& E:/IsaacLab/env_isaaclab/Scripts/python.exe -B rl_exp/tools/diagnose/palm_spatial_probe.py --build_report rl_exp/out/lizard2_palm_spatial_replay/candidate/build.json --output_dir rl_exp/out/lizard2_palm_spatial_replay/free
& E:/IsaacLab/env_isaaclab/Scripts/python.exe -B rl_exp/tools/diagnose/palm_spatial_probe.py --build_report rl_exp/out/lizard2_palm_spatial_replay/candidate/build.json --output_dir rl_exp/out/lizard2_palm_spatial_replay/locked --lock_twist
& E:/IsaacLab/env_isaaclab/Scripts/python.exe -B rl_exp/tools/diagnose/palm_spatial_probe.py --build_report rl_exp/out/lizard2_palm_spatial_replay/candidate/build.json --output_dir rl_exp/out/lizard2_palm_spatial_replay/wrong_axis --inject_error twist_axis
```

## 未覆盖边界

尚未完成错 pivot、未重绑网格等独立负例；完整迈步、转向/恢复轨迹、连续安全域与地面接触相位仍须按方案验证。局部任务 Jacobian 满秩不证明全域可达；碰撞采样及连接排除需独立复核。探测脚本的成功退出只表示其几何诊断通过，碰撞详情须另读报告，不能当仿真安全闸门。虚拟承载 link、驱动耦合、USD/IsaacLab 接线、承重、最终 ROM/PD 均未验。正式机体和冻结配方没有采用本试作，事项保持 in_progress。
