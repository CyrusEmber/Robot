---
name: isaaclab-pretrain-check
description: >
  IsaacLab 训练启动前预检：离线地形统计 + 渲染图 + GUI 目视机器人站上真实地形。
  当用户提到"预训练检查"、"开训前检查"、"训练前检查"、"启动前看地形"、
  "看地形"、"地形预检"、"地形预览"、"检查地形"、"地形够不够粗"、
  "pretrain check"、"terrain preflight"等需求时使用此 skill。
  对应版本 NOTES（v4 起）启动前警示第 1 条：先看地形再开训。
metadata:
  version: "1.0.0"
---

# IsaacLab 训练启动前预检（地形）

## 核心规则

1. **两步走完才有结论**：离线统计（快）+ GUI 目视（慢）都完成才许给"可以开训"结论；只跑统计不算过检。
2. **结论必须带数字**：引用 preflight 输出的 relief/std/p2p 实测值 + 与上一版的对比，禁止"看起来还行"式结论。
3. **脚本只出事实，判断留给定标**：够不够粗对照机体定标（脚掌尺寸/站高/提脚极限实测值，见该家族 FAMILY.md 几何备忘），不改脚本凑结论。
4. **不代替用户拍板**：给出事实 + 建议，开训与否用户定。
5. 有 checkpoint 想看策略跑地形 → 用标准 play 脚本，不是本 skill 的 view_terrain。

## 工作流程

### 第 1 步：定位版本

- 训练版本 vN → 参数与文档在 `<robot>_exp/versions/<family>/<vN>/`（NOTES/PLAN）。
- 地形生成器配置在该家族基座 env cfg（读其 FAMILY.md 代码地图定位当前版本所用 cfg）。

### 第 2 步：离线统计（无 sim，秒级）

```bat
<venv python> <robot>_exp\tools\verify\terrain_preflight.py --version <vN>
```

- 输出每个子地形的 z std / p2p / **foot-plate relief**（0.5 m cell 内高差 ≈ 一块脚掌跨到的高度差，抓"太平整"的核心指标）。
- 与上一版对比就再跑一次 `--version <上一版>`（预期：只有改过的子地形有差异，其他行应一致——不一致 = 隔离性破了，先查代码）。
- `--difficulty 1.0` 默认最难课程排（0.0 = 最易排）。
- 渲染图自动存 `_tmp_terrain_previews/`（git 已忽略），逐张打开目视。

### 第 3 步：GUI 目视（拉起 Isaac Sim，分钟级）

```bat
<venv python> <robot>_exp\tools\verify\view_terrain.py --viz kit --task <Robot>-<变体>-Play-vN
```

- 机器人零动作站在**真实训练地形**上（PLAY 变体：无随机化）。
- 看四件事：①脚掌与碎块的尺度关系（一块碎石 ≥ 脚掌，还是脚掌能横跨踩平）②高差肉眼可见 ③机器人默认站姿下肚皮/大腿离地间隙 ④`[contact check]` 输出的 robot-terrain 接触点/env（mean/max）——接触栈容量重验的量化依据，外推训练 env 数对照历史标定。
- `--num-envs` 调大可同屏看更多子地形；Ctrl+C 退出。
- headless 冒烟（不开窗验证 env 构建通过）：加 `--headless --steps 10`。

### 第 4 步：结论回写

- 给用户：实测数字表 + 目视发现 + 与上版 diff + "可开训/建议调参（方向）"建议。
- 用户确认后，在版本 NOTES 的"启动前警示"下补一行过检记录（日期 + 数字摘要）。

## 注意事项

- venv python 路径见仓 README；IsaacLab 根可用环境变量 `RL_ISAAC_ROOT` 覆盖。
- preflight 与 view_terrain 都要在仓根下运行（脚本自定位）。
- 卡排风险判据（地形太难导致 terrain_levels 停排）不在本 skill：见对应版本 PLAN。
- 定标数据必须实测（历史教训：误把骨长当掌宽 → 碎石间距小于真实掌宽 → 大平脚横跨碎块等效踩平）。换机体/改骨长 = 换家族，定标要重测。

## 资源说明

- `<robot>_exp/tools/verify/terrain_preflight.py`：离线统计 + PNG 渲染（numpy + matplotlib，无 sim）。
- `<robot>_exp/tools/verify/view_terrain.py`：GUI/无头查看机器人站上版本地形。
