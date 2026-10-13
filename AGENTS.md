# Agent Working Rules

- 审核要质疑方案：找隐藏缺陷、脆弱假设、长期风险，并说明如何实际验证；不迎合实现。
- 修改前说明计划；单文件、无 API 变化且一句话可解释的小改动可直接做并自检。
- 直接说明限制；错了承认，不确定就查证。
- 按任务检索 `FILEMAP.md`、家族 `FAMILY.md` 和子系统文档，不整份通读。
- 临时脚本不留仓根；可复读诊断进 `rl_exp/tools/diagnose/`，历史工具进 `rl_exp/tools/archive/`。

## Work 与证据

- 在办事项 `work/active/`，关闭归档 `work/closed/<year>/`，结果唯一归 `acceptance/records/`。
- **新建 work 必须用 `check_work_docs.py --scaffold ... --apply`；禁止手工创建。**
- 操作 work 或验收记录前，必读 [work-ledger](.codemaker/rules/work-ledger.mdc)；文件格式以 `rl_exp/tools/verify/check_work_docs.py` 模块文档为准。

## 按任务必读

以下规则按任务读取，不依赖编辑器自动加载 `.mdc`；不相关的不加载。

| 任务 | 入口 |
|---|---|
| 代码、API、依赖、测试、文件头、CI | [isaaclab-development](.codemaker/rules/isaaclab-development.mdc) |
| 版本、配方、PLAN/NOTES/FAMILY | [versioning](.codemaker/rules/versioning.mdc) |
| FILEMAP | [docs](.codemaker/rules/docs.mdc) |
| 编写或修改 skill | [skill-authoring](.codemaker/rules/skill-authoring.mdc) |
| 新增闸门 | `rl_exp/tools/verify/OFFLINE_CHECKS.md` §4：真实缺陷与破坏测试，区分声明一致和行为验证 |
| 迭代收尾、提交、推送 | [git-auto-sync](.codemaker/skills/tool/git-auto-sync/SKILL.md)；只提交本轮文件，不用 `git add -A` / `git add .` |
