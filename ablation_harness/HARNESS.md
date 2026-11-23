# Locomotion 评测

`eval.cmd --ckpt <checkpoint> --protocol locomotion_eval_v3` 默认跑 robust。可以显式使用 `--mode nominal`。旧 v7 没有内嵌签名时，从相邻的 `model_5999.pt.interface.json` 读取，并核对权重摘要；用 `--exp rl_exp/lizard2_v7.py` 指定实验。

- `metrics/eval.json` 保存实际工况、速度误差、跌倒、位移、能耗、停车残速、各地形与命令窗口的有效样本。robust 另记扰动与恢复。离地高度缺测时记录覆盖数。协议没有总通过阈值时，结果保留为未定义。
- `video/matrix.json` 索引三档速度 × 三个视角的九段原片。`video/plane_overview.mp4` 是带标签的合成片。录像采用平地 nominal 工况，robust 扰动及恢复由数值评测覆盖。
- `metrics/execution.json` 和 `video/execution.json` 记录命令、时间和退出状态，日志在同目录。

按九段录像检查步态，再决定放弃、续做或采纳。普通试验的证据保存在 Run。重大决定才补充一份短验收记录，写实际看片观察和结论。

[协议目录](protocols/)保留各版时间线、地形和阈值。比较结果时使用相同权重、协议、seed、框架和采样口径。
