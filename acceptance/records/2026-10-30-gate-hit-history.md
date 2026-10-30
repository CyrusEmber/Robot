# 离线闸门历史命中调查（2026-10-30）

## 适用范围

`work/active/gate-hit-history.md`。统计对象固定为提交 `657924efe102a5156c3f9279c19756b053ed82bd` 的 `rl_exp/tools/verify/offline_suite.py` 中 37 条 `CHECKS` 进程，不以现今工作树或历史序号代替该快照。检索范围为该提交可达历史、已提交的 `acceptance/records/`、`rl_exp/docs/pitfalls.md` 与对应检查的提交历史；未逐条阅读全部历史提交和记录。

**真实命中**：该检查或现存检查承接的同一断言，当时已执行并对非人为注入的实际缺陷报错，证据可指向当时的对象和结果。开发中无意写错配置或摘要也计入；合法同步迁移尚未完成的预期不一致、审核记录尚待落盘等中间红态不计入，除非另有证据证明其为实际错误。人为破坏测试、为缺陷新建门后的回退测试、生产工具本身报错而非套件检查报错，都不计入。真实执行时检查自身崩溃或误报另列，不能算捕获被保护对象的缺陷。记录无具体失败工具或无法确定先后时归未知；未知不代表从未命中。

## 验收条件

- 按冻结清单逐项标识已证实命中或未知；说明证据、历史执行与当前检查的对应、检索方法和缺口。
- 区分自然失败、人工注入反例、事后新增覆盖和工具本身误报；不能凭未观察到命中要求删除检查。
- 新上下文对照真实原始证据、统计口径和抽查结果审核，不以格式闸门代替审核。

## 结果

已定位 **2 条检查至少各有一次有记录支持的真实命中**，其余 **35 条本次未找到满足口径的证据**。这是定向检索得到的下限，不是完整历史命中次数或命中率；同一缺陷、检查报错和修复不自动等于独立事件。历史输出大多只保留在入库验收记录的叙述中，以下不假称原始红测日志均已归档。

### 已证实命中

| 基线检查 | 当时真实失败与对应关系 | 证据与限制 |
|---|---|---|
| `check_dr_parity.py --strict` | 2026-09-20 干净 checkout 出现真实资产锁字节摘要漂移，该检查实报 4 项；另一 checkout 配置下约 770 项。基线仍包含资产锁检查。 | `acceptance/records/2026-09-20-lizard-baseline-line-eol-and-fixed-window-eval.md` 的「摘要对 EOL 敏感」及前一节观察；修复提交 `7acc84f`。这是文本行尾可移植性问题，不是资产几何损坏；未确认原始失败 stdout 已入库。 |
| `check_golden_frozen.py` | 重锚脚本把 LF 文本视图当磁盘字节计算摘要，既有检查报 `GOLDEN_FROZEN_DRIFT`；文件内容未坏，错误是冻结摘要，并非合法重锚本身。基线仍校验冻结摘要。 | `acceptance/records/2026-09-16-lizard-frozen-baseline-reanchors.md` 的「B0 追加②」记作 9 月 17 日，相关提交 `bbedd96` 为 9 月 18 日；具体报红时间未能另证，不能把两者等同。记录保留判词，未确认原始 stdout 入库。 |

### 未证实真实命中

以下 35 条均为**未知**，路径前缀为 `rl_exp/tools/verify/`，并不表示检查无用：

| 基线项 | 本次查证边界 |
|---|---|
| `framework_pin_check.py` | 补丁人为破坏反例不计。 |
| `test_recovery_parity.py` | 未查到非注入失败。 |
| `test_v5_terrain_sir.py` | 新增课程及其测试不是既有门命中。 |
| `test_joint_sir.py` | mock 断言不是历史命中。 |
| `terrain_preflight.py --self-test` | 一般地形预检不能归为该自测命中。 |
| `test_terrain_geometry.py` | 记录中一次真实运行因默认编码解码失败，是检查自身崩溃，非检出地形缺陷；传感器绑定断言为事后新增。 |
| `check_version_docs.py` | 删除 tag、破坏声明的隔离测试为人工反例。 |
| `check_work_docs.py` | 已有检查对尚未落盘的审核记录报红；该中间状态不证明最终交付遗留缺失证据。见 `acceptance/records/2026-10-10-pending-review-before-close.md` 和 `acceptance/records/2026-10-23-lizard2-v4-configuration-review.md`。后例本机原日志 `rl_exp/out/lizard2_v4_offline_suite.log` 有输出，未承诺入仓。 |
| `check_pxr_leak.py` | P003 是建门来源；P004 时旧门未检出构造期泄漏，构造断言事后加入。 |
| `test_resume_state.py` | 删除守卫的反例不计。 |
| `test_dump_tb_sampling.py` | tfevents 丢失风险是来源，不证明该单测自然报红。 |
| `test_baseline_contract.py` | 有既有回归抓住 legacy 桥问题的记载，但未定位具体断言和红测输出，不能确认归属。 |
| `test_eval_frame_v2.py` | 真实 eval 拒跑后才补摘要回归，不倒算历史命中。 |
| `check_configclass_fields.py` | 未确认旧主体检查对惰性化缺陷报红。 |
| `test_cfg_snapshot.py` | 未查到非注入失败。 |
| `check_cfg_lock.py` | 候选：记录「切片 4 · commands」称既有配置锁检查发现训练范围由 `2.0 -> 5.0` 并修正；`fb788ba^` 的套件已列该检查，基线保留同类快照比较，但历史 v4 已退休。原始提交 `fb788ba` 留有这一叙述；同一拆分记录第 32 行却称该切片为夹具/断言写错，此摘要由 `37e5df6` 加入。两种说法无法凭现有材料消解，原始红测 stdout 未确认入库，保守归未知；不声称当时完整套件执行。见 `acceptance/records/2026-09-16-lizard-component-library-b1.md` 和 `acceptance/records/2026-10-30-gate-hit-history-second-review.md`。 |
| `test_run_manifest.py` | 旧夹具失败的记录未给出该检查独立失败输出，归属待证。 |
| `test_rebuild_gate.py` | 真实 `rebuild` CLI 拒绝材料不等于该测试失败；删载荷是注入反例。 |
| `test_recipe_lines.py` | 人工负例不计。 |
| `check_recipe_registry.py` | 未查到非注入失败。 |
| `check_recipe_map.py` | 未查到非注入失败。 |
| `check_suite_banners.py` | 仓根污染是机制来源，未确认既有检查当时捕获。 |
| `test_params_isolation.py` | 记录中的并行失败被描述为抖动，独跑和复跑通过。 |
| `recipe_lifecycle.py` | 未查到非注入失败。 |
| `check_suite_shape.py` | 未查到非注入失败。 |
| `test_lifecycle_gate.py` | 未查到非注入失败。 |
| `test_launcher.py` | 未查到非注入失败。 |
| `check_recipe_build.py` | 已有断言对入口迁移中的旧 golden 报红；同次合法重锚过程不足以证明缺陷遗留，不能计作真实缺陷命中。见 `acceptance/records/2026-09-16-lizard-frozen-baseline-reanchors.md`「B0 追加③」。 |
| `check_obs_protocol.py --self-test --live` | 事后新增断言及人为回退不能算当时自然命中。 |
| `test_eval_record.py` | 新训 checkpoint 缺陷先出现，承接测试后加入；见 `acceptance/records/2026-10-30-gate-admission-rule-independent-review.md`。 |
| `test_terrain_map.py` | 未查到非注入失败。 |
| `check_terrain_split_source.py` | 未查到非注入失败。 |
| `check_split_probe_wait.py` | P005 是真实来源缺陷，但当时离线套件全绿，此检查后来加入。 |
| `check_record_bindings.py` | 真实套件报错源于误扫被忽略的历史快照，是检查误报而非第二份现行实现；见 `acceptance/records/2026-10-22-record-binding-source-scope.md`。 |
| `check_leg_reachability.py --self-check` | 真实候选机体自检失败发生在该检查进入套件之前，不能计为已安装套件项命中；见 `acceptance/records/2026-10-09-lizard2-knee-reverse-bending-measurement.md`。 |

这些结果能帮助优先追查有证据的失败与检查误报；不能评估真实检出率、收益成本比，也不能仅凭未知或低计数退役闸门。尤其缺少运行总次数、未入库日志、漏报和每项成本，现有人工准入仍是独立约束。

## 证据引用

下列只读命令从仓根执行，固定快照可避免并发工作区影响。序号以当时 `CHECKS` 为准，旧记录的 `[i/N]` 不跨版本使用：

```cmd
git show 657924e:rl_exp/tools/verify/offline_suite.py
git show 657924e:acceptance/records/2026-09-20-lizard-baseline-line-eol-and-fixed-window-eval.md
git show 657924e:acceptance/records/2026-10-10-pending-review-before-close.md
git show 657924e:acceptance/records/2026-09-16-lizard-frozen-baseline-reanchors.md
git show --stat a526276 -- rl_exp/tools/verify/check_recipe_build.py
git show --stat 27ca424
git show fb788ba^:rl_exp/tools/verify/offline_suite.py
git show fb788ba^:rl_exp/tools/verify/check_cfg_lock.py
git show 657924e:rl_exp/tools/verify/check_cfg_lock.py
git show 657924e:acceptance/records/2026-09-16-lizard-component-library-b1.md
git show --format=fuller --no-patch bbedd96
python -c "import ast,subprocess; s=subprocess.check_output(['git','show','657924e:rl_exp/tools/verify/offline_suite.py'],text=True,encoding='utf-8'); t=ast.parse(s); a=next(n for n in t.body if isinstance(n,ast.AnnAssign) and isinstance(n.target,ast.Name) and n.target.id=='CHECKS'); p=[n.args[1].elts[0].values[-1].value.rsplit('/',1)[-1] for n in a.value.elts]; print('COUNT',len(p)); print(*p,sep=chr(10)); cmds=[['git','grep','-n','-i','-F']+sum([['-e',x] for x in p],[])+['657924e','--','acceptance/records','rl_exp/docs/pitfalls.md'],['git','grep','-n','-i','-E','DRIFT|FAIL|报红|失败|误写|泄漏|误报','657924e','--','acceptance/records','rl_exp/docs/pitfalls.md'],['git','log','--format=%h %as %s','657924e','--']+['rl_exp/tools/verify/'+x for x in p]]; [subprocess.run(c) for c in cmds]"
```

上述 Python 命令解析固定快照的 37 个检查路径，打印全部名称，分别检索完整名称、通用失败词及各检查路径的可达提交历史；从候选人工打开上下文核对时间、实际运行、断言及有无注入，不把每个检索命中当作缺陷。脚本名可能未出现在旧记录中，通用词和人工定向追查不能保证穷尽；历史重命名需要另查 `git log --follow`。其余关键排除证据：`acceptance/records/2026-10-30-lizard2-foot-control-tiprise-review.md`、`acceptance/records/2026-09-22-harness-criteria-and-suite-lock.md`、`acceptance/records/2026-10-23-lizard2-v4-configuration.md`、`rl_exp/docs/pitfalls.md` 的 P003–P005 和 P007。原始失败日志未确认入库时，以记录叙述为证，无法仅靠 Git 原样回放。

## 未覆盖边界

- 本次未穷举所有记录、所有可达提交 diff 或仓外日志，不覆盖基线之后的提交。未知项及候选需更多证据才能改判。
- 一次报红可能是预期重锚、误报、测试自身故障或人为反例；计数不代表真实产品缺陷数或风险降低量。
- 不要求回补存量闸门准入来源，不建立自动统计或新增闸门；是否继续追查某条未知项不作为本次关闭条件。
