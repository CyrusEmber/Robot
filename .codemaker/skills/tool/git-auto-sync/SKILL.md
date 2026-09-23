---
name: git-auto-sync
description: >
  通用 git 迭代同步：AI 完成一次迭代（改代码 / 修 bug / 冻结版本 / 回填结果 /
  改协议）后自动 commit + push 更新云端仓库，不限于任何具体项目。
  当用户提到"提交"、"commit"、"push"、"同步云端"、"更新远端"、"推 GitHub"、
  "打个 tag"、"发版"、"冻结版本入库"、"git 仓"、"一次迭代完成，同步一下"等需求时，
  或 AI 刚完成一轮代码改动即将收尾时，务必使用此 skill。
---

# Git Auto Sync

**默认行为：每次工作迭代收尾（改动闭环 / 结果回填 / 版本冻结）自动 commit + push，
不再请示。** 推送失败只报告原因，绝不强推。仓的实例事实（路径 / 远端 / 当前版本）
以各仓 `README.md` 与项目文档为准，本 skill 只载方法与纪律。

## 核心规则

- **无改动不造空 commit** —— status 干净就报告"无改动"
- **只暂存本次迭代涉及的文件** —— 禁 `git add -A` / `git add .`
- **推送只增不改历史** —— 绝不 force / amend 已推提交
- **commit 不带 AI 署名**（Co-Authored-By 等归属行）
- 每次提交内容向用户汇报

## 触发场景

满足其一即执行，无需请示：代码/配置/文档改动闭环、版本冻结、记录回填
（训练结果 / eval 跑分 / NOTES 报告）、用户明说提交同步。
不触发：改动半途、讨论中、用户明说"先别提交"。

## 工作流程

1. `git status` + `git diff --stat` 审查改了什么、是否该提交
2. 分组提交（见粒度节），写规范 message
3. `git push`；有 tag 时 `git push --tags`
4. 汇报：提交哈希 + 一句话内容 + 远端状态

### 提交粒度与信息规范

- **一次迭代一组提交**：代码 / 文档 / 版本冻结分开，不混成一坨；纯格式噪音
  （编辑器重排）单独或并入相关改动
- **message**：subject 与 body 空行分隔；subject 命令式、~50 字符、无句尾句号；
  body 72 字符换行，讲 what/why 不讲 how；中英随仓库惯例
- **版本族提交前缀** `<family>-vN[.minor]:` —— 多版本家族并存时裸 `vN` 有歧义；
  非版本提交用普通 conventional subject
- **分支纪律**：默认单分支开发直提 main，非必要不开分支；开了就要收，合回即删
  （本地+远端），不留死分支（main 落后活跃分支 = 分叉未回卷，发现即合）。
  真走 PR/分支流程时，迭代反馈加新 commit 不 amend

### 暂存纪律（多会话共用工作树）

- `add -A` / `add .` 会扫进工作树里别人的在办改动 ⇒ 归属丢失、回滚粒度变粗、
  review 看到两件事。提交前先 `git status`，逐路径 `git add`；归属不明的不 add
- **逐路径 add 仍不够**：`git commit` 交的是整个索引，他人于你 `add` 与 `commit`
  之间暂存的内容会混入你那一笔 ⇒ 用 `git commit -m "..." -- <本次路径...>` 限定，
  只提交这些路径的工作树内容；未跟踪文件先 `git add`（pathspec 只认已知路径），
  两步都要
- **别用裸 `git reset` 清索引**（会拆下他人已暂存内容）；要撤只撤自己的：
  `git restore --staged <自己的路径>`
- 拆一笔未推的混装提交：先确认未推（`git branch -r --contains <sha>`），
  `git reset --soft HEAD~1` 后按上面的 pathspec 法分笔，仍禁 `add -A`

## 版本冻结 = commit + tag（锚点纪律）

适用于一切冻结语义版本：训练配方、评测协议、数据集。

```
git add <冻结文件...> && git commit -m "Freeze vN: <摘要>" && git tag vN && git push --tags
```

- **冻结提交只含该版本文件集**，不用 `git add -A` 收尾 —— 并行会话在办改动、
  他人 WIP 不归这次冻结
- 复现 = `git checkout vN -- <冻结目录>`
- 锚点之后的结果回填是正常提交，**不重打 tag**
- 已推送的 tag 不改指不改名；冻结内容错了 = 开 vN+1

## 安全纪律（推送 = 共享状态操作）

- **绝不** `--force` / `--force-with-lease` / 改写已推历史 / amend 已推提交
- 仓自带验证闸门 / pre-commit 钩子 **commit 前必跑**（各仓闸门入口见其
  README/项目文档）；钩子改了文件 → review + `git add` + 重跑，全绿才 commit，
  推前再核一遍 —— 先 commit 后跑 = 逼 amend，先推后跑 = 推坏代码。code review
  时也顺带跑闸门
- 推送前扫 diff：密钥、token、绝对路径泄漏、意外大文件（资产/数据集/权重）
- 无远端 → 一次性问用户要 URL；push 报错（网络/权限/非快进）→ 报告，
  不 retry 循环，更不强推
- push 被沙箱拦（网络封锁）→ 用 `dangerouslyDisableSandbox: true` 让用户拿审批
  弹窗，别叫用户手动跑
- **绝不推公共上游 origin** —— 推自己 fork 或 PR 所属远端；不明确先问用户
- 敏感实验代码默认建议私有仓

## 进仓 / 不进仓（通用判据）

| 进 | 不进 |
|---|---|
| 源码、配置、协议、文档 | venv / 环境目录 |
| 评测跑分、导出的指标 csv（记录即数据） | 训练产物（checkpoint / TB 事件文件） |
| 冻结版本目录（含 NOTES） | `__pycache__` / 编辑器缓存 / OS 垃圾文件 |
| 工具脚本 | 大体积资产二进制（另走 LFS 或制品库） |

新仓起步 `.gitignore` 至少挡：`__pycache__/`、`*.pyc`、venv 目录、logs。

## 布局：单一真身 + junction（Windows）

- 真身只在仓内；宿主树内同名目录 = junction
- 宿主树若是 git 仓，junction 目录进 `.git\info\exclude`，防误 add 穿透链接
- 新机器消费：clone 仓 → 按仓根 `README.md` 摆位步骤走，不重建 junction
  （那是原机布局）
- 删 junction 只准 `rmdir`（只摘链接）；递归删会穿透删真身
- 报错中真身路径与链接路径混用 = 正常，同一文件

通用原则：**任何时刻一份真身** —— 仓即工作树，或链接回接；不接受 copy 双份
靠人肉同步。

## 注意事项

- CRLF 警告（`LF will be replaced by CRLF`）无害，跨平台协作再上 `.gitattributes`
- status 大量意外删除 → 先查是否误动真身（move/del），恢复用 `git restore`
- 宿主仓 status 冒出本该 exclude 的目录 → `.git\info\exclude` 被清，先补防护
- 首次 push 弹浏览器登录 = Credential Manager 正常流程
- tag 推送要显式 `--tags`（普通 push 不带 tag）
