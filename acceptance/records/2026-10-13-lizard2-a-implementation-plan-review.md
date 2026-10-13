# lizard2 A 实现与计划审核（2026-10-13）

## 适用范围

审核 `work/active/lizard2-body-drive-candidate.md` A/P1–P4、Blender 构建实现、P1/P2 证据与当前保存候选。本上下文此前参与计划路由修订，故这是实现与计划对照复核，不冒充 D 的新上下文最终验收，不关闭事项。

- `code_rev`：`cc6a4123a2c42c308f18fc8f7288e7477b5e87e4`；受审生成器没有工作树改动。
- `code_digest`：`rl_exp/blender/scripts/lizard2_stance_candidate.py` SHA256 `1d39f1e0ef1ef38b6eb65e1442a3dee2dd6aba35f62666da44e60fde71c62bad`。
- `asset_digest`：本地 `rl_exp/blender/lizard2_palm_p2_sample_claw_all_lowered_body75_vertical/sample_neutral.blend` SHA256 `4f286a0cc1d7a5a00db99ef0e30e0375f372f44dd6f805379664e5c563b83016`。
- 当前产物：本地 `rl_exp/blender/lizard2_palm_p2_sample_claw_all_lowered_body75_vertical_tail_ground/sample_neutral.blend` SHA256 `c6566679f514581dd972e40dfbbb9d6f115a43e975f861ab4c57a53e3496ca47`。二进制与渲染仍只在本地；本次直接打开保存文件读取 actual pose 与 evaluated mesh，并查看实际侧视图。
- 未改模型、实现、冻结版本、导出产物；其它会话的 dirty 文件不纳入本次提交。

## 验收条件

按事项当前目标及 A1/A2 逐项核对：骨段方向、掌根连接、镜像、限定诊断转动、碰撞前置；P1 契约、P2 几何、P3 导出、P4 动力学不能互相替代。用户的新体高/竖直下段要求覆盖旧角度视觉认可，但 A1 仍明确引用蜥蜴近端方向目标。

## 结果

**A 尚不能交付 P3；发现一项实现与计划冲突。** P2 已披露的碰撞缺口仍成立；没有把历史已知缺口冒充新增发现。

### F1 / P2：后肢股骨向前，却被自检固定为正确方向

事项第 31 行要求“上臂/股骨外展并向后”，第 122 行明确近端仍按该目标；新姿态也没有另行批准股骨向前。生成器第 957–960 行直接继承旧上段 XY 朝向，第 1099–1103 行要求新旧方向符号与 yaw 一致。尾分支随后保持非尾几何，所以此冲突存在于当前交付的保存模型中。

直接读取保存文件的世界系 actual pose，四个上段的 head→tail 向量如下，单位 m。+X 是掌段朝前方向，四掌骨 X 分量均为正；侧视图也与此一致。

| 骨 | ΔX | ΔY | ΔZ |
|---|---:|---:|---:|
| lf_shoulder_abduct | -0.169049352 | +0.464459121 | -0.085715950 |
| rf_shoulder_abduct | -0.169049233 | -0.464459002 | -0.085715950 |
| rl_hip_abduct | +0.169053584 | +0.464471132 | -0.085725218 |
| rr_hip_abduct | +0.169053763 | -0.464471072 | -0.085725218 |

前肢向后、后肢向前。当前检查只证明“保留旧方向”，不能证明“满足目标方向”；按现计划把后肢改向后反而触发自检失败。这会使后续导出/FK/动力学围绕错误目标继续投入，长期风险是各层都继承同一个源模型错误而一致通过。

修正动作：先消除目标歧义。若保留现计划，修改后肢构造和方向断言；若用户决定后肢向前，则将该决定具名记录后统一目标与判据。不能根据当前模型静默改需求。随后用明确机体前向、左右外向与批准角域核对保存模型；用错误方向的实际姿态作负例，确认检查能拒绝，并重跑镜像、连接、碰撞及受影响尾/体高保持检查。阈值不得由这次读数倒定。

### 当前执行状态与计划评估

- **P1 窄范围成立**：本次真实 Blender 契约正例退出 0，3 个旧消费者、1 个 palm 正例、10 个负例；去掉验证的逆例退出 1，命中 `old long source accepted under palm; distal silently discarded`。不等于几何或真实导出成立。
- **P2 部分完成**：body75 内存重建检查退出 0，覆盖四肢竖直、连接、镜像与限定单关节诊断；尾分支检查实际重开保存候选后退出 0。尾抬高逆例退出 1；原始静态读数与边界仍归对应上游记录。
- **碰撞仍未解决**：本次对当前保存模型的 evaluated lower-cylinder/palm 直接构造 BVH，中立姿态表面交叉对数 lf/rf/rl/rr = 7/7/9/9。与上游披露一致。表面交叉不是穿透深度或碰撞体物理结论，当前也没有正式接受规则。应先判定具体相交面及连接/碰撞体方案，不因相邻 link 或只看渲染就直接忽略。
- **P3 未执行**：真实 palm 导出目标、轴/网格归属/惯量及 FK 接线仍是计划任务。`generate_urdf.py:88` 明确阻止 palm 实际导出；只读 contract 不能替代真实 URDF/USD。
- **P4 未执行**：没有当前候选的完整承重周期动力学证据。现计划已把隔离运行接线、B/C 安全标定、S5 阈值前置、D 比较分开，未发现原先的依赖闭环复活；应保持该顺序。

最先做 F1 目标一致性和 P2 碰撞处置，再由用户确认新姿态及工程容差，才能进入 P3。避免先做导出和驱动标定，再因几何目标改变全部重做。

### 本次复读方法

仓根 PowerShell；Blender 5.2.2 LTS。下列检查均只读/内存操作：

```powershell
$blender = 'E:\SteamLibrary\steamapps\common\Blender\blender.exe'
& $blender --background --factory-startup --python-exit-code 1 --python rl_exp/blender/scripts/lizard2_stance_candidate.py -- --contract_self_check
# 同命令追加 --regression_without_fix：预期退出 1，本次符合。
& $blender --background --factory-startup --python-exit-code 1 --python rl_exp/blender/scripts/lizard2_stance_candidate.py -- --p2_sample --output_dir E:/Robot/rl_exp/blender/lizard2_palm_p2_sample_claw_all_lowered_body75_vertical --diagnostic_angles=-10,0,10 --palm_shape claw --all_legs --sole_at_ball_bottom --body75_vertical --check_only
& $blender --background --factory-startup --python-exit-code 1 --python rl_exp/blender/scripts/lizard2_stance_candidate.py -- --p2_sample --output_dir E:/Robot/rl_exp/blender/lizard2_palm_p2_sample_claw_all_lowered_body75_vertical_tail_ground --diagnostic_angles=-10,0,10 --palm_shape claw --all_legs --sole_at_ball_bottom --body75_vertical --tail_ground --check_only
# 尾分支同命令追加 --regression_without_fix：预期退出 1，本次符合。
```

注意：body75 的 `--check_only` 从 four-low 源重建内存候选，第 1234 行直接返回；它没有重新检查已保存的 body75 文件。尾分支才在第 876 行后重开已存在的目标文件。本次因此另用 Blender `--python-expr` 打开当前保存文件独立取值，不将内存正例误作所有落盘产物的重新认证。

独立方向复读可用以下表达式（传给上述 Blender 的 `--python-expr`）；不调用生成器的方向断言：

```python
import bpy
bpy.ops.wm.open_mainfile(filepath='E:/Robot/rl_exp/blender/lizard2_palm_p2_sample_claw_all_lowered_body75_vertical_tail_ground/sample_neutral.blend')
arm = next(o for o in bpy.context.scene.objects if o.type == 'ARMATURE')
for name in ('lf_shoulder_abduct', 'rf_shoulder_abduct', 'rl_hip_abduct', 'rr_hip_abduct'):
    bone = arm.pose.bones[name]
    print(name, list(arm.matrix_world.to_3x3() @ (bone.tail - bone.head)))
```

碰撞复读使用同一保存场景：按对应 `elbow/knee` 与 `wrist/ankle` 的 `parent_bone` 取网格，以两个多边形端盖识别下段圆柱、72 顶点识别当前掌体；经 depsgraph 的 `evaluated_get().to_mesh()` 取世界顶点与 polygons，以 `BVHTree.FromPolygons` 构树并计 `overlap()`。这些形状识别仅适用于绑定的这份候选，不能作为未来任意网格的角色契约。

提交前 `check_suite_banners`、`framework_pin_check --strict --self-test`、`check_dr_parity --strict`、`check_version_docs`、`check_work_docs`、`check_obs_protocol --live` 及 `git diff --check` 全部退出 0。既有 IsaacLab dirty、旧版本 tag 与限速警告未消除；这些闸门不证明 A 的几何能力成立。

## 证据引用

- `work/active/lizard2-body-drive-candidate.md`：目标、A1/A2、B/C 标定与 D 路由。
- `rl_exp/blender/scripts/lizard2_stance_candidate.py`：实际构建及回归入口。
- `rl_exp/blender/scripts/generate_urdf.py`：真实 palm 导出阻断。
- `acceptance/records/2026-10-12-lizard2-palm-chain-p1.md`：P1 窄范围契约。
- `acceptance/records/2026-10-13-lizard2-lowered-body-vertical-shanks.md`：body75 构造、有限转动与碰撞边界。
- `acceptance/records/2026-10-13-lizard2-natural-ground-tail.md`：当前尾候选与保持约束。
- `acceptance/records/2026-10-13-lizard2-body-drive-plan-review.md`：既有计划及 E 审核，依赖路由修订依据。

## 未覆盖边界

未修 F1、未生成新模型、未批准朝向/外观/工程容差，未验证全身碰撞、完整 ROM/周期、URDF/USD 或动力学。各局部 PASS 仅在上述范围有效。当前工作保留 `in_progress`，D 后新上下文验收仍待执行。
