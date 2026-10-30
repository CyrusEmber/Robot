# 闸门准入判据：独立审核（2026-10-30）

## 适用范围

对 `gate-admission-rule` 的关闭条件、规则落点、提交 `3420339` 和来源证据进行新上下文独立重审。用户将原先等待首个新增套件项的条件改为审核既有检查扩展；命中史统计另由 `work/active/gate-hit-history.md` 跟进。

## 验收条件

- `AGENTS.md` 与 `rl_exp/tools/verify/OFFLINE_CHECKS.md` 包含真实缺陷、破坏测试、类别与行为证明边界。
- 对选定扩展核实真实来源、类别、反证和替身测试的边界；未完成动作不随关闭消失。

## 结果

**通过，适用于本次审核的证据快照。**

- `AGENTS.md` 的实现与验证红线要求真实缺陷、修复前失败的回归测试；`OFFLINE_CHECKS.md` §4 区分声明一致与行为成立，§6 明示新增条目准入靠人工审核，无机器闸门。
- `3420339` 扩展现有 `test_eval_record.py`，没有新增 `CHECKS` 进程；它符合修改后的观察条件，不证明首条新增项的准入实践。提交中的约 0.5 秒是扩展后单项耗时，不是前后增量。
- 来源记录记载新训两迭代后错误寻找 `model_2.pt`；审核者看到原训练目录中的 `model_0.pt`、`model_1.pt`，manifest 的非恢复训练和两次迭代预算，并核对当前安装训练器的末次迭代保存方式。原失败终局仍主要依赖历史记录。
- 分类为调度行为成立：测试调用真实调度逻辑，替换仿真子进程和共享路径。本次内存破坏分别恢复旧完成判定、旧默认 checkpoint 和相对 eval 入口，三项均失败，恢复后通过；不等于真实仿真通过。
- 当前测试 `test_eval_record.py` 34 passed；完整离线套件 37/37，50.3 秒。套件在含其他会话改动的工作区运行，不代表干净提交快照。
- 统计动作已迁入活跃事项；未发现本事项内其他未迁走的未决动作。

## 证据引用

- `AGENTS.md`；`rl_exp/tools/verify/OFFLINE_CHECKS.md` §4、§6。
- `git show 3420339 -- rl_exp/tools/verify/offline_suite.py rl_exp/tools/verify/test_eval_record.py ablation_harness/run_ablation.py`；`acceptance/records/2026-10-10-isaac-root-parameterisation.md`；`acceptance/records/2026-10-30-gate-admission-rule-evidence.md`。
- 新测：`"E:\IsaacLab\env_isaaclab\Scripts\python.exe" -B rl_exp\tools\verify\test_eval_record.py`；`set "PYTHONDONTWRITEBYTECODE=1" && rl_exp\tools\verify\run_offline_checks.bat`。
- 独立破坏测试，在仓根 cmd 中运行：

```cmd
"E:\IsaacLab\env_isaaclab\Scripts\python.exe" -B -c "import ast,inspect,subprocess,sys; sys.path.insert(0,'rl_exp/tools/verify'); import test_eval_record as t; m=t.run_ablation; old=subprocess.check_output(['git','show','3420339^:ablation_harness/run_ablation.py'],text=True,encoding='utf-8'); tree=ast.parse(old); orig_train=m._run_train; orig_sweep=m._sweep; orig_eval=m._run_eval; code='def check(label, test):\n    try:\n        test()\n    except AssertionError as e:\n        print(label + \' EXPECTED FAIL: \' + str(e))\n    else:\n        raise RuntimeError(label + \' unexpectedly passed\')\n'; exec(code); node=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='_run_train'); exec(compile(ast.fix_missing_locations(ast.Module(body=[node],type_ignores=[])),'<3420339-parent>','exec'),m.__dict__); check('old completion',t.test_a_fresh_run_is_scored_at_its_last_checkpoint); m._run_train=orig_train; node=next(n for n in tree.body if isinstance(n,ast.FunctionDef) and n.name=='_sweep'); exec(compile(ast.fix_missing_locations(ast.Module(body=[node],type_ignores=[])),'<3420339-parent>','exec'),m.__dict__); check('old default',t.test_a_fresh_run_is_scored_at_its_last_checkpoint); m._sweep=orig_sweep; src=inspect.getsource(orig_eval); src=src.replace('str(_HARNESS_DIR / '+chr(34)+'eval.py'+chr(34)+')',repr('ablation_harness/eval.py')); assert src!=inspect.getsource(orig_eval); exec(compile(src,'<relative-eval>','exec'),m.__dict__); check('relative eval',t.test_the_sweep_launches_from_the_repo_and_runs_isaaclab_as_cwd); m._run_eval=orig_eval; t.test_a_fresh_run_is_scored_at_its_last_checkpoint(); t.test_the_sweep_launches_from_the_repo_and_runs_isaaclab_as_cwd(); print('RESTORED BOTH PASS')"
```

## 未覆盖边界

- 首条新增套件项尚未观察；未来新增项仍须按现行规则人工审核。
- 原探针二的 spec 和 eval 产物已删除；不能独立复现其历史成功，也不能把后续旁证混为原探针结果。
- 替身硬编码末档为预算减一，不会发现训练器保存契约漂移；tag 后缀与文件名也不能保证运行身份。未重训或重跑真实仿真。
