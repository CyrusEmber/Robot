---
name: lizard-git
description: >
  管理 lizard_migration git 仓（单一真身 + junction 布局）：日常提交、版本冻结打 tag、
  发布与移植。当用户提到"提交代码"、"commit"、"同步到 git"、"打个 tag"、"发版"、
  "冻结版本入库"、"lizard 仓库"、"git 仓"、"推远端/GitHub"、"新机器拉代码/移植到新机器"、
  "lizard_migration"等需求时，务必使用此 skill。
  覆盖：仓布局纪律、提交时机与信息规范、版本-tag 锚点、禁区防护、junction 常见坑。
---

# Lizard Git（单一真身仓管理）

仓 = `E:\lizard_migration\`（lizard_exp + ablation_harness +
.codemaker\skills + README）。实例事实（当前版本/路径/流程细节）以仓内
`README.md` 与 `lizard_exp\FAMILY.md` 为准，本 skill 只载方法与纪律，防漂移。

## 布局纪律（单一真身 + junction）

- **真身只此一份**：所有文件改动发生在仓内（原机经 `E:\IsaacLab\lizard_exp`、
  `E:\IsaacLab\ablation_harness` 两个 junction 触达，路径不变，venv/fork shim 无感）。
  skill 本身同律：真身在仓内 `.codemaker\skills\tool\`，工作区同名 junction 指回。
- **IsaacLab 树内永远不 git 操作我们的目录**：防护 = `.git\info\exclude` 里
  `lizard_exp/`、`ablation_harness/` 两行（本地排除，不动 fork 文件）。
  若在 IsaacLab 出现在 status，说明 exclude 被清，先修防护再干活。
- **不进仓的东西**：IsaacLab 本体、venv、logs（checkpoint/TB 都在
  `E:\IsaacLab\logs\`，属训练产物不是代码）；仓内 `__pycache__` 已被 .gitignore 挡。
- **进仓的记录**：`ablation_harness\results\`（eval 跑分）、
  `versions\vN\tb_scalars.csv`（导出的训练曲线）——记录即数据，随版本提交。

## 日常提交

工作流：在 IsaacLab 树里改代码/参数 → 完成后进仓提交：

```bat
cd /d E:\lizard_migration
git add -A
git commit -m "<一句话：改了什么、为什么>"
```

**提交时机**（对齐训练节奏）：
1. 开新版本 `versions\vN\` 建立时 → 立即 commit + tag（见下节）
2. 版本 NOTES.md 回填训练/eval 结果时
3. 代码修复/工具脚本变更后
4. eval 协议（protocols/）任何改动后

不搞完美主义：训练中的开发态 yaml（`lizard_params.yaml`）改动可攒到
上述节点一起提交，但**冻结目录与协议文件改动必须即时提交**。

## 版本冻结 = commit + tag（锚点纪律）

版本管理的核心：**每个 versions\vN 在 git 里有一个不可动的锚点**。

```bat
cd /d E:\lizard_migration
git add -A
git commit -m "Freeze vN: <一句话摘要>"
git tag vN
```

- 训练复现时 `git checkout vN -- lizard_exp/versions` 即可取回整套冻结配方
- 回填 NOTES.md 结果属于 vN 锚点之后的正常提交，**不打 tag、不重打**——
  tag 只钉"配方冻结那一刻"，结果回填不影响配方可复现性
- 已 push 的 tag 不改名不改指；发现冻结内容错了 = 开 vN+1，不是改 vN

## 发布 / 远端（按需）

- 加远端：`git remote add origin <url>` → `git push -u origin main --tags`
- 仓刻意不含 IsaacLab（README 已声明自装要求 + MIGRATION.md 五步摆位），
  不要为了方便把 IsaacLab 树塞进来
- 新机器消费：clone 仓 → 按 `lizard_exp\MIGRATION.md` 走（装 IsaacLab、
  venv、.pth、fork shim、play.py 补丁），**不需要重建 junction**（那是原机布局）

## 常见坑

- **CRLF 警告无害**：`warning: LF will be replaced by CRLF` 是 Windows 默认
  autocrlf 行为，不理会；若团队跨平台再上 .gitattributes
- **删 junction 用 `rmdir`**（只摘链接），**永远不要对 junction 递归
  del/rd 内容**——会穿透删掉真身文件
- **junction 路径出现在报错里**：有些工具解析出 `E:\lizard_migration\...`
  真身路径，与 `E:\IsaacLab\...` 是同一文件，不是错乱
- **仓里 status 出现大量意外删除**：先确认不是误在 IsaacLab 树内对真身
  做了 move/del；恢复 = `git restore`，别手补
- **IsaacLab 拉取上游后 status 冒出 lizard 相关未跟踪项**：检查
  `.git\info\exclude`（git 操作或重装可能清掉本地 exclude）
