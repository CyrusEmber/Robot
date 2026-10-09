# lizard2 rl 脚碰撞网格换代 + 家族资产隔离

- 日期：2026-09-28
- 范围：lizard2 的 `rl_foot_collision` 几何缺陷修复（与"家族网格树按家族声明"这一方案变更**一起验收**）
- 关联：`acceptance/records/2026-09-23-lizard2-v1-gait-skate.md`（⑪ 发现该不对称）、`work/active/floor-contact-attribution.md`

## 适用范围

本次只处理两件事，且不分开验收：

1. **几何修复**：`rl` 脚碰撞 hull 与另三只不同形（平板 vs 穹面），修为 `rr` 的 y 镜像。
2. **资产隔离**：让每个家族消费**自己声明**的网格树，使"修一个家族的几何"不再改写另一个家族的冻结资产。

不覆盖：旧家族 `lizard` 的几何修复（它的 `rl` 脚仍是平板，属另一条线的事）；不覆盖任何训练/奖励变更。

## 验收条件

1. 两个家族使用不同几何时，**实际物理加载**与**诊断**都指向各自的资产。
2. 修改 lizard2 网格，**只触发 lizard2 的锁漂移**；19 个冻结版本的资产与锁**逐字节不变**。
3. **生成器与 URDF 的相对路径约定一致**，重新生成仍能正确加载。
4. 网格摘要明确表示"**该家族实际消费的网格**"，口径变化在独立记录中说明。

## 结果

**发现（改前没有暴露）**：同一份几何躺在**三棵树**里，而只有一棵被锁钉住 ——

| 拷贝 | 被谁读 | 被锁钉 |
|---|---|---|
| `rl_exp/meshes/**`（共享） | `diag_metrics.collision_mesh_dir()`（所有诊断/验收工具） | 是，**两个家族共 20 个版本** |
| `rl_exp/versions/<family>/meshes/**` | 该家族 URDF 的相对路径（`meshes/...`） | 否 |
| `assets/<family>/<family>.usda`（内联点） | **物理**（`physics:approximation = "convexHull"`） | 是（usda 本身） |

三套路径约定互不一致：生成器输出到 `rl_exp/<robot>_urdf/meshes/**` 却引用 `../meshes/...`（解析到共享树，**不是它自己刚写的目录**）；两个提交的 URDF 写 `meshes/...`（解析到家族树）；`_lock_files()` 给每个家族钉共享树，且 docstring 明说这是**故意的**。后果：改共享树 = 一次跨家族、整棵树的换代，两个家族的物理都要动。

**做法（两条候选，取后者）**

| 方案 | 动作 | 代价 |
|---|---|---|
| A 按既有设计修 | 共享树 + 两个 usda 都改，**20 个锁全刷新** | 旧家族 19 个冻结版本的物理被改写，历史 run 不再可复现 |
| **B′ 家族隔离（取此）** | 共享树**回滚到原字节**；修复进 lizard2 自己的树；`_lock_files` 与诊断按**家族声明**解析 | 旧家族逐字节不变；代价是一次方案变更（需本记录 + 生成器对齐） |

**改动落点**

- 新增 `versions/lizard/assets.json`（`{"meshes_dir": "meshes"}`，显式承认退休家族消费共享树）与 `versions/lizard2/assets.json`（`{"meshes_dir": "versions/lizard2/meshes"}`）。**缺声明是拒绝项**，不是静默默认。
- `diag_metrics.meshes_dir(family)` / `collision_mesh_dir(family)`：按声明解析；`obs_protocol.family_of(task_id)` 从路由线取家族。
- 五处调用点改传家族：`gait_probe`（含报告新增 `family`/`mesh_dir`/`mesh_digests`）、`diagnose_support`、`baseline_eval`（`foot_geometry` 的 sha256 改取家族树）、`baseline_probe`、`check_dr_parity._lock_files`。
- 生成器 `generate_urdf.py`：输出目录改读声明、引用改 `meshes/{visual,collision}/<link>_{visual,collision}.obj`、**补写 .obj**（原先只写 .stl，而两个提交的 URDF 都引用 .obj）。
- lizard2 的 `rl_foot_collision.obj` = 该树内 `rr` 的 y 镜像（含绕序反转，法线仍朝外）；`lizard2.usda` 内联点与之一致（实测 ≤0.086 mm）。

**读数**

| 项 | 修复前 | 修复后 |
|---|---|---|
| `rl` hull 最低点 z [m] | −0.07462 | **−0.07902**（= rr） |
| `rl` hull 边界 z 尺寸 [m] | 0.18793 | **0.19160**（= rr） |
| 平放时的带内面积（2 mm 带）[m²] | 0.119282 | **0.013352**（= 另三只） |
| 地板面法线偏 link −z [°] | 0.24 | **1.45**（= 另三只） |
| 四只脚 cap 一致性 | 1 只离群（9×） | **四只全同形**（0.013352/0.013353） |

验证读数：`check_dr_parity` **只报 lizard2**（改前 41 条跨两家族 → 改后 0 条，刷新锁后 `PARITY_OK`）；`git status` 显示**lizard 的 19 个 `asset_lock.json` 一个未改**；资产隔离的四条拒绝**折进 `check_dr_parity` 的"asset isolation"一节**（含 4 条自证伪例在它的 `--self-test` 里，同一进程，不新增套件条目 ⇒ `MAX_CHECKS` 不动）；`gait_probe --self-check` 新增一条"两家族读两棵树"断言（lizard 仍 0.119282、lizard2 0.013352）；usda↔obj 全 18 个连杆实测最差 **0.244 mm**。

**口径变化（第 4 条验收）**：`foot_geometry.sha256` 从"共享树的文件哈希"变成"**该家族树**的文件哈希"，而 `obj` 字段仍只有文件名 —— 因为两个家族下同名文件已不是同一份几何，**区分靠 digest，不靠名字**。框架格式未变（不加新键：`baseline_frames` 的 meta 形状随格式冻结，加键等于换格式名）。旧报告里的 digest 指向共享树那一份；要重读必须按当时的树，不能按当前路径重算。

## 证据引用

- 几何对比与 dry-run：`_tmp_foot_{audit,audit2,compare,trees,delta,fix,source,plan,stl,flat,families}.py`（一次性，`_tmp_*` 已 gitignore；**2026-10-09 已删，见文末勘误**）
- 修复脚本：`_tmp_tree_fix.py`（lizard2 树内镜像；**2026-10-09 已删，见文末勘误**）
- 落点代码：`rl_exp/tools/diagnose/diag_metrics.py`（`meshes_dir`/`collision_mesh_dir`）、`rl_exp/tasks/obs_protocol.py`（`family_of`）、`rl_exp/tools/verify/check_dr_parity.py`（`_lock_files` + 资产隔离一节与它的伪例）、`rl_exp/blender/generate_urdf.py`
- 声明：`rl_exp/versions/lizard/assets.json`、`rl_exp/versions/lizard2/assets.json`
- 复读命令：
  ```
  python rl_exp\tools\verify\check_dr_parity.py --strict --self-test
  python rl_exp\tools\diagnose\gait_probe.py --self-check
  ```

## 未覆盖边界

1. **生成器未真跑**（本机无 Blender）：改动是静态的，由闸门的"URDF 引用必须落在声明树内"覆盖约定这一半；"重新生成后能加载"这半边**未经实测**。剩余动作归 `work/active/asset-tree-per-family.md`。
2. **旧家族的分歧只记录不修**：`lizard` 的 URDF 引用 `versions/lizard/meshes/**`（无人加载的遗留树），而它声明并消费共享树。闸门把它作为 note 打印（键在**声明本身** = 共享树，不是家族名），因为它被 19 个冻结锁压住，改它 = 改写那 19 个锚。处置（换树或带期限的豁免）同归 `work/active/asset-tree-per-family.md`。
3. **旧家族物理未动**：`lizard.usda` 的 `rl` 脚仍是平板 hull ⇒ 若那条线要修，得再走一次同样的换代（并接受其历史 run 不再可复现）。
4. **`foot_geometry` 仍不带树路径**：靠 digest 区分；若将来要让报告自证"读的是哪棵树"，那是一次帧格式版本变更（新名字），不是在现有 meta 里加键。
5. 本次**未重训、未重评**：修复改变的是物理接触几何，lizard2 v1 的既有 run/报告仍是"平板 hull"下的读数，可比性到此为止（v1 已训练，属"已训配方变更"⇒ 依版本规则进 `lizard2/main/v2`）。
6. **一处归属事实**：⑪ 引用的探针读数（`sole_*`/`tilt`）与"两家族读两棵树"的自检断言落在 `gait_probe.py`；该文件当时同时载有**另一会话在飞的** blade / 逐关节力矩读数（30 个 hunk 里 18 个属本线、5 个双方同块）⇒ 无法按 hunk 干净切开，本记录的提交不含它。它随后被那一侧的整文件提交 `62b92c9` 一并带入（含本线的读数），归属按那次 commit 记；本记录的"口径"一节仍以本线提交的 `diag_metrics`/`mesh_dir` 为准。

## 勘误（2026-10-09，仓根 `_tmp_*` 清仓）

本记录"证据引用"里的一次性脚本（`_tmp_foot_{audit,audit2,compare,trees,delta,fix,source,plan,stl,flat,families}.py`
与 `_tmp_tree_fix.py`）**未入仓，已于 2026-10-09 随 64 个 `_tmp_*` 删除**（原委见
`2026-10-09-repo-architecture-review.md` 的善后节与 `rl_exp/tools/verify/OFFLINE_CHECKS.md` §6）⇒ 那两行
"几何对比与 dry-run / 修复脚本"的路径**作废**，修复形态只能从落点代码（`diag_metrics.py` 的
`meshes_dir`/`collision_mesh_dir`、两个 `assets.json`）读。**读数不变**（usda↔obj 最差 0.244 mm、
`PARITY_OK`、19 个 lizard 锁逐字节未动都在正文里）；那份"复读命令"两行仍有效，跑的是入仓闸门。
