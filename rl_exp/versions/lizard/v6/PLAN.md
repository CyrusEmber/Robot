# v6 —— 资产前向轴转正

> 状态：提案（未冻结——训练启动时补打 tag `lizard-v6`，versioning.mdc §A）。
> 本版唯一变更在资产层，方案细节与验收判据继承 `../v5/PLAN.md` 全文，
> 此处只记 v6 特有内容。

## 目的

v5 首跑横行（crab-walk）的根因是资产坐标系错配，不是奖励设计。URDF 长轴 = Y
（neck +y / tail -y / 腿沿 x），任务给 base +X 付钱 → policy 按最优解沿自身
右侧横移。转正资产，v5 奖励包原样重训。

## 根因证据链

| # | 证据 | 位置 |
|---|---|---|
| 1 | neck1_yaw_joint origin y=+1.0696（头在 +y） | 旧 `versions/lizard/lizard.urdf` |
| 2 | tail_yaw_joint origin y=-1.2613（尾在 -y） | 同上 |
| 3 | lf/rf_haa 在 y=+0.60、x=∓0.33（左右沿 x） | 同上 |
| 4 | reward 用 yaw 对齐系（≈base 系）x 分量付钱 | `teacher_mdp.py::track_lin_vel_xy_lin` |
| 5 | 命令 `lin_vel_x (0,3)` 打在 base-x | `v5/lizard_params.yaml` v5 段 |
| 6 | v5 曲线健康（跟踪核 0.4+）→ 横行是 spec 内最优 | `v5/tb_scalars.csv` |

v3/v4 原地划脚不位移 → 错配不可见；v5 让位移首次有收益 → 显形。

## 变更（yaml/reward/obs/DR/网络零变更）

- blend SSOT 刚体旋转 R_z(-90°)：`blender/rotate_rig.py`（1e-6 刚性自检；
  不烘焙——transform_apply 过 bone-roll 往返有浮点漂移，保留臂架对象变换）
- `generate_urdf.py`：骨位改读世界系（`arm.matrix_world @ head_local`）+
  AXIS_MAP 轴旋转（haa/kfe Y→X、pitch/foot X→-Y、hfe/yaw 不变）
- `fix_bones.py`：世界↔臂架显式转换 + foot 桩外展轴 X→Y
- 转换链重跑（STL→OBJ→convert→flatten）；usda 自包含
- 全版本 asset_lock 同 commit `--update-locks`（有意资产退役）

## 验收

1. v5 PLAN 全部反划脚 KPI 原样适用；
2. 新增：GUI 回放前进方向 = 头朝向（横行消失）；
3. 装配 gate：teacher_smoke_v6 + offline 闸门全绿（已于 2026-09-07 过，
   记录见 NOTES.md）。

## 结论

（一句话，训练后补）
