# 删掉 FILEMAP 的逐版本行（第 4 步第一个候选，2026-09-23）

## 适用范围

- 落点：`rl_exp/tools/verify/check_version_docs.py`（删 FILEMAP 子串检查 + 随之变死的 `filemap_text` + docstring）、
  `FILEMAP.md`（删 20 行逐版本行 + 改写该节标题与说明）、`rl_exp/tools/pipeline/declare_family.py`
  （打印器只出线级行；模块 docstring 与 FAMILY 模板注记）、`rl_exp/tools/verify/offline_suite.py`（`[14]` 标签）、
  `.codemaker/rules/versioning.mdc`（`:66` 的闸门清单、`:89` 的"同步三处"→两处）。
- 属 `work/active/freeze-maintenance-simplification` 第 4 步的第一个候选；形态由 owner 选定（**删除**，理由见下）。
- **不覆盖**：`FILEMAP.md` 里其余 `versions\` 提及的散文；`_a0_layout_migration.py` 的历史说明；旧记录里的历史引用（按"历史不改"留存）。

## 验收条件

1. 删前先答第 4 步三问，并把"它现在抓什么"变成**观测**而不是断言。
2. 删后：原来抓住的错误要么有接替并有反例，要么明确写成"不再被发现"——不许含糊。
3. 同一变更内建新删旧（闸门、文档、打印器、规则一处不漏），不留中间红。
4. 套件入口数与 `MAX_CHECKS` 不变。

## 结果

**一、观测（受控变更，均已 byte-exact 还原）**

```
1) 删掉 v14 的 FILEMAP 行 ⇒ rc=1
   DRIFT: lizard/main/v14: no 'lizard\main\v14\' row in FILEMAP.md (versioning.mdc A-5)

2) 把同一串只写进散文、不留行 ⇒ rc=0（无任何判词）
```

⇒ 这条检查只做**子串匹配**：它区分不了"有一行"和"散文里提过"。也就是说"两份都必须写"这条约束，
严格说只有**一半**被真正强制，而那一行本身只重复路径 + 一句同样的说明。

**二、三问的答案**

| 问 | 答 |
|---|---|
| 原来抓什么具体错误 | "有人建了版本目录却忘了在文档里登记"。本质是**文档完整性**问题，不是代码/配置事实 |
| 依据来自哪里 | 目录树（存在性）+ `versions/<family>/FAMILY.md` 版本史（身份）。**都可机读** |
| 删后谁接替 | 目录**形态**检查接替（反例见下）；**没有**接替的是"忘登记"这一发现渠道 ⇒ 见末节 |

**三、接替的反例**：移走 v14 的 `NOTES.md` ⇒ `rc=1`，判词
`DRIFT: lizard/main/v14: NOTES.md missing (versioning.mdc A-2 four-piece set)`，已还原。
即"目录存在且齐件"由形态检查读**目录**来判，不再依赖一份手抄索引。

**四、删除规模与同变更对齐**

- `FILEMAP.md`：**−20 行**（保留 3 条线级行与 `<线>\vN\` 模板行）；该节改为"版本目录不逐条登记"。
- `check_version_docs.py`：删 1 条检查、1 个随之变死的变量、docstring 两处。
- `declare_family.py`：`filemap_rows()` 只出线级行（docstring 写明为什么版本行没了）、模块 docstring、
  打印标签、FAMILY 模板里那句"版本目录登记行见 FILEMAP"。
- `offline_suite.py`：`[14]` 标签去掉 "FILEMAP row"。
- `versioning.mdc`：闸门清单去掉 "FILEMAP 行"；"状态跃迁同步三处"改两处。

**五、验证**：`check_version_docs` → `VERSION_DOCS_OK`；全量套件 `ALL_OFFLINE_CHECKS_PASSED (47/47 in 51.3s)`，
`[14]` 已按新标签打印。

## 证据引用

见"结果"节的两条观测与一条接替反例（三条都是受控变更：`try/finally` 还原并逐字节校验）。
文件面：`git status --short` 只见 `FILEMAP.md`、`check_version_docs.py`、`declare_family.py`、`offline_suite.py`、
`.codemaker/rules/versioning.mdc`。

## 未覆盖边界

- **唯一没有接替的损失**："有人忘了登记版本目录"不再被发现。这是**决定**不是遗漏——owner 的判断是那行不给"选哪版"
  的身份信息，值不回它的读取成本；但若将来这种人肉错误真的发生，届时不会有人报错。
- `FILEMAP.md` 里其余提到 `versions\` 的散文（线级行、指向 FAMILY 的说明）未逐条核；它们不受本次影响。
- `_a0_layout_migration.py:76` 的说明仍写 "FAMILY/FILEMAP rows"（一次性迁移脚本，未动）。
- 旧记录/旧规则文本里的历史引用按仓规"历史不改"留存，故 grep 仍能命中已废的措辞。
