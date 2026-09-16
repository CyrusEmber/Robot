# v4 —— 碎石地重定标（脚掌实测 0.46×0.51 m）

- 目的/假设: v3.6 碎石粗化把 kfe→foot 骨长 0.131 m 当掌宽定标，实测掌板
  0.46×0.51 m（rl_foot 碰撞网格 bbox，USD scale=1）→ 0.3 m 间距 < 掌宽，
  大平脚横跨多块碎石骑在包络上，等效平整。假设：间距 ≥ 掌宽 + 高度档加密
  后，脚必须包络贴合碎石，extero/接触信号重新有信息量。
- 相对 v3 的变更（obs 381 不变，任务 id `Lizard-Rough-v4`）:
  - **random_rough**: downsampled_scale 0.3→0.5 m、noise (0.06,0.2)→
    (0.10,0.35)、noise_step 0.04→0.02（5 档→14 档；最大局部坡 0.52 m/m
    < slope_threshold 0.75，无垂直化）
  - **collision stack 回退**: v3.6.1 的 gpu_collision_stack_size 2**28
    删除，回 stock 2**26——疑似掩盖接触密度根因（平脚板贴密 heightfield =
    最大接触对数），v4 用粗地形重验 stock 容量
  - yaml/网络/奖励/DR/终止：与 v3 逐字相同（纯地形+物理缓冲区变更，
    spec 集合不变）
- 训练命令:
  ```bat
  python scripts\reinforcement_learning\rsl_rl\train.py --task Lizard-Rough-v4 --max_iterations 4000 --seed 42
  ```
- log 目录: logs/rsl_rl/lizard_rough_teacher_v4/
- **启动前警示（用户拍板 2026-09-02，三步缺一不可）**:
  1. **先看地形再启动**——可视化确认碎石粗糙度（粗块 ≥ 脚掌 0.46 m、高差
     可见）后才许开训/开测。工具（skill `isaaclab-pretrain-check`，v4.2）：
     `terrain_preflight.py --version v4`（离线统计+渲染图，秒级）→
     `view_terrain.py --viz kit --task Lizard-Rough-Play-v4`（GUI 目视）；
  2. gpu_collision_stack_size 已回 stock 2**26：若 PhysX 接触溢出复发
     （静默丢接触→非确定性物理），根因 = 接触密度（平脚板 × 密
     heightfield），修法 = 粗化脚碰撞体/地形，**禁止再加 headroom**。
     量化监控（v4.3）：`view_terrain.py` 的 `[contact check]` 行输出
     robot-terrain 接触点/env（mean/max），外推训练 env 数对照 v3.6.1
     标定（4096 env 溢出需 67,137,584 B）；
  3. 判据沿用 v3.4.1：terrain_levels 长期卡排 → 降 0.35 顶或缩 0.5 间距。
- 验收: 沿用 v3.2 口径——不设中途达标门，起步 sanity（~100 iters 无 NaN /
  非零 reward / 终止计数正常）后直训，训完以 harness eval 为准（v4 vs v3
  仅 nominal 可比 + 逐地形 completion 对账）。
- 结果回填: （训练后补：reward 曲线读数 / eval 跑分表 / 逐地形 completion /
  collision stack 溢出观察 / 结论）
- 结论: （一句话，训练后补）
