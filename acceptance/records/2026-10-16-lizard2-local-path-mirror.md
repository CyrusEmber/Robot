# 另两腿原局部路径的镜像几何检查

## 适用范围

承接 `acceptance/records/2026-10-16-lizard2-local-path-quarters.md`。用户本轮选择“先验另两腿镜像”：rf、rl 各最多 129 个姿态，中立加原 32 段的端点、中点与四分点，每腿首个失败即停；复用原轨迹、容差与碰撞集合，不求解、不处理接缝、不进入四肢组合。连续域证明仍按前记录的用户范围取消，不新增验收前置。

主执行者直接实现、运行、自查，无子任务或独立关闭审核。不改候选或正式资产、ROM、PD、运行时、冻结配方，不起仿真或训练；并行会话的生成器及 runtime 改动不归本轮。新增检查属于动作几何，不是正式采用或承重步态验收。

## 验收条件

- 消费相同 `budgeted_local_path`、候选绑定、根变换及完整几何依赖；源 lf/rr 必须完整闭合，具名五轴与其余关节零值一致，不以源判词替代目标腿几何。
- 从真实链轴推导镜像符号，核同角色链及镜像后的限位区间；映射 lf→rf、rr→rl，不默认所有轴同号。
- 每目标腿重新采中立及每原段 u=0.25/0.5/0.75/1，共最多 129 个姿态，失败即停；原 1e-5 m 数值容差、0.05 rad 源端点步距、139 对检查及 14 对排除不变。
- 每姿态保留完整 30 关节、18 个碰撞实体最低读点、掌最低特征、参考点、法向、原反曲判据、实体相交／包含及限位。核接地、非零离地、前后行程、落掌采样顺序及完整关节／参考点闭合。
- 实际镜像映射／采样函数的符号、限位拒错、采样点、停止、预算与闭合破坏须令同一自检失败；输出目录不能覆盖。源路径、求解器与原四分点行为不退化。

## 结果

### 实现与复用

在 `rl_exp/tools/diagnose/local_path_check.py` 增加 `--mirror`，不新建框架或求解器。`_mirror_mapping` 复用已有 `palm_gait_kinematics.mirror_signs` 的轴向量反射；`_mirror_check` 顺序采目标姿态、限预算及失败停止；实际几何仍走原 `_state`、`_static_prepare` 与 `_local_failures`。历史四轴求解器没有被调用，源五轴采集报告未改。

轴反射为 (-ax, ay, -az)，不是位置向量的 (x,-y,z)。两组真实链的映射符号均为 `[+1,+1,-1,+1,+1]`，只有 twist 反号；镜像限位区间最大差为 0。已采源端点映射到目标限位的最小余量分别为 rf 0.4812261935 rad、rl 0.4278808254 rad，仅指 URDF 占位限位，不升级为 ROM 或策略余量。

### 实际输入与读数

源仍为 `rl_exp/out/lizard2_palm_local_path_contact_20261015/report.json`，绑定 `rl_exp/out/lizard2_palm_spatial_20261014/checkpoint_v3/build.json`。输出为 `rl_exp/out/lizard2_palm_local_mirror_20261016/report.json`，模式 `sampled_local_path_mirror`。

| 目标腿 | 新姿态 | 完整段 | 接地采样最大绝对 z [m] | 全机采样最小 z [m] | 最低法向 z |
|---|---:|---:|---:|---:|---:|
| rf | 129 | 32 | 8.97526931998e-7 | -8.97526931998e-7 | 0.9980709929 |
| rl | 129 | 32 | 3.68910273785e-6 | -2.60737345670e-6 | 0.9977475844 |

两腿 `completed_local_loop=true`、`failure=null`，共 258 个实际新姿态；没有实体相交／包含、全机超容差穿地、接地残差、翻掌、反曲、限位、落掌高度增加或方向／离地失败。参考 X 跨度 rf 0.03056919883 m、rl 0.03063828898 m；最大掌最低高度 rf 0.03056984695 m、rl 0.03056742860 m，仅作原探索路径读数，不批准步长或净空。

与原端点／中点及历史四分点逐姿态比对，镜像参考位置最大差 rf 1.29032258310e-7 m、rl 1.84700397833e-6 m；法向最大差分别 0、1.17295770866e-8。保留原网格微小非对称，不手修镜像或放宽接地容差。负高度仍只在原数值容差内，不声称物理精确零穿透。

执行者复核全部行的段号、u、完整映射角度及其它关节零值，候选、源码及报告身份一致，每行 30 关节、18 实体且失败为空。未重复采源腿或把源腿历史检查冒认为本轮目标腿结果。

### 回归与仓库检查

正常自检退出 0。六项新增实际函数破坏 `mirror_sign/mirror_limits/mirror_stop/mirror_budget/mirror_samples/mirror_closure` 均退出 1，分别拒绝同号误映射、错误限位、失败不停止、超预算、漏四分点与假闭合；五项原四分点破坏也退出 1。首次统一复核发现原部分自检在判词缺失时以 TypeError 失败，补先验断言后全部为明确 AssertionError；检查口径未变。

原 `_quarter_check` 复放已有 128 行读点，完整判词和插值顺序与旧报告相同，没有新增源腿几何采样。原 `local_path_view.py --self_check` 通过。既有镜像输出再次调用被拒绝，退出 1、报告摘要不变。

既有完整离线套件 37/37 通过，50.7 s；baseline 波内 33.3 s、单独复核 21.3 s，符合原 25 s 预算。未改套件、预算或新增闸门。实现提交 `8ddb058` 的全部提交钩子通过；格式、套件及记录存在不替代独立关闭审核。

## 证据引用与复读

- 原路径与原采样：`acceptance/records/2026-10-15-lizard2-palm-local-contact-repair.md`、`acceptance/records/2026-10-16-lizard2-local-path-quarters.md`。
- 接缝原读数：`acceptance/records/2026-10-16-lizard2-local-path-postprocess.md`，本轮未修复。
- 实现：`rl_exp/tools/diagnose/local_path_check.py`；复用方法：`rl_exp/docs/leg_geometry_reuse.md`。
- 源报告 SHA256：`f0671a53a8d5b97c40844f6ea771b655bdd3bf8d5ab98ef64b02a1a7550a34c8`。
- 镜像报告 SHA256：`02b4ea060064e77bc46ea248e51dfd0a7b76cb2f8373ec1313d2f3cfc1bff7ee`。
- 本轮检查源码 SHA256：`fffa2a9061be856f0981788e1e3c37ae3dc72d3ae277ccc8ed84013dda3172ce`。
- 报告含全部候选、依赖、源报告身份及每姿态判词；本机约 8.9 MB 产物不承诺入仓。旧四分点报告保留旧检查源码身份，不被改写成新版。

从仓根运行，解释器由 `python -B ablation_harness/host_paths.py --python` 解析。复读必须使用不存在的目录：

```cmd
"E:\IsaacLab\env_isaaclab\Scripts\python.exe" -B rl_exp/tools/diagnose/local_path_check.py --self_check
"E:\IsaacLab\env_isaaclab\Scripts\python.exe" -B rl_exp/tools/diagnose/local_path_check.py --self_check --break_test mirror_sign
"E:\IsaacLab\env_isaaclab\Scripts\python.exe" -B rl_exp/tools/diagnose/local_path_check.py --self_check --break_test mirror_limits
"E:\IsaacLab\env_isaaclab\Scripts\python.exe" -B rl_exp/tools/diagnose/local_path_check.py --self_check --break_test mirror_stop
"E:\IsaacLab\env_isaaclab\Scripts\python.exe" -B rl_exp/tools/diagnose/local_path_check.py --self_check --break_test mirror_budget
"E:\IsaacLab\env_isaaclab\Scripts\python.exe" -B rl_exp/tools/diagnose/local_path_check.py --self_check --break_test mirror_samples
"E:\IsaacLab\env_isaaclab\Scripts\python.exe" -B rl_exp/tools/diagnose/local_path_check.py --self_check --break_test mirror_closure
"E:\IsaacLab\env_isaaclab\Scripts\python.exe" -B rl_exp/tools/diagnose/local_path_check.py --mirror --source_report rl_exp/out/lizard2_palm_local_path_contact_20261015/report.json --output_dir rl_exp/out/lizard2_palm_mirror_reproduce
```

正常采集退出 0 只表示报告完成，需读每腿失败及闭合字段；负测试应退出 1。

## 未覆盖边界与下一步

本轮仅验证 rf／rl 各自运动、其它腿与躯尾零位；四条腿分别通过不等于四肢组合通过。不改变原路径或处理内部／周期斜率跳变，没有新增另两腿动画、时间映射、世界根运动／材料滑移、承重或 PD 结果。原反曲平面角不冒称完整解剖包络，有限采样不改称全区间安全；不开展连续域证明。

下一步仍需按获准方案处理接缝并明确四肢组合相位、预算与根运动口径；运行时与 A/E、P2/P3 交接继续。两项 work 保持 in_progress，不宣告 A 完成，不把本轮自查替代 D 集成后的独立审核。
