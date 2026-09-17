# -*- coding: utf-8 -*-
"""Real-run half of the terrain split work (ARCH_PLAN Step 3.3c observation / 3.3d consumption).

The offline gate (``terrain_split_feasibility.py``) proves a generator *can* be watched
headless. This runs the same thing inside a real env construction -- the path training
actually takes -- and checks the consumer side: a curriculum term is handed the record of the
generation that ran, its column ownership agrees with that record, and a param-grid terrain
whose record is unsound refuses instead of guessing.

Not part of the offline suite (it starts the simulator): run it by hand, like
``terrain_preflight.py``. Usage, from the IsaacLab tree:

    <venv python> <repo>\\rl_exp\\tools\\verify\\terrain_split_env_run.py --task Lizard-Rough-v11 --num_envs 64
"""

import argparse
import pathlib
import sys

_REPO = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO))

from isaaclab.app import AppLauncher  # noqa: E402

parser = argparse.ArgumentParser(description="Terrain split probe, inside a real env.")
parser.add_argument("--task", type=str, default="Lizard-Rough-v11", help="A param-grid recipe task.")
parser.add_argument("--num_envs", type=int, default=64, help="Override the recipe's env count.")
AppLauncher.add_app_launcher_args(parser)
args_cli = parser.parse_args()
app_launcher = AppLauncher(args_cli)
simulation_app = app_launcher.app

import gymnasium as gym  # noqa: E402

import isaaclab_tasks  # noqa: F401, E402  (registers the gym tasks)

from isaaclab.utils.string import string_to_callable  # noqa: E402
from rl_exp.tasks import terrain_map  # noqa: E402
from rl_exp.tasks.teacher_mdp import JOINT_SIR_TERM  # noqa: E402
from rl_exp.tools.verify import terrain_split_probe as probe  # noqa: E402


def main() -> int:
    problems: list[str] = []
    spec = gym.spec(args_cli.task)
    env_cfg = string_to_callable(spec.kwargs["env_cfg_entry_point"])()
    env_cfg.scene.num_envs = args_cli.num_envs
    env_cfg.seed = 0  # the probe reads the generator's output, not a random stream of its own
    env = gym.make(args_cli.task, cfg=env_cfg).unwrapped
    terrain = env.scene.terrain
    print(f"[env] {args_cli.task}: {env.num_envs} envs, terrain origins {tuple(terrain.terrain_origins.shape)}")

    record = probe.record_for(terrain)
    cells = len(record["cells"])
    expected = int(record["num_rows"]) * int(record["num_cols"])
    print(f"[probe] mode={record['mode']} cells={cells}/{expected} anomalies={len(record['anomalies'])}")
    print(f"[probe] columns={record['columns'][:12]}... ({len(record['columns'])} columns)")
    print(f"[probe] sub-terrains={len(record['sub_terrains'])} "
          f"difficulty {min(c['difficulty'] for c in record['cells']):.3f}.."
          f"{max(c['difficulty'] for c in record['cells']):.3f}")
    if cells != expected or record["anomalies"]:
        problems.append(f"record incomplete or anomaly-carrying: {cells}/{expected} {record['anomalies'][:3]}")

    # Consumption evidence: the manager already built this term while the env was created, and
    # the term refuses a terrain with no sound record -- so reaching this line at all means the
    # consuming path read the record. The extra instance below only re-reads it for the
    # column-ownership cross-check (the manager keeps no public handle on a term).
    term_cfg = env.cfg.curriculum.__dict__.get(JOINT_SIR_TERM)
    if term_cfg is None:
        problems.append(f"no {JOINT_SIR_TERM} term in this task: it is not the consuming path")
    else:
        from rl_exp.tasks.teacher_mdp import JointSIRTerrainCurriculum

        term = JointSIRTerrainCurriculum(term_cfg, env)
        by_type: dict[str, set[int]] = {}
        for col, index in enumerate(record["columns"]):
            by_type.setdefault(record["sub_terrains"][index].partition("|")[0], set()).add(col)
        for type_index, type_cols in enumerate(term._combo_cols):
            owned = {col for cols in type_cols for col in cols.tolist()}
            declared = by_type.get(term._types[type_index], set())
            print(f"[consume] {term._types[type_index]}: {len(owned)} column(s), "
                  f"{len(term._combo_cols[type_index])} combo(s) from the record")
            if owned != declared:
                problems.append(
                    f"{term._types[type_index]}: term owns {sorted(owned)[:6]} vs record {sorted(declared)[:6]}"
                )
    env.close()

    for problem in problems:
        print(f"[problem] {problem}")
    print("TERRAIN_SPLIT_ENV_RUN_FAILED" if problems else "TERRAIN_SPLIT_ENV_RUN_OK")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())
