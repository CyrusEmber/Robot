---
name: paper-summarizer
description: 将机器人学/强化学习/运动控制/游戏AI相关论文总结为固定的12点结构化字段表+七段详细总结（含与当前 SOTA 的对比），或按"精简总结"模式只输出优缺点、方法对比、结果与当前 SOTA 对比，服务于游戏开发技术调研。当用户提供论文链接或论文名并要求"总结论文"、"论文笔记"、"按这个格式总结"、"paper summary"、"读一下这篇论文"、"调研论文"，或想整理 locomotion/RL/角色控制类论文笔记时，务必使用此技能。用户说"精简总结"、"简版"、"简要总结"时用精简模式。
---

# Paper Summarizer（论文调研笔记）

把论文压缩成统一格式的调研笔记，便于多篇论文横向对比，并直接服务于游戏开发决策（locomotion / 动画 / 角色 AI 选型）。

## 模式

- **标准模式（默认）**：12 点字段表 + 七段详细总结（含 SOTA 对比段），见工作流程 3~6。
- **精简模式**：用户说"精简总结 / 简版 / 简要总结"时启用。只输出：元数据一行（论文名、年份 venue、链接）+ 优点 + 缺点与局限 + 方法对比（论文内与 baseline/相关方法的对比结论）+ 结果（核心数字结论）+ 与当前 SOTA 的对比。不写实验过程、训练管线、实现细节。结构与规范见 `references/format-template.md` 精简模式一节。

## 工作流程

1. **获取论文**：元数据（标题/作者/年份/venue）以 arXiv abs 页为准；需要正文与附录细节（网络尺寸、reward 逐项、噪声配置等）时抓 TeX 源码 `https://arxiv.org/src/<arxiv_id>`（tar.gz，解包后定位 main.tex 递归读），比 PDF 可靠且能拿到附录，可消除"凭记忆，待核实"。abs 页信息不足时补抓项目主页或搜索结果。PDF 直抓常失败，不要依赖 PDF 链接。
2. **元数据核对（强制）**：
   - 标题、作者、机构、年份、发表 venue 必须以 arXiv/官方页面为准，不得凭记忆填写。
   - arXiv ID 与论文名不符时，必须向用户指出错误并给出正确链接（相近 ID 对应不同论文是高频错误）。
   - 年份以论文首发为准（arXiv 提交或会议收录），附 venue，Oral/Spotlight 可注明。
3. **填 12 点字段表**：字段定义与填写指南见 `references/format-template.md`，先读它。
4. **写详细总结**：七段结构（背景与动机 / 方法详解 / 实现与部署 / 实验与泛化 / 局限 / 与当前 SOTA 的对比 / 对游戏开发的启示），结构见模板文件。方法详解必须写到可复现粒度：训练管线分阶段、观测与动作空间逐通道、reward 逐项、噪声与随机化逐项（含作用域与课程退火）、网络结构尺寸——论文正文和附录给的都要收，宁可长不可糊。
5. **SOTA 对比（强制，两种模式都做）**：结合网络搜索核实该方向截至当前的 SOTA 工作，回答"这篇论文今天还剩多少价值"：哪些结论已被新工作超越或修正、哪些机制被后续 SOTA 吸收沿用、SOTA 视角暴露的本文盲点。例：总结 Learning by Cheating 时应指出 LEAD / TransFuser v6 这条线证明 privileged expert 仍有用，同时暴露 learner–expert asymmetry——expert 能看到学生因遮挡/不确定性物理上看不到的东西。搜索核实的与凭记忆写的 SOTA 事实必须区分，后者标"（待核实）"。
6. **我的结论**：先基于论文内容给出建议结论，聚焦"对当前游戏项目可借鉴什么、不该照搬什么"；用户已写结论时以用户的为准，可帮其校验是否有论文事实支撑。
7. **入库（可选）**：存入仓库根目录 `papers/`（结构见 `references/format-template.md` 第五节）：`papers/<论文名短横线>/brief.md` 必存；用户要详细总结时再生成 `papers/<论文名短横线>/detail.md`，只写 brief 没有的可复现细节。同时在 `papers/INDEX.md` 对应分类下加一行（论文名链接、一句话概括、要点）。入库前先读一篇现有 brief 对齐粒度。

## 输出规范

- 中文为主，专业术语保留英文原词（gait、policy、proprioception、reward shaping 等不硬译）。
- 术语优先用论文原文措辞；自己加的解读性标签（如"DAgger 式"、"类似 XX 机制"）必须显式标注"（解读）"，与论文原词区分。
- 每个字段一句话说清，不堆砌；12 点用表格输出。
- "能力"字段只列论文实际演示的行为，不写论文没展示的东西。
- 数值类事实（网络结构、速度范围、机器人型号）必须核实；不确定就标"待核实"，禁止编造。
- 直接引语必须来自本次实际抓取的内容；凭记忆复述的"原文"（尤其补充材料/附录，常不在 arXiv HTML 内）必须标注"（凭记忆，待核实）"，与已核实引文严格区分。
- 完整示例见 `references/example-walk-these-ways.md`，总结新论文前先读示例对齐粒度与口吻。

## 参考资料

- `references/format-template.md` — 12 点字段定义、Game Friendly 评级标准、详细总结七段结构、精简模式、papers/ 入库结构
- `references/example-walk-these-ways.md` — Walk These Ways (CoRL 2022) 完整示例，含链接勘误记录
- `references/example-miki-perceptive-locomotion.md` — Miki et al. (Science Robotics 2022) 完整示例，含勘误记录与"已核实 vs 待核实"清单
- 外部参考：[huangkiki/dailypaper-skills](https://github.com/huangkiki/dailypaper-skills)（1.2k star）— Claude Code 论文流水线：每日抓取 HF Daily/arXiv → 按研究方向打分（必读/值得看/可跳过）→ paper-reader 生成结构化笔记 → Obsidian 概念库 + 目录页自动刷新，支持 Zotero。定位是"发现新论文"，与本 skill"深读沉淀"互补；若以后要做每日筛选/批量入库，参考它的抓取-打分-笔记三段拆分。TeX 源码抓取法（`arxiv.org/src/<id>`）借鉴自 karpathy/nanochat 的 read-arxiv-paper skill。
