# lizard2 E：独立入口与真实退出状态

## 适用范围

承接 `work/active/lizard2-candidate-wiring.md` 的布局、站姿、baseline 与接触独立入口。当前资产仍取固定 `rl_exp/out/lizard2_e_fresh_reset_20261020/measured_manifest.json`；派生输入只改具名根位姿或环境数，不改资产、零增益、无重力和 force timing。短窗口只检接线，不作静站、受载、跟踪或步态结论。

## 验收条件

- 真实入口执行；引用共享 loader 通过不能代替入口本身。
- 拒绝必须同时有明确诊断及非零进程退出码，成功不能覆盖失败日志。
- 布局允许只读布局与小角度 FK；默认全流程保持原参数与可用性。纯运动学分支前完成动作覆盖检查，不能暗中进入百步动态流程。
- 保存入口源码、输入身份、原始日志、每步读回及复读代码；未完或失败按对象保留。

## 结果

初始离地接触反例已揭示 `CONTACT_OWNERSHIP_FAILED` 但进程退出 0；单纯提前 close 仍返回 0。本机 SDK `SimulationApp.close(exit_code=0)` 快速退出会终止进程，因此需显式传递状态。四个入口在异常前保留 traceback，并把失败、显式 SystemExit 和中断状态传给关闭接口。

布局新增显式 `--kinematics_only/--inject_rad/--json`，旧默认全流程和 0.3 rad 保留。动作覆盖检查提前到 FK 前，纯运动学输出不称为动态/碰撞通过。主程序加 try/except/finally 保留全局符号与原执行体；大段缩进的行为差异按忽略空白的 diff 核对。

新增只读模式后，独立完整树 FK 揭示旧 `joint_turn()` 的斜轴缺陷：选变化最大的一个基向量求圆弧，不等于完整旋转。修前真实 25 项读回相对 URDF 的最大轴角分量差 `0.00017093994510855408 rad`，修后为 `2.725025152490847e-7 rad`，端点位置差 `5.98546447516668e-7 m`。使用官方 xyzw `quat_mul/quat_conjugate/axis_angle_from_quat` 后转回 base 坐标，不手写四元数。非零根姿态与子帧、三类轴、正负小角和原 0.3 rad 的便携反例确认修前失败、修后通过；首次夹具误用 float64 与旧实现 float32 eye 不匹配，保留在 `oblique_axis_before.log`，真正数值反例见 `oblique_axis_before_v2.log`。

站姿最短窗口没有内部采样点，原汇总 `min(steady)` 抛错后退出 0；改为明确输出不可测，并在四个入口统一给 SDK close 传真实状态。另修正实际动作变换：原实现把各列 scale 都读成首列，并误从 term 本身取 use_default_offset，遗漏了真实 offset。便携反例请求 0.03 rad 却经实际 scale/offset 得到 -0.185 rad；修后按每列已解析的 scale/offset 求逆，当前源码中 cfg.use_default_offset 仅作说明，不再替代实际 offset。夹具漏补原列起点的首次错误也保留；真正红灯为 `stance_target_before_v2.log`。

| 当前入口切片 | 实际结果 | 原始出口 |
|---|---|---|
| 布局纯运动学 | 25 项 FK、30 列动作覆盖，观察器记录无 env.step；实际库轴角与完整树 FK 对照如上 | `layout02`，退出 0 |
| 布局破坏输入 | 只删除 lf_shoulder_twist_joint 动作列，真实 --require-all-actions 拒绝 | `layout_missing_twist.log`，退出 1 |
| 站姿空窗口 | 8 步；修前 min(empty) 异常退出 0，空窗口修补后的中间版明确不可测并收尾 | `stance_short01/02.log`，后者退出 0；最终源码空窗另经回归 |
| 站姿完整小窗口 | 最终源码 12 步、0.24 s；twist 动作列 2、backend DOF 列 20，±0.001 rad；其它目标为零；目标/后台/缓存最大分量差 `4.749745128457272e-11 rad` | `stance01.log`、`stance01/audit.json`，退出 0 |
| baseline | 最终源码 2 环境 × 2 步，102 维孤立观测及已有命令/事件/动作/终止检查通过 | `baseline_air02.log`、`baseline_air02/audit.json`，退出 0 |
| 接触离地拒错 | 两步未见触力；从日志 FAIL 却退出 0 修成 JSON FAIL 与进程退出 1 一致 | `ownership_air01/02/03`，最终退出 1 |
| 接触候选正例 | 原地面设置下中立尾段与足端同低，首次预检查拒绝；具名根俯仰/高度后仍未见非零触力，不能判正例 | `ownership_floor01/02`，退出 1，缺口保留 |

`ownership_floor02` 实际 backend 根高约 `0.61350107 m`，根位姿并非未应用；两步后 rf_wrist 原网格最低点约 `-0.000257827 m`，全部读回触力仍为零。原网格最低点不等于 PhysX 已生成非零力的证据，不据此猜测传感器坏了或改 force timing。实际有限读回保持固定基、31/62 个对应环境的无重力 body、零缓存增益和 force timing False。

默认动态流程的循环体另对照提交 `8cd5102` 的 AST：布局 4 个、站姿 3 个含 env.step 的循环完整保持。解析回归确认默认仍走完整流程、注入 0.3 rad；只新增显式分支，不以纯运动学通过冒充承重/驱动阶段通过。API 符号仍在模块全局作用域，保护块没有把原函数藏入新 main 或删去原出口。

最终代码提交 `1dba1bf`。完整离线套件通过 `37/37 in 52.3s`，显式提交前钩子及代码提交实际钩子通过。记录内只读复读实际执行得到 `INDEPENDENT_ENTRY_EVIDENCE_REPLAY_OK`；格式通过与这些自检不替代 D 的独立审核，E 保持在办。

## 证据引用

本机根目录为 `rl_exp/out/lizard2_e_entry_consumers_20261022/`。`ownership_air01` 是真实旧失败退出 0；`ownership_air02` 是仅改变关闭顺序仍失败退出 0；`ownership_air03` 为显式传入状态后返回 1。`baseline_air01` 是修前两环境短窗口；`layout_before` 是旧入口拒绝新增模式参数；`exit_cleanup_before.log/entry_regressions.log` 保存隔离红/绿及动作覆盖破坏分支。`prepare.log` 的首次派生检查因中立位尾段也触地而拒绝，不能删去当作已经通过；后续具名位姿派生见 `prepare_v2.log`。

最终定向回归日志为 `entry_regressions_with_observer.log`，原始斜轴、空窗口、目标换算的真实数值红灯分别在 `oblique_axis_before_v2.log`、`stance_summary_before.log`、`stance_target_before_v2.log`；初次夹具错误另保留而不当作产品缺陷红灯。完整套件在 `offline_suite_release.log`，较早通过的套件为 `offline_suite.log`；显式钩子/实际代码提交钩子为 `precommit.log`、`code_commit.log`。`evidence_replay.log` 是下述保留代码的执行输出，生成/验证日志不混入固定制品索引。

最终源码 SHA256：布局 `2b81347d951176d197bb73e6094f98c5217ae3cf9c9fd93717954bd2572c7a86`；站姿 `99423fb482f7350b3de53add1e0f1ff9261d2a04d75a711bcc6a6ce156a6e29b`；接触 `6869f7c2312807a1330d08e082e4fa55ef6ed7eb5f43de654c5b1f8d6f260a60`；baseline `a635a4c0149ece913659617591a4de7dff3493bbb5faa5aff6ef53cf18c5d290`；观察器 `b5efd799cef25b3118a0ad7e65bae4e8d98daa514b9e92172ae44aac13a59176`；回归文件 `c66560706793b61222ef7e684b3ad3067925e63b94c57fb7e18ce7e09e138cbf`。入口源码字节身份与实际采样一同保留，不用当前代码同名推定旧制品由其产生。

可复读观察器落在 `rl_exp/tools/diagnose/palm_entry_wiring.py`，只包装真实 env.step/env.close，不改动作、传感器或生产判断。早期采集由记录中的同一观察逻辑直接执行，现已整理为工具；运行时只读状态、有限步数约束保持，另增加输出路径限制和完整的调用/源码字节快照。最终工具自身另作真实布局和接触拒错验证。

早期观察器用文本模式写 `source.py`，Windows 换行规范化使快照字节摘要与实际入口摘要不同，但文本一致。本轮未覆盖这些旧快照；在核对当前源码摘要等于当时 audit 中的 `source_sha256` 后，新建 `source_raw_at_review.py` 作为原始字节补充，明示其创建阶段。当前工具直接按字节保存入口与自身源码，并在启动前写 `invocation.json`，不会让异常退出丢失调用身份。

原输入 manifest SHA256 为 `d876713b1a4aa6a4fef51f39bed284f4a15a01d562815eefefcf74eebfb77137`，URDF 为 `e8896feb8b0dbdbeaa35e74a01c2ffcb4ab38d89b52f221831b3f287943edd00`。两环境派生 manifest 为 `1be287d24ba847c94978b3f6d9ca64109907a8472dfbf3c96bd6f5c13e6bbccf`；根位姿派生为 `dba22f4be95876d12c8c97c9193a57d5d589bee892e2e79df92d6ae7b9d93e46`；缺 twist 动作列反例为 `7285192533670e221d0653a7b5a5d03b8b1450fad32a046747e72cc4b4344319`。所有派生只改绑定 source 及记录具名 config_delta，原 manifest 与 USD/URDF 未写入。

从仓根、IsaacLab Python 复跑时使用全新输出目录；以下给出具名工况，不覆盖本次制品。接触离地案例预期退出 1，不能按命令失败简单忽略。父目录下的实测输入和源资产是本机制品，不承诺随仓库提供；缺输入应拒绝，不回退正式 v3。

```powershell
python -B rl_exp/tools/diagnose/palm_entry_wiring.py --entry layout --out rl_exp/out/lizard2_e_entry_consumers_20261022/layout_replay_new --target_config rl_exp/out/lizard2_e_fresh_reset_20261020/measured_manifest.json -- --task Lizard2-Flat-Play-v3 --headless --kinematics_only --inject_rad 0.001 --require-all-actions --json rl_exp/out/lizard2_e_entry_consumers_20261022/layout_replay_new/report.json
python -B rl_exp/tools/diagnose/palm_entry_wiring.py --entry stance --out rl_exp/out/lizard2_e_entry_consumers_20261022/stance_replay_new --target_config rl_exp/out/lizard2_e_fresh_reset_20261020/measured_manifest.json -- --task Lizard2-Flat-Play-v3 --headless --drop-joints= --self-collision on --joint shoulder_twist --steps 2 --settle 0 --amplitude 0.001
python -B rl_exp/tools/diagnose/palm_entry_wiring.py --entry baseline --out rl_exp/out/lizard2_e_entry_consumers_20261022/baseline_replay_new --target_config rl_exp/out/lizard2_e_entry_consumers_20261022/baseline_air01/manifest.json -- --task Lizard2-Flat-Play-v3 --num_envs 2 --steps 2 --headless
python -B rl_exp/tools/diagnose/palm_entry_wiring.py --entry ownership --out rl_exp/out/lizard2_e_entry_consumers_20261022/ownership_replay_new --target_config rl_exp/out/lizard2_e_fresh_reset_20261020/measured_manifest.json -- --task Lizard2-Flat-Play-v3 --num_envs 1 --steps 2 --headless --json rl_exp/out/lizard2_e_entry_consumers_20261022/ownership_replay_new/report.json
```

既有链继续引用 [非零 gait/碰撞及 E3 清点](2026-10-22-lizard2-e-nonzero-gait-collision.md)、[baseline 终止分支](2026-10-22-lizard2-e-baseline-terminal.md)、[FK 父系坐标](2026-10-22-lizard2-e-fk-parent-frame.md)；本轮不把它们改写成新执行的全流程。

当前工具自身的真实正例是 `layout03`：同工况完成并生成原始入口/观察器字节快照。`ownership_budget01` 故意请求第三步，实际观察器在两步上限处抛出 `env.step budget exceeded`，原进程返回 1；该运行不作为完整采样通过。隔离破坏测试另核对零预算、两步后不再调用后端、NaN/Inf/超幅动作在后端调用前拒绝。

数值复读及完整性基线是 `artifact_digests_v2.json`，SHA256 `cc7a9406438daf1985c52c0cc1603f8f7af3fe53439c25df8bc9dcea55d879a2`，锁定 92 个已完成制品。初稿 `artifact_digests.json` 误计其仍在写入的生成日志，不作基线；原文件保留。最终索引排除自身、生成/验证日志，并在生成后逐文件复核。全部摘要使用共享 `binding.sha256_file`，不重写原日志或用后来的成功覆盖失败。

下面只读复读当前制品；不启动仿真，也不重建索引。布局数值预算 `1e-5` 对应已知六位导出与 float32 计算，仅检查读数一致性，不是 ROM、clearance 或驱动阈值。修前真实斜轴报告及缺项、NaN 破坏对象必须被拒绝。

```python
import ast
import copy
import json
from pathlib import Path
import subprocess
import xml.etree.ElementTree as ET
import numpy as np
from rl_exp.tools.runrecord.binding import sha256_file
from rl_exp.tools.verify import check_self_collision as c

root = Path('rl_exp/out/lizard2_e_entry_consumers_20261022')
index_path = root / 'artifact_digests_v2.json'
assert sha256_file(index_path) == 'cc7a9406438daf1985c52c0cc1603f8f7af3fe53439c25df8bc9dcea55d879a2'
index = json.loads(index_path.read_text(encoding='utf-8'))
assert len(index['files']) == 92
for name, digest in index['files'].items():
    assert sha256_file(root / name) == digest, name

def read(label, name):
    return json.loads((root / label / name).read_text(encoding='utf-8'))

for label, count in [('layout02', 0), ('layout03', 0), ('stance01', 12), ('baseline_air02', 2)]:
    audit = read(label, 'audit.json')
    assert audit['closed'] and len(audit['env_steps']) == count and audit['force_timing'] is False
    assert len(audit['body_disable_gravity']) == 31 * len(audit['initial']['backend_link_poses'])
    assert all(audit['body_disable_gravity'].values()) and audit['fixed_base']
    assert audit['max_joint_stiffness'] == audit['max_joint_damping'] == 0.
    raw = root / label / 'source_raw_at_review.py'
    if not raw.exists():
        raw = root / label / 'source.py'
    assert sha256_file(raw) == audit['source_sha256']
    assert raw.read_text(encoding='utf-8') == (root / label / 'source.py').read_text(encoding='utf-8')
    if 'observer_sha256' in audit:
        assert sha256_file(root / label / 'observer.py') == audit['observer_sha256']

report = read('layout02', 'report.json')
urdf = Path(report['target_binding']['urdf'])
assert sha256_file(urdf) == 'e8896feb8b0dbdbeaa35e74a01c2ffcb4ab38d89b52f221831b3f287943edd00'
assert all(not any(map(float, joint.find('origin').get('rpy', '0 0 0').split()))
           for joint in ET.parse(urdf).getroot().findall('joint') if joint.find('origin') is not None)
model = c.load_urdf(urdf)
expected = {name for name in model['joints'] if name[:2] in ('lf', 'rf', 'rl', 'rr')}
expected |= {'chest_pitch_joint', 'neck_yaw_joint', 'neck_pitch_joint', 'tail1_yaw_joint', 'tail3_pitch_joint'}

def audit_layout(value):
    assert value['mode'] == 'kinematics_only' and value['inject_rad'] == .001
    assert len(value['fk']) == len(expected) == 25
    assert {row['joint'] for row in value['fk']} == expected
    assert len(value['action_names']) == len(value['joint_names']) == 30
    assert set(value['action_names']) == set(value['joint_names'])
    errors = np.zeros(2)
    for row in value['fk']:
        turn, delta = np.array(row['turn_rad']), np.array(row['endpoint_delta_m'])
        assert turn.shape == delta.shape == (3,) and np.isfinite(turn).all() and np.isfinite(delta).all()
        spec = model['joints'][row['joint']]
        axis = c.fk(model['joints'], spec['parent'], {})[:3, :3] @ spec['axis']
        axis = axis / np.linalg.norm(axis) * value['inject_rad']
        moved = c.fk(model['joints'], row['endpoint'], {row['joint']: value['inject_rad']})[:3, 3]
        zero = c.fk(model['joints'], row['endpoint'], {})[:3, 3]
        errors = np.maximum(errors, [np.abs(turn - axis).max(), np.abs(delta - (moved - zero)).max()])
    assert np.isfinite(errors).all() and errors.max() < 1e-5, ('numeric disagreement', errors)
    return errors.tolist()

for label in ('layout02', 'layout03'):
    print('LAYOUT_FK_OK', label, audit_layout(read(label, 'report.json')))
bad = copy.deepcopy(report)
bad['fk'].pop()
nan = copy.deepcopy(report)
nan['fk'][0]['turn_rad'][0] = float('nan')
for value in (read('layout01', 'report.json'), bad, nan):
    try:
        audit_layout(value)
    except AssertionError:
        pass
    else:
        raise AssertionError('damaged/old report was accepted')

audit = read('stance01', 'audit.json')
column = audit['action_names'].index('lf_shoulder_twist_joint')
joint = audit['joint_names'].index('lf_shoulder_twist_joint')
errors = []
for i, row in enumerate(audit['env_steps']):
    phase, point = divmod(i, 3)
    fraction = point / 2.
    target = .001 * (fraction, 1. - fraction, -fraction, fraction - 1.)[phase]
    action = np.array(row['action'])
    backend = np.array(row['after']['backend_joint_target_rad'])
    cached = np.array(row['after']['joint_target_rad'])
    assert np.isfinite(action).all() and np.isfinite(backend).all() and np.isfinite(cached).all()
    assert np.abs(np.delete(backend[0], joint)).max() == 0.
    errors.append(max(abs(action[0, column] - target), abs(backend[0, joint] - target),
                      float(np.abs(backend - cached).max())))
assert max(errors) < 1e-8
print('STANCE_TARGET_OK', column, joint, max(errors))
for path, expected_count in [('ownership_air01/exit.txt', 0), ('ownership_air02/exit.txt', 0),
                             ('ownership_air03/exit.txt', 1), ('layout_missing_twist_exit.txt', 1),
                             ('ownership_budget01_exit.txt', 1), ('layout02_exit.txt', 0),
                             ('layout03_exit.txt', 0), ('stance01_exit.txt', 0),
                             ('baseline_air02_exit.txt', 0)]:
    assert int((root / path).read_text().strip()) == expected_count
assert read('ownership_air03', 'report.json')['status'] == 'FAIL'
assert not read('ownership_floor02', 'report.json')['touching']

for path in ('rl_exp/tools/verify/check_joint_layout.py', 'rl_exp/tools/diagnose/stance_step_probe.py'):
    before = ast.parse(subprocess.check_output(['git', 'show', '8cd5102:' + path], text=True))
    after = ast.parse(Path(path).read_text(encoding='utf-8'))
    def loops(tree):
        found = []
        for node in sorted((node for node in ast.walk(tree) if isinstance(node, (ast.For, ast.While))),
                           key=lambda node: node.lineno):
            if any(isinstance(item, ast.Call) and isinstance(item.func, ast.Attribute)
                   and isinstance(item.func.value, ast.Name) and item.func.value.id == 'env'
                   and item.func.attr == 'step' for item in ast.walk(node)):
                found.append(ast.dump(node, include_attributes=False))
        return found
    assert loops(before) == loops(after)
    print('DEFAULT_DYNAMIC_LOOPS_PRESERVED', path, len(loops(after)))
print('INDEPENDENT_ENTRY_EVIDENCE_REPLAY_OK')
```

## 未覆盖边界

零增益、无重力与受限窗口不证明静站承重、PD 跟踪、限速或动力学安全。布局纯运动学模式不执行原承重组合/驱动阶段，也不作全 ROM 壳碰撞裁决。接触空值须结合真实 backend 位姿核对，不能将“未测到接触”误写为资产无碰撞。接触非零正例、`diagnose_support` 独立入口、旧 shared 消费者扩展边界、旧资产 cap/contact ownership 及最终 D 审核继续按在办路由保留；本记录不关闭 E。
