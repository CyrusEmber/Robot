# lizard2 后肢恢复原尺寸并保持四掌共面（2026-10-13）

## 适用范围

用户要求“先把后腿缩小回来”，撤销单标本比例放大，保留此前确认的四掌同一水平地面。当前候选改取本记录；放大样本与其记录仅作历史对照，不删除、不覆盖。恢复 natural-ground-tail 源的大腿、小腿与后掌长度，保持前肢长度、机身体高、颈尾、前上臂向后/后股骨向前、下段竖直；骨头、实体与掌根一致。四掌共面为中立站姿约束，不约束整个步态周期。

落点：`rl_exp/blender/scripts/lizard2_specimen_proportions.py --restore_source_lengths`。从已锁哈希的原尺寸源重建，不对放大产物反复缩放。默认历史比例模式保留。

## 验收条件

保存重开后，各腿逐段长度须匹配源，四掌共面、原绑定、骨头与网格连接、方向和镜像均须成立；实际转动与独立刚体预期一致。旧放大样本必须被恢复检查拒绝，抬掌负例必须被共面检查拒绝。碰撞如实登记，不扩大接受范围。

## 结果

本地当前候选：`rl_exp/blender/lizard2_hindlimb_restored/sample_neutral.blend`；SHA256 `2caf7e17fb327c6fb424ea8eaf7fbedc7e7766a308d70c0cdc93bddd52f33560`。源为 `rl_exp/blender/lizard2_palm_p2_sample_claw_all_lowered_body75_vertical_tail_ground/sample_neutral.blend`，SHA256 `c6566679f514581dd972e40dfbbb9d6f115a43e975f861ab4c57a53e3496ca47`，生成前后未变。

| 实测 [m] | 后左 | 后右 |
|---|---:|---:|
| 上段 | 0.501658604 | 0.501658675 |
| 下段 | 0.382120422 | 0.382120305 |
| 掌根至末端 | 0.279844522 | 0.279844522 |

四掌最低 Z 均为 −0.971132159 m；共面与逐段恢复源长度断言通过。为消除源站姿微小共面误差，重求关节点位置，不要求中立姿态与源逐字节相同。非腿 actual head/tail、pose basis 与世界网格保持源值。

生成及独立保存重开检查均退出 0；全部预期顶点变换、实体端盖、掌根连接、骨/网格镜像和上下段方向通过。四腿肘/膝、腕/踝各 ±10° 的 16 档真实转动核对最大残差 4.172325134277344e−7 m，小于 float32 构造界 2.781680814223364e−5 m。该界不是 ROM 或碰撞容差。抬高前左掌 0.01 m 的真实负例被共面断言拒绝并恢复。

对旧放大候选运行恢复模式的 check-only，实际退出 1，命中 `source length not restored: rl:upper_m`；对恢复候选同一检查退出 0，防止仅切换文档而未缩回几何。

默认比例模式对旧放大候选的 check-only 仍退出 0，原文件哈希未变。提交前 `check_suite_banners`、`framework_pin_check --strict --self-test`、`check_dr_parity --strict`、`check_version_docs`、`check_work_docs`、`check_obs_protocol --live` 均通过；记录初次缺标准章节，被格式闸门拒绝后补齐并复跑通过。既有框架 dirty、历史 tag 与限速警告保留，闸门不证明新候选动力学。

中立下段—掌表面交叉对数为前左/前右/后左/后右 7/7/9/9，仍有连接区相交；不代表碰撞通过。图像已生成并查看斜视预览。完整动作周期、肩髋运动表达能力、机械限位、质量惯量、PD、导出及物理仍未验证；维持 A/P2，不作为正式采用或步态通过。reward 与现行运行配置未改。

## 证据引用

仓根 PowerShell：

```powershell
& 'E:\SteamLibrary\steamapps\common\Blender\blender.exe' --background --factory-startup --python-exit-code 1 --python rl_exp/blender/scripts/lizard2_specimen_proportions.py -- --restore_source_lengths --output_dir E:/Robot/rl_exp/blender/lizard2_hindlimb_restored --check_only
```

新建时选择新的独立输出目录并去掉 `--check_only`；已有目录拒绝覆盖。恢复负例：同一命令仅将输出目录改为 `E:/Robot/rl_exp/blender/lizard2_specimen_hindlimb`，保留 `--check_only`，应非零退出。原始报告 `rl_exp/blender/lizard2_hindlimb_restored/measurements.json`；四视图在同目录。产物仅本地，代码与记录进仓。

依据：用户本轮回退要求；历史比例记录 `acceptance/records/2026-10-13-lizard2-specimen-hindlimb.md`；旧源限位探测 `acceptance/records/2026-10-13-lizard2-palm-limit-candidate-probe.md` 不能自动算作恢复候选的限位验收。

## 未覆盖边界

本轮仅恢复尺寸并保留中立四掌共面；有限角度转动检查不证明完整 ROM 或拟真步态。未完成整机碰撞、运动轴能力、导出及驱动验证，不关闭机体与驱动事项。
