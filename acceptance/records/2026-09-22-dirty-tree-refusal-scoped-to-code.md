# 脏树拒绝按"代码脏"判，不按"文档脏"判（2026-09-22）

## 适用范围

`rl_exp/tools/runrecord/provenance.py`（`git_state` / 新增 `split_prose` / `_changed_paths`）、
`rl_exp/tools/runrecord/manifest.py`（`dirty_tree_refusal`）、`rl_exp/tools/verify/test_run_manifest.py`
（dirty 判据组）。**不覆盖**：`rebuild.py` 的重建判据（本次未动，它本来就是代码根口径）、
`eval-protocol-before-training`/`freeze-maintenance-simplification` 所辖的 `manifest.begin` 其它缺口。

## 验收条件

1. **只挡代码脏**：任何非 `.md` 的改动（配方 yaml、cfg/id 模块、资产、锁、`.gitignore`、脚本）仍然硬拒。
2. **文档脏不挡**：全部改动都是 `.md`（`work/`、`acceptance/`、`versions/**/PLAN.md|NOTES.md`）时开训放行，
   且 manifest 仍如实记 `dirty: true` 与变更清单——**放行不等于当作干净**。
3. **旧记录语义不漂**：没有新字段的 provenance（本改动之前写的 manifest）仍按旧规矩拒。
4. 拒绝信息**点名**阻挡的路径（否则人要自己去找哪条脏）。
5. 反例齐全：散文放行 / 代码仍拒且点名 / 锁文件不算散文 / 无字段仍拒 / 分割按扩展名。

## 结果

- 判据从 `dirty = bool(任何 porcelain 行)` 收窄为 `changed_non_prose`（非 `.md` 的改动路径）。
  `dirty` 与 `changed_paths` 仍是**记录**，不变。
- 依据是**仓内已有口径**而非新发明的豁免：`rebuild.py:166,197` 的重建判据早就是"代码根内的脏要归档、
  文档脏不管"；拒绝闸门没跟上，导致两处对同一棵树的判断不一致。IsaacLab 树被豁免也是同一条理由
  （"拒它就会让所有人养成设 override 的习惯"）。
- 为什么切在扩展名：它不是目录白名单，加目录不会悄悄放宽；而**没有任何配方、锁、资产是 `.md`**
  （`**/main_params.yaml`、`cfg_lock.json`、`asset_lock.json`、`*.usda`、`*.obj` 都不受影响）。
- 实测（本仓真实状态）：改动前 5 条脏（3 条代码 + 2 条文档）⇒ 拒并点名三条代码路径；提交代码后
  只剩两条文档 ⇒ **放行**。
- 途中修掉一个自己的解析缺陷：首版按 `status --porcelain -z` 固定偏移切路径，而 `git()` 助手返回的是
  **去掉前导状态列的行**，于是每条被修改路径的首字母被吃掉（`rl_exp/...` → `l_exp/...`）。改为取两个
  原始名字列表（`diff --name-only -z HEAD` + `ls-files --others --exclude-standard -z`），不做状态解析。
  这个 bug 是**在真实树上跑一次**才露出来的：单元测试的 fixture 是构造的字典，走不到解析器。
- 离线套件 `ALL_OFFLINE_CHECKS_PASSED (47/47)`，其中 `RUN_MANIFEST_TEST_OK`（含 5 条新判据）。

## 证据引用

- 复读：`E:\IsaacLab\env_isaaclab\Scripts\python.exe rl_exp\tools\verify\test_run_manifest.py`（`dirty/` 组九条）。
- 真实树判据：
  `python -c "from rl_exp.tools.runrecord import provenance as p, manifest as m; import types; print(m.dirty_tree_refusal(types.SimpleNamespace(manifest={'code': p.code_sources()})))"`。
- 套件：`rl_exp\tools\verify\run_offline_checks.bat`。

## 未覆盖边界

- **`results/` 下的未跟踪 json 仍算脏**（不是 `.md`）。本次只按所有者那句"文档修改不应阻挡"收窄到散文；
  要不要把"运行产物"也排除是另一条判断（产物影响的是"重建可读性"，不是"训练读了什么"），未做。
- `.gitignore` 本身仍算代码脏（保守：它的改动会改变"什么算未跟踪"，虽然不影响某一次 run 读了什么）。
- 这只是**开训闸门**的口径；`manifest` 里那条"rebuildable"承诺的强度不变——文档脏照样如实记录，
  谁要重建就得面对当时的文档状态（`status_porcelain_sha256` 仍在）。
- 该口径改动落在 `manifest.py`，而 `work/active/freeze-maintenance-simplification.md` 第 ② 步与
  `work/active/eval-protocol-before-training.md` 都把 `manifest.begin` 列为落点——两项的所有者若要
  在此基础上继续（协议绑定、Git 编码稳定），本次改动不阻塞它们，但需知道拒绝判据已经按散文/非散文分过一刀。
