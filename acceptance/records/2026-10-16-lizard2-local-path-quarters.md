# 两腿原局部路径的四分点几何检查

## 适用范围

承接 `acceptance/records/2026-10-16-lizard2-local-path-postprocess.md`。用户选择先补段内几何检查：不改原轨迹或容差，每段增加 1/4、3/4 检查点，每腿最多 64 个新姿态；核接地、全机穿地、实体碰撞及翻掌，首个失败立即停止。获准动作是有限加密，不称连续域证明，不自动扩展到四肢或平滑接缝。

主执行者直接实现、运行和自查，无子任务或独立关闭审核。不改正式资产、ROM、PD、冻结配方，不起仿真或训练。本轮未发现新四分点失败，未进入分支修复或改变采集求解条件。

## 验收条件

- 独立入口消费相同 `budgeted_local_path` 绑定；原接受端点／中点只作源证据，新增姿态是原完整关节向量的线性插值，不重新求解或平滑。
- 每条原接受段固定 u=0.25/0.75；每腿新姿态不超过 64，失败即停止，完整源路径通过与部分前缀通过分开记录。
- 根姿态、全部候选文件、采集／几何代码及 139 对检查／14 对排除保持一致，使用原 1e-5 m 数值接地／穿地容差、0.05 rad 关节步距，不改碰撞过滤或安全余量。
- 每个新姿态核全部碰撞实体地面、实体相交／包含、掌法向、原膝肘反曲禁区及 URDF 限位；接地后摆核最低特征接地，落掌按起点—四分点—中点—四分点—终点的顺序核高度不增加。
- 同一实际函数的采样位置、停止、预算、接地拒错及落掌检查破坏须令正常自检失败；正常采集退出 0 不当腿通过证据。

## 结果

### 实现与解耦

新增 `rl_exp/tools/diagnose/local_path_check.py`，与 `local_path_view.py` 的纯显示入口分离。复用其 `_load` 的原报告、候选文件与 FK 对齐检查，再复用 `palm_spatial_probe._static_prepare` 的真实五轴链、完整候选、全部检查对、独立 stdlib FK 对照，以及 `_static_ground/_static_pair_readings/_local_failures` 的原几何口径。没有重写 FK、碰撞器或求解器；导入探测模块只复用读点和拒错，不调用 least_squares 或路径采集。

`_quarter_check` 顺序遍历原接受段，按全部具名关节线性插值，检查预算先于读点。`_state` 保留 30 个完整关节、18 个碰撞实体最低读点、最低顶点身份、掌法向、膝肘平面角、实体相交／包含、正间隙与零间隙未相交对。末项不被冒称安全；正间隙可能是 AABB 下界。每帧五轴 numpy FK 与独立 stdlib 链 FK 对照。

原端点／中点的几何判词没有重跑，不计入本轮 64 点预算；但它们的名字、FK 显示一致性、完整关节与其它关节零值经输入检查。源报告和采集源码未改；本轮只对新四分点给判词，不把新报告混成旧报告的重新身份。

### 输入与实际结果

源：`rl_exp/out/lizard2_palm_local_path_contact_20261015/report.json`；绑定 `checkpoint_v3/build.json` 的同一候选。根姿态、采集代码和几何依赖摘要、候选 38 文件及完整检查／排除对一致。输出：`rl_exp/out/lizard2_palm_local_quarters_20261016/report.json`。

| 腿 | 新姿态 | 完整检查段 | 四分点失败 | 接地后摆四分点最大绝对高度 [m] | 全机新采样最小地面高度 [m] |
|---|---:|---:|---|---:|---:|
| lf | 64 | 32 | 无 | 6.6462888360e-7 | -6.6462888360e-7 |
| rr | 64 | 32 | 无 | 3.5056355108e-6 | -3.5056355108e-6 |

两腿 `full_source_loop_quarters_pass=true`，共 128 个新姿态；未超过预算、没有通过缩短轨迹或少检查来取得结果。新采样未检出实体相交／包含、反面掌、原反曲禁区、限位失败或落掌采样顺序高度增加。最低掌法向 z：lf 0.9981391549，rr 0.9978848073。接地后摆最低特征身份 lf 为 320，rr 为 320／380；特征变化不称无滑移滚动。

全机读数包含微小负高度，仍在原 1e-5 m 数值容差内；不能说物理意义上完全零穿透。报告记录全部读点，不把全机最低值为别腿接地误当目标掌接地；接地条件单独读活动掌最低高度。

执行者另核：全部 128 行有原 u=0.25/0.75、原段索引与实际 s，具名关节向量逐值等于起点+u×端点差；每行完整 30 关节、18 个实体读点和失败项为空。候选、代码、源报告与输出摘要复读通过；原轨迹、动画和接缝读数未变。

### 回归与仓库检查

正常 `--self_check` 通过。合成隐藏接触带在 u=0/0.5/1 高度为零、u=0.25 超出容差，用同一实际 `_quarter_check` 捕捉，1 个调用即停，复核 s 与插值角度。将四分点改回仅中点（`fractions`）、取消失败停止（`stop`）、取消预算（`budget`）、关闭原接地判据（`contact`）或关闭落掌向下一原采样点的单调检查（`landing`），同一自检均退出 1；恢复后退出 0。还覆盖穿地、翻掌、反曲、实体相交与限位失败的传播。此为行为拒错，不新增“报告存在即通过”闸门。

完整既有离线套件 37/37 通过，53.0 s；baseline 波内 25.3 s、单独复跑 21.0 s，符合原 25 s 单项预算。未增减套件或改预算。工作格式与实现提交 `02e0aa6` 的全部提交钩子通过，既有输出重跑被拒绝且内容不变，最终源码绑定复核通过；这些检查不替代独立审核。提交曾与其它会话撞索引锁，确认并行进程结束、锁自然释放后正常提交，未删除锁或改动他人索引。

## 证据引用与复读

- 源路径修复：`acceptance/records/2026-10-15-lizard2-palm-local-contact-repair.md`。
- 已采显示与接缝：`acceptance/records/2026-10-16-lizard2-local-path-postprocess.md`。
- 实现：`rl_exp/tools/diagnose/local_path_check.py`；方法路由：`rl_exp/docs/leg_geometry_reuse.md`。
- 源报告 SHA256：`f0671a53a8d5b97c40844f6ea771b655bdd3bf8d5ab98ef64b02a1a7550a34c8`。
- 四分点报告 SHA256：`be290ca097e26be6edc6cbf829dd74f2b3eae2606fc9c5bcca7862bebf43d7d7`。
- 检查源码 SHA256：`c54550f099d720364dae63f5cc1d1ef19acbb7cf7fb9b5c0ab6b28b4d9d6e7fe`。
- 报告保留原来源、全部候选／代码身份、采样口径及逐点判词；本机产物不承诺入仓。

从仓根运行，解释器由 `python -B ablation_harness/host_paths.py --python` 解析。复读输出目录必须不存在：

```cmd
"E:\IsaacLab\env_isaaclab\Scripts\python.exe" -B rl_exp/tools/diagnose/local_path_check.py --self_check
"E:\IsaacLab\env_isaaclab\Scripts\python.exe" -B rl_exp/tools/diagnose/local_path_check.py --self_check --break_test fractions
"E:\IsaacLab\env_isaaclab\Scripts\python.exe" -B rl_exp/tools/diagnose/local_path_check.py --self_check --break_test stop
"E:\IsaacLab\env_isaaclab\Scripts\python.exe" -B rl_exp/tools/diagnose/local_path_check.py --self_check --break_test budget
"E:\IsaacLab\env_isaaclab\Scripts\python.exe" -B rl_exp/tools/diagnose/local_path_check.py --self_check --break_test contact
"E:\IsaacLab\env_isaaclab\Scripts\python.exe" -B rl_exp/tools/diagnose/local_path_check.py --self_check --break_test landing
"E:\IsaacLab\env_isaaclab\Scripts\python.exe" -B rl_exp/tools/diagnose/local_path_check.py --source_report rl_exp/out/lizard2_palm_local_path_contact_20261015/report.json --output_dir rl_exp/out/lizard2_palm_quarters_reproduce
```

正常采集退出 0 只表示报告采集完毕，应读各腿失败详情和 `full_source_loop_quarters_pass`。破坏自检应退出 1。

## 未覆盖边界与下一步

结合原端点／中点，现在每段有 u=0/0.25/0.5/0.75/1 的有限采样证据；不是任意 u 接地／碰撞证明。没有检查更窄的离地／穿透／相交带、连续距离界、材料滑移或承重；原反曲平面角也不冒称完整解剖方向包络。局部探索尺度仍不是合理步长、抬脚高度或自然步态批准值。

本轮新四分点通过，故不修改原分支或为无实测失败增加求解复杂度。接缝斜率跳变仍保留；下一步明确是否及怎样处理接缝，按获准相位和预算核实际另两腿镜像与四肢组合，再决定是否需要更强的段内验证。超预算的采样、时间映射及平滑重新验证须先确认；两项 work 保持 in_progress，不宣告 A 完成或完整 5a 交付。
