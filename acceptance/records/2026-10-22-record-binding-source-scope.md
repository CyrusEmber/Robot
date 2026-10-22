# 单源检查区分当前源码与历史证据快照

## 适用范围

开发接触配置修正的完整检查发现：`check_record_bindings.py` 默认递归扫描 `rl_exp`，把另一个诊断流程在已忽略输出根保存的三份 `executed-sources` 历史快照也当成当前实现。快照原样保留旧哈希/修订号实现是证据要求；本轮不修改、删除或迁移这些证据。

## 验收条件

默认检查覆盖已跟踪源码及未忽略的新源码；已跟踪文件即使位于忽略目录也不豁免。显式 `--root` 仍检查给定文件中的旧实现。源码清单不可取得时失败，不能空扫通过；原模式检测及编码反例保留。

## 结果

原完整套件 36/37 通过，唯一失败是三份历史快照中的旧实现签名，记录在 `rl_exp/out/lizard2_dev_contact_20261022/offline_suite.log`。这些是 `real-final-v2/v3/v4/executed-sources/312487338a8e48d33b0dc57baa048a7859ef6f68b82b02c91f672d6adcde88ed.py`，不是当前工具的第二份实现。

修复默认入口使用 Git 的 tracked + untracked/non-ignored 文件清单，沿用 `binding.git_run` 的输出解码；扫描函数与签名检测不变，显式根不做该筛选。清单为空或不可取得即失败。独立默认入口检查通过，当次扫描 197 个当前文件；显式指向上述 v4 历史文件仍退出 1，检出原三个签名。

破坏控制在同一进程的真实临时 Git 仓库执行：重复实现分别放入已跟踪文件、未跟踪当前文件、忽略目录中强制跟踪的文件，三者均被检测；未跟踪的忽略快照不纳默认清单，显式扫描仍检出；Git 清单不存在被拒绝。该修复为扫描范围的行为回归，不增加套件条目，不放宽签名规则。

## 证据引用

源码修复提交：`448612f`。修复后的完整套件结果随[开发选择修正](2026-10-22-lizard2-dev-contact-selection.md)收尾。

本机制品 `rl_exp/out/record_binding_scope_20261022/`：`before.py/after.py`、默认通过和显式失败的 log/exit，以及同字节 `historical_snapshot.py`。索引 `artifact_digests.json` 覆盖 7 个输出、3 个输入，SHA-256 `394d7eb40cc543cec33d0eb97af9d0cb3860ca0804e5d3c7394f12d92e027776`；输入绑定当前检查源码、原失败整套日志和忽略规则。

```python
from pathlib import Path
import json
from rl_exp.tools.runrecord.binding import sha256_file
root = Path('rl_exp/out/record_binding_scope_20261022')
index = root / 'artifact_digests.json'
assert sha256_file(index) == '394d7eb40cc543cec33d0eb97af9d0cb3860ca0804e5d3c7394f12d92e027776'
data = json.loads(index.read_text(encoding='utf-8'))
for name, digest in data['files'].items():
    assert sha256_file(root / name) == digest
for name, digest in data['inputs'].items():
    assert sha256_file(Path(name)) == digest
assert (root / 'after.exit').read_text().strip() == '0'
assert (root / 'explicit.exit').read_text().strip() == '1'
assert '1 file(s)' in (root / 'explicit.log').read_text(encoding='utf-8')
print('RECORD_BINDING_SOURCE_SCOPE_REPLAY_OK')
```

复跑默认检查：`python rl_exp/tools/verify/check_record_bindings.py`；显式负例：`python rl_exp/tools/verify/check_record_bindings.py --root rl_exp/out/record_binding_scope_20261022/historical_snapshot.py`（预期退出 1）。

## 未覆盖边界

默认入口需要可读取的 Git 清单；导出副本或 Git 忽略的未跟踪材料须显式指定根。签名检测仍有原模块声明的语法覆盖限制，不证明记录内容或物理能力正确。该修复不完成记录体系 A1/B1，也不改变诊断产物的生命周期状态。
