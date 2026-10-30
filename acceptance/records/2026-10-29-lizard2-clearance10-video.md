# lizard2 两足支撑抬高非支撑脚录像

## 适用范围

用户反馈侧视录像看不清哪些脚抬起，要求抬高一点。使用正式 v6 的隔离导轨、左前＋右后支撑，将右前与左后的名义初始净空由 0.04 m 改为 0.10 m，并调整摄像机视角；不是双轴候选或训练策略。驱动参数、初始支撑方式和停止线沿用 `2026-10-29-lizard2-lift-guide-calibration.md`；用户请求授权本次单独录像，不覆盖此前试验。

## 验收条件

采样前固定目标及身体升高路径，使用实际 URDF 和碰撞网格检查限位、全部实体配对、指定支撑地面及非支撑净空，包含节点与关节线性插值中点；不能由静态几何推断动态平衡。计划一个物理进程、至多一次 2600 子步与 900 s，5 s 稳定、随后按原方案上升/保持/回落/恢复；触发原停止线立即停止，失败不自动重试。实际物理过程逐子步录像、记录同帧数据及读回，图像时间同步不作为精确接触证据。

## 结果

执行前几何候选及全机节点/中点预查通过；初始时两指定支撑足最低点约为地面，右前及左后足最低点约离地 0.10 m，目标在 v6 动作裁剪范围内。实际独立录像试验在 0.130 s、第 26 个物理子步停止，触发 `forbidden_contact` 与 `joint_speed`：尾部 `tail2_pitch` 地面过滤力该帧约 1782.74 N，`tail2_pitch_joint` 速度约 -2.377 rad/s，超过其 4 rad/s 上限的一半。该值是停止帧采样，不是持续负荷；尾部受力/速度的冲击原因尚未作因果验证。

按记录的 base 位姿、实际关节角和 URDF 碰撞网格复算，首帧右前/左后脚最低点约离地 99.76/99.76 mm，停止时约 40.53/38.77 mm；同窗机身 base 高度由约 0.60256 m 降至 0.55629 m。两只脚是在初始化时放到抬高姿态，没有记录从地面主动抬起它们的动作；身体抬高阶段同样尚未开始。脚底是 FK 重建，未独立核 runtime 足部 actor 位姿，不用该高度数值替代实际接触采样。

视频为实际运行中捕获的侧前斜视图，20 帧每秒、每子步重复 8 帧，约 80 倍慢放；原片保留。另在原片副本添加中文状态、右前脚固定屏幕圈注和停止提示，左后脚在远侧受到遮挡；圈注仅用于此固定镜头，像素与物理子步无独立同步校准。离线审计复算两项停止和传递力轴向投影最大差约 9.54e-6 N·m，不能把尾部瞬态接触或投影直接解释为电机能力不足。

## 证据引用

- 活跃事项 `work/active/lizard2-two-foot-body-lift.md`，原试验录像 `acceptance/records/2026-10-29-lizard2-guided-lift-video.md`。
- 本机输入 `rl_exp/out/lizard2_two_foot_body_lift/clearance10_geometry01/v6-lf-rr.json`、预查 `rl_exp/out/lizard2_two_foot_body_lift/clearance10_precheck01/report.json`；生成入口 `rl_exp/tools/diagnose/lizard2_lift_geometry.py --support lf-rr --tail_pitch 0.1 --samples 11 --clearance 0.10` 与 `lizard2_lift_precheck.py --midpoints`。
- 实际试验入口 `rl_exp/tools/diagnose/lift_guided_trial.py`，使用隔离导轨资产与上述输入，录像指定 `--video`，斜视摄像机使用 `--eye 2.5 -4.5 2.5`。输出归本机专用 run 子目录，不覆盖历史工件。
- 本机实际运行视频 `rl_exp/out/lizard2_two_foot_body_lift/guided_clearance10_video01/run.mp4`，带中文标注副本 `run_annotated.mp4`；同目录 `report.json`、`audit.json`、`kinematic_audit.json` 和实际采集 `source.py`。报告 SHA256 `242d254be433da690e268c451fddae9961a29d69cef32ff3fab79529ba064d54`。标注副本由原录像逐帧附加静态屏幕提示，不更改原录像；结果仅属本机工件。

## 未覆盖边界

预查是有限离散几何检查，不验证连续路径、碰撞运行时绑定、实际硬件或步态；试验在稳定与抬身前停止，尚未证明脚掌、膝肘能抬高身体。不得把静态初始化离地当作主动抬脚成功，也不把静止导轨试验当成学习策略表现。
