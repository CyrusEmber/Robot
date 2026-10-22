# E 旧对象 cap 校准与接触处罚回交

## 适用范围

接续 [旧工具出口表](2026-10-22-lizard2-e-legacy-exit.md)，只处理旧 adopted shared 及 2026-10-13 同几何 shared/split 样本。当前 palm_spatial 的腕/踝实体与旧 split 的无碰撞中间腕/踝不是同一对象。本记录为执行者自检，E/D 的独立出口审核仍待完成。

## 验收条件

- cap 修复须说明校准对象，保留历史平板/穹面数值与原失败；不得改网格、阈值或冻结配方来过闸。
- 原对象的真实 ownership CLI 做负/正对照，读取已解析处罚集合、live USD collider 与 URDF；非零接触须由精确 body→ground 过滤力核实。
- 对照只改隔离配置中的空处罚选择；绑定源、资产、驱动、采样预算、实际退出码与报告可复读。全部相关仓库检查通过后提交。

## 结果

### cap 的失败来自过期校准对象

`gait_probe --self-check` 在原实现退出 1：按当前 lizard2 声明读到后脚 2 mm cap `0.11928214877843857 m²`，仍要求 `0.013352 m²`。9 月穹面修复及家族隔离归 [历史记录](2026-09-28-lizard2-foot-hull-and-asset-isolation.md)；[10 月正式采用](2026-10-08-lizard2-v3-landing.md)明确原样采用候选 URDF/USD/meshes，家族树换至 `lizard2_candidate/meshes`。当前后脚平板由该已采用输入带来，不能据 9 月断言判当前资产损坏。

修复将历史校准固定到原共享 `rl_exp/meshes` 与历史 `versions/lizard2/meshes` 的 rl 网格，仍分别要求 `0.119282/0.013352 m²`、误差 `<1e-6`。当前家族解析必须落到不同真实目录；当前逐脚 cap 单独输出：lf/rf `0.013351869/0.013351872`，rl/rr `0.119282149/0.119282328 m²`。没有改任何资产或面积阈值，也没有把当前几何读数当作承重能力。

真实 CLI 修复后退出 0；新增回归执行实际校准函数，原源码失败、修复后通过。破坏测试分别将家族解析串树、历史穹面换平板、裁剪结果全置零，三者均失败。原解析退化检测与历史几何数值控制均保留。

### 三个原资产的真实接触对照

新诊断观察器 `legacy_contact_wiring.py` 仅接受以下三组原始 URDF/USD digest，实际运行生产者 `check_contact_ownership.py`，不改变生产者的数据或判词：

| 对象 | URDF SHA-256 | USD SHA-256 |
|---|---|---|
| adopted shared | `da05432efd5d3c3dd9302682286825869b289d5f912cb5703bd0d32642e0c52b` | `fceaf55be1f045572121c464cb32e1eb0ae7d5d0ba63dfbe9a0d943f84df3b6c` |
| 10-13 shared | `9c57fbb7af1558c7da86d19650c5a6bd28fdaafcd27b1517f0ff31db09baf1c7` | `cce0989b30fb642138aa8a20752a1d5042ed6499417ee70319135dc40c1fde6d` |
| 10-13 split | `d758c56f69f7eb3d65684db37ca49f249630777c2757448ec47f3ae385e7aecd` | `dc41586cf31eb89a38f69e2157804b78c8b009a823de6a212e47e22db9ac95a6` |

直接用正式路径配 diagnostic manifest 的首轮 before/after 都被 loader 的隔离保护拒绝，退出 1、无测量报告，不能计为接触负例。随后把正式 URDF/USD 及其引用网格按字节复制到本轮 `formal_asset/`，SHA 与原件相同；有效正式对象对照使用 `formal_isolated_*`。未绕过入口保护。

有效六次运行均为 `Lizard2-Flat-Play-v3`，1 env，30 joints/31 bodies/22 actions，零 action；初始化之后 60 control/240 physics steps。保留原 free base、重力开启、自碰撞关闭、腿 PD 800/40、脚 200/12、躯干 400/20；实际 stage force timing 为 **False**。传感器每个 physics step 更新，历史覆盖 decimation 4，lazy update False。启动初始化步不计入该观察窗口，观察器不注入状态或额外物理步。

| 对象 | 原选择：退出码/报告 | 隔离修正：退出码/报告 | 空项 |
|---|---|---|---|
| shared | 1 / FAIL | 0 / PASS | 四个 `*_kfe` |
| split | 1 / FAIL | 0 / PASS | 前 `*_wrist`、后 `*_ankle` |
| adopted shared 字节相同隔离副本 | 1 / FAIL | 0 / PASS | 四个 `*_kfe` |

原负例均只有 `every penalty body carries a collider` 失败。实际 USD 与 URDF 都无这四个 collider，不能把永远为零的通道当作有效处罚。修正 manifest 仅覆写 `rewards.undesired_contacts.params.sensor_cfg.body_names` 为原四个 hfe 对应实体：shared 的 `lf/rf/rl/rr_hfe`；split 的 `lf/rf_elbow, rl/rr_knee`。`base_link` 腹部项及权重不变。没有添加或迁移碰撞体，没有把旧无 collider 腕/踝换成新空间候选的承重实体。正式冻结 YAML 保持原样，默认正式选择的已知失败没有被宣称消除；隔离修正是后续采用时的具名配置参考。

每次读取 18 个实际 collider owner 的精确一行一地面过滤 view，检查 native sensor/ground 路径、行列计数、矩阵形状与有限性。四足端峰值（lf/rf/rl/rr）均为 `1291.596/1393.894/1982.381/1931.628 N`；shared 末端 `*_foot`，split 前 `*_finger`、后 `*_toe`。其余体在本窗口为零；全部原生 net force 与对应 ground-filtered force 逐样本一致。报告与 observer 的 physics 峰值一致，18 行 live USD/URDF extent 全匹配。每组前后完整 physics force 数组、初始/最终 q 相同，证明观察到的选择修正没有改变本次物理轨迹。

完整 `offline_suite.py` 37/37，通过用时 56.5 s；baseline 合并检查 22.1 s，obs protocol 23.9 s，保留原 25 s 单项预算与 37 条棘轮。已暂存本轮源码后执行 `git hook run pre-commit`，静态闸门全通过；work 为 30 active/61 closed、178029/180000 bytes。证据复读输出 `LEGACY_CONTACT_EVIDENCE_REPLAY_OK`。这是共享工作树上的检查，其他会话未提交改动不纳入本轮提交；格式通过不代替独立审核。

## 证据引用

- 代码提交：`08b99b8`（本轮三个源码/测试文件）；记录与事项指针随后同次提交。
- 本轮本机制品根：`rl_exp/out/lizard2_e_legacy_contact_20261022/`。`artifact_digests.json` 覆盖 111 个输出、101 个输入；SHA-256：`378cee72ef841ea02862926f566ab9d1537943ad3d44d63184dec92da7160548`。输入包括实际三对资产及引用网格、冻结 v3 YAML、家族声明、生产者/观察器源码；输出包括原失败、回归红绿、六组真实报告、audit、退出码、源件字节快照，以及首轮路径拒绝。制品未承诺入 Git。
- cap：`cap_before/after.log` 与同名 `.exit`，`cap_regression_before/after.log`；源码 `gait_probe_before.py`、`gait_probe_release.py`，测试 `contract_release.py`。
- 接触：`shared_before/after`、`split_before/after`、`formal_isolated_before/after` 目录内 `source.py/observer.py/invocation.json/audit.json/report.json`，根目录同名 `.log/.exit`。shared/split 原 manifest 仍取 `rl_exp/out/lizard2_e_20261013_final/`；修正 manifest 与正式对象隔离 manifest 留在本轮根。
- 重跑例子（输出须换新目录；共享观察窗口不会恢复或覆盖原报告）：

```powershell
& E:/IsaacLab/env_isaaclab/Scripts/python.exe -B rl_exp/tools/diagnose/gait_probe.py --self-check
& E:/IsaacLab/env_isaaclab/Scripts/python.exe -B rl_exp/tools/diagnose/legacy_contact_wiring.py --target_config rl_exp/out/lizard2_e_legacy_contact_20261022/split_after.json --out rl_exp/out/lizard2_e_legacy_contact_recheck
```

在仓根执行下列 Python 只读复读，逐项核对身份和原始采样，不启动 Kit：

```python
from pathlib import Path
import json
import xml.etree.ElementTree as ET
import numpy as np
from rl_exp.tools.runrecord.binding import sha256_file

root = Path('rl_exp/out/lizard2_e_legacy_contact_20261022').resolve()
index = root / 'artifact_digests.json'
assert sha256_file(index) == '378cee72ef841ea02862926f566ab9d1537943ad3d44d63184dec92da7160548'
digests = json.loads(index.read_text(encoding='utf-8'))
assert len(digests['files']) == 111 and len(digests['inputs']) == 101
for name, digest in digests['files'].items():
    assert sha256_file(root / name) == digest, name
for name, digest in digests['inputs'].items():
    assert sha256_file(Path(name)) == digest, name
assert (root / 'cap_before.exit').read_text().strip() == '1'
assert (root / 'cap_after.exit').read_text().strip() == '0'
assert 'AssertionError' in (root / 'cap_regression_before.log').read_text(encoding='utf-8')
assert (root / 'cap_regression_after.log').read_text(encoding='utf-8') == 'PASS'
formal = Path('rl_exp/lizard2_candidate').resolve()
copy = root / 'formal_asset'
for path in copy.rglob('*'):
    if path.is_file():
        assert sha256_file(path) == sha256_file(formal / path.relative_to(copy))
for case in ('shared', 'split', 'formal_isolated'):
    audits = []
    for phase in ('before', 'after'):
        name = case + '_' + phase
        audit = json.loads((root / name / 'audit.json').read_text(encoding='utf-8'))
        report = json.loads((root / name / 'report.json').read_text(encoding='utf-8'))
        manifest = json.loads(Path(audit['manifest']).read_text(encoding='utf-8'))
        assert audit['closed'] and audit['env_steps'] == 60 and len(audit['physics_steps']) == 240
        assert audit['decimation'] == 4 and audit['force_timing'] is False
        assert audit['gravity_enabled'] and not audit['fixed_base'] and not audit['self_collisions']
        assert len(audit['joint_names']) == 30 and len(audit['body_names']) == 31
        assert len(audit['action_names']) == 22 and len(audit['ground_contact_mapping']) == 18
        assert sha256_file(root / name / 'source.py') == audit['source_sha256']
        assert sha256_file(root / name / 'observer.py') == audit['observer_sha256']
        assert sha256_file(Path(audit['manifest'])) == audit['manifest_sha256']
        assert sha256_file(Path(manifest['target_binding']['urdf'])) == audit['urdf_sha256']
        assert sha256_file(Path(manifest['target_binding']['target'])) == audit['usd_sha256']
        names = audit['sensor_body_names']
        assert [p.rsplit('/', 1)[-1] for p in audit['native_sensor_paths']] == names
        net = np.array([p['net_forces_w_n'] for p in audit['physics_steps']]).reshape(240, 31, 3)
        assert np.isfinite(net).all()
        for row in audit['ground_contact_mapping']:
            assert row['sensor_paths'] in ([row['source']], [[row['source']]])
            assert len(row['ground']) == 1 and row['filter_paths'] in (row['ground'], [row['ground']])
            ground = np.array([p['ground_forces_w_n'][row['body']] for p in audit['physics_steps']])
            assert ground.shape == (240, 1, 1, 3) and np.isfinite(ground).all()
            assert np.array_equal(ground.reshape(240, 3), net[:, names.index(row['body']), :])
        peaks = np.linalg.norm(net, axis=-1).max(axis=0)
        expected_feet = set(manifest['target_binding']['end_links'].values())
        assert set(report['touching']) == expected_feet and not report['blind']
        assert {n for n, p in zip(names, peaks) if p > report['threshold']} == expected_feet
        assert all(row['extent_match'] for row in report['bodies'].values())
        for body, data in report['bodies'].items():
            assert abs(data['peak_n'] - peaks[names.index(body)]) <= .00051
        selected = set().union(*map(set, report['terms'].values()))
        dead = selected.intersection(report['no_collider'])
        links = ET.parse(manifest['target_binding']['urdf']).getroot().findall('link')
        missing = {link.get('name') for link in links if link.find('collision') is None}
        assert selected.intersection(missing) == dead
        expected_status, expected_exit = ('FAIL', '1') if phase == 'before' else ('PASS', '0')
        assert report['status'] == expected_status
        assert (root / (name + '.exit')).read_text().strip() == expected_exit
        assert report['terms']['belly_contact_force'] == ['base_link']
        if phase == 'before':
            assert len(dead) == 4 and report['problems'] == ['every penalty body carries a collider']
        else:
            assert not dead and not report['problems']
            wanted = {f'{leg}_{roles["hfe"]}' for leg, roles in manifest['target_binding']['roles'].items()}
            assert set(report['terms']['undesired_contacts']) == wanted
        audits.append(audit)
    assert audits[0]['physics_steps'] == audits[1]['physics_steps']
    assert audits[0]['initial_q'] == audits[1]['initial_q'] and audits[0]['final_q'] == audits[1]['final_q']
    before = json.loads(Path(audits[0]['manifest']).read_text(encoding='utf-8'))
    after = json.loads(Path(audits[1]['manifest']).read_text(encoding='utf-8'))
    assert before['sha256'] == after['sha256']
    key = 'rewards.undesired_contacts.params.sensor_cfg.body_names'
    wanted = [f'{leg}_{roles["hfe"]}' for leg, roles in before['target_binding']['roles'].items()]
    assert after['config'][key] == wanted
    assert {k: v for k, v in after['config'].items() if k != key} == before['config']
assert sha256_file(root / 'offline_suite.log') == '6501fc44d28d016fae45dfadbf690e5b3ad249a694348a02145ee150eac413f5'
assert sha256_file(root / 'precommit.log') == '808d67a387a912015d9661d7500c6069b1497aa4798acfa2f55eb3898d1367cf'
print('LEGACY_CONTACT_EVIDENCE_REPLAY_OK')
```

## 未覆盖边界

- 六次原对象对照为短时零动作落地；峰值含初始冲击，不是稳态支撑力，也不证明全 ROM、步态、自碰撞、长期稳定或实际驱动限速。
- hfe/肘/膝和腹部处罚实体确有 live collider，但本窗口未主动把这些实体压地，不声称其处罚函数已由非零非足端接触触发。正式冻结 v3 的空项留为已知原配置问题，后续正式配置迁移须按新版本规则处理。
- 当前 cap 只给网格局部姿态下的带内面积；倾斜、加载后的面积/滑移相关性、COM 接触点速度、切向力方向、穿透容忍度及参数对照继续归 `floor-contact-attribution`，不随本切片消失。
- E 按本记录接旧对象回交，再对照 E3/E4 出口交 D 新上下文审核；本记录不关闭 E、地面接触总项或 B/C/S6。
