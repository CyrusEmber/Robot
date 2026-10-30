# 活文档旧台账编号核验

## 适用范围

核验 `work/active/live-doc-ledger-numbers.md` 的事项标题、冻结协议注释及两处已有路径指针；不修改协议内容或历史记录。

## 验收条件

- 活跃事项标题不含无法解析的 HARNESS 旧挂账编号。
- 指定协议注释逐处有处置，保留冻结协议的只读纪律。
- 核认 `ARCH_PLAN.md` 和 `ablation_harness/HARNESS.md` 的事项指针与实际路径一致。

## 结果

- 检索 `work/active/*.md` 的 `title:`，未发现 `挂账 #N` 标题。原四项均已归档，历史标题不属于本次修改范围。
- `ablation_harness/protocols/locomotion_eval_v1.yaml:53`、`v2.yaml:63`、`v3.yaml:64`、`v4.yaml:83` 的延迟注释保留；`v3.yaml:8` 的 `#18 ①` 注释也保留。各协议头均声明落库冻结、只读；不以锚点未覆盖注释为就地修改的依据。若日后需要协议内新指针，应在新协议版本处理，不能改写既有版本。
- 原延迟注入事项 `work/closed/2026/deployment-delay-injection-dr.md` 已由用户裁决取消，不是活跃或 blocked 事项；未来 lizard2 需求须另立事项。旧 `#6` 不再是活跃待办；四份协议各自仍声明 `latency: not_available`，该声明不能证明当前运行时的实际行为。`acceptance/records/2026-09-20-harness-migration.md:26` 显示迁移时 #6 已是指针，并非本次新建映射。
- `work/closed/2026/record-format-live-checks.md` 和 `work/closed/2026/runtime-acceptance-v3.md` 是已完成事项，历史标题仅佐证原事项已归档，不是本次现行落点。
- `ARCH_PLAN.md:47` 指向现存 `work/active/verified-rebuild-rating.md`；`ablation_harness/HARNESS.md:10` 指向现存 `work/closed/2026/isaac-root-parameterisation.md`。

## 证据引用

- Windows CMD 复读标题检索：`python -c "import pathlib,re; print('\n'.join(f'{p}:{i}:{s}' for p in pathlib.Path('work/active').glob('*.md') for i,s in enumerate(p.read_text(encoding='utf-8').splitlines(),1) if re.search(r'^title:.*挂账\s*#\d+',s)))"`；本机实跑无匹配。
- `ablation_harness/protocols/locomotion_eval_v1.yaml:2`、`ablation_harness/protocols/locomotion_eval_v2.yaml:2`、`ablation_harness/protocols/locomotion_eval_v3.yaml:2`、`ablation_harness/protocols/locomotion_eval_v4.yaml:2`。
- `work/closed/2026/stale-doc-pointers-in-code.md` 的 v3 冻结注释处置；`acceptance/records/2026-09-20-harness-migration.md` 的历史迁移表。

## 未覆盖边界

不核查历史类文档所有编号，不改变协议语义、协议文件或黄金基线；本记录是执行者核验，不代替独立审核。
