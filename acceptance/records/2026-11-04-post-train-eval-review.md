# 训后评估规范复核与修订

## 适用范围

范围：响应本轮用户逐项审核。落点为 `ablation_harness/HARNESS.md`、`POST_TRAIN_EVAL_TEMPLATE.md`、`AGENTS.md` 与 `eval.py` 用法示例。
本文是规范修订验证，不是新一次策略评估，不补造历史验看或运行证据，不改变旧记录判词。

## 验收条件

- 完成状态区分能力缺口与执行遗漏；模板可逐项记录身份、条件、观察、预先约定与来源。
- 以现有 Lizard2 数据如实走查；读取实际 PLAY/录像代码，不把静态检查说成运行验证。
- 同一历史 checkpoint 的有限值正例、NaN 与截断反例符合检查规则，原文件不变；示例变更不改变可执行代码和 CLI 默认值。

## 结果

### 现有 Lizard2 记录逐项走查

输入：`ablation_harness/results/locomotion_eval_v3/runtime-acceptance/Lizard2-Flat-v3_v3ckpt5999_nominal_seed123/` 下 `eval.json` 与 `record.json`。
历史训练路径取 `rl_exp/versions/lizard2/main/v3/NOTES.md`；旧版已退休，本轮只读历史证据，不重新运行任务。

| 清单项 | 实际证据 | 按新规范能否满足 |
|---|---|---|
| checkpoint / run | record 绑定 `lizard2_v3/2026-10-10_10-14-50/model_5999.pt`，读取前后摘要相同；本轮隔离校验见下 | 身份可追溯；有限值核验不替代当前 runner/机体兼容验证 |
| 模式与样本数 | nominal、seed 123、72 env；`perturbation: null` | 历史 nominal 事实成立，不冒充本轮 robust；恢复时间对这次实际工况为 N/A |
| 速度误差 | global 与六个命令段有线/角误差，但每段没有 flat 专属误差 | 已有数据可引用；不能把全地形段均值当作平地段指标 |
| 几何跌倒 / 位移 | `terrains.flat.fall_rate`、`terrains.flat.completion` 存在 | 有按成绩面分列的数据 |
| 停车 | 末段存在 `stop_overshoot_mps`，但没有平地分列或有效样本细分 | 测量有覆盖；不足以补证平地停车窗口全部有效 |
| 提前终止 / 有效样本 | `num_envs` 有，总体提前终止和分窗口覆盖没有写入这两个 JSON；该结果目录无 `eval.log` 或原始帧 | 核心旁证不齐，不能从均值倒推样本量 |
| 平地足端专项 | locomotion 这两个文件不含承载、摆动、非足支撑；另有历史 baseline 记录但本次未混入 | 这只是入口覆盖差异；不可据此声称新机体的工具一定不支持，须核对适配性后分类 |
| 视频 | 本地 `ablation_harness/videos/matrix.json` 匹配同一 checkpoint；仅三段，0.5/1.5/2.8 m/s、6 秒、单 env、seed 0、无具名 view | 不是九段九宫格，且所查记录没有逐段验看行；本轮不声称已观看 |
| 速度范围 / OOD | 配方 v3 `lin_vel_x: [0,3]`，视频 `command_box_mps: [0,3]`，三段均 `in_recipe_box: true` | 三段均在配方前向范围内；不能推广到其它版本，且 eval 的转向段超出该配方 `wz=[0,0]` |
| 冻结时序 | 协议来源 commit `29dee477f328246d49955804f4648af169138b2b`（2026-09-20T10:31:04+08:00）；eval 时间 `2026-10-10T15:30:34` 无时区且是分析结束时间 | 摘要核对见下；仅凭结束时间不能证明实际启动前已冻结，不补造开始时间 |

**实际判定：若用新清单检查，仍为“未完成”。** 原因是核心运行旁证与九宫格/逐片观察缺失，不是把“机体缺少专项工具”一概拒绝。
这不追溯推翻当时的历史报告，也不把一条旧 eval 伪装成新流程正例。

规则推演（不是运行结果）：

- 身份、核心运动评估、总体样本与提前终止、所选模式、九段视频和逐片观察都齐，仅有已证实且不属于本轮门槛的足端采集能力缺口 → **完成但有缺测**。
- 同一案例补齐专项读数 → **完成**；模型读数是否通过另判。
- 同一案例少一条原片观察或核心评估报错 → **未完成**，不能用能力缺口豁免。
- 所有环境在扰动前失败，有明确计数与阶段证据 → 流程可完成，参与数零、恢复时间无定义；恢复能力不得判成功。

### 视频条件源码核对

- `rl_exp/tasks/lizard2_recipe.py:recipe_class` 在配方 elements 后对 PLAY 调用 `apply_play_wiring`；v3 的 `play_elements` 为空。
- `rl_exp/tasks/play_utils.py` 清除 `DR_EVENT_NAMES` 中的随机化与 push/wrench，关闭观测噪声；没有删除 reset events。
- `lizard2_recipe.py:lizard2_no_dr` 保留 reset base/joints 并固定范围；不能写“events 全部关闭”。
- `video_matrix.py:record_cell` 在构造环境前显式 `apply_eval_mode(cfg, "nominal")`，所以即使手动传 TRAIN 也仍是录像器的 nominal 条件；该函数无 recovery kick 注入。
- `matrix.json` 当前只存部分条件，不能证明历史实际 DR 全貌。本轮是源码核对，不是启动 Isaac 的运行时采样；模板要求未来记录实际配置及来源。
- `eval.py` 的 `result.timestamp` 在 `_analyze` 中生成，`_persist` 将它写入 `rec.run.timestamp`；新增执行者日志约定以保存真正的启动时序。

### checkpoint 反例复读

以下 Python 块用现有可信 checkpoint 作母本，只在 `rl_exp/tools/diagnose/out/post_train_eval_review/<独立运行>/` 创建反例和报告；原 run 不写入。
这是有限值/反序列化的隔离验证，不是生产闸门、不是新模型加载器，也不证明推理兼容或策略行为。
执行方式（仓根 PowerShell，使用 `paths.yaml` 中已登记 Python；提取本文件唯一 Python 块执行，复读入口保留）：

```powershell
$auditText = Get-Content acceptance/records/2026-11-04-post-train-eval-review.md -Raw
$auditCode = [regex]::Match($auditText, '(?s)```python\r?\n(.*?)\r?\n```').Groups[1].Value
$auditCode | & E:/IsaacLab/env_isaaclab/Scripts/python.exe -
```

```python
import copy
import hashlib
import json
import pathlib
import subprocess
import tempfile
import torch

source = pathlib.Path('E:/IsaacLab/logs/rsl_rl/lizard2_v3/2026-10-10_10-14-50/model_5999.pt')
root = pathlib.Path('rl_exp/tools/diagnose/out/post_train_eval_review')
root.mkdir(parents=True, exist_ok=True)
output = pathlib.Path(tempfile.mkdtemp(prefix='check_', dir=root))

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def tensors(value, name='payload'):
    if isinstance(value, torch.Tensor):
        yield name, value
    elif isinstance(value, dict):
        for key, child in value.items():
            yield from tensors(child, f'{name}.{key}')
    elif isinstance(value, (list, tuple)):
        for index, child in enumerate(value):
            yield from tensors(child, f'{name}[{index}]')

def inspect(path):
    before = sha(path)
    try:
        payload = torch.load(path, map_location='cpu', weights_only=True)
        # This historical runner uses actor_state_dict, not model_state_dict.
        assert isinstance(payload, dict) and payload.get('actor_state_dict')
        bad = [name for name, value in tensors(payload)
               if (value.is_floating_point() or value.is_complex())
               and not torch.isfinite(value).all().item()]
        after = sha(path)
        return {'loadable': True, 'finite': not bad, 'nonfinite': bad,
                'stable': before == after, 'sha256': before, 'iter': payload.get('iter')}
    except Exception as exc:
        return {'loadable': False, 'error': type(exc).__name__ + ': ' + str(exc), 'sha256': before}

before = sha(source)
original = torch.load(source, map_location='cpu', weights_only=True)
nan_payload = copy.deepcopy(original)
key, value = next((k, v) for k, v in nan_payload['actor_state_dict'].items()
                  if v.is_floating_point() and v.numel())
value.reshape(-1)[0] = float('nan')
nan_path = output / 'nan_checkpoint.pt'
torch.save(nan_payload, nan_path)
truncated = output / 'truncated_checkpoint.pt'
raw = source.read_bytes()
truncated.write_bytes(raw[:len(raw)//2])
cases = {name: inspect(path) for name, path in
         [('original', source), ('nan', nan_path), ('truncated', truncated)]}
assert cases['original']['loadable'] and cases['original']['finite'] and cases['original']['stable']
assert cases['nan']['loadable'] and not cases['nan']['finite']
assert not cases['truncated']['loadable']
assert before == sha(source)
record_path = pathlib.Path('ablation_harness/results/locomotion_eval_v3/runtime-acceptance/Lizard2-Flat-v3_v3ckpt5999_nominal_seed123/record.json')
record = json.loads(record_path.read_text(encoding='utf-8'))
assert before == record['checkpoint']['sha256'].removeprefix('sha256:')
frozen = subprocess.check_output(['git', 'show', '29dee477f328246d49955804f4648af169138b2b:ablation_harness/protocols/locomotion_eval_v3.yaml'])
protocol_sha = hashlib.sha256(frozen).hexdigest()
assert protocol_sha == record['eval_protocol']['digest'].removeprefix('sha256:')
report = {'source': str(source), 'source_unchanged': True, 'cases': cases,
          'nan_key': key, 'protocol_commit_sha256': protocol_sha, 'output': str(output)}
(output / 'report.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
print(json.dumps(report, indent=2))
```

实跑结果：三个断言分支均满足预期，母本摘要未变。母本可安全反序列化且张量有限；NaN 副本仍能被 `torch.load` 读取，有限值检查拒绝 `actor_state_dict.distribution.std_param`；截断副本在反序列化阶段报缺失 ZIP central directory。
因此“能 load”单独不足以判断可用，NaN 与截断必须分别检查；本次没有验证 runner 形状兼容或运行时推理。
协议冻结 commit 的文件摘要与历史 `record.json.eval_protocol.digest` 相符：`00f8c067932eacdf680f8104c452e98f1ce61973af042cd0f95db2e9818ec47f`。
本机反例及结构化报告保留在 `rl_exp/tools/diagnose/out/post_train_eval_review/check_yajox_ho/`；复读上方块会生成独立目录，不覆盖此次证据。

### 仓库检查

修正五节结构后，适用的 pre-commit 检查全部通过：目录卫生、框架 pin/自检、DR/资产契约、版本文档、事项与验收记录格式、obs 协议（含 live cfg 构造）。
日志为反例目录的 `pre_commit_retry.log`。框架脏树、历史 tag 与历史文字指针提示保留，不在本轮清理；检查是在共享工作树上运行，不宣称独立干净快照验证。
模板已使用同一套五个二级标题，细项为三级节；没有把模板存在当成实际评估或验看证据。

## 证据引用

- 规范及模板：`ablation_harness/HARNESS.md`、`ablation_harness/POST_TRAIN_EVAL_TEMPLATE.md`。
- 历史结果与视频索引：见结果节具名路径；视频和 checkpoint 为本机文件，不承诺入仓。
- checkpoint 核验：`rl_exp/tools/diagnose/out/post_train_eval_review/check_yajox_ho/report.json` 及保留的两个坏载荷。
- 首次提交钩子日志：同目录 `pre_commit.log`；其发现本记录缺少仓规五节结构，已连同模板修正，不覆盖失败日志。
- `eval.py` 去掉模块 docstring 后与修改前 AST 一致；只修改用法中的 mode 示例，CLI 默认和调度默认未变。

## 未覆盖边界

- 没有运行新训练、仿真、策略推理或视频播放；没有补认历史逐片观察或新流程完成。
- 三状态正向路径是明确标注的规则推演，不是新一次全流程真跑证明；当前历史样本不满足新流程，原因已逐项列出。
- 未新增机器闸门；复核仍须对照实际证据，勾选、格式检查或记录存在均不能单独证明执行行为。
