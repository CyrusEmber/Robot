# v8 计划 —— 资产解剖学转正 + 全关节重命名

> 状态：**已实施，待训**（2026-09-08）。方案与结果 SSOT = `v8\NOTES.md`；
> 判废归因（v6 倒走）见 `v6\NOTES.md` 结果回填节。

## 为什么是 v8（而不是 v6.M / v7）

- v6 已训（8950 iters）→ 训练启动锚不可逆（versioning.mdc §A 状态机），
  资产换代影响配方行为 → 必开新版本。
- v7 槽位已被 ghost 断腿鲁棒性提案占用（未训可修订，但混入资产换代会毁
  归因隔离——本家族两次判废教训都是"一次只动一个变量"的反面教材）。

## 改动面（实施记录）

1. `blender/rename_flip_v8.py`：+180° 旋转 + 26 骨重命名（两阶段防撞名）+
   mesh 重挂 + 布局断言（球头 +X / 天线 −X / 腿序）
2. `generate_urdf.py` AXIS_MAP 轴翻转；URDF/STL/OBJ → convert → flatten 重跑
3. `migrate_joint_names_v8.py`：9 份 yaml 机械迁移；root/v8 joint_order =
   新 URDF 实际序（export_ue 序列断言）
4. `teacher_env_cfg.py` 基类 spine 正则 + V8/V8_PLAY 类；任务/runner 注册
5. 校验：`teacher_smoke_v8` + `check_joints_v8`（布局硬闸）+ offline 闸门
6. 全版本锁同 commit 刷新

## 训练前闸门（顺序执行，全绿才开训）

1. offline 闸门（run_offline_checks.bat）
2. `position_check.py --headless --rough`（站立稳定）
3. `check_joints_v8.py`（布局 + 驱动）
4. `teacher_smoke_v8.py`
5. **GUI 目视**（`view_terrain.py` 或 play_fast）：球头朝 +X、四足站位——
   以造型为准，不信骨名（v6 教训）

## 训练后

- `direction_probe.py`（默认指 v8 最新 run）：disp_head>0 + GUI 球头朝前
- 结果回填 v8 NOTES → FAMILY 版本史
- v7 PLAN 前提修正：微调基座 v6 ckpt → v8 ckpt
