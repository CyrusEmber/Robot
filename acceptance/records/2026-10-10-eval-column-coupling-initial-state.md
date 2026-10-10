# 套件列间耦合：改一格的几何，让站在**别的、逐字节相同**格子上的 env 走出不同轨迹（2026-10-10）

## 适用范围

- **被验的问题**：`work/active/eval-column-coupling.md`（`close_when` 的机制部分）。上一轮证据与审核：
  `acceptance/records/2026-10-10-eval-column-coupling-probes.md`、`2026-10-10-eval-column-coupling-review.md`。
  审核 P1 认定的缺口是"cell 摘要只证明**生成器交出的几何 + origin** 只在 rough_b 改变"，其余通道未控制。
- **手段**：不改仪器。`ablation_harness/eval.py`、`suites.py`、冻结协议、归档 run 一律未动；用**一次性只读诊断脚本**
  （落在 `%TEMP%`、不入仓，正文见"证据引用"——本记录正文即脚本本体，那条 `%TEMP%` 路径会消失）。
- **地面**：与归档探针同一对（同款内存注入），`geometry_digest` 与归档逐字相同：
  `ctrl` = `sha256:9f38cddb912dfb3999381adabcec12d23bb94ef8f9adf61bc88734c80e831028`；
  `rougha` = `sha256:52b69c126146243f4ac78c019dfde7f5b74c33bf3276981a9be31a51cf8ad984`。
  两臂的差别只有 rough_a / rough_b 的生成参数（ctrl 两列都回到 v1，rougha 只回 rough_a）。
- **流程照 eval 真实路径**：`gym.make` → `RslRlVecEnvWrapper`（其 `__init__` 会 `env.reset()`，
  `source/isaaclab_rl/isaaclab_rl/rsl_rl/vecenv_wrapper.py:95`）→ 读数 → 零动作步进。
  `--task Lizard2-Flat-v3`、`--seed 123`、nominal、9 列 × 8 env = 72 env。
- **不起 policy、不加载 ckpt、不算指标**：读数与策略强弱无关。
- **对照**：同一地面重跑一次，输出逐字节相同（见结果①）。

## 验收条件

1. **探针自身确定性**：同一地面两次运行逐字段逐位相同；否则本次读数作废（差异可能是进程噪声）。
2. **排除 spawn/reset 通道**：reset 写入态（含两臂各自采样到的值）在**未改列**上必须逐位相同。不同则说明初态输入通道存在。
3. **把分叉定位到动作之前**：零动作步进时，未改列的物理状态是否在几步内分叉。分叉 ⇒ 通道在引擎层；
   始终不分叉 ⇒ 只能说"策略/观测闭环里才有"，不能说引擎层。
4. **边界**：允许判定"通道在哪一层"；不得宣称引擎内部路径已取证，也不得宣称已定量解释 30 s 指标差。

## 结果

### ① 探针自身确定性（条件 1 成立）

`ctrl` 跑两次，`fc` 报"找不到差异"：同一地面下本诊断逐字段可重现。

### ② eval 起跑态逐位相同，只有 rough_b 自己那列不同（条件 2 成立）

`after_wrapper_reset`（= eval 起跑前 wrapper 重置后的状态），两臂逐列比对六个字段
（`pos` / `quat` / `lin` / `ang` / `qpos` / `qvel`，各自按该列 env 子集取 sha256 前 12 位）：

| 列 | 0 flat | 1 slope_5deg | 2 slope_10deg | 3 stairs_10cm | 4 stairs_20cm | 5 rough_a | 6 rough_b | 7 gap_20cm | 8 gap_40cm |
|---|---|---|---|---|---|---|---|---|---|
| 两臂 | SAME | S | SAME | SAME | SAME | **DIFF（仅 `pos`）** | SAME | SAME |

- 未改的八列**六字段逐位相同**；唯一不同的是 rough_b 自己那列的位置——它自己那格的 origin z 从 0.15 m 变到 0.17 m
  （写入态 z = `default 1.1 + 格 origin z`，实测 `1.25` vs `1.27`），与它自己几何被改一致。
- 全局 RNG 流指纹：numpy `6412e2d72a56`(ctrl) vs `5e6d9ae2e5c2`(rougha) —— **流确实被地形生成分流了**；
  torch `b04f168bb97a` 两臂相同。但 reset 区间被配方钉成零区间（`reset_base.pose_range` 各轴 `(0,0)`、
  `velocity_range` 全 `(0,0)`；`reset_robot_joints` `(1.0,1.0)` / `(0,0)`），流的分岔没有变成任何写进初态的取值
  ⇒ **RNG 通道在"值"这一层被排除**。

### ③ 零动作步进：几何与初态都逐位相同的列，0.2 s 内就分叉（条件 3 成立）

无策略（动作为零）、无观测闭环，只让引擎跑：

| 里程碑 | 与另一臂不同的列 | 备注 |
|---|---|---|
| `step_1` | 6 rough_b（`pos/lin/ang/qpos/qvel`） | 只有它自己那格几何变了 |
| `step_10`（0.2 s） | **4 stairs_20cm**、6 | stairs_20cm 的六字段全不同 |
| `step_100`（2 s） | 4、6 | 集合未再扩大 |

- `stairs_20cm` 的**网格摘要与另一臂逐字节相同、起跑态逐位相同**，却在 10 步内走出不同状态。
- `flat / slope_5deg / gap_20cm / gap_40cm` 在 2 s 内始终逐位相同。
- 该段没有抑制 auto-reset（脚本注释说要抑制、代码没有），故终止后的重落格会按同一份钉死的区间重写状态：
  重落**只会掩盖**未改列的分叉，不会制造它（两臂的写入态在未改列上逐位相同）⇒ `stairs_20cm` 的分叉不是重落造成的；
  反过来，"另几列 2 s 内没分叉"这一半是弱证据（可能被重落掩盖）。

### ④ 与归档读数的列集合对应

- 归档里跨臂**读数变化**的列 = `slope_10deg`、`stairs_10cm`、`stairs_20cm`、`rough_a`、`rough_b`
  （`2026-10-10-eval-column-coupling-probes.md` 的逐列表）。
- 本诊断中 **2 s 内始终逐位相同**的列 = `flat`、`slope_5deg`、`gap_20cm`、`gap_40cm` ——
  **与归档里"读数没变"的四列完全相同**。
- 两个独立观测（30 s 策略轨迹的指标 / 2 s 零动作的状态）给出相容的列集合。

### ⑤ 构造期另有同一通道的第二次显现

构造完成、**尚未步进**时（`_sim_step_counter = 0`、`common_step_counter = 0`）读到的状态，两臂在未改列上已有差异：
列 2 `max|Δroot_z|` 6e-06、列 3 3.9e-04、列 4 4.9e-04、列 5 1e-05、列 6 2.3e-05；列 0/1/7/8 逐位相同。
该状态不是写入态（各列 root z 都读 ~1.0993，而写入态是 `1.1 + 格 origin z`）——即构造期引擎自己已把同一批 env 解到
不同结果。eval 流程在构造后由 wrapper 的 reset 重写 spawn，故 **eval 的载体是第③条的步进分叉**，⑤ 只作"同一通道的
第二次显现"。

### ⑥ 判定：坐实到"层"，不坐实到求解器内部

1. **不是** spawn/reset RNG 取值通道：未改列写入态逐位相同（②）。
2. **不是**指标口径或聚合：未改列的状态本身在几步内就分叉，早于任何指标（③）。
3. **不是**策略/观测闭环的产物：零动作、无观测就已经分叉（③）。
4. **是引擎层**：同一张共享碰撞地面里改一格的几何，会让站在**别的、逐字节相同格子**上的 env 在几步内走出不同轨迹。
   ⇒ "改套件里的一列"不是"只影响这一列"；未变的列在**物理上**就已经不是同一次实验。
5. **未取证**：引擎内部路径（mesh cooking / BVH / 接触流形批处理 / GPU 归约序）没有定位；1e-5~5e-4 的分野
   如何变成 0.11 级 completion 差也**没有做定量**（那需要真跑策略，不在本诊断范围内）。

## 证据引用

复读命令（cwd = 仓根；两臂各跑一次，再比对）：

```bat
E:\IsaacLab\env_isaaclab\Scripts\python.exe "%TEMP%\initial_state_probe3.py" ctrl   --headless --device cuda:0
E:\IsaacLab\env_isaaclab\Scripts\python.exe "%TEMP%\initial_state_probe3.py" rougha --headless --device cuda:0
E:\IsaacLab\env_isaaclab\Scripts\python.exe "%TEMP%\initial_state_probe4.py" ctrl   --headless --device cuda:0 --steps 100
E:\IsaacLab\env_isaaclab\Scripts\python.exe "%TEMP%\initial_state_probe4.py" rougha --headless --device cuda:0 --steps 100
python "%TEMP%\cmp_probe4.py"
```

`.bat`/shell 里重定向到 `%TEMP%` 是日志，不是判据；判据是上表的逐列 digest 比对。以下三个脚本是本次实际运行的版本
（本机 `%TEMP%` 会清空，以本记录为准）。

### `initial_state_probe3.py`（写入态 vs 构造态）

```python
# round 3: is the t0 difference in the *written* spawn (reset event inputs) or in the *physics* the
# env has already run by the time a reader looks? Prints the env's own sim counters, the state as
# found, and the state immediately after an explicit `_reset_idx` (no step in between).
import argparse
import hashlib
import pathlib
import sys
import traceback

REPO = pathlib.Path(r"e:\Robot")
HARNESS = REPO / "ablation_harness"
sys.path.insert(0, str(HARNESS))
sys.path.insert(0, str(REPO))

from isaaclab.app import AppLauncher

parser = argparse.ArgumentParser(description="written vs settled spawn for the suite change")
parser.add_argument("mode", choices=["ctrl", "rougha"])
AppLauncher.add_app_launcher_args(parser)
args_cli = parser.parse_args()
simulation_app = AppLauncher(args_cli).app

import gymnasium as gym  # noqa: E402
import numpy as np  # noqa: E402
import torch  # noqa: E402
from isaaclab.utils.string import string_to_callable  # noqa: E402

import isaaclab_tasks  # noqa: F401, E402

from ablation_harness import suites  # noqa: E402
from ablation_harness.components.dr_controller import apply_eval_mode  # noqa: E402
from rl_exp.tasks.terrain_geometry import seed_rngs  # noqa: E402
from rl_exp.tools.verify import terrain_split_probe  # noqa: E402

TASK = "Lizard2-Flat-v3"
SEED = 123
ENVS_PER_TERRAIN = 8
FIELDS = ("pos", "quat", "lin", "ang", "qpos", "qvel")

_V1 = suites._LIZARD_SUITE_V1_GENERATOR


def suite_factory():
    cfg = suites.lizard_suite_v2()
    sub = cfg.terrain_generator.sub_terrains
    sub["rough_a"] = _V1.sub_terrains["rough_a"].copy()
    if args_cli.mode == "ctrl":
        sub["rough_b"] = _V1.sub_terrains["rough_b"].copy()
    return cfg


def digest(tensor) -> str:
    array = np.ascontiguousarray(tensor.detach().cpu().numpy())
    return hashlib.sha256(array.tobytes()).hexdigest()[:12]


def fields_of(robot) -> dict:
    data = robot.data
    return {
        "pos": data.root_pos_w.torch,
        "quat": data.root_quat_w.torch,
        "lin": data.root_lin_vel_w.torch,
        "ang": data.root_ang_vel_w.torch,
        "qpos": data.joint_pos.torch,
        "qvel": data.joint_vel.torch,
    }


def report(label: str, mbenv, names) -> None:
    robot = mbenv.scene["robot"]
    terrain = mbenv.scene.terrain
    values = fields_of(robot)
    types = terrain.terrain_types
    for col, name in enumerate(names):
        ids = (types == col).nonzero(as_tuple=False).squeeze(-1)
        parts = " ".join(f"{key}={digest(values[key][ids])}" for key in FIELDS)
        z = [round(float(v), 6) for v in values["pos"][ids][:, 2]]
        print(f"[PROBE] {label} col={col} {name} {parts} root_z={z}", flush=True)


def main() -> None:
    spec = gym.spec(TASK)
    env_cfg = string_to_callable(spec.kwargs["env_cfg_entry_point"])()
    env_cfg.scene.terrain = suite_factory()
    env_cfg.scene.num_envs = ENVS_PER_TERRAIN * len(suites.LIZARD_SUITE_V2_NAMES)
    env_cfg.episode_length_s = 30.0
    env_cfg.seed = SEED
    env_cfg.curriculum.terrain_levels = None
    apply_eval_mode(env_cfg, "nominal")

    seed_rngs(suites.SUITE_SEED)
    terrain_split_probe.install()
    env = gym.make(TASK, cfg=env_cfg)
    mbenv = env.unwrapped

    ground = terrain_split_probe.record_for(mbenv.scene.terrain)["geometry_digest"]
    print(f"[PROBE] mode={args_cli.mode} geometry_digest={ground}", flush=True)
    print(f"[PROBE] mode={args_cli.mode} counters sim_step_counter={mbenv._sim_step_counter} "
          f"common_step_counter={getattr(mbenv, 'common_step_counter', 'n/a')} "
          f"max_episode_length={getattr(mbenv, 'max_episode_length', 'n/a')}", flush=True)
    report("as_found", mbenv, suites.LIZARD_SUITE_V2_NAMES)

    # the write path alone: no step happens between the event writes and this read
    write_env_ids = torch.arange(mbenv.num_envs, device=mbenv.device)
    mbenv._reset_idx(write_env_ids)
    print(f"[PROBE] mode={args_cli.mode} after_reset sim_step_counter={mbenv._sim_step_counter}", flush=True)
    report("written", mbenv, suites.LIZARD_SUITE_V2_NAMES)
    env.close()


if __name__ == "__main__":
    status = 0
    try:
        main()
    except BaseException:
        traceback.print_exc()
        status = 1
    try:
        simulation_app.close()
    except BaseException:
        traceback.print_exc()
    raise SystemExit(status)
```

### `initial_state_probe4.py`（eval 路径：wrapper reset 后 + 零动作步进）

```python
# round 4: the eval path itself -- wrapper construction (which resets) then zero-action steps,
# printing per-column digests at reset, after 1, 10 and 100 steps so divergence can be dated.
import argparse
import hashlib
import pathlib
import sys
import traceback

REPO = pathlib.Path(r"e:\Robot")
HARNESS = REPO / "ablation_harness"
sys.path.insert(0, str(HARNESS))
sys.path.insert(0, str(REPO))

from isaaclab.app import AppLauncher

parser = argparse.ArgumentParser(description="eval-path divergence date")
parser.add_argument("mode", choices=["ctrl", "rougha"])
parser.add_argument("--steps", type=int, default=100)
AppLauncher.add_app_launcher_args(parser)
args_cli = parser.parse_args()
simulation_app = AppLauncher(args_cli).app

import gymnasium as gym  # noqa: E402
import numpy as np  # noqa: E402
import torch  # noqa: E402
from isaaclab.utils.string import string_to_callable  # noqa: E402

import isaaclab_tasks  # noqa: F401, E402

from isaaclab_rl.rsl_rl import RslRlVecEnvWrapper  # noqa: E402

from ablation_harness import suites  # noqa: E402
from ablation_harness.components.dr_controller import apply_eval_mode  # noqa: E402
from rl_exp.tasks.terrain_geometry import seed_rngs  # noqa: E402
from rl_exp.tools.verify import terrain_split_probe  # noqa: E402

TASK = "Lizard2-Flat-v3"
SEED = 123
ENVS_PER_TERRAIN = 8
FIELDS = ("pos", "quat", "lin", "ang", "qpos", "qvel")

_V1 = suites._LIZARD_SUITE_V1_GENERATOR


def suite_factory():
    cfg = suites.lizard_suite_v2()
    sub = cfg.terrain_generator.sub_terrains
    sub["rough_a"] = _V1.sub_terrains["rough_a"].copy()
    if args_cli.mode == "ctrl":
        sub["rough_b"] = _V1.sub_terrains["rough_b"].copy()
    return cfg


def digest(tensor) -> str:
    array = np.ascontiguousarray(tensor.detach().cpu().numpy())
    return hashlib.sha256(array.tobytes()).hexdigest()[:12]


def fields_of(robot) -> dict:
    data = robot.data
    return {
        "pos": data.root_pos_w.torch,
        "quat": data.root_quat_w.torch,
        "lin": data.root_lin_vel_w.torch,
        "ang": data.root_ang_vel_w.torch,
        "qpos": data.joint_pos.torch,
        "qvel": data.joint_vel.torch,
    }


def report(label: str, mbenv, names) -> None:
    robot = mbenv.scene["robot"]
    values = fields_of(robot)
    types = mbenv.scene.terrain.terrain_types
    for col, name in enumerate(names):
        ids = (types == col).nonzero(as_tuple=False).squeeze(-1)
        parts = " ".join(f"{key}={digest(values[key][ids])}" for key in FIELDS)
        print(f"[PROBE] {label} col={col} {name} {parts}", flush=True)


def main() -> None:
    spec = gym.spec(TASK)
    env_cfg = string_to_callable(spec.kwargs["env_cfg_entry_point"])()
    env_cfg.scene.terrain = suite_factory()
    env_cfg.scene.num_envs = ENVS_PER_TERRAIN * len(suites.LIZARD_SUITE_V2_NAMES)
    env_cfg.episode_length_s = 30.0
    env_cfg.seed = SEED
    env_cfg.curriculum.terrain_levels = None
    apply_eval_mode(env_cfg, "nominal")

    seed_rngs(suites.SUITE_SEED)
    terrain_split_probe.install()
    gym_env = gym.make(TASK, cfg=env_cfg)
    ground = terrain_split_probe.record_for(gym_env.unwrapped.scene.terrain)["geometry_digest"]
    wrapper = RslRlVecEnvWrapper(gym_env, clip_actions=None)  # this is the reset an eval run does
    mbenv = wrapper.unwrapped if hasattr(wrapper, "unwrapped") else gym_env.unwrapped
    print(f"[PROBE] mode={args_cli.mode} geometry_digest={ground}", flush=True)
    report("after_wrapper_reset", mbenv, suites.LIZARD_SUITE_V2_NAMES)

    actions = torch.zeros(mbenv.num_envs, mbenv.action_manager.total_action_dim, device=mbenv.device)
    milestones = {1, 10, args_cli.steps}
    for step in range(1, args_cli.steps + 1):
        wrapper.step(actions)
        if step in milestones:
            report(f"step_{step}", mbenv, suites.LIZARD_SUITE_V2_NAMES)
    gym_env.close()


if __name__ == "__main__":
    status = 0
    try:
        main()
    except BaseException:
        traceback.print_exc()
        status = 1
    try:
        simulation_app.close()
    except BaseException:
        traceback.print_exc()
    raise SystemExit(status)
```

### `cmp_probe4.py`（逐列比对；`fc` 会因长行折行报假差异）

```python
"""Compare round-4 dumps (eval path): per milestone and column, which state fields differ."""

import pathlib
import re
import sys

TEMP = pathlib.Path(r"C:\Users\yanke03\AppData\Local\Temp")
LABELS = ("after_wrapper_reset", "step_1", "step_10", "step_100")


def load(path):
    rows = {}
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if not line.startswith("[PROBE] "):
            continue
        header = re.match(r"\[PROBE\] mode=(\S+) geometry_digest=(\S+)", line)
        if header:
            rows["geometry_digest"] = header.group(2)
            continue
        body = re.match(r"\[PROBE\] (\S+) col=(\d+) (\S+) (.*)", line)
        if body and body.group(1) in LABELS:
            rows[(body.group(1), int(body.group(2)))] = (body.group(3), body.group(4))
    return rows


def main() -> int:
    left = load(TEMP / "t_ctrl_probe.txt")
    right = load(TEMP / "t_rougha_probe.txt")
    print(f"geometry_digest ctrl={left.get('geometry_digest')}")
    print(f"geometry_digest rougha={right.get('geometry_digest')}")
    for label in LABELS:
        differing = []
        for col in range(9):
            key = (label, col)
            if key not in left or key not in right:
                print(f"{label} col={col} MISSING")
                continue
            name, left_blob = left[key]
            _, right_blob = right[key]
            if left_blob == right_blob:
                print(f"{label} col={col} {name:12s} SAME")
                continue
            changed = [f.split("=")[0] for f, r in zip(left_blob.split(), right_blob.split()) if f != r]
            differing.append((col, name, changed))
            print(f"{label} col={col} {name:12s} DIFF fields={changed}")
        print(f"  -> {label}: differing columns {[c for c, _, _ in differing]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

## 未覆盖边界

- **不起 policy**：不解释 30 s 里 1e-5~5e-4 的分野如何放大成 0.11 级 completion 差（需要真跑策略），也不评策略强弱；
  本诊断读数只作耦合证据，不得引用进任何成绩行或验收表。
- **单一条件**：nominal、seed 123、单机（同 GPU/驱动/PhysX 版本）、9 列 × 8 env；两臂只在 rough_a/rough_b 生成参数上不同。
- **引擎内部路径未取证**：只能说"通道在引擎层"，不能说清是 mesh cooking、BVH、接触流形批处理还是归约序。
- **构造期差异的成因未定位**：⑤ 只报"引擎在构造期已把未改列解成不同结果"，没有指出是哪一次调用做的。
- **零动作段的弱半边**：③ 未抑制 auto-reset，"另几列 2 s 内没分叉"可能被重落掩盖（重落只掩盖不制造分叉）。
- **未落规则**：没有把"改套件 ⇒ 未变列不可比"写进 `HARNESS.md`/协议，也没有把这套诊断变成常驻工具——两件都是待决动作，
  见 `work/active/eval-column-coupling.md` 的 `next`。本记录存在不等于返工已完成。
