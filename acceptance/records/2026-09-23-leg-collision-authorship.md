# 2026-09-23 腿部碰撞归属：USD 侧读数与运行时接触归属

## 适用范围

- 对象：`lizard`（退役线）与 `lizard2`（活线）两代资产的**碰撞几何归属**与**罚项实际选中的 body**
- 工况：`Lizard-Baseline-Flat-v2` / `Lizard2-Flat-v1`，8 envs，零动作 100 控制步（= 2 s）稳态站立
- 覆盖：USD 侧（运行时 prim 树，即 PhysX 实际加载的东西）、URDF 侧（`<collision>` 逐 link）、
  罚项解析后的 body 名单、以及这段时间里真正承重的 body
- 不覆盖：接触力学的归因（谁在滑/谁在牵引，归 `work/active/floor-contact-attribution.md`）、
  自碰撞（`enabled_self_collisions=False` 下的穿透对）、非站立姿态（腿在摆动期能不能碰到地）

## 验收条件

- USD 与 URDF 两侧的碰撞几何须能互相校验：同一 body 的 bbox 尺寸一致（容差 10 mm）
- 罚项名单须读**解析结果**（`SceneEntityCfg.body_ids` → 名字），不读正则原文
- 运行时须给出"这段时间里哪个 body 真的在承重"，且承重 body 必须落在某个罚项 ∪ 脚之内
- 无碰撞体的 body 单独列出——它们不可能成为穿透方，罚到它们等于罚一个恒 0 的量

## 结果

工具：`rl_exp/tools/verify/check_contact_ownership.py`（task 参数化，家族与 URDF 取自任务的 spawn 路径；
直跑，不经 `startup_check` ⇒ 退役线仍可做诊断，因为它不是训练）。
复读：

```
E:\IsaacLab\env_isaaclab\Scripts\python.exe rl_exp\tools\verify\check_contact_ownership.py ^
    --task Lizard-Baseline-Flat-v2 --num_envs 8
E:\IsaacLab\env_isaaclab\Scripts\python.exe rl_exp\tools\verify\check_contact_ownership.py ^
    --task Lizard2-Flat-v1 --num_envs 8
```

四条读数：

1. **USD 侧与 URDF 侧逐 body 一致**：两代资产每个 body 的 bbox 尺寸在两侧完全相同（4 位小数同值），
   `physics:approximation` 全为 `convexHull`。"USD 侧碰撞形状"不再是假设。
2. **`*_kfe` 两代都没有碰撞体**：URDF 侧与 USD 侧都没有（`no collider` 清单里），
   而 v1/v2/lizard2 三处 yaml 的 `undesired_contact_body_names` 都点名 `.*_kfe`
   ⇒ 罚项名单里有一半是**恒 0 的死条目**。
3. **胫骨几何所属 body = `*_hfe`**（bbox 0.234 × 0.238 × 0.326 m，两代同值），
   而股骨几何挂在 `*_haa`（0.284 × 0.494 × 0.436 m），**不在罚项名单内**。
   v1 `PLAN.md` 把罚项写成"大腿/小腿"，实际是"只有小腿（借 hfe 之名），大腿无人罚"——
   名单与几何的错误方向是"漏罚一个真会碰地的 body"，不是"多罚一个"。
4. **运行时承重 = 四只脚**（旧线 643 / 949 / 1077 / 3778 N，新线 787 / 858 / 970 / 2556 N），
   稳态站姿下 hfe/haa/kfe 全 0 N ⇒ 第 3 条那条漏罚在**站姿下不触发**，它不是当下的分数问题，
   是姿态一低（膝部扫板、趴行）时才会打开的口子。

判定：`CONTACT_OWNERSHIP_FAILED (1)` —— 唯一那条红是第 2 条的死条目，两代资产同判。
**新家族的碰撞归属与旧资产完全相同**：换了骨骼（新增 `hip`）、修了轴位，碰撞几何的作者身份没动过。

## 证据引用

- 工具：`rl_exp/tools/verify/check_contact_ownership.py`（自带断言：死条目 / 漏罚 / 空测量三条）
- 两侧来源：`rl_exp/assets/lizard/lizard.usda`、`rl_exp/assets/lizard2/lizard2.usda`（spawn 路径指向它们，
  不是外部的 .usd）；`rl_exp/versions/lizard/lizard.urdf`、`rl_exp/versions/lizard2/lizard2.urdf`
- 名单来源：`rl_exp/versions/lizard/baseline/v1/baseline_params.yaml:119`、`v2:123`、
  `rl_exp/versions/lizard2/main/main_params.yaml:136`
- 前序读数：`acceptance/records/2026-09-21-lizard-leg-axis-kinematics.md`（URDF 侧普查 + 力臂）

## 未覆盖边界

- 只测了稳态站姿：漏罚的股骨在摆动/趴行姿态下是否真碰地未测（那需要一条会低姿态的策略或受控姿态注入）
- 不含自碰撞与地面专属力分离（归 `floor-contact-attribution`）
- 两代资产复用同一批碰撞网格（尺寸逐比特相同），本记录不评价该复用是否合理
- 不改配方、不改资产、不改罚项名单：本记录只给结论，改与不改是资产线/家族线的决定
