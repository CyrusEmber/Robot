# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

"""Train an RSL-RL policy from a standalone experiment definition."""

import argparse
from contextlib import ExitStack
from datetime import datetime
from importlib.util import find_spec
from pathlib import Path
from random import SystemRandom
import sys
import traceback
from uuid import uuid4

from isaaclab.app import AppLauncher

from rl_exp.locomotion.env import load_experiment, make_env, make_runner_cfg, wrap_env
from rl_exp.locomotion.train_record import interface_signature, write_json, write_provenance

_DEFAULT_OUTPUT = Path(__file__).resolve().parents[1] / "out" / "train"


def _positive_int(value: str) -> int:
    number = int(value)
    if number < 1:
        raise argparse.ArgumentTypeError("must be a positive integer")
    return number


def main() -> None:
    """Run training using the experiment's environment and PPO configuration factories."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--exp", type=Path, help="Python experiment definition (required).")
    parser.add_argument("--num-envs", type=_positive_int, help="Override the number of environments.")
    parser.add_argument("--max-iterations", type=_positive_int, help="Override the PPO iteration count.")
    parser.add_argument("--seed", type=int, help="Override the random seed (-1 chooses a seed).")
    parser.add_argument("--output-root", type=Path, default=_DEFAULT_OUTPUT, help="Parent directory for runs.")
    parser.add_argument("--run-dir", type=Path, help=argparse.SUPPRESS)
    AppLauncher.add_app_launcher_args(parser)
    args = parser.parse_args()

    if args.exp is None:
        parser.error("--exp is required")
    experiment_path = args.exp.resolve()
    if experiment_path.suffix != ".py" or not experiment_path.is_file():
        parser.error(f"--exp must point to an existing Python file: {experiment_path}")

    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    run = args.run_dir or args.output_root.resolve() / f"{timestamp}_{uuid4().hex[:8]}"

    experiment = load_experiment(experiment_path)

    from isaaclab.utils.io import dump_yaml

    env_cfg = experiment.make_env_cfg()
    runner_cfg = make_runner_cfg(experiment)
    if args.num_envs is not None:
        env_cfg.scene.num_envs = args.num_envs
    if args.max_iterations is not None:
        runner_cfg.max_iterations = args.max_iterations
    if args.seed is not None:
        runner_cfg.seed = args.seed
    if runner_cfg.seed == -1:
        runner_cfg.seed = SystemRandom().randrange(10_000)
    env_cfg.seed = runner_cfg.seed
    env_cfg.validate()

    env_cfg.log_dir = str(run)
    if find_spec("isaacsim") is None:
        raise SystemExit("Isaac Sim/Kit is unavailable in this Python environment. PhysX training requires it.")
    run.mkdir(parents=True)
    launcher = AppLauncher(args)
    try:
        print(f"Run directory: {run}", flush=True)
        with ExitStack() as cleanup:
            from rsl_rl.runners import OnPolicyRunner

            env_cfg.sim.device = launcher.device
            runner_cfg.device = launcher.device
            dump_yaml(str(run / "resolved_cfg.yaml"), {"env": env_cfg.to_dict(), "runner": runner_cfg.to_dict()})
            env = make_env(env_cfg)
            cleanup.callback(env.close)
            robot_mod = getattr(experiment, "ROBOT", None)
            urdf_path = getattr(robot_mod, "URDF_PATH", None) or getattr(experiment, "URDF_PATH", None)
            write_provenance(run, experiment_path, env_cfg.scene.robot.spawn.usd_path, urdf_path)

            signature = interface_signature(env)
            write_json(run / "interface_signature.json", signature)

            class TrainingRunner(OnPolicyRunner):
                def save(self, path: str, infos: dict | None = None) -> None:
                    super().save(path, {**(infos or {}), "interface_signature": signature})

            wrapped_env = wrap_env(env, runner_cfg)
            runner = TrainingRunner(wrapped_env, runner_cfg.to_dict(), log_dir=str(run), device=runner_cfg.device)
            # This entry point records source state itself without requiring a clean Git worktree.
            runner.logger.git_status_repos.clear()
            runner.learn(num_learning_iterations=runner_cfg.max_iterations, init_at_random_ep_len=True)
            if not (run / f"model_{runner.current_learning_iteration}.pt").is_file():
                raise RuntimeError("Training finished without writing its final checkpoint")
    except BaseException:
        # Kit's default fast shutdown terminates Python and would discard this error.
        traceback.print_exc()
        sys.stdout.flush()
        sys.stderr.flush()
        launcher.app.close(exit_code=1)
        raise SystemExit(1)
    launcher.app.close()


if __name__ == "__main__":
    main()
