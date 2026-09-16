# v10 PLAN —— 删除 tilt 终止（摔倒交给奖励账本 + 学翻身）

> 修订：v10.0（2026-09-09 定案于 NOTES；本文件 2026-09-10 按修订后规则
> 追认回填，方案与 `NOTES.md` v10.0 同源，无实质变更——用户拍板：PLAN
> 每版必写简短版）。状态：**在训**（tag `lizard-v10`，commit `3c1b14e`；
> 结果回填见 NOTES）。

## 目的/假设（≤3 行）

v3 装机的 `tilt_terminate` 把合法 pitch 当摔（假阳占 episode 0.60–0.76，
success 钉死 0.019，地形课程被饿死）。假设：删除终止后摔倒净收益已为负
（tracking 归零 + belly 罚 −0.5/步），起身梯度天然存在；躺到 timeout 是
允许结局（用户拍板）。完整依据（2 m 尾链形态学 / gecko 翻正文献）见 NOTES。

## 相对 v8.1 的 diff（单变量，reward/obs/DR/地形/网络零变更）

1. `lizard_params.yaml` = v8.1 全量拷贝 + `v10.tilt_terminate: null`（v3 段保留作 v1–v8 冻结记录）
2. `LizardRoughTeacherEnvCfg_V10(V8)`：`__post_init__` 里 `terminations.tilt = None`（yaml 驱动，可经 yaml 复原）
3. 注册 `Lizard-Rough-v10` / `Lizard-Rough-Play-v10`（runner `lizard_rough_teacher_v10`）
4. 静态闸 `rl_exp/tools/verify/check_terminations_v10.py`（V10 tilt=None 且 time_out 存活，V8 冻结不动）

## 验收

1. `Episode_Termination/` 只剩 `time_out`，占比 → 1.0
2. success_rate 离开 0.019 地板，terrain_levels 继续爬
3. `belly_contact_force` 保持 ≈0（持续 >0 且 tracking 高 = 仰面爬行 hack，
   触发预注册反制：升 v5 段 belly 权重）
4. track_lin_vel 回升（v8.1 终值 ~0.79 为基线）
5. 观察项（非闸）：摔倒后数秒内自行起身是否涌现

## 训练

```bat
python scripts\reinforcement_learning\rsl_rl\train.py --task Lizard-Rough-v10 --max_iterations 15000 --seed 42
```

log：`logs/rsl_rl/lizard_rough_teacher_v10/`

## 修订记录

| 日期 | 版本 | 变更 + 原因 + 依据 |
|---|---|---|
| 2026-09-09 | v10.0 | 初稿（单变量：tilt 终止删除；v9 空号保留断腿协议，跳号依据 versioning §A，方案全文录 NOTES） |
| 2026-09-10 | v10.0 | 追认回填本文件：规则修订（PLAN 每版必写简短骨架）后补方案文档，内容与 NOTES 同源无实质变更（用户拍板） |
