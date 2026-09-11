# -*- coding: utf-8 -*-
"""Parameterized teacher smoke runner: one protocol, one version contract table.

v3/v5/v6/v8/v11 each carried a copied ~120-line script (near-duplicate
skeleton, a couple dozen version-diff lines each). Copies have no gate: a
missed edit in a duplicated assertion stays silent forever -- same lesson as
the v10/v11 record debt (纯约定没闸门 = 必然欠账, versioning.mdc). This runner
holds the shared assertions; the per-version contract lives in SMOKE_SPEC,
shaped like TEACHER_PRIVILEGED_SPEC (version -> its own values, code-level
single source). A new recipe version = add one SMOKE_SPEC row + a thin
teacher_smoke_vN.py shell; never copy a whole smoke file (versioning.mdc A-3).

DISCIPLINE: a SMOKE_SPEC row must be field-reviewed against the row it forks
from -- a wrong row keeps this runner GREEN (the table has no gate of its own;
review is the gate, same contract as the privileged spec). Rows must bite:
when adding or migrating a row, flip one version-unique value and confirm the
run goes red before trusting it.

Scope: teacher main line only. teacher_smoke.py (v2, single 308-dim group,
pre-group era) stays a legacy standalone; parkour_smoke.py (side-line schema)
never uses this runner.

Usage: python rl_exp\\tools\\verify\\teacher_smoke_vN.py --headless
"""
import pathlib
import sys

_REPO = pathlib.Path(__file__).resolve().parents[3]

# network reshape contract, identical v3..v12 (not a per-version knob)
EXPECTED_EXTERO_ORDER = ("lf_foot_ring", "rf_foot_ring", "rl_foot_ring", "rr_foot_ring")


def _bucket_jitter_check(train_env, reset_info):
    """v11 TRAIN: commanded vx must sit within jitter of a particle bucket
    (the Eq. 2 label accumulator rides the same term)."""
    import torch
    import yaml

    from rl_exp.tasks.teacher_mdp import ParticleVelocityCommand

    term = train_env.unwrapped.command_manager.get_term("base_velocity")
    assert isinstance(term, ParticleVelocityCommand), f"TRAIN command term is {type(term).__name__}"
    v11_yaml = _REPO / "rl_exp" / "versions" / "lizard" / "v11" / "lizard_params.yaml"
    v11y = yaml.safe_load(v11_yaml.read_text(encoding="utf-8"))["v11"]
    buckets = torch.tensor(v11y["velocity_buckets"])
    vx = term.vel_command_b[:, 0]
    for i in range(vx.shape[0]):
        dist = (buckets - vx[i]).abs().min()
        assert dist <= v11y["velocity_command"]["command_jitter"] + 1.0e-6, (
            f"env {i} commanded vx {float(vx[i]):.3f} is not within jitter of a bucket {buckets.tolist()}"
        )
    print("COMMANDS particle buckets OK (vx: %s, buckets %s)" % (vx.tolist(), buckets.tolist()))


# One row per version, values as they were asserted in the copied scripts.
# None fields mean "this version's original script did not check it" -- a
# documented gap, not a forgotten fill.
SMOKE_SPEC: dict[str, dict] = {
    "v3": {
        "group_dims": {"proprio": 90, "extero": 208, "priv": 83},
        "rewards_required": ("foot_clearance",),
        "rewards_absent": ("feet_air_time",),  # D2 replacement
        "terminations_required": ("tilt",),
        "terminations_absent": (),  # tilt still in (removed v10)
        "curriculum_play_absent": (),  # v3 script did not check curriculum
        "command": None,  # v3 script did not check commands
        "spine_scale": None,  # pre-v6.1: spine locked
        "train": None,  # v3-era contract is PLAY-only
    },
    "v5": {
        "group_dims": {"proprio": 90, "extero": 208, "priv": 83},
        "rewards_required": ("track_lin_vel_xy_lin", "feet_slide", "belly_contact_force",
                             "foot_clearance", "track_ang_vel_z_exp"),
        "rewards_absent": ("track_lin_vel_xy_exp",),
        "terminations_required": ("tilt",),
        "terminations_absent": (),
        "curriculum_play_absent": ("speed_curriculum", "terrain_levels"),
        "command": "forward",
        "spine_scale": None,  # v5 spine still locked (yaml 0)
        "train": {"label": "SIR", "sir": "terrain_levels", "sir_absent": (),
                  "grid": (10, 20), "log_key": "Curriculum/terrain_levels",
                  "param_grid": False},
    },
    "v6": {
        # v5 contract on the axis-corrected asset + v6.1 spine unlock
        "group_dims": {"proprio": 90, "extero": 208, "priv": 83},
        "rewards_required": ("track_lin_vel_xy_lin", "feet_slide", "belly_contact_force",
                             "foot_clearance", "track_ang_vel_z_exp"),
        "rewards_absent": ("track_lin_vel_xy_exp",),
        "terminations_required": ("tilt",),
        "terminations_absent": (),
        "curriculum_play_absent": ("speed_curriculum", "terrain_levels"),
        "command": "forward",
        "spine_scale": 0.25,
        "train": {"label": "SIR", "sir": "terrain_levels", "sir_absent": (),
                  "grid": (10, 20), "log_key": "Curriculum/terrain_levels",
                  "param_grid": False},
    },
    "v8": {
        # v6 contract on the anatomy-correct asset (v6.2 params, rebase of v6)
        "group_dims": {"proprio": 90, "extero": 208, "priv": 83},
        "rewards_required": ("track_lin_vel_xy_lin", "feet_slide", "belly_contact_force",
                             "foot_clearance", "track_ang_vel_z_exp"),
        "rewards_absent": ("track_lin_vel_xy_exp",),
        "terminations_required": ("tilt",),
        "terminations_absent": (),
        "curriculum_play_absent": ("speed_curriculum", "terrain_levels"),
        "command": "forward",
        "spine_scale": 0.25,
        "train": {"label": "SIR", "sir": "terrain_levels", "sir_absent": (),
                  "grid": (10, 20), "log_key": "Curriculum/terrain_levels",
                  "param_grid": False},
    },
    "v11": {
        # v10 tilt removal + joint particle curriculum (v8 PLAY minus tilt)
        "group_dims": {"proprio": 90, "extero": 208, "priv": 83},
        "rewards_required": ("track_lin_vel_xy_lin", "feet_slide", "belly_contact_force",
                             "foot_clearance", "track_ang_vel_z_exp"),
        "rewards_absent": ("track_lin_vel_xy_exp",),
        "terminations_required": ("time_out",),
        "terminations_absent": ("tilt",),
        "curriculum_play_absent": ("speed_curriculum", "joint_sir"),
        "command": "particle",
        "spine_scale": 0.25,
        "train": {"label": "JOINT_SIR", "sir": "joint_sir", "sir_absent": ("terrain_levels",),
                  "grid": (4, 120), "log_key": "Curriculum/joint_sir/frontier_max_v",
                  "param_grid": True},
        "train_extras": (_bucket_jitter_check,),
    },
}


def _run_play(ver: str, spec: dict, gym, torch, teacher_env_cfg) -> None:
    cfg_cls = getattr(teacher_env_cfg, f"LizardRoughTeacherEnvCfg_{ver.upper()}_PLAY")
    cfg = cfg_cls()
    cfg.scene.num_envs = 2
    env = gym.make(f"Lizard-Rough-Play-{ver}", cfg=cfg)
    obs, _ = env.reset()

    group_dims = spec["group_dims"]
    print("OBS_KEYS %s" % (sorted(obs.keys()),))
    assert set(obs.keys()) == set(group_dims), f"obs groups {sorted(obs.keys())} != contract"
    for group, dim in group_dims.items():
        assert obs[group].shape == (2, dim), f"group '{group}' shape {tuple(obs[group].shape)} != (2, {dim})"
        print("GROUP %s %s" % (group, tuple(obs[group].shape)))
    print("GROUP_TOTAL %d" % sum(group_dims.values()))

    om = env.unwrapped.observation_manager
    extero_terms = om.active_terms["extero"]
    assert tuple(extero_terms) == EXPECTED_EXTERO_ORDER, f"extero order {extero_terms} != {EXPECTED_EXTERO_ORDER}"
    print("EXTERO_ORDER %s" % (extero_terms,))

    tm = env.unwrapped.termination_manager
    for required in spec["terminations_required"]:
        assert required in tm.active_terms, f"{ver} termination '{required}' missing: {tm.active_terms}"
    for absent in spec["terminations_absent"]:
        assert absent not in tm.active_terms, f"{ver} must drop the '{absent}' termination: {tm.active_terms}"
    rm = env.unwrapped.reward_manager
    for required in spec["rewards_required"]:
        assert required in rm.active_terms, f"{ver} reward '{required}' missing: {rm.active_terms}"
    for absent in spec["rewards_absent"]:
        assert absent not in rm.active_terms, f"{ver} must replace/remove reward '{absent}': {rm.active_terms}"
    cm = env.unwrapped.curriculum_manager
    for absent in spec["curriculum_play_absent"]:
        assert absent not in cm.active_terms, f"{ver} PLAY must drop '{absent}' (no roaming)"
    print("TERMS %s OK (rewards/terminations/curriculum as spec)" % ver)

    if spec["command"] is not None:
        term = env.unwrapped.command_manager.get_term("base_velocity")
        if spec["command"] == "particle":
            from rl_exp.tasks.teacher_mdp import ParticleVelocityCommand

            assert isinstance(term, ParticleVelocityCommand), (
                f"PLAY command term is {type(term).__name__}, not ParticleVelocityCommand"
            )
        cmd = term.vel_command_b
        assert (cmd[:, 0] >= -1.0e-6).all(), f"forward-only commands violated: {cmd[:, 0]}"
        print("COMMANDS forward-only OK (sample vx: %s)" % (cmd[:, 0].tolist(),))

    if spec["spine_scale"] is not None:
        # spine unlock rides the yaml spine_scale (chest + neck + tail1-3, 10 joints)
        spine_scale = float(env.unwrapped.action_manager.get_term("joint_pos_spine")._scale)
        assert spine_scale == spec["spine_scale"], (
            f"{ver} spine action scale {spine_scale} != yaml {spec['spine_scale']}"
        )
        print("SPINE_UNLOCKED scale=%.2f OK" % spine_scale)

    with torch.inference_mode():
        for _ in range(10):
            obs, rew, term, trunc, info = env.step(
                torch.zeros(2, env.unwrapped.action_manager.total_action_dim))
    assert torch.isfinite(rew).all(), f"non-finite reward: {rew}"
    for group, tensor in obs.items():
        assert torch.isfinite(tensor).all(), f"non-finite obs in group '{group}'"
    # anti-regression: the ring channels must actually vary (a dead caster reads
    # back a constant row and every downstream encoder silently learns nothing)
    assert obs["extero"].std() > 1.0e-3, f"extero group is near-constant (std {obs['extero'].std():.2e})"
    print("STEP_FINITE %s EXTERO_STD %.4f" % (bool(torch.isfinite(rew).all()), float(obs["extero"].std())))
    env.close()


def _run_train(ver: str, spec: dict, gym, torch, teacher_env_cfg) -> None:
    """2-env TRAIN pass: the SIR curriculum must instantiate against the REAL
    terrain importer (column split from generator proportions) and run its
    reset + bookkeeping paths on live tensors -- the offline unit tests only
    cover mocked terrains."""
    tr = spec["train"]
    if tr is None:
        print("TRAIN_SKIPPED %s (PLAY-only contract)" % ver)
        return
    cfg_cls = getattr(teacher_env_cfg, f"LizardRoughTeacherEnvCfg_{ver.upper()}")
    cfg = cfg_cls()
    cfg.scene.num_envs = 2
    env = gym.make(f"Lizard-Rough-{ver}", cfg=cfg)
    res = env.reset()
    train_obs = res[0]
    reset_info = res[-1] if isinstance(res[-1], dict) else {}
    for group, dim in spec["group_dims"].items():
        assert train_obs[group].shape == (2, dim), f"train group '{group}' shape {tuple(train_obs[group].shape)}"

    cm = env.unwrapped.curriculum_manager
    assert tr["sir"] in cm.active_terms, f"'{tr['sir']}' term missing in TRAIN: {cm.active_terms}"
    for absent in tr["sir_absent"]:
        assert absent not in cm.active_terms, f"TRAIN must drop the superseded '{absent}' term"
    terrain = env.unwrapped.scene.terrain
    num_rows, num_cols = terrain.terrain_origins.shape[0], terrain.terrain_origins.shape[1]
    assert (num_rows, num_cols) == tuple(tr["grid"]), f"terrain grid {num_rows}x{num_cols} != {tr['grid'][0]}x{tr['grid'][1]}"
    if tr["param_grid"]:
        gen = terrain.cfg.terrain_generator
        assert gen.curriculum is True, ("generator-swap pit: curriculum flag lost "
                                        "(column split would be random)")
        assert any("|" in n for n in gen.sub_terrains) and "flat" in gen.sub_terrains, "param-grid combo names missing"
    for i in range(2):
        lvl = terrain.terrain_levels[i].item()
        col = terrain.terrain_types[i].item()
        assert 0 <= lvl < num_rows and 0 <= col < num_cols, f"env {i} spawned at ({lvl}, {col}) out of grid"
        assert torch.equal(terrain.env_origins[i], terrain.terrain_origins[lvl, col]), f"env {i} origin mismatch"
    print("%s_TRAIN origins re-pointed inside the %dx%d grid OK (levels %s cols %s)" %
          (tr["label"], num_rows, num_cols, terrain.terrain_levels.tolist(), terrain.terrain_types.tolist()))

    with torch.inference_mode():
        for _ in range(30):
            train_obs, rew, term, trunc, info = env.step(
                torch.zeros(2, env.unwrapped.action_manager.total_action_dim))
    assert torch.isfinite(rew).all(), f"non-finite train reward: {rew}"
    # a tilt-less version may not reset mid-episode within 30 steps, so the
    # curriculum log key is taken from the last step OR the reset info
    log = info.get("log", {}).get(tr["log_key"], reset_info.get("log", {}).get(tr["log_key"]))
    assert log is not None and torch.isfinite(torch.tensor(float(log))), f"{tr['log_key']} {log}"
    print("%s_TRAIN stepped, %s = %s" % (tr["label"], tr["log_key"], log))

    for extra in tr.get("train_extras", ()):
        extra(env, reset_info)
    env.close()


def main(ver: str) -> int:
    spec = SMOKE_SPEC[ver]
    import argparse

    from isaaclab.app import AppLauncher

    parser = argparse.ArgumentParser()
    AppLauncher.add_app_launcher_args(parser)
    args_cli = parser.parse_args()
    simulation_app = AppLauncher(args_cli).app

    import gymnasium as gym
    import torch

    import isaaclab_tasks  # noqa: F401
    from rl_exp.tasks import teacher_env_cfg

    _run_play(ver, spec, gym, torch, teacher_env_cfg)
    _run_train(ver, spec, gym, torch, teacher_env_cfg)
    print("=== DONE ===")
    return 0


if __name__ == "__main__":
    # direct use: teacher_smoke_runner.py v11 --headless (version arg removed
    # before AppLauncher's parser sees argv); the teacher_smoke_vN.py shells call main()
    raise SystemExit(main(sys.argv.pop(1)))
