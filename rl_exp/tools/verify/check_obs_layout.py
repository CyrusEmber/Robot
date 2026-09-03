# -*- coding: utf-8 -*-
"""Static obs-layout gate for the teacher recipe versions (no sim, plain python).

Asserts, straight from the configclass definitions (constructed, never built
as envs): group names, per-group term order, extero foot order, ring-pattern
total points, and the c_k steps_per_iteration == runner num_steps_per_env
consistency. Live dims (90/208/83) are asserted by teacher_smoke_v3.py against
the observation manager; this gate catches the silent reorders and contract
breaks before an env ever loads.
"""

import pathlib
import sys

import yaml

_REPO = pathlib.Path(__file__).resolve().parents[3]
_EXP = _REPO / "rl_exp"
sys.path.insert(0, str(_REPO))

from rl_exp.tasks.teacher_env_cfg import (  # noqa: E402
    LizardRoughTeacherEnvCfg_V1,
    LizardRoughTeacherEnvCfg_V2,
    LizardRoughTeacherEnvCfg_V3,
    LizardRoughTeacherEnvCfg_V4,
    LizardRoughTeacherEnvCfg_V5,
)
from rl_exp.tasks.agents.rsl_rl_ppo_cfg import (  # noqa: E402
    LizardTeacherV3PPORunnerCfg,
    LizardTeacherV4PPORunnerCfg,
    LizardTeacherV5PPORunnerCfg,
)

V3_EXTERO_ORDER = ["lf_foot_ring", "rf_foot_ring", "rl_foot_ring", "rr_foot_ring"]
V3_PROPRIO_ORDER = [
    "base_lin_vel", "base_ang_vel", "projected_gravity", "velocity_commands",
    "joint_pos", "joint_vel", "actions",
]
V3_PRIV_BASE = [
    "base_lin_vel_true", "base_ang_vel_true", "foot_contact", "feet_air_time",
    "body_mass",
]
V3_PRIV_ORDER = V3_PRIV_BASE + [
    "foot_contact_forces", "foot_contact_normals", "foot_friction",
    "thigh_shank_contacts", "base_external_wrench",
]
V1_POLICY_ORDER = V3_PROPRIO_ORDER + ["height_scan"] + V3_PRIV_BASE
V2_POLICY_ORDER = V3_PROPRIO_ORDER + ["height_scan"] + V3_PRIV_ORDER

# group-level settings, not terms (mirrors the observation manager's skip list)
_GROUP_FIELDS = {
    "enable_corruption", "concatenate_terms", "history_length",
    "flatten_history_dim", "concatenate_dim",
}


def _groups(observations) -> dict[str, list[str]]:
    """Group name -> ordered term names, from the cfg (manager reads __dict__)."""
    out = {}
    for name, group in vars(observations).items():
        if group is None:
            continue
        terms = [t for t in vars(group) if t not in _GROUP_FIELDS and vars(group)[t] is not None]
        out[name] = terms
    return out


def main() -> int:
    problems = []

    # v1/v2: single policy group with the frozen flat order
    for cls, tag, expected in (
        (LizardRoughTeacherEnvCfg_V2, "v2", V2_POLICY_ORDER),
        (LizardRoughTeacherEnvCfg_V1, "v1", V1_POLICY_ORDER),
    ):
        groups = _groups(cls().observations)
        if set(groups) != {"policy"}:
            problems.append(f"{tag}: expected single 'policy' group, got {sorted(groups)}")
        elif groups["policy"] != expected:
            missing = set(expected) ^ set(groups["policy"])
            if missing:
                problems.append(f"{tag}: policy term set drift {sorted(missing)}")
            else:
                problems.append(f"{tag}: policy term ORDER changed (silent mis-wiring)")

    # v3: three named groups, frozen orders
    v3 = LizardRoughTeacherEnvCfg_V3()
    groups = _groups(v3.observations)
    if set(groups) != {"proprio", "extero", "priv"}:
        problems.append(f"v3: expected proprio/extero/priv groups, got {sorted(groups)}")
    else:
        if groups["proprio"] != V3_PROPRIO_ORDER:
            problems.append(f"v3: proprio order {groups['proprio']} != contract")
        if groups["extero"] != V3_EXTERO_ORDER:
            problems.append(f"v3: extero order {groups['extero']} != {V3_EXTERO_ORDER}")
        if groups["priv"] != V3_PRIV_ORDER:
            problems.append(f"v3: priv order {groups['priv']} != contract")

    # yaml: ring pattern totals to 208 extero dims and c_k step consistency
    with open(_EXP / "versions" / "lizard" / "v3" / "lizard_params.yaml", encoding="utf-8") as f:
        params = yaml.safe_load(f)
    v3y = params["v3"]
    counts = v3y["foot_ring"]["ring_counts"]
    radii = v3y["foot_ring"]["ring_radii"]
    if len(counts) != len(radii):
        problems.append(f"v3 yaml: ring_counts/radii length mismatch {counts} vs {radii}")
    total = sum(counts)
    if total * 4 != 208:
        problems.append(f"v3 yaml: ring total {total} x 4 feet != 208 extero dims")
    ck_steps = v3y["curriculum_ck"]["steps_per_iteration"]
    runner_steps = LizardTeacherV3PPORunnerCfg().num_steps_per_env
    if ck_steps != runner_steps:
        problems.append(
            f"v3: yaml curriculum_ck.steps_per_iteration {ck_steps} != runner "
            f"num_steps_per_env {runner_steps} (c_k iteration length would lie)"
        )

    # scan-reading sensors: v3 must not keep a policy group or base height scanner
    if getattr(v3.scene, "height_scanner", "missing") is not None:
        problems.append("v3: base height_scanner should be retired (foot rings own extero)")
    for foot in ("lf", "rf", "rl", "rr"):
        if getattr(v3.scene, f"{foot}_foot_ring", None) is None:
            problems.append(f"v3: missing {foot}_foot_ring RayCasterCfg")

    # v4: same three-group contract as v3 (terrain-only re-tune), own yaml copy
    v4 = LizardRoughTeacherEnvCfg_V4()
    groups = _groups(v4.observations)
    if set(groups) != {"proprio", "extero", "priv"}:
        problems.append(f"v4: expected proprio/extero/priv groups, got {sorted(groups)}")
    else:
        if groups["proprio"] != V3_PROPRIO_ORDER:
            problems.append(f"v4: proprio order {groups['proprio']} != contract")
        if groups["extero"] != V3_EXTERO_ORDER:
            problems.append(f"v4: extero order {groups['extero']} != {V3_EXTERO_ORDER}")
        if groups["priv"] != V3_PRIV_ORDER:
            problems.append(f"v4: priv order {groups['priv']} != contract")
    if getattr(v4.scene, "height_scanner", "missing") is not None:
        problems.append("v4: base height_scanner should be retired (foot rings own extero)")
    for foot in ("lf", "rf", "rl", "rr"):
        if getattr(v4.scene, f"{foot}_foot_ring", None) is None:
            problems.append(f"v4: missing {foot}_foot_ring RayCasterCfg")

    # yaml: v4 is a verbatim copy of v3's (terrain lives in code, not yaml) --
    # guard the copy's own ring totals and c_k step consistency
    with open(_EXP / "versions" / "lizard" / "v4" / "lizard_params.yaml", encoding="utf-8") as f:
        params = yaml.safe_load(f)
    v4y = params["v3"]
    counts = v4y["foot_ring"]["ring_counts"]
    radii = v4y["foot_ring"]["ring_radii"]
    if len(counts) != len(radii):
        problems.append(f"v4 yaml: ring_counts/radii length mismatch {counts} vs {radii}")
    total = sum(counts)
    if total * 4 != 208:
        problems.append(f"v4 yaml: ring total {total} x 4 feet != 208 extero dims")
    ck_steps = v4y["curriculum_ck"]["steps_per_iteration"]
    runner_steps = LizardTeacherV4PPORunnerCfg().num_steps_per_env
    if ck_steps != runner_steps:
        problems.append(
            f"v4: yaml curriculum_ck.steps_per_iteration {ck_steps} != runner "
            f"num_steps_per_env {runner_steps} (c_k iteration length would lie)"
        )

    # v5: same three-group obs contract (reward-side package only), own yaml
    v5 = LizardRoughTeacherEnvCfg_V5()
    groups = _groups(v5.observations)
    if set(groups) != {"proprio", "extero", "priv"}:
        problems.append(f"v5: expected proprio/extero/priv groups, got {sorted(groups)}")
    else:
        if groups["proprio"] != V3_PROPRIO_ORDER:
            problems.append(f"v5: proprio order {groups['proprio']} != contract")
        if groups["extero"] != V3_EXTERO_ORDER:
            problems.append(f"v5: extero order {groups['extero']} != {V3_EXTERO_ORDER}")
        if groups["priv"] != V3_PRIV_ORDER:
            problems.append(f"v5: priv order {groups['priv']} != contract")

    # v5 recipe wiring: anti-collapse reward package must be complete
    rewards = vars(v5.rewards)
    if "track_lin_vel_xy_exp" in rewards and rewards["track_lin_vel_xy_exp"] is not None:
        problems.append("v5: track_lin_vel_xy_exp should be replaced by track_lin_vel_xy_lin")
    for required in ("track_lin_vel_xy_lin", "feet_slide", "belly_contact_force", "foot_clearance"):
        if rewards.get(required) is None:
            problems.append(f"v5: reward term '{required}' missing")
    if rewards.get("foot_clearance") is not None and not (float(rewards["foot_clearance"].weight) < 0.0):
        problems.append(
            f"v5: foot_clearance.weight {rewards['foot_clearance'].weight} must be negative "
            "(v3/v4 shipped the anti-drag hinge with a REWARD sign)"
        )
    if v5.curriculum.speed_curriculum is not None:
        problems.append("v5: staged speed curriculum should be removed")
    if tuple(v5.commands.base_velocity.ranges.lin_vel_x) != (0.0, 3.0):
        problems.append(f"v5: lin_vel_x range {v5.commands.base_velocity.ranges.lin_vel_x} != (0.0, 3.0)")

    # v5 yaml: ring totals, c_k step consistency, r_fc sign
    with open(_EXP / "versions" / "lizard" / "v5" / "lizard_params.yaml", encoding="utf-8") as f:
        params = yaml.safe_load(f)
    v5y_v3 = params["v3"]
    counts = v5y_v3["foot_ring"]["ring_counts"]
    radii = v5y_v3["foot_ring"]["ring_radii"]
    if len(counts) != len(radii):
        problems.append(f"v5 yaml: ring_counts/radii length mismatch {counts} vs {radii}")
    if sum(counts) * 4 != 208:
        problems.append(f"v5 yaml: ring total {sum(counts)} x 4 feet != 208 extero dims")
    ck_steps = v5y_v3["curriculum_ck"]["steps_per_iteration"]
    runner_steps = LizardTeacherV5PPORunnerCfg().num_steps_per_env
    if ck_steps != runner_steps:
        problems.append(
            f"v5: yaml curriculum_ck.steps_per_iteration {ck_steps} != runner "
            f"num_steps_per_env {runner_steps} (c_k iteration length would lie)"
        )
    if not (float(v5y_v3["r_fc"]["weight"]) < 0.0):
        problems.append("v5 yaml: r_fc.weight must be negative (sign fix)")
    if params["v5"]["commands"]["lin_vel_x"] != [0.0, 3.0]:
        problems.append("v5 yaml: v5.commands.lin_vel_x != [0.0, 3.0]")

    print(f"  teacher versions checked: v1/v2/v3/v4/v5")
    for p in problems:
        print(f"  DRIFT: {p}")
    if problems:
        print(f"OBS_LAYOUT_DRIFT ({len(problems)})")
        return 1
    print("OBS_LAYOUT_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
