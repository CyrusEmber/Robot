# lizard2 体高降低与竖直下段隔离候选（2026-10-13）

## 适用范围

### 输入、决定与边界

用户选择降低 **BODY GROUND HEIGHT** 25%，不是压薄机身；保留机身尺寸、颈尾形状、掌形与骨长。新姿态覆盖旧 A1 的角度视觉认可。代码仅 `rl_exp/blender/scripts/lizard2_stance_candidate.py` 新增显式 `--body75_vertical` 分支；旧参数路径不改。未导出 URDF/USD、未训练、未采用、未提交或推送。

实际输入：`rl_exp/blender/lizard2_palm_p2_sample_claw_all_lowered/sample_neutral.blend`；不是根据旧文件名或 JSON 假定姿态。编辑前真实 Blender 预检输出全部 rest bones 与网格 ground minima。唯一无父 root 为 `base_link`。

## 验收条件

固定最新源的 root/ground 量法；高度比例、骨长、rigid vertices、掌形与sole、下段实际骨与caps竖直、绑定与镜像均须在 float32 算术界限内；实际错高度/倾斜下段必须被拒。旧选项回归不退化；仅隔离输出，源/采用/冻结产物 hash 不变。几何自检不授予外观/碰撞/物理接受。

## 结果

### 固定量法与原始证据

体高 = **实际 `base_link` 世界 rest head Z − 四个 evaluated 掌底最低 Z 的平均水平面**。旧、新均用同一固定平面；不靠猜 mesh 名，不改参考点抵消降幅。原始 JSON：`rl_exp/blender/lizard2_palm_p2_sample_claw_all_lowered_body75_vertical/measurements.json`。

- 固定 ground Z：−0.9711321443319321 m。
- 旧 root Z：−0.16740000247955322 m；旧体高 0.8037321418523788 m。
- 新体高：0.6027991026639938 m；比值 0.7499999953650102。
- 机身/颈/尾统一刚性 Z 平移：−0.200933039188385 m；无缩放/压薄。
- 旧掌底 Z（lf/rf/rl/rr）：−0.9710970520973206 / −0.9710972905158997 / −0.9711672067642212 / −0.9711670279502869 m。原本非完全共面，ground 偏差依次 +3.509223461151123e−5 / +3.485381603240967e−5 / −3.5062432289123535e−5 / −3.488361835479736e−5 m；保持各掌原 Z，不强行拉齐。
- 腕/踝 XY 可移；lf/rf 向后 0.0928504467010498 m、向外 0.2551044225692749 m；rl/rr 向前 0.09285104274749756 m、向外 0.2551058530807495 m。Z 平移均 0。上段保留旧 sagittal yaw 与 X/Y 符号，固定长度解 Z，下段向量 (0,0,−1)。可达性与机身 floor 相交在修改前检查，不缩骨。

### 真几何与保存重开检查

保存 `sample_neutral.blend` 后实际重开，独立比较最新源快照的 evaluated vertices、rest head/tail、父子/绑定、长度、掌根与 cylinder caps、水平 ground、上段 yaw/sign、镜像；不以 pose-only 改动当 rest。

| leg | 下段骨相对水平角 deg | 实际 cylinder cap axis deg | 最大四端 cap 残差 m | 掌根残差 m | neutral BVH crossing pairs |
|---|---:|---:|---:|---:|---:|
| lf | 90 | 89.9999677764932 | 1.2460079765538498e−6 | 2.980232238769531e−7 | 7 |
| rf | 90 | 89.99996777648371 | 1.1891089286363127e−6 | 1.6858739404357614e−7 | 7 |
| rl | 90 | 89.99996777636628 | 5.470979139413184e−7 | 3.816559456248789e−7 | 9 |
| rr | 90 | 89.99995187154931 | 4.6932744228910274e−7 | 5.623090941939713e−7 | 9 |

所有长度最大残差 1.1980795988630888e−7 m；非腿 evaluated vertices 对统一平移最大残差 4.777820964108429e−7 m；掌形刚性平移最大残差 5.196212462831347e−7 m。neutral 镜像最大 9.019819468511079e−7 m；同角镜像运动最大 1.1246181883879427e−6 m。镜像轴仍按 axial-vector `−R axis`。检验界限仅 64 float32 ulps × max(1,坐标绝对值)，没有按读数反推解剖容差。

非腿最低 vertex 对 floor 净空 0.2516508549451828 m。仅获准 elbow/wrist/knee/ankle −10/0/+10，共 24 个单关节 evaluated snapshots；逐 vertex 真刚性运动与同角左右镜像通过，连接残差逐项保存在 JSON。

**碰撞未通过**：24/24 下段 cylinder/palm snapshots 仍有 BVH 表面交叉，pair count 7–10。没有穿透深度、containment、全机 self-collision 或动力学结论；未裁切、缩球、过滤碰撞或新增接受规则。body floor 净空不能代替全身碰撞验证。此项继续停 P2，不进 P3。

### 真实负例、消费者与保护

- 实际修改 root rest head/tail 回旧体高，拒绝于 `body ground height not 75%`。
- 同时倾斜左右前下段实际 rest tail，拒绝于 `lower leg not vertical: lf`，目标判据先于 mirror/网格检查，未被镜像错误掩盖。
- 修改→拒绝→恢复→通过，在生成和 check-only 内执行。`--regression_without_fix` 将真实旧体高回填，进程 exit 1；恢复构建 exit 0。
- P1 真实 `generate_urdf.py --robot lizard2_palm_contract --contract_check --memory_scene` 消费内存场景，四个原生末端 binding 通过；未导出。
- 521 个源/此前 Blender 工件/采用资产/冻结版本/导出 mesh 文件 SHA256 before=after；cfg_lock 仅 hash bytes，不读正文。完整清单在 JSON。旧 halfpad、claw、四肢低掌只读。
- 新精确目录仅加本地 `.git/info/exclude`；二进制、图像与 JSON 不 staging。

## 证据引用

### 命令与退出码

以下实际执行，Windows cmd，Blender 5.2.2 LTS：

```cmd
"E:\SteamLibrary\steamapps\common\Blender\blender.exe" --background --factory-startup --python-exit-code 1 --python rl_exp\blender\scripts\lizard2_stance_candidate.py -- --p2_sample --palm_shape claw --all_legs --sole_at_ball_bottom --body75_vertical --output_dir E:/Robot/rl_exp/blender/lizard2_palm_p2_sample_claw_all_lowered_body75_vertical --diagnostic_angles=-10,0,10
```

exit 0；构建、真实 mutations、24 snapshots、消费者、save/reopen、四图、保护 hash 完成。输出存在时拒绝覆盖；复读加 `--check_only` 不写文件（exit 0）。本轮只清理并重建自己刚生成的精确六工件目录，断言目录文件集合后删除；无旧产物删除。

同上述 check-only 命令加 `--regression_without_fix`：exit 1（预期真实 height 负例）。同 check-only 入口去除 `--body75_vertical` 并分别参数为默认 halfpad / `--palm_shape claw` / `--palm_shape claw --all_legs --sole_at_ball_bottom`：exit 均 0；旧实际 geometry regressions 保持通过。subprocess 汇总：`[('body75_fail_before',1,1),('halfpad',0,0),('claw',0,0),('four_low',0,0),('body75_pass_after',0,0)]`，外层 exit 0。

编译使用 `"E:\IsaacLab\env_isaaclab\Scripts\python.exe" -B -c "from pathlib import Path; compile(Path('rl_exp/blender/scripts/lizard2_stance_candidate.py').read_text(encoding='utf-8'),'rl_exp/blender/scripts/lizard2_stance_candidate.py','exec')"`：exit 0；`git diff --check`：exit 0。`"E:\IsaacLab\env_isaaclab\Scripts\python.exe" -B rl_exp\tools\verify\check_work_docs.py`：初次 exit 1（新记录缺五节标准标题），修正后 exit 0，`WORK_DOCS_OK (86 item file(s))`。未跑完整 hook，由父执行者处理。

开发中两次实际 check-only 失败（exit 1）：误以为 cylinder 有 64 vertices，改为真实两 cap polygon 识别；nested evaluated `to_mesh` 清理造成 `ReferenceError: StructRNA of type Mesh has been removed`，改为同 mesh 直接取世界 vertices。随后 check-only/生成通过。角度读数改用 `atan2(vertical,horizontal)`，避免 float32 normalized Z 的 asin 假偏差；未放宽几何断言。

### 非腿真实姿态纠偏复验（本轮替代此前相关审核结论）

**根因**：body75 分支曾将全部 `pose.matrix_basis` 归零，再把 bone-parented object 的 `matrix_world` 设回旧 evaluated 目标变换；重新挂接的世界矩阵补偿使 mesh residual 通过，掩盖非腿实际关节 frame 被改动。此前审核由 mesh 残差推断“源非腿 pose 为 identity”是未经验证的经验假设，现明确撤回。父执行者 Blender 源探测和本轮源快照均证实：11 根非腿骨中 `tail1_pitch` 的 basis identity 最大残差 **0.19801978766918182**，不是 identity。

修补仅 body75 当前函数：只归零四条重建腿链的 16 根骨，不碰非腿 pose channels。不能把非腿 basis 重新赋回作为“精确保留”：真实试跑发现 Blender matrix_basis setter 的分解/重组会使 `tail1_pitch` 出现浮点变化，首次修补 check-only 因 `nonleg pose basis changed: tail1_pitch` exit 1；改为完全不赋值后通过。负例恢复直接使用原始 location/scale/rotation channels。

当前 JSON 的 `nonleg_pose_preserved` 保存每根源/新 basis、evaluated world head/tail 与 3×3 axes、源/新 pose-minus-rest offset；在修改、真实负例恢复、24 转动恢复和 **save/reopen 后**执行同一源快照对比。非腿 basis 逐值最大差 **0**；world axes 最大差 **0**；head/tail 对 delta 的最大残差各 **2.9802322387695312e−8 m**。`nonleg_object_positions` 的 evaluated world origin 平移最大残差 **2.5466564101445526e−7 m**，逐 vertex 平移检查仍通过。

`root_rest_vs_actual`：源 rest/actual height 均 **0.8037321418523788 m**；新 rest/actual 均 **0.6027991026639938 m**；两侧 actual-minus-rest 均 **0**，actual 比值 **0.7499999953650102**。固定源 rest reference 与原地面不变，delta Z **−0.200933039188385 m**。当前四条下段 evaluated 骨均 **90°**，不是仅 rest 角。

**继承偏置不冒充修好**：源尾部非零 pose 导致尾二/三 evaluated head 与 rest head 存在真实偏置，`tail3_pitch` 为 `[0.019387245178222656, -0.00019775796681642532, 0.19388218224048615] m`。原样继承，未归零、未重新定义参考、未宣称原始模型解剖对齐；object origin 与 joint head 的源偏置也逐对象保存在 JSON，origin 不等同 mesh 关节几何点。此次证明“不新增 frame/mesh 相对变化”，不能证明源几何原本无错位。

真实负例将源非零 `tail1_pitch.matrix_basis` 设 identity，先拒于 **`nonleg pose basis changed: tail1_pitch`**，不是体高或其它断言；恢复后通过。另曾暂时撤回只清腿链的修补、恢复旧全 pose reset，新增回归确实 exit **1** 并命中同一 pose 断言；重新应用修补后当前正例通过。无需源 identity guard。

**本轮实际命令/退出码**：上方 Blender check-only 命令 exit **0**；加 `--regression_without_fix` exit **1**（预期 height 负例）；不带 body75 的 halfpad / claw / four_low 各 exit **0**，subprocess 汇总 `body75 0; height_inverse 1; halfpad 0; claw 0; four_low 0`，外层 exit **0**。仅核验本轮旧目录的六文件集合及逐文件 SHA256 后删除重建该精确目录，上方生成命令 exit **0**：三真实负例、24 转动、消费者、save/reopen、四图全部完成。521 个保护文件 before=after；所有此前源与旧分支工件未修改。此前 hooks 绿不算此次复验，最终 hooks 由父执行者处理；不 commit/push。

当前 SHA256：

| 文件 | SHA256 |
|---|---|
| 源 `rl_exp/blender/lizard2_palm_p2_sample_claw_all_lowered/sample_neutral.blend` | `19ca32ddf78056098e33ddb7382a12f655478745c6ba361ab00c17db7883b26a` |
| `rl_exp/blender/scripts/lizard2_stance_candidate.py` | `a72d35e88a1e903e5e4b583e68207c9b408b2de62ce5cdf5710e183ed200f813` |
| 新目录 `sample_neutral.blend` | `4f286a0cc1d7a5a00db99ef0e30e0375f372f44dd6f805379664e5c563b83016` |
| 新目录 `measurements.json` | `8a1f7d605d85a7988ad84276c56001a67ed792b7ec1d489f2edb872009561ef6` |
| 新目录 `full_side_ground.png` | `b6678e7aba775098d01ebe8277fa42c5c8894ce1ab0e2a45f1ba17099b59e3ce` |
| 新目录 `full_front_ground.png` | `b16d28105eeeaa392c50db26ea0355921cd541226cdb339b594da2628d168924` |
| 新目录 `full_oblique_ground.png` | `6e55e5f5959f7f04cc033013cb6d134555dd70d448be29d8f4c82f53a0060e37` |
| 新目录 `full_top.png` | `ca783bc5cc474007842773c1ab74187a9f131fb9fa18303fca072bf618972fe4` |

### 本地交付

模型：`rl_exp/blender/lizard2_palm_p2_sample_claw_all_lowered_body75_vertical/sample_neutral.blend`。

四图（不超过六）：同目录 `full_side_ground.png`、`full_front_ground.png`、`full_oblique_ground.png`、`full_top.png`。侧/前图有真实固定 ground 的橙色 cross-line；诊断 camera/floor/cross 在 save 后添加，不进入 robot blend。侧图已实读检查全身与 ground 可见，前图全身同样不裁切。

## 未覆盖边界

待用户看新姿态；新上下文复核实际几何和未验碰撞。尚无外观/容差/物理接受，不关闭事项。未做 P3 导出/USD、完整 ROM/周期/全身碰撞、训练或采用。

### 父执行者最终复读与提交前闸门

最终修补后，父执行者独立以实际 Blender 运行上述 `--check_only --regression_without_fix`，退出 1 且命中 `body ground height not 75%`；同一入口去掉 inverse，退出 0。正反例前后核对新目录六个工件 SHA256 完全相同；最终 JSON 的实际 root 比例、四肢倾角及非腿 basis 保留读数与上述纠偏记录一致。已实读最终侧视、前视与斜视图；未把目视当碰撞接受。

以下实际提交前命令全部退出 0；既有 fork dirty、退休版本 tag 与限速警告保留，不解释为物理能力通过：

```cmd
python rl_exp/tools/verify/check_suite_banners.py
"E:\IsaacLab\env_isaaclab\Scripts\python.exe" -B rl_exp/tools/verify/framework_pin_check.py --strict --self-test
"E:\IsaacLab\env_isaaclab\Scripts\python.exe" -B rl_exp/tools/verify/check_dr_parity.py --strict
"E:\IsaacLab\env_isaaclab\Scripts\python.exe" -B rl_exp/tools/verify/check_version_docs.py
"E:\IsaacLab\env_isaaclab\Scripts\python.exe" -B rl_exp/tools/verify/check_work_docs.py
"E:\IsaacLab\env_isaaclab\Scripts\python.exe" -B rl_exp/tools/verify/check_obs_protocol.py --live
git diff --check
```

