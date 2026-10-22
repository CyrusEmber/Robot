# E 非零 gait 映射与碰撞构姿修补

## 适用范围

用户要求继续修复 `lizard2-candidate-wiring`。承接[baseline terminal 切片](2026-10-22-lizard2-e-baseline-terminal.md)，补真实 gait writer 的非零列证据，并在 E3 清点中修复碰撞构姿仍沿旧位次的问题。新增专用入口 `palm_gait_wiring.py`，生产 `gait_probe.py`、绘图实现、正式资产/v3、PD、训练和冻结协议均未修改。

物理仅一个固定根、31 body 禁重力、零增益环境的四个控制步（0.08 s 采集窗），一次启动，无自动物理重试。时序保持实际 `enable_external_forces_every_iteration=False`。通过受限包装器复用真实 gait CLI：在每步正常物理推进前注入极小关节状态和动作，原 action manager、物理步进、gait 采集及 writer 均照常执行。它是数值/列映射诊断，不是学习策略或步态成功。

碰撞共享文件开始时无并行改动，本轮只修改 `check_self_collision.sweep_poses()` 的 spatial 构姿选择；不改 FK 核心、网格、阈值或旧命名行为。E3 出口表是本轮清点，不代替新上下文关闭审核。

## 验收条件

- 实际 runtime/action 顺序分别留存，独立 backend q/dq/position target 与缓存对照；腿五角色和胸颈尾的 90 条保存序列均须对应相同实体，零值不能充当非零证据。
- gait 保持原首次终止前掩码，末帧 reset 后读数不混进有效序列；报告明确动作被诊断注入，不能仍自称零动作策略。
- 原 reader/绘图消费真实新报告；twist 与 elbow 数值互换、速度归零、错目标、删 twist、缺 source 必须被独立值核对或绑定 reader 拒绝。
- 碰撞构姿修复前真实测试失败、修复后通过；当前 URDF 四腿根摆动/真实肘膝配对与完整五轴角点均须存在且不越关节限位。旧 shared/split/palm 的完整姿态列表保持原样，不以样本总数相同证明角色正确。

## 结果

### 真实 gait 非零 writer → reader

输入仍为 `rl_exp/out/lizard2_e_fresh_reset_20261020/measured_manifest.json`，批准 SHA256 `d876713b1a4aa6a4fef51f39bed284f4a15a01d562815eefefcf74eebfb77137`，实际 URDF 为 `e8896feb8b0dbdbeaa35e74a01c2ffcb4ab38d89b52f221831b3f287943edd00`。启动前核 manifest 与 USD/URDF 身份，实际环境核固定根、31 body 禁重力、缓存 Kp/Kd 为零及 false 时序。

四步依次交替正/负号，runtime 状态 `q[i]=sign*(i+1)*0.0001 rad`、`dq[i]=sign*(i+1)*0.0002 rad/s`；输入最大 0.003 rad / 0.006 rad/s。动作按实际 action 顺序用倒序数列，最大 0.0045；所有注入位置及期望目标均在实际限位内。然后走原 `process_action/apply_action/write_data_to_sim` 和四个正常控制步，没有改驱动。

物理后、reset 前独立读取 backend q/dq/position target/velocity target；q/dq/target 缓存差均不超过 `1e-7`，目标按实际 action-name → runtime-name 对应，velocity target 为零。最后一步由原短 episode timeout 触发 done，序列 `[False,False,False,True]`；有效/记录帧均为 3，末帧保持排除，未改原 gait 终止语义。

腿 60 列、胸颈尾 30 列共 90 条序列，前三帧均非零并逐列核对相应 backend。最大保存舍入误差 `4.015700146555758e-6`；现有 writer 保留五位小数，核对预算 `5.1e-6` 仅覆盖该数值舍入，不是机械精度阈值。数值通过不证明零增益跟踪、受载、真实速度精度或有效限速；尤其不解除 false 时序下的速度物理一致性边界。

包装器在写文件前明确标注 `policy_mode=injected_wiring`、`producer_policy_mode=zero` 和 `wiring_probe`，原 producer argv 仍保留；调用方不会把被替换的 raw action 当成原零动作。源码、manifest 快照和全部四步的输入/backend/cache 原始数组存于本轮新目录，不覆盖旧报告。

原 producer 随后仍向 stdout 打印它自己构造的 zero 模式对象；完成判定及复读使用带明确诊断身份的保存文件和 `GAIT_WIRING_COLLECTOR_OK` 标记，不把 stdout 中的 zero 当作实际无注入。

实际磁盘回放退出 0，五反例均拒绝；原 `plot_joints.py` CLI 退出 0，`JOINT_PLOT_OK (palm_spatial)`，生成两张 PNG 和 index 并目视核对。图仍按原限位坐标展示，微小位移肉眼接近零，非零证明取原始数组及独立核对，不能靠图片。twist 原始列完整，原三面板仍选 swing、elbow/knee、wrist/ankle。

### 碰撞构姿实际缺陷与修复

原 `sweep_poses()` 固定 `knee_token=roots[2]`、其它折叠轴 `roots[1:4]`。对 palm_spatial，第三位是 twist、肘膝在第四位、腕踝在第五位，导致根/肘膝配对缺失且组合角点漏末端。单轴样本和总数仍正常，绑定名表和“132 个样本”无法发现它。

先加入回归，修前实际失败列出四腿各两类错选；再只对 `PALM_SPATIAL_NAMING` 将肘膝选为倒数第二位、组合角点包含全部非根轴。三个旧命名保留原路径和顺序；公共函数签名未变。修前捕获完整列表的规范 JSON 指纹，修后保持相同：shared/split 各 132、palm 120，指纹由便携测试固定，不复制到活跃事项。

实际 fresh URDF 再用 Git `9c81a7c` 中修前函数在内存对照：两版总数均 132，但修前四腿的正确根/肘膝配对及完整五轴角点各为零；修后每腿各 9 个，全部值处在 URDF 限位。没有执行 hull overlap 全扫描，不称碰撞安全或全 ROM 通过。

同时用实际 `load_chain/chain_joint_names/straight_hfe/thigh_shank_angle/load_case_angles` 读取新 URDF；折叠只动 elbow/wrist 或 knee/ankle，非零 twist 和组合构姿经过独立树 FK 对照。132 个姿态、四腿相对各自近端父 link 的矩阵最大差 `2.220446049250313e-16`。伸直骨段残差保留原导出截断量级，不修改工程阈值或取超限伸直姿态作为可达工况。

### 全仓检查的历史工件误报

首次完整离线套件退出 1：一项失败、15 项 fail-fast 跳过，31.0 s。`test_no_hand_rolled_quat_yaw()` 用 `rglob` 把正在并行生成的历史 A/B 工件也当源码，命中 `_tmp_support_native_510277d2c2f9_{before,after}.py` 与 `diagnose/out/runs/support-native-ab/20261022-paired/sources/{before,after}.py` 中原诊断器故意保留的错误对照式。原生产文件已有同一对照的例外；这四条路径均由现有 `.gitignore` 声明为临时产物或输出数据。本轮没有修改、删除、迁移或重写这些实验字节，也没有增加它们的路径例外。

先用临时 Git 仓库复现：正常源码只有库调用、错误只在忽略的历史工件中时，原真实扫描入口仍错误失败。随后将该检查的文件枚举改为 Git 的已跟踪文件加未忽略新文件，原匹配公式及生产文件例外不变。便携回归确认忽略的历史数据不误报、未跟踪错误新源码仍被拒、即使在忽略目录中强制跟踪的错误源码仍被拒、无法枚举源码必须失败；快照字节前后一致。修前/修后日志为 `rl_exp/out/lizard2_e_yaw_scope_before_20261022.log` / `lizard2_e_yaw_scope_after_20261022.log`，后者 `YAW_SOURCE_SCOPE_TESTS_OK`。这只是源码扫描边界的行为修复，不作为机器人能力证据；默认套件条数未增加。

### E3 出口清点与仍需补证

| 消费链 | 当前可用证据 | 本轮后的出口边界 |
|---|---|---|
| Blender → URDF → USD | [正式导出切片](2026-10-19-lizard2-a-delivery-plan.md#正式导出与写前拒错切片验收)、[新输入身份/转换/reset](2026-10-15-lizard2-e-spatial-runtime-wiring.md)按原输入与范围复用 | 本轮未重跑 Blender；不将隔离转换等同正式采用 |
| URDF → FK/碰撞构姿 | 本轮 actual fresh 骨段读点、局部 FK、角色修补和真实限位 | 仅构姿/局部 FK，非壳碰撞安全；见下述父系口径 |
| 运行时布局/站姿/gait | 当前独立 obs、baseline、非零 gait 已执行，绑定和动作/末端读回有证据 | `check_joint_layout`、`stance_step_probe` 仍须逐一补当前输入的独立入口证据；前者有至少 100 步及 0.3 rad 的既有全流程，未擅自启动；不能以共享 loader 通过替代其本身执行 |
| 接触与在线协议 | [fresh 接触归属/负例](2026-10-15-lizard2-e-spatial-runtime-wiring.md)、[非零观测](2026-10-22-lizard2-e-live-values-gait.md)、本轮 gait 的实际 `diag_metrics` 消费 | `baseline_probe/check_contact_ownership/diagnose_support` 对当前输入的独立执行证据还需定位或补齐；旧对象 cap/ownership 按 `floor-contact-attribution` 回交，不称其源码未支持新名 |
| 报告 writer → reader/绘图 | baseline 人工 terminal 非零记录、本轮 gait 90 非零序列和真实绘图、绑定/数值反例 | 接口采集连通，不交完整性能协议或学习策略表现 |
| 旧基线 | 三旧命名碰撞样本逐列表不变；gait/plot 生产源码字节不变；默认离线回归覆盖历史绑定 | 旧资产既有 cap 红项保留原归属，不取消或用新候选解除 |

**父系口径缺口**：`chain_joint_names()` 明确只走该腿前缀，前腿止于 `chest_pitch`；当前其零位相对 `base_link` 平移为 `[-0.005,0,0] m`，后腿父系才是 `base_link`。而 `foot_pose()`/`chain_frames()` 部分说明及 CLI 仍称 base_link 坐标。本轮的独立矩阵比较明确先变换到实际父系，不能拿这个一致性证明整机 base_link 输出正确。E 接 A 核对调用方需要局部还是整机坐标，保留原公共接口语义/兼容边界后再修，不能直接把五轴腿链扩成含躯干的链而破坏原调用者。

## 证据引用

本机目录 `rl_exp/out/lizard2_e_nonzero_gait_20261022/attempt01/`，工件不承诺入仓：

| 文件 | SHA256 |
|---|---|
| `report.json` | `6f0e75db97d2e9c19782758d46e974c9837143767f55a1fa3a0df3f6cb0e0cb0` |
| 采集入口 `source.py` / 当前 `palm_gait_wiring.py` | `63ef7ca530a794bf93e7ced6a54e5fa48709bbdb8a4f2b303f088fc1c1024863` |
| 原 producer `gait_probe.py` | `ae3addafe300aa86d7dc3656302c07cc6f596a6dbaf54817d5a86463d7501d8f` |
| `plots/report_index.json` | `d66f6a07e4a07ab8fcd02cb4c683f1516931a91f5cc9a3106228902fc34b3b8f` |

最终碰撞实现 SHA256 `6a1767a7bcdf585cfa184535e367ea74b787c0086758bb142d2f066ab55cec2e`。实际旧三命名样本指纹见 `rl_exp/out/lizard2_e_collision_legacy_before_20261022.log` 与 `test_self_collision_spatial_combined_roles()`。红/绿日志为同目录 `lizard2_e_collision_roles_before_20261022.log` / `lizard2_e_collision_roles_after_20261022.log`；实际 URDF 修前/修后、骨段与局部 FK 明细为 `lizard2_e_collision_fresh_final_20261022.log`，早期局部读数另保留 `lizard2_e_collision_fresh_20261022.log`。

唯一物理启动日志 `rl_exp/out/lizard2_e_nonzero_gait_20261022_attempt01.log`；磁盘回放/五反例 `lizard2_e_nonzero_gait_replay_20261022.log`；绘图 `lizard2_e_nonzero_gait_plots_20261022.log`；便携非零 fixture `lizard2_e_nonzero_gait_test_20261022.log`。便携 fixture 的 runtime/action 顺序特意不同，不用 fixture 冒充上面的真实采集。

最终完整套件退出 0：`ALL_OFFLINE_CHECKS_PASSED (37/37 in 51.4s, jobs=6)`，日志 `rl_exp/out/lizard2_e_nonzero_gait_offline_final_20261022.log`；保留首轮误报日志 `lizard2_e_nonzero_gait_offline_20261022.log`，未改写为通过。本轮路径 diff 格式通过；记录内构姿/骨段/局部 FK 复读代码已直接执行，`FRESH_COLLISION_ROLE_REPLAY_OK`，日志 `lizard2_e_collision_retained_replay_20261022.log`。提交前钩子按仓库流程另行执行。

代码提交 `5891f67` 仅含本轮新诊断入口、碰撞构姿修补及 `test_baseline_contract.py`；显式提交前钩子和 commit 内正常钩子均退出 0，日志 `rl_exp/out/lizard2_e_gait_collision_precommit_code_20261022.log`、`lizard2_e_gait_collision_commit_code_20261022.log`。记录与对应事项指针另笔同次提交，不包含其它事项文件。

从仓根复读，不启动物理：

```powershell
& E:/IsaacLab/env_isaaclab/Scripts/python.exe -B rl_exp/tools/diagnose/palm_gait_wiring.py --replay rl_exp/out/lizard2_e_nonzero_gait_20261022/attempt01/report.json --approved_report_sha256 6f0e75db97d2e9c19782758d46e974c9837143767f55a1fa3a0df3f6cb0e0cb0
& E:/IsaacLab/env_isaaclab/Scripts/python.exe -B rl_exp/tools/verify/test_baseline_contract.py --binding-only
& E:/IsaacLab/env_isaaclab/Scripts/python.exe -B rl_exp/tools/diagnose/plot_joints.py --report rl_exp/out/lizard2_e_nonzero_gait_20261022/attempt01/report.json --out_dir rl_exp/out/lizard2_e_nonzero_gait_plots_replay
```

显式重采集必须换不存在的 out，仍只限相同四步条件，无自动物理重试：

```powershell
& E:/IsaacLab/env_isaaclab/Scripts/python.exe -B rl_exp/tools/diagnose/palm_gait_wiring.py --manifest rl_exp/out/lizard2_e_fresh_reset_20261020/measured_manifest.json --approved_manifest_sha256 d876713b1a4aa6a4fef51f39bed284f4a15a01d562815eefefcf74eebfb77137 --out rl_exp/out/lizard2_e_nonzero_gait_replay/new01
```

实际 URDF 构姿修前/修后复读（保留 Git 源入口，不依赖删除后的临时脚本）：

```powershell
@'
import ast
from pathlib import Path
import numpy as np
from rl_exp.tools.verify import check_self_collision as c, check_leg_reachability as r
from rl_exp.tools.runrecord import binding
p,n,_=r.diagnostic_urdf(Path('rl_exp/out/lizard2_e_fresh_reset_20261020/measured_manifest.json'),None,'palm_spatial')
j=c.load_urdf(p)['joints']
source=binding.git_run(Path('.'),'show','9c81a7c:rl_exp/tools/verify/check_self_collision.py')
node=next(x for x in ast.parse(source).body if isinstance(x,ast.FunctionDef) and x.name=='sweep_poses')
scope=vars(c).copy()
exec(compile(ast.Module(body=[node],type_ignores=[]),'pre-fix sweep','exec'),scope)
old,new=scope['sweep_poses'](j,n),c.sweep_poses(j,n)
assert len(old)==len(new)==132
for leg in r.joint_names.LEGS:
    names=r.chain_joint_names(p,leg,n)
    count=lambda cases,keys: sum(kind=='combined' and set(q)==keys for q,kind in cases)
    for keys in ({names[0],names[-2]},set(names)):
        assert count(old,keys)==0 and count(new,keys)==9
    chain=r.load_chain(p,leg,n)
    parent=j[names[0]]['parent']
    error=0.
    for q,_ in new:
        local=np.asarray(r.chain_frames(chain,[q.get(name,0.) for name in names])[-1])
        other=np.linalg.inv(c.fk(j,parent,q)) @ c.fk(j,r.joint_names.end_link(leg,n),q)
        error=max(error,float(abs(local-other).max()))
    assert error<1e-12
    straight=r.straight_hfe(chain)
    angles=[0.]*len(chain); angles[-2]=straight
    print(leg,'local FK error',error,'straight residual deg',r.thigh_shank_angle(chain,angles),'fold',r.load_case_angles(chain,n)['fold'])
assert all(j[name]['limits'][0]<=value<=j[name]['limits'][1] for q,_ in new for name,value in q.items())
print('FRESH_COLLISION_ROLE_REPLAY_OK')
'@ | & E:/IsaacLab/env_isaaclab/Scripts/python.exe -B -
```

## 未覆盖边界

本轮不证明零增益或当前默认 PD 的任意姿态跟踪、受载、接触安全、速度物理精度、限速、步态或训练性能。碰撞有限构姿和 chain-local FK 不代替实际几何 clearance 全流程或整机 base_link 坐标口径；独立入口缺证按上表补，不把全局离线绿当它们都已执行。

事项保持 `in_progress`，E3 表内缺口、旧对象回交和 B/C/D/S5/S6 原职责继续保留。没有提交候选采用或事项关闭审核。
