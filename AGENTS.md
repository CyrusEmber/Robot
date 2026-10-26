# Agent Working Rules

- 审核要质疑方案：找隐藏缺陷、脆弱假设、长期风险，并说明如何实际验证；不迎合实现。
- 修改前说明计划；单文件、无 API 变化且一句话可解释的小改动可直接做并自检。
- 直接说明限制；错了承认，不确定就查证。
- 按任务检索 `FILEMAP.md`、家族 `FAMILY.md` 和子系统文档，不整份通读。
- 临时脚本不留仓根；可复读诊断进 `rl_exp/tools/diagnose/`，历史工具进 `rl_exp/tools/archive/`。
- 录制策略视频默认用 `ablation_harness/video_matrix.py` 输出带速度/视角标签的九宫格，保留单段原片；默认三档目标速度 × 三个视角，参数与输出见 `ablation_harness/HARNESS.md`。

## Work 与证据

- 在办事项 `work/active/`，关闭归档 `work/closed/<year>/`，结果唯一归 `acceptance/records/`。
- **新建 work 必须用 `check_work_docs.py --scaffold ... --apply`；禁止手工创建。**
- 活跃事项只写当前状态与未完动作；数值、摘要和完整结论只进验收记录，其它文档留指针。
- 关闭前先置 `pending_review`，由不带执笔历史的新上下文对照实际落点与证据审核；证据变化须重审。
- 审核记录与事项的证据指针同次提交；格式检查通过、记录存在都不代表审核已经完成。
- 未完动作不得随事项关闭而消失；迁移同次建新删旧，不能为预算达标自动取消、关闭或归档。
- 操作 work 或验收记录前，必读 [work-ledger](.codemaker/rules/work-ledger.mdc)；文件格式以 `rl_exp/tools/verify/check_work_docs.py` 模块文档为准。

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
| 版本、配方、PLAN/NOTES/FAMILY | [versioning](.codemaker/rules/versioning.mdc) |
| FILEMAP | [docs](.codemaker/rules/docs.mdc) |
| 编写或修改 skill | [skill-authoring](.codemaker/rules/skill-authoring.mdc) |
| 新增闸门 | `rl_exp/tools/verify/OFFLINE_CHECKS.md` §4：真实缺陷与破坏测试，区分声明一致和行为验证 |
| 迭代收尾、提交、推送 | [git-auto-sync](.codemaker/skills/tool/git-auto-sync/SKILL.md) |
