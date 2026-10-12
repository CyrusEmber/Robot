# 复杂计划探测链与事项可读性、骨架生成（2026-10-12）

## 适用范围

用户于 2026-10-12 批准：保留当前结构，在复杂 PLAN 加“关键假设 → 最小探测 → 停止条件”；当前整理 lizard2 机体驱动、接触协议、配方采用三条事项；扩展现有生成入口并建立本轮事项。只改写法与骨架，不执行三条事项的技术工作。

本轮落点：`.codemaker/rules/versioning.mdc`、`AGENTS.md`、`FILEMAP.md`、`rl_exp/tools/pipeline/declare_family.py`、`rl_exp/tools/verify/check_work_docs.py`、`rl_exp/tools/verify/test_declare_family.py`、上述三条事项及 `work/active/plan-probe-and-work-readability.md`。工作树中的 Blender/诊断/命名改动属于并行工作，不收进本轮。

## 验收条件

- 复杂 PLAN 骨架列可证伪假设、最小输入/对照、已有命令、观察判据及失败/缺证时的停止动作和责任人；读数仍归记录，已训/冻结 PLAN 不回写。
- 事项保留单行 next/close_when；正文分条呈现动作、审核输入、可观察验收、交接及失败出口，不删未完动作。
- 生成入口默认预览不写盘；显式写入到 work/active，拒绝重复 active/closed id、路径型 id、多行字段及不存在的 scope/landing；骨架不代作决定。
- 使用真实入口验证并留最小回归；不新增机器闸门，不放宽已有验收。

## 结果

### 落地与边界

版本规则新增复杂计划探测链。已有 `declare_family.py` 的新线 PLAN 骨架增加相应节，仍是待填写 TODO；不新增 specs/plans/checklist 层。

`check_work_docs.py --scaffold` 新增事项骨架预览，`--apply` 用独占创建写入，既有字段解析与状态词未变。格式规范要求 next/close_when 只路由，详情在正文，不设长度闸门。三条事项已移动/分条原动作与关闭条件；机体与配方未采用，训练未启动，原状态与 evidence 保持。

### 可复读检查

在仓根运行（项目解释器从 `ablation_harness/host_paths.py --python` 解析，不在规则或事项复制机器路径）：

```text
python rl_exp/tools/verify/check_work_docs.py --self-test
<项目 Python> rl_exp/tools/verify/test_declare_family.py
rl_exp\tools\verify\run_offline_checks.bat
git diff --check
```

- 修改前事项工具：自检与真实仓形状通过，86 个事项文件；增加本轮事项后仍在预算内。
- 修改后事项工具：自检包含预览不写盘、生成可解析、重复不覆盖、closed id/非法 id/多行字段/缺失路径拒绝；真实仓形状通过。
- 新线生成回归：真实子进程在临时单家族树生成文件，新增 `apply/plan-probe-chain` 检查通过。
- 红绿验证：临时撤掉 `_plan_md` 的探测链节，运行同一 `test_declare_family.py`，仅 `apply/plan-probe-chain` 失败；恢复后回归通过，离线套件再次覆盖该检查。
- 事项生成破坏对照：在内存中把 `scaffold` 替换为成功但不写盘的实现，同一自检因缺少产物失败；恢复后自检通过。不改仓内文件，不遗留一次性脚本。
- 离线套件：首次 37/37 通过，46.7 s；Unicode 修复及事项关闭后复跑 37/37 通过，37.5 s（并行工作树快照，不能单独归因本轮）。`git diff --check` 通过。
- 真实 CLI 预览：`python rl_exp/tools/verify/check_work_docs.py --scaffold example-work --title "示例事项" --scope work/active --landing rl_exp/tools/verify/check_work_docs.py` 输出带“下一步/关闭条件”的骨架，未写示例事项。

### 验证过程限制

普通系统 Python 跑 `test_declare_family.py` 因 `gymnasium` 缺失失败；改用 host_paths 解析的项目环境后通过，不安装依赖。

一次内存替换 `_plan_md` 的尝试未使子进程回归变红：测试启动真实生成器子进程，父进程替换不生效。随后按上述临时撤修复方式完成真实红绿验证。最早独立 exec 旧源码的尝试还因未注册 dataclass 模块失败；不当作测试证据。

### 独立审核与修复

首次新上下文审核判 FAIL：字段验证仅拒绝 CR/LF/NUL，而 `_parse` 使用 `splitlines()`，Unicode 行分隔符可注入重复 status。隔离 CLI 实跑 title 为 `Audit\u2028status: done` 时成功写入后解析报重复字段；未作通过结论。

修复将字段验证与 `splitlines()` 行边界一致，并把生成/重复覆盖检查改为经 `main(... --apply)`；CLI 回归覆盖 CR/LF、VT/FF、FS/GS/RS、NEL、LS/PS，拒绝后断言无产物。暂撤修复时同一自检变红，恢复后通过。

复审（独立新上下文，任务 `70db6039-de03-44fc-8000-19795e1dc23e`）判 PASS，无阻塞：实跑预览/生成、active/closed 重复拒绝、非法 ID/缺失路径/空字段及 title/scope/landing 的 66 个行边界案例，全部拒绝且无非法产物；在内存撤掉修复复现 LS 注入，当前实现拒绝。独立重跑事项自检、真实仓形状、新线生成子进程回归与 diff 格式检查通过；对照 HEAD 确认三条技术要求保留、无版本 PLAN 改动。此审核只批准本轮格式与骨架交付，不批准三条 lizard2 技术工作。

## 证据引用

- 文档与事项格式唯一规范：`rl_exp/tools/verify/check_work_docs.py` 模块文档。
- 版本探测链规范：`.codemaker/rules/versioning.mdc` §A。
- PLAN 骨架与回归：`rl_exp/tools/pipeline/declare_family.py`、`rl_exp/tools/verify/test_declare_family.py`。
- 当前整理对象：`work/active/lizard2-body-drive-candidate.md`、`work/active/lizard2-contact-protocol.md`、`work/active/lizard2-family-landing.md`。
- 本轮事项已审核后移入：`work/closed/2026/plan-probe-and-work-readability.md`。
- 提交期间并行会话的 `d5246ae` 已收入 `FILEMAP.md` 路由与 `lizard2-body-drive-candidate.md` 的可读性变更；这两文件不再重复暂存。本轮其余文件按路径限定提交，归属差异由该 commit 保留。

## 未覆盖边界

- 生成器只能省格式与重复写作；未测 token 节省量，不自动发现关键假设、不生成判据/预算或审核结论。
- `declare_family.py` 仍仅服务已有新家族/新线声明流程，不能从零创建任意软件仓库或代填新配方；本轮没有放宽其既有前置。
- 不批量回写历史事项、已冻结/已训版本 PLAN，不执行 S5/S6，不跑仿真或训练。
- 新上下文复审已发生并判 PASS，细节见“独立审核与修复”；后续若实现或验收证据实质改变须重审。
