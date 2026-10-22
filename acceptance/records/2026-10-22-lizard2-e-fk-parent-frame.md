# lizard2 E：FK 父系坐标与轴读数核对

## 适用范围

承接 `work/active/lizard2-candidate-wiring.md` E3 的 FK 父系口径。当前输入仍为 `rl_exp/out/lizard2_e_fresh_reset_20261020/measured_manifest.json` 及其同目录 URDF；不重导出、不改网格、限位、USD、驱动或训练配方。

开始时 `check_leg_reachability.py` 与 `test_baseline_contract.py` 没有未提交差异。本轮 E 承接这两个文件中的父系接口与回归切片；不修改并行跟踪实现或其它在办文件。这里只核几何坐标，不能由离线变换推导动力学结论。

## 验收条件

- 先复现单姿态 CLI 把链父 link 坐标误标为 `base_link`；回归必须修前失败、修后通过。
- 保留 `load_chain/chain_frames/foot_pose/pad_state` 的默认局部结果；整机读数显式组合第一关节父 link 到 `base_link` 的祖先变换。
- 固定祖先不要求 axis/limit；活动祖先支持自身 origin/rpy 和非零转角；断链、环、错误角名、固定关节非零角、非有限角和不支持的类型拒绝。
- 单姿态及比较入口用同一父系变换，明确上游关节零位；掌面朝向/最低点与整机坐标一致。
- 轴与自身 origin/rpy 的组合也须红/绿证明；当前新 URDF 用独立完整树 FK 对照，旧基线与仓库闸门通过。

## 结果

### 根因与落点

`chain_joint_names()` 按既有约定在第一个非腿前缀 link 停止。前腿父 link 是 `chest_pitch`，后腿父 link 是 `base_link`；`chain_frames()` 从单位矩阵开始，因此原结果是链父系坐标。旧文档和 `--pose`、`--compare` 输出却把它称为 `base_link`，掌面世界读数也沿用这个假设。当前资产零位前腿已有 x 平移；带上游转角时遗漏还会影响方向和最低点。

新增 `chain_parent_transform()` 读取 URDF 祖先路径，复用现有矩阵组合；给现有局部接口增加可选关键字 `parent_transform`，默认局部语义不变。单姿态/比较入口显式传入整机父系变换，并打印上游关节保持零位。`joint_effect()` 与 `hinge_vs_body_z()` 同时修复轴读数漏乘自身关节 origin/rpy 的独立缺陷；不改变原角度阈值或求解预算。

继续质疑比较入口后发现第四个缺陷：把 spatial 五轴逐序号映射为旧五角色，与四轴 palm 比较时，新增 twist 被映射成 elbow 对应的 `hfe`，真正 elbow 被映射成 wrist 对应的 `kfe`，wrist 则被报为新增 `foot`。修补仅按声明的 spatial 合同把插入 twist 留作独立 token，四个原 palm 角色仍成对比较；不改变其它命名映射。四轴/五轴便携比较的修前日志确实输出 `extra foot`，修后输出 `extra shoulder_twist`，且实际 reader 收到的两条链都以 elbow/wrist 对应 `hfe/kfe`；不是只改显示文字。相同输入自比较只能证明一致性，因此此独立配对反例另行保留。

### 反例与兼容性

便携夹具包含固定安装点平移、固定 yaw、胸关节 origin roll、五个腿关节和一个平面掌网格。旧真实 CLI 把 `[0, 0, -0.5]` 输出为整机原点，闭式 `T Rz Rx` 对照失败；修后通过。另以非零胸关节角和 base roll 的闭式 `Rz Rx Ry` 对照掌面方向、各顶点最低点与输出坐标，比较入口调用实际 `_candidate_read()`。原 `foot_pose(chain, zero)` 仍精确返回局部 `[0, 0, -0.5]`。

两个轴反例均从提交 `a279158` 的原函数 AST 加载执行：自身 origin 绕 x 转 90° 后，y 轴应成为参考系 z；旧 hinge 返回 90°、旧 joint_effect 返回 y 轴，各自失败。修后两者通过，且父系反向 roll 抵消该 origin roll 后 hinge 回到 90°。未只用最终绿灯代替修前证明。

最终完整离线套件通过 `37/37 in 51.7s`，显式提交前钩子与代码提交实际钩子均通过；代码提交为 `645364b`。当前 URDF 的四腿 × 132 个有限构姿 × 零位/非零祖先两种状态，共 1,056 组对照，矩阵与掌面世界法向最大差均为 `4.440892098500626e-16`，最低点差为 `2.220446049250313e-16 m`。矩阵包含无量纲旋转与米制平移，统一 `1e-12` 仅为双精度数值一致性检查，不是几何或碰撞安全阈值。前腿原局部读法在零位漏掉 `0.005 m` 平移；非零祖先时矩阵最大分量差 lf/rf 为 `0.019702513572327218/0.014027954374482551`。后腿无祖先变换，保留原局部数值，跨两种 FK 的差只在双精度舍入量级。四腿真实单姿态入口、同输入比较入口均复读。

首次实际资产复读的尾部断言误用跨实现的精确零等式，后腿 `2.22e-16` 舍入差触发失败；修正为与其余矩阵对照相同的数值预算，并额外逐例检查后腿显式/默认两条局部接口精确一致。初次失败与诊断日志保留，不改写首次结果；此修订只涉及复读代码，不改工程阈值或产品实现。

本轮记录与指针写入后，最终套件及提交前钩子命中活跃文档总量超预算。仅合并本事项重复的共用文件归属/交接说明，原未完动作、回交责任与关闭条件继续保留；不关闭、迁移或取消事项，也不提高预算。失败日志保留，修订后重新执行套件与钩子。

### 调用方与未完路由

| 调用方 | 本轮核对 | 后续边界 |
|---|---|---|
| `check_leg_reachability --pose/--compare` | 已修正父系组合及四轴/五轴角色对齐；便携反例与当前资产复读 | CLI 上游关节零位；非零祖先由显式 API 提供，不表示整机运动学全域验收 |
| `palm_spatial_probe.Leg`、`local_path_check` | 已有 `model.root @ chain_frames(...)`，完整树 `pose()` 是另一读法 | 保持默认局部接口，避免重复乘父系；未重跑其全部 IK/壳碰撞流程 |
| `fit_gait_target`、`pose_slider` | 仍绑定旧 shared 链，直接使用局部 API | 不能据本轮报告宣称它们支持当前 spatial 候选；若扩展命名/树，需显式接父系和独立行为验证 |
| `check_joint_layout` | 已确认含无物理 FK 注入和后续至少百步的既有动态流程 | 当前输入独立入口证据仍未完成，不能把局部套件当作它已运行 |
| `stance_step_probe` | 已追到 manifest 加载后移除动作列与 self-collision 覆盖；当前代码的空 `--drop-joints` 会保留全部列 | 独立入口仍需按明确工况补证；不能复用先前对空参数的未核实推断，也不把默认删除末两轴当完整动作覆盖 |
| `baseline_probe`、`check_contact_ownership`、`diagnose_support` | 与既有 E3 清点分开保留 | 当前输入各独立入口、非零接触量和旧资产回交继续在办 |

## 证据引用

- 实现与永久回归：`rl_exp/tools/verify/check_leg_reachability.py`；`rl_exp/tools/verify/test_baseline_contract.py` 中 `test_reachability_parent_frame_cli/test_reachability_hinge_axis_own_rpy/test_reachability_joint_effect_axis_own_rpy`。
- CLI 修前日志：`rl_exp/out/lizard2_e_fk_parent_before_20261022.log`；修后初验：`lizard2_e_fk_parent_after_20261022.log`；两个旧函数 AST 红/绿及完整父系回归：`lizard2_e_fk_parent_regressions_20261022.log`。
- 四轴/五轴比较的真实修前失败：`rl_exp/out/lizard2_e_fk_compare_roles_before_20261022.log`；旧 `compare` AST 控制与修后结果包含在最终保留代码复读日志中。
- 最终套件：`rl_exp/out/lizard2_e_fk_parent_offline_release_20261022.log`；最终显式钩子/代码提交钩子：`lizard2_e_fk_parent_precommit_release_20261022.log`、`lizard2_e_fk_parent_code_commit_20261022.log`。较早套件通过为 `lizard2_e_fk_parent_offline_20261022.log` 与 `lizard2_e_fk_parent_offline_verified_20261022.log`；预算失败保留为 `lizard2_e_fk_parent_offline_final_20261022.log` 和 `lizard2_e_fk_parent_precommit_20261022.log`。
- 实际新输入首次复读/诊断：`rl_exp/out/lizard2_e_fk_parent_fresh_20261022.log`、`lizard2_e_fk_parent_replay_diagnosis_20261022.log`；含四项红/绿和新输入的最终复读：`lizard2_e_fk_parent_fresh_release_20261022.log`。这些本机制品不承诺入仓。
- 最终 SHA256（共享 `binding.sha256_file` 读取）：FK 实现 `ea1678f045d367e87676df7d6e6d1ec1c6bcede0486b70b60484801d044ae087`；回归文件 `beacc471493a0b37fcf5e91f22fd3962d55ca624bb0a8a512c0100bdefddbbc9`；最终复读日志 `33ec33adbceb72fe28b95a9435971740d764ca1d7d17c1003890ccba1055d12c`。
- 前一轮有限构姿与局部 FK 的边界：[非零 gait 与碰撞记录](2026-10-22-lizard2-e-nonzero-gait-collision.md)。本轮补整机坐标，不能倒推上一轮当时已经覆盖它。

从仓根用 IsaacLab Python 执行下列代码；manifest/URDF 摘要不符即拒绝。独立对照 `check_self_collision.fk()` 未处理 origin/rpy，因此先断言此实际 URDF 所有关节 origin/rpy 为零；含旋转 origin 的能力由上述闭式便携反例覆盖，不借此比较器外推。

```python
import ast
import subprocess
from rl_exp.tools.verify import check_leg_reachability as r, test_baseline_contract as t

old = ast.parse(subprocess.check_output(
    ['git', 'show', 'a279158:rl_exp/tools/verify/check_leg_reachability.py'], text=True))
for name, test in [('main', t.test_reachability_parent_frame_cli),
                   ('compare', t.test_reachability_parent_frame_cli),
                   ('hinge_vs_body_z', t.test_reachability_hinge_axis_own_rpy),
                   ('joint_effect', t.test_reachability_joint_effect_axis_own_rpy)]:
    fn = next(node for node in old.body if isinstance(node, ast.FunctionDef) and node.name == name)
    namespace = vars(r).copy()
    exec(compile(ast.Module(body=[fn], type_ignores=[]), '<before-parent-frame>', 'exec'), namespace)
    current = getattr(r, name)
    setattr(r, name, namespace[name])
    try:
        test()
    except AssertionError:
        print(name, 'BEFORE_EXPECTED_FAIL')
    else:
        raise AssertionError(name + ': before version unexpectedly passed')
    finally:
        setattr(r, name, current)
    test()
print('PARENT_FRAME_RED_GREEN_OK')
```

```python
import ast
import contextlib
import io
import json
from pathlib import Path
import re
import sys
from unittest.mock import patch
import xml.etree.ElementTree as ET
import numpy as np
from rl_exp.tools.runrecord.binding import sha256_file
from rl_exp.tools.verify import check_leg_reachability as r, check_self_collision as c

manifest = Path('rl_exp/out/lizard2_e_fresh_reset_20261020/measured_manifest.json')
assert sha256_file(manifest) == 'd876713b1a4aa6a4fef51f39bed284f4a15a01d562815eefefcf74eebfb77137'
path, naming, _ = r.diagnostic_urdf(manifest, None, None)
assert sha256_file(path) == 'e8896feb8b0dbdbeaa35e74a01c2ffcb4ab38d89b52f221831b3f287943edd00'
tree = ET.parse(path).getroot()
assert all(not any(map(float, j.find('origin').get('rpy', '0 0 0').split()))
           for j in tree.findall('joint') if j.find('origin') is not None)
model = c.load_urdf(path)
samples = c.sweep_poses(model['joints'], naming)
assert len(samples) == 132
base_rotation = np.array(r._rpy_matrix((.04, -.03, .02)))
errors = dict(matrix=0., normal=0., lowest_z=0.)
old_errors = {}
cases = 0
for leg in r.LEGS:
    chain = r.load_chain(path, leg, naming)
    names = r.chain_joint_names(path, leg, naming)
    end = r.joint_names.end_link(leg, naming)
    parent = model['joints'][names[0]]['parent']
    ancestors = c.chain_up(model['joints'], parent)
    vertices = np.array(r.pad_vertices(path, leg, naming))
    normal = np.array(r.pad_normal_in_link(path, leg, naming))
    old_errors[leg] = []
    for moving in (False, True):
        upstream = {name: .01 for name in ancestors
                    if moving and model['joints'][name]['axis'] is not None}
        assert all(model['joints'][name]['limits'][0] <= q <= model['joints'][name]['limits'][1]
                   for name, q in upstream.items())
        root = r.chain_parent_transform(path, leg, naming, upstream)
        old_error = 0.
        for q, _ in samples:
            angles = [q.get(name, 0.) for name in names]
            actual = np.array(r.chain_frames(chain, angles, parent_transform=root)[-1])
            expected = c.fk(model['joints'], end, {**q, **upstream})
            errors['matrix'] = max(errors['matrix'], float(np.abs(actual - expected).max()))
            local = np.array(r.chain_frames(chain, angles)[-1])
            if not ancestors:
                assert np.array_equal(actual, local)
            old_error = max(old_error, float(np.abs(local - expected).max()))
            state = r.pad_state(chain, angles, normal.tolist(), vertices.tolist(), .9,
                                (.04, -.03, .02), parent_transform=root)
            world_normal = base_rotation @ expected[:3, :3] @ normal
            points = (vertices @ expected[:3, :3].T + expected[:3, 3]) @ base_rotation.T
            errors['normal'] = max(errors['normal'], float(np.abs(state['world_normal'] - world_normal).max()))
            errors['lowest_z'] = max(errors['lowest_z'], abs(state['lowest_z'] - (.9 + points[:, 2].min())))
            cases += 1
        old_errors[leg].append(old_error)
    output = io.StringIO()
    argv = ['reach', '--target_config', str(manifest), '--leg', leg, '--pose', '0', '0', '0', '0', '0']
    with patch.object(sys, 'argv', argv), contextlib.redirect_stdout(output):
        r.main()
    print(output.getvalue())
    values = ast.literal_eval(re.search(r'pad origin in base_link (\[.*\])', output.getvalue())[1])
    expected = c.fk(model['joints'], end, {})[:3, 3]
    assert max(abs(float(a) - b) for a, b in zip(values, expected)) < 5.1e-7
assert max(errors.values()) < 1e-12
assert all(old_errors[leg][0] > .0049 and old_errors[leg][1] > .01 for leg in ('lf', 'rf'))
assert max(old_errors['rl'] + old_errors['rr']) < 1e-12
output = io.StringIO()
argv = ['reach', '--target_config', str(manifest), '--compare_target_config', str(manifest), '--samples', '2']
with patch.object(sys, 'argv', argv), contextlib.redirect_stdout(output):
    r.main()
print(output.getvalue())
lines = [line.split('32 poses', 1)[1] for line in output.getvalue().splitlines() if '32 poses' in line]
assert len(lines) == 2 and lines[0] == lines[1]
print('FRESH_PARENT_FRAME_OK', json.dumps(dict(cases=cases, errors=errors, old_frame_errors=old_errors)))
```

## 未覆盖边界

本轮无物理步进，不证明默认驱动、受载、接触安全、任意姿态可达、全 ROM 壳碰撞、限速或学习策略性能。`chain_parent_transform` 的非零角只是几何输入，不替代运行时关节读回；prismatic 等不支持的祖先明确拒绝。单姿态/比较 CLI 上游保持零位，不声称测得真实整机姿态。旧 shared 工具未迁移、布局/站姿/接触独立入口和旧资产 cap/contact ownership 按在办路由保留；E 未关闭，D 尚未作最终独立审核。
