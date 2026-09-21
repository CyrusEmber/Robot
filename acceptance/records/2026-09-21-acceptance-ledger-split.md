# ACCEPTANCE 分流（批次 3）：按主题迁成记录 + 路由表

## 适用范围

`rl_exp/versions/lizard/ACCEPTANCE.md` 的分流：把"逐批次追加的验收日志"拆成按主题的独立记录，
原文只留迁移期指针。时点 2026-09-21。对象是**这一份文档**；不含 `PLAN.md`（批 2）、
`ablation_harness/HARNESS.md`（批 1）。**原始正文一字未删**：迁移是搬家，不是缩写。

## 验收条件

主判据 = **可定位 / 可执行 / 可关闭 / 无约束遗漏**，加一条本批特有的：**证据不得在搬运中失真**
（读数、命令、run id、摘要、通过/失败/未知判定原样保留）。分流前已定：**按主题建记录（约 8–12 条）**，
因为按节建会产生约 50 条、比原文件更碎；并以**路由表**替代原文的"同一主题以最后一个提到它的节为准"。

## 结果

- **12 条记录**落在 `acceptance/records/`，覆盖原文 50 节（主题分组见路由表）。
- **`ACCEPTANCE.md` 236719 → 7736 字节（−96.7%）**，213 个标题 → 0 条验收正文；留存四块：
  通则（验收标准 ≠ 已通过）、迁移期用法与路由规则、通读口径（`[N]` 是当日运行编号不是闸门身份 +
  `MAX_CHECKS` 棘轮 ⇒ 成功行只在当日 commit 上成立；「已修」与「仍是缺口」并存；两条已知作废带前向指针）、
  主题 → 现行记录表 + 旧路径表。
- **追加序的替代**：记录各自的「适用范围」写明它承载哪些旧节、作废了哪些旧读数；**9 处节间矛盾**
  以记录内前向指针保留（未在迁移中"调和"成一句新结论）。这九条已逐条核过 —— 见下「九条前向指针核验」。
- **无损核对（可独立复验，源 commit 已固定）**：源 = `84593a7:rl_exp/versions/lizard/ACCEPTANCE.md`
  （分流前最后一版，234,656 字节）。比对只取**机械可提取的唯一标记**，对源与 `acceptance/records/*.md`
  逐类求集合差；2026-09-21 复跑结果：

  | 类别 | 源 | 记录 | 缺失 |
  |---|---|---|---|
  | `sha256:` 摘要 | 3 | 3 | **0** |
  | `[N]` 运行编号 | 32 | 32 | **0** |
  | `N/M` 比率 | 37 | 41 | **0** |
  | `0.x` 小数 | 25 | 35 | **0** |
  | 时间戳 | 1 | 1 | **0** |

  复现方式（**无附加产物**：比对命令本身就是审阅对象；当时用的临时脚本未入库，已删）：

  ```
  git show 84593a7:rl_exp/versions/lizard/ACCEPTANCE.md > src.md
  # 与 acceptance/records/*.md 逐类求差，五类正则：
  #  sha256:[0-9a-f]{8,} | \[\d+\] | \b\d+/\d+\b | \b0\.\d+\b | \d{4}-\d{2}-\d{2}[ T]\d{2}
  ```

  **逐行核对（2026-09-21 补齐）**：迁移时报的"机械类之外有 187 行不逐字命中"是**人工过一遍**的结论，
  没有留下产物（当时的临时脚本已删）⇒ 独立核只能重做那一步。现把它改成一条**规则**，谁在仓根跑一次
  都得同一组数。语料 = `acceptance/records/*.md` + **现行 `ACCEPTANCE.md`**（抬头的通则/用法与路由表
  留在本文、不搬进记录，须算合法落点）。`norm(s)`：只留 `[0-9A-Za-z]` 与 CJK —— 丢 markdown 记号、
  空白与**全部标点**（含 `""` 与 `「」` 互换，记录常把直引号写成直角引号）。逐行四分类，互斥且穷尽
  原文 1541 条非空行：

  | 类 | 判据 | 行数 |
  |---|---|---|
  | (a) 逐字命中 | 该行 `strip()` 后是语料里的完整一行 | 1169 |
  | (b) 归一后相等 | `norm(行)` = 语料某行的 `norm` | 120 |
  | (c) 折行 / 加注 | 所在**块**（连续非空行）的每一句（按 `。！？；` 切、`norm` ≥6 字）都在语料里出现 | 148 |
  | (d) 查无此内容 | 块内至少一句在语料里找不到 | **104** |

  (c) 是"折行"的量化版：句子都在，只是断行位置或记录端的加注不同。(d) 才是"不逐字命中"的真集合，
  104 行按形状分四类、**行号全给**（前 64 行可由规则直接复现，后 40 行是逐条改写）：

  | 子类 | 行号 | 是什么 |
  |---|---|---|
  | 抬头 | 6 11 13 14 15 16 18 20–33 35 37 38 | §本文用法 / 通读口径 / 旧"主题 → 最新节"表；由本文新抬头与主题路由表取代，正文不同、内容未丢 |
  | 旧节标题（`#` 起） | 42 158 197 250 288 365 558 630 670 698 725 767 809 861 1056 1109 1113 1178 1208 1230 1306 2058 | 记录按**主题**重编标题，标题文字进记录的「适用范围」表：`## 1.3a · 载荷与接口离线验收` → `\| §1.3a \| 载荷与接口离线验收（S01–S10 + A/B 层） \|` |
  | `**性质**：**追加**条目…` | 427 465 560 727 769 811 863 1058 1141 1210 1232 1397 1469 1591 1647 1662 1936 1988 | 原文的**追加序**元信息；记录按主题成文后只留 `**性质**：` 后的内容 |
  | 其余（逐条改写） | 127 129 130 132 192 252 253 282 283 313 415 500 501 502 578 1040 1041 1228 1257 1275 1277 1278 1470 1471 1619 1620 1648 1772 1787 1788 1789 1790 1794 1930 1931 1937 1989 1990 1991 1992 | 见下 |

  这 40 行只有四种改写，**没有一条承载证据**。下面的"例"另跑了一遍
  `difflib.SequenceMatcher`（对每条 (d) 行取语料里最相似的记录行），所以每条都能指认去哪了；
  这一段**不是**上表数字的来源，只用来给形态取例。

  | 改写形态 | 行号 | 例 |
  |---|---|---|
  | 节引用改成记录内引用（`见 1.5a 节` → `见本记录 §1.5a 节`） | 127 129 130 192 282 415 1040 1228 1794 | `- **追加（2026-09-15 晚）**：已执行一轮按需演练…，见 1.5a 节` → 同句，`见本记录 §1.5a 节`（r 0.97） |
  | 记录端**加**了接续/失效注 | 1275 1277 1278 1619 1620 | `- **注册表未翻**：…` → `- **注册表未翻**（当日）：… → 由「C2 收尾」接上。` |
  | 措辞改口径 | 500 502 | `（B3 的活）` → `（硬 A 的活）`；`本次只验读模式` → `本节只验读模式` |
  | 同段重新断行 / 并入一行（文字基本一致） | 132 252 253 283 313 501 578 1041 1257 1470 1471 1648 1772 1787 1788 1789 1790 1930 1931 1937 1989 1990 1991 1992 | §1.3a「不可据本表宣告」在记录里并入该节边界小节；`本批 commit：…` 与「提交归属」合并 |

  另一条**机器可查**的旁证：五类标记在 (d) 行里只出现在 8 行（26 465 502 560 811 863 1109 1397），
  且每处 `[35]`/`[37]`/`[41]` 都**同时**出现在记录里 ⇒ 五类集合差为空（上表），(d) 行不独占任何
  可提取标记。

  复跑：把下面这段存成临时文件（如 `%TEMP%\loss_check.py`）、**在仓根**执行，用完即删；**不入库**
  —— 它是一次性迁移核对，不是常设闸门，不属 `rl_exp/tools/verify/` 的套件形状。

  ```python
  import re, subprocess, pathlib
  SRC = "84593a7:rl_exp/versions/lizard/ACCEPTANCE.md"
  src = subprocess.run(["git","show",SRC], capture_output=True, check=True).stdout.decode("utf-8")
  corpus = {p.name: p.read_text(encoding="utf-8") for p in pathlib.Path("acceptance/records").glob("*.md")}
  corpus["ACCEPTANCE.md"] = pathlib.Path("rl_exp/versions/lizard/ACCEPTANCE.md").read_text(encoding="utf-8")
  norm = lambda s: "".join(re.findall(r"[0-9A-Za-z\u4e00-\u9fff]+", s))
  exact = {l.strip() for t in corpus.values() for l in t.splitlines()}
  nrm   = {norm(l) for t in corpus.values() for l in t.splitlines() if norm(l)}
  blob  = "".join(norm(l) for t in corpus.values() for l in t.splitlines())

  lines = src.splitlines()
  blocks, cur = [], []
  for i, l in enumerate(lines, 1):
      if l.strip(): cur.append(i)
      elif cur: blocks.append(cur); cur = []
  if cur: blocks.append(cur)
  own = {i: bi for bi, b in enumerate(blocks) for i in b}
  def absent(idxs):   # 块内某句在语料里找不到
      t = "".join(lines[i-1] for i in idxs)
      return any(norm(f) not in blob for f in re.split(r"(?<=[。！？；])", t) if len(norm(f)) >= 6)
  gone = [absent(b) for b in blocks]

  A = [(i,l) for i,l in enumerate(lines,1) if l.strip() and l.strip()  in exact]
  B = [(i,l) for i,l in enumerate(lines,1) if l.strip() and l.strip() not in exact and norm(l) in nrm]
  seen = {i for i,_ in A} | {i for i,_ in B}
  C = [(i,l) for i,l in enumerate(lines,1) if l.strip() and i not in seen and not gone[own[i]]]
  D = [(i,l) for i,l in enumerate(lines,1) if l.strip() and i not in seen and     gone[own[i]]]
  print(len(A), len(B), len(C), len(D))          # 1169 120 148 104
  for i, l in D: print(i, l.strip())
  ```

  唯一**搬没搬不靠这条规则判**的是 §2.4 的一个**空标题**（无正文）：它的 `norm` 恰是记录里
  `### §2.4 回填（执行后，2026-09-16）` 的子串，机器上落 (c)，与"折行"不可分；这一行的归属以本
  记录的人工声明为准（未保留空标题，已在对应记录里说明）。

**四项走查**：可定位 ✅（主题 → 现行记录一步到位）/ 可执行 ✅（记录内"落地/命令/结果"可直接复跑参照）/
可关闭 ✅（各记录「未覆盖边界」就是该主题还没关的项）/ 无约束遗漏 ✅（每节的"不得据本节宣称"都进了
对应记录的未覆盖边界，这是本批最要紧的一项）。

### 九条前向指针核验（2026-09-21 补）

「9 处」在仓内**没有账**：`37e5df6` 的提交信息只说 "nine places where sections contradict each other
are kept as forward pointers inside records"，没有任何地方把它们列出来。可复算的替代规则 =
**记录「适用范围」里把"当前读数"转指另一份记录的条目**（区别于「与其它记录的关系」那种纯 see-also）；
按此规则在 12 条记录里恰好得到 9 条、与本记录声明的数一致，故以此为核验对象。核验**只查指针**
（名字对不对、跟过去能否看到作废声明）；**不对矛盾本身表态** —— 谁对谁错是人的决定，本轮不调和、
不改写、不新建指向。

| # | 指针所在 | 指向 | 判 |
|---|---|---|---|
| 1 | `2026-09-16-lizard-builder-hard-a.md`「适用范围」末条（L21–28） | `2026-09-17-lizard-entry-switch-and-declaration-gap.md` 的「收掉最后一条声明缺口」 | **broken** |
| 2 | `2026-09-16-lizard-component-library-b1.md`「适用范围」（L30–31） | "上面那条记录" = `2026-09-16-lizard-frozen-baseline-reanchors.md` | resolves |
| 3 | `2026-09-16-lizard-frozen-baseline-reanchors.md`「适用范围」第 1 条（L17–18） | `2026-09-17-lizard-entry-switch-and-declaration-gap.md`（`硬 B 只覆盖 env cfg` 的作废方） | **broken** |
| 4 | `2026-09-16-lizard-layout-migration-lifecycle.md`「适用范围」第 1 条（L18） | `2026-09-17-lizard-entry-switch-and-declaration-gap.md` 的「生命周期收缩」 | **broken** |
| 5 | `2026-09-16-lizard-layout-migration-lifecycle.md`「适用范围」第 2 条（L20） | 同上（入口侧读数：L02 通过、parkour 退休） | **broken** |
| 6 | `2026-09-16-lizard-layout-migration-lifecycle.md`「适用范围」第 4 条（L23–25） | `2026-09-16-lizard-frozen-baseline-reanchors.md` 的「B0 追加②/③」 | resolves |
| 7 | `2026-09-16-lizard-obs-protocol-gate.md`「适用范围」第 3 条（L22–25） | "`2026-09-16-lizard-layout-migration-lifecycle.md` **之后**的入口批次" | **ambiguous** |
| 8 | `2026-09-17-lizard-entry-switch-and-declaration-gap.md`「适用范围」第 3 条（L23–28） | `2026-09-16-lizard-builder-hard-a.md`（ClassVar 两条读法的另一半） | resolves |
| 9 | `2026-09-17-lizard-hard-b-difference-declarations.md`「适用范围」第 1 条（L17–19） | `2026-09-16-lizard-frozen-baseline-reanchors.md`（`硬 A 前置未满足`） | resolves |

- **broken ×4（#1 #3 #4 #5）**：四处都写成 `2026-09-17-lizard-entry-switch-and-declaration-gap.md`，而**该文件名在
  任何历史里都不存在** —— `git log --all --name-only --diff-filter=AD` 查不到这个路径，`37e5df6` 落的
  文件就叫 `2026-09-17-lizard-entry-switch-and-declaration-gap.md`。四处想指的内容确实在那份记录里
  （#1 → `### 收掉最后一条声明缺口`；#4 → `### 生命周期收缩：删掉未接线的一半判定机件`；#5 → 该记录
  「入口切换」的边界与 L02 补记）。**#3 还多错一层**：`硬 B 只覆盖 env cfg` 的作废方按本文抬头是
  `2026-09-17-lizard-hard-b-difference-declarations.md`，不是入口切换记录。**未修**（改名属人的决定）。
- **ambiguous ×1（#7）**：指的不是记录，而是"某记录**之后**的入口批次"；跟过去落在
  `2026-09-16-lizard-layout-migration-lifecycle.md`，那份记录**没有**作废或闭合这句话（其「未覆盖边界」
  仍把它记为开项）⇒ 读者到不了"作废声明"。**缺的是**：该动作最终落在哪份记录、有没有落地。
- **resolves ×4（#2 #6 #8 #9）**：指名的记录都在，目标节也真的写着这件事（#2 → frozen 记录
  `### B0 结论文更新：B3 前置**已解锁**`；#6 → `### B0 追加②`/`③`；#8 → hard-a 记录「适用范围」第 3 条，
  两边各持一半、都声明未在同一句区分；#9 → frozen 记录「适用范围」第 1 条明写`硬 A 前置未满足`被判
  `自此失效`）。
- 附注：`ACCEPTANCE.md` 抬头「通读口径」用的是**正确文件名**（`…entry-switch-and-declaration-gap.md`），
  所以 dangling 只出现在三份记录里 —— 同一份文档在本文与记录里被叫了两个名字。

## 证据引用

- 闸门：`check_work_docs.py` → `WORK_DOCS_OK (30 item file(s))`、records 17（2026-09-21 复核复跑：
  `WORK_DOCS_OK (33 item file(s))`、23 active / 10 closed、records 18 —— 数随后续批次增长，判据不变）；
  `check_version_docs.py` → `VERSION_DOCS_OK`；pre-commit 四道静态门通过。
- 体积：`os.path.getsize` / `git cat-file -s`（字节）。
- 搬迁同批完成：提交 `37e5df6`（13 文件，+3105/−2057 行）。
- 无损核对方法与逐节去向表见本记录「结果」节（含可复现命令）与 `ACCEPTANCE.md` 的主题路由表；
  逐文件改动可审 `git show 37e5df6 --stat` 与 13 个文件的 diff。
- **两处格式归一（已做变更，非待办；差异按 `git show 37e5df6` 逐行核过）**：
  - **① §B1 切片 4 的检查表缺表头**。原文 `84593a7` 该处（源 L711–713）是 `### 检查与结果` + 空行 +
    直接 `| 门 1（字段面） | …`；同一份文档里其余五个切片的同类表都有 `| 编号 | 命令 | 结果 |` +
    `|---|---|---|`，只有这一片没有 ⇒ 记录 `2026-09-16-lizard-component-library-b1.md`（切片 4·
    `commands`）补了这两行，**表体四行一字未动**。diff 里这一片的删除侧是
    `-| 门 1（字段面） | \`check_cfg_lock.py\` | **通过（修正后）**：…`，紧邻上方**没有**被删的表头行。
  - **② §2.4 的空标题**。原文该处是连续两行：L526 `### 回填（执行后）`（L527 空行，**无正文**）+
    L528 `### 回填（执行后，2026-09-16）`（实稿）⇒ 记录只留后者，并按主题加了前缀：
    `### §2.4 回填（执行后，2026-09-16）`。diff 里两行都在删除侧（`-### 回填（执行后）`、
    `-### 回填（执行后，2026-09-16）`），新增侧只有带前缀的那一行。删掉的是一行**空标题**，
    没有正文、没有读数。

## 未覆盖边界

- **判据仍是形状 + 机械比对**：闸门只验记录的五节与路径存在，**验不了"证据是否失真"**。本批的
  无损核对现在有两层机械判据（五类标记的集合差 + 逐行四分类规则），它证明的是"内容可定位"，
  **不证明**"某个读数被抄写时抄对了" —— 后者只有读记录里那条读数本身、或对着当日 commit 复跑才成立。
  这两层也不等于此后新增记录被同样核过。
- 原文的「本文用法」里"未闭合项无对应挂账行"那份清单（如 `社会控制`、`静默跳过`、`不可复跑`、
  `首回合失败`）现在分散在各记录的「未覆盖边界」里；**要问"还剩什么没做"仍要同时翻三处**
  （PLAN / HARNESS / 各记录），这个代价没有降低，只是位置更明确了。
- 记录总量比原文**更大**（236719 → 约 297 KB）：每条自带适用范围与未覆盖边界。省的是默认读取
  （原文不再被通读），**不是磁盘**。
- 迁移未替人决的事：归档位置替代仍"需用户确认"；9 处矛盾保留为指针、未调和 —— **矛盾本身仍由人定，
  本轮只核指针**。九条已逐条核过（表在「结果」节）：**4 条 resolves、1 条 ambiguous、4 条 broken**。
  broken 的四处写成 `2026-09-17-lizard-entry-switch-and-declaration-gap.md`，**该文件名在全部历史里都不存在**
  （`git log --all --name-only --diff-filter=AD` 无此路径），内容实际落在
  `2026-09-17-lizard-entry-switch-and-declaration-gap.md`；ambiguous 的那一条指向"某记录之后的入口
  批次"，跟过去落在的记录里记的是开项、不是作废声明。**本记录不修这四条指针**（改名与调和不属迁移）；
  dangling 只在三份记录内，`ACCEPTANCE.md` 抬头用的是正确文件名。
- 两处格式已在「证据引用」节写明具体差异（见该节末条）；逐行无损核对的方法、行号与命令也在
  「结果」节，`187 行`那一步已由可复跑规则替代。
