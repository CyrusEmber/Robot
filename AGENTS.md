# Agent Working Rules

- 审核要质疑方案：找隐藏缺陷、脆弱假设、长期风险，并说明如何实际验证；不迎合实现。
- 修改前说明计划；单文件、无 API 变化且一句话可解释的小改动可直接做并自检。
- 直接说明限制；错了承认，不确定就查证。
- 仓库入口、训练评测和人工记录见 [README](README.md#实验何时需要人写字)。按任务检索相关代码与文档，不整份通读。
- 临时脚本不留仓根或输出根；一次性操作优先系统临时目录并在使用后清理，可复读诊断进 `rl_exp/tools/diagnose/`，历史工具进 `rl_exp/tools/archive/`。诊断输出和日志按事项组织；同一事项的运行或重试可共用目录，以不同文件名或标识区分，禁止覆盖已有产物。保留失败现场和未核定证据，不按日期自动删除。

## 实现与验证红线

- 破坏公开 API 前须先在此前版本弃用；避免新增依赖，优先复用已有能力。
- 回归测试必须验证修复前失败、修复后通过；只跑通过不能证明覆盖了缺陷。
- 新闸门须对应真实缺陷并有破坏测试；声明一致不能单独作为行为能力已验证的依据。
- 提交前完成相关检查与仓库闸门；只提交本轮明确归属的文件，禁止 `git add -A` / `git add .`。
- 不强推、不改写已推历史；提交、推送及分组细则按下方 git-auto-sync 执行。

## 按任务必读

以下规则按任务读取，不依赖编辑器自动加载 `.mdc`；不相关的不加载。

| 任务 | 入口 |
|---|---|
| 代码、API、依赖、测试、文件头、CI | [isaaclab-development](.codemaker/rules/isaaclab-development.mdc) |
| 编写或修改 skill | [skill-authoring](.codemaker/rules/skill-authoring.mdc) |
| 迭代收尾、提交、推送 | [git-auto-sync](.codemaker/skills/tool/git-auto-sync/SKILL.md) |
