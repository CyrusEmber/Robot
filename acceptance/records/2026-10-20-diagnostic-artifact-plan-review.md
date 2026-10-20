# 诊断产物整理方案审核与实施前置

## 适用范围

对应 [诊断产物整理事项](../../work/active/diagnostic-artifact-lifecycle.md)。本记录保存用户对方案的五项审核意见及本轮静态核查依据；仅支撑修订实施前置，不是迁移完成证明，也不是事项关闭所需的独立审核。

## 验收条件

实施须证明：旧路径不可用时真实消费者仍能读取保留证据；目标布局经 Git 重新检出后字节身份不变；同名运行在写入前拒绝且旧证据不变；身份校验不被优化模式绕过；两个输出根均纳管且已跟踪产物逐项处置。

具体动作与支持模式取事项“迁移前必须补齐”。每个修复保存修复前失败、修复后通过的行为对照，不能用文本检查替代消费者运行。

## 结果

方案存在以下实施缺口，本轮只修订 work：

1. **消费者定位（高）**：`local_path_view._load` 从报告读取 `source_report`、`identity.build_report`，再读取构建报告中的 `candidate_urdf`；这些路径不会自动使用额外映射。`palm_spatial_runtime.check_build` 还要求输入路径等于固定 `BUILD`，并核候选路径位置。仅移动文件并另存映射不能保证复读。必须接通真实读取路径，同时保留内容与授权校验。
2. **Git 字节身份（高）**：原检查点下的 `.gitattributes` 以局部路径声明 `-text`。本轮 `git check-attr text eol` 显示原 URDF 为 `text: unset, eol: lf`，候选归档路径为 `text: auto, eol: lf`；本机 `core.autocrlf=true`。根规则的 `eol=lf` 也参与生效，不能仅凭 autocrlf 判断必然变字节；但保护范围丢失，必须通过目标布局的入库及重新检出对照验证，不能只比较搬迁前后工作树。
3. **覆盖写入与漏掉输出根（高）**：`diagnose_support.main` 在 `rl_exp/tools/diagnose/out/<label>/` 使用 `mkdir(..., exist_ok=True)`，逐报告及 `summary.md` 用写模式打开。同 label 会复用目录；本项不能只治理 `rl_exp/out/`。尚未在本轮执行重复运行破坏对照，需使用隔离样本验证真实写入路径。
4. **优化模式身份校验（高）**：`local_path_view._load` 对上游、build、候选文件和 FK 摘要使用 `assert`。用户提供无落盘对照：错误 build 摘要在普通模式拒绝，`-O` 接受。本轮独立确认代码使用 assert，但未独立重跑该对照；用户报告不能冒充本轮实测。实施须补普通模式与优化模式拒错对照，并修复或明确在入口拒绝不支持模式。
5. **忽略与保留语义（中）**：`.gitignore` 的诊断条目只覆盖 `rl_exp/tools/diagnose/out/`，注释将 dump 一概描述为可再生成，与唯一证据需保留的边界冲突。本对话此前 `git ls-files -- rl_exp/out` 盘点有 43 个已跟踪文件；该数为历史盘点，执行前必须刷新。新增忽略规则不会自动解除已跟踪文件的索引状态。

以上不证明对应缺陷已修复；work 保持 `open`，不批准据此清理原始证据。

## 证据引用

- 用户在本对话提交的五项审核意见及其无落盘优化模式对照；未提供独立日志附件。
- [读取上游及身份校验](../../rl_exp/tools/diagnose/local_path_view.py)：`_load`。
- [检查点位置授权](../../rl_exp/tools/diagnose/palm_spatial_runtime.py)：`BUILD`、`check_build`。
- [另一输出根与覆盖写入](../../rl_exp/tools/diagnose/diagnose_support.py)：`main` 内目录创建、case JSON 与摘要写入。
- [检查点字节保护](../../rl_exp/out/lizard2_palm_spatial_20261014/.gitattributes)、[根属性](../../.gitattributes)、[忽略规则](../../.gitignore)。
- 本轮只读核查命令：

```powershell
git config --get core.autocrlf
git check-attr text eol -- rl_exp/out/lizard2_palm_spatial_20261014/checkpoint_v3/palm_spatial.urdf rl_exp/out/archive/palm/checkpoint_v3/palm_spatial.urdf
git ls-files -- rl_exp/out
```

候选归档路径仅用于属性匹配，不表示已经迁移或确定最终归档位置。末条用于刷新此前盘点。

## 未覆盖边界

未执行产物迁移、删除、重新检出恢复、同名生产运行或身份校验修复；未穷举所有输出根和消费者；未独立复现用户的 `-O` 对照。文档格式与提交前检查通过不解除这些行为验证前置，实施结果变化后须重新审核。
