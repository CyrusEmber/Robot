# A 执行顺序与当前实现核查（2026-10-14）

## 适用范围

用户要求检查 A 的方向、实现及耗时，随后要求修复计划。本次只读代码、已有报告与日志，未重跑仿真；不是资产或事项关闭审核。结构方向仍遵循前上臂向后、后股骨向前、掌根腕踝和恢复后肢尺寸。关键缺证是完整目标周期的运动能力，不能由导出一致或小角度运动替代。

## 验收条件

计划需解除 A 对整个专项关闭的等待，保持碰撞与动力学前提，保留转向/恢复等未完动作；已有证据只按其代码、输入及工况解释。

## 结果

### 最新证据与边界

产物目录为 `rl_exp/out/lizard2_palm_pd_restored_20261013/`，均为本机文件，不承诺已进仓。

- `resume_v3_asset_chain.json`：完成标记成立，零位和全关节 0.03 rad 两快照的 Blender/URDF/USD/运行时几何比较最大残差约 2.07e-6 m；不是完整周期。报告脚本哈希为 `c3025ee1e4740a74253aec945977fb320f0ffec01d37b6c721803b56962b4550`。
- `resume_v1_inertia_fixed.json`、`resume_v1_inertia_pose_pos.json`、`resume_v1_inertia_pose_neg.json`：已有修正隔离资产的零位及正负姿态报告；旧交接中的“尚未保存隔离 USD”不再代表全部进展。对应资产为 `lizard2_palm_normalized_20261014.usda`，SHA256 `a100d38f74cf9024173654be172db6a69cfbad99944534e99dcb6c57e20d1afd`。表面积质量和箱体惯量近似仍有限制。
- `resume_v1_collision_six.json` 与 `resume_v1_collision_cross.json`：均列六对过滤及完成标记，后者保留 `lf_wrist ↔ rl_ankle` 实际接触；补上旧交接所缺的六对版本反例，但不证明整个动作域安全。
- `resume_v1_pivot/axis/state/inertia_broken/filter` 等日志保留相应断言失败；本次未重新验证进程退出状态。前次完整问题与命令形状见 `2026-10-14-lizard2-restored-validation-handoff.md`。

核查时 `palm_pd_probe.py` 哈希为 `f2e89e113c3f7e5489a60ec4b4399c03a32428e81015398f864c06f33c56a281`，不同于上述报告；`palm_pd_probe.py`、`palm_asset_probe.py` 仍未跟踪，导出器混有其它接线改动。须分清代码归属、差异影响和证据版本，不能拼接为最终通过，也不因哈希变化机械地重跑全部实验。

### 具体实现缺口

`palm_pd_probe.py` 的连接过滤分支定义六对 `approved`，但实际 `filtered` 仅由扫描结果及树关系生成，未与 `approved` 比较；后续读回只与生成列表比较。当前输入得到六对不证明未来不会扩大过滤。专项步骤 4 应修此责任层，并用扫描额外连接对的拒错及真实跨腿反例验证。

### 计划修订依据与出口

总项等待整个限位/PD 专项交回，会推迟 A 的核心问题；C2“待实现”也未区分已有诊断出口和未验收的正式候选。已将总项及专项改为：收口输入/坐标 → 优先单一直行周期运动学 → 相关资产前提齐备后围绕同一轨迹做动力学。工程数值仍须比较前确定；本次没有批准新数值。

转向、恢复、最终限位与 PD、外观确认、P2/P3 余项及 D 独立审核全部保留。本记录不关闭事项、不宣布骨架能走；执行路由唯一归两份 active work，已有 E 接线改动保留其原归属。

## 证据引用

复读上列 JSON 的 `identity`、状态及对应日志，并对照 `rl_exp/tools/diagnose/palm_pd_probe.py`、`palm_asset_probe.py` 和 `rl_exp/blender/scripts/generate_urdf.py`；本次只修订 `work/active/lizard2-body-drive-candidate.md` 与 `work/active/lizard2-restored-limits-pd-validation.md`。

## 未覆盖边界

未执行新仿真或关闭审核，未修复过滤代码，未确定工程数值、限位或 PD；几何周期和承重行为仍待执行。
