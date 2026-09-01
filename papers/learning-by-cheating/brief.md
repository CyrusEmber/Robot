# Learning by Cheating — Brief

**Learning by Cheating** | CoRL 2019 | [arXiv:1912.12294](https://arxiv.org/abs/1912.12294)

## 一句话概括

先用真值信息"作弊"训练特权 agent，再把它蒸馏成纯视觉学生——privileged teacher → sensor student 范式的开山作。

## 要点

- 两阶段：特权 agent（观测真值环境布局 + 全部交通参与者位置）→ 作为 teacher 蒸馏出纯视觉 sensorimotor 学生（测试时无任何特权信息）
- 首次在 CARLA 原始 benchmark 全任务 100% 成功率，NoCrash 新纪录，违规率比当时 SOTA 低一个数量级
- 确立了"特权训练 + 传感蒸馏"研究家族（DriveAdapter、TransFuser 系、LEAD 均在此框架内）
- 2019 结论是"特权 teacher 超好用，直接模仿"；2026 LEAD 修正为"好用的前提是控制 teacher/student 信息不对称"

## 优点

- 把"感知 + 决策"解耦成两阶段，各自学习难度大幅下降，训练稳定
- 范式通用、工程成本低，直接催生一个研究家族
- CARLA 闭环成绩当时碾压级领先

## 缺点与局限

- 学生只能模仿 teacher 行为：teacher 看得到而学生物理上看不到的（遮挡、不确定性）成为学生学不到也推不出的盲区，2019 年论文未处理此不对称（解读）
- 特权 agent 质量上限即学生上限；行为克隆偏差靠 DAgger 补偿有限
- 全程 CARLA 仿真内蒸馏，sim-to-real 未验证

## 方法对比（论文内）

- 对比当时端到端 IL / 条件模仿学习（CIL）系 baseline：两阶段特权蒸馏在 CARLA 与 NoCrash 各难度全面领先，违规率低一个数量级（论文摘要级结论；单元格级数字待核实）

## 结果

- 原始 CARLA benchmark：首次全任务 100% 成功率
- NoCrash benchmark：新纪录
- 违规（infraction）频率：比先前 SOTA 降低一个数量级

## 极简 Input / Output / 实现

- `Input:` 学生 = 前视相机 + LiDAR(BEV) + GPS + 车速；特权 agent = 真值 BEV 布局 + 全部交通参与者位置
- `Output:` 未来路径点序列（plan），PID 转转向/油门
- `实现:` CARLA；特权 agent 在真值 BEV 上 RL → 感知模块监督学 BEV 语义 → DAgger 式蒸馏把特权 agent 的 plan 传给视觉学生

## 与当前 SOTA 的对比

- 范式仍是主流：DriveAdapter (ICCV 2023) 明确把当时 SOTA 端到端驾驶描述为"特权 teacher（真值周车/地图状态）+ 传感 student"
- 2026 NVIDIA LEAD（[arXiv:2512.20563](https://arxiv.org/abs/2512.20563), CVPR 2026）系统性定义三种不对称——visibility / uncertainty / intent——证明特权 expert 仍有用，但须"以学生为中心"设计 teacher/student 接口；其 TransFuser v6 刷新 CARLA 闭环全线 SOTA（Bench2Drive 95 DS、Longest6 v2 62 DS、Town13 15 DS）
- 2025/2026 risk-aware distillation：RL teacher 带特权 BEV/risk 信息 → 蒸馏视觉学生（用户提供，待核实）
- 演化主线：2019"特权 teacher 超好用 → 直接模仿" → 2026"特权 teacher 超好用，但要回答 teacher 知道什么而学生不可能推断 → 精心设计 teacher/student 接口"
