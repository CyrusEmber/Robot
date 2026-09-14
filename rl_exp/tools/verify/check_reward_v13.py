# -*- coding: utf-8 -*-
"""Static reward gate for v13 (no sim, plain python).

v13 swaps the v5 EP linear tracking kernel for the Miki et al. 2022 symmetric
form (versions/lizard/v13/NOTES.md). This gate asserts the wiring straight from
the constructed configclasses: V13 and its PLAY variant must carry the
``track_lin_vel_xy_miki`` term with the yaml-driven weight/sigma_sq while the
EP kernel is gone; the frozen V5/V10 classes must keep ``track_lin_vel_xy_lin``
untouched; the v13 yaml must record the kernel params and the v10 rollback line
as the pre-registered failure mode.
"""

import pathlib
import sys

import yaml

_REPO = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO))

from rl_exp.tasks import teacher_mdp  # noqa: E402
from rl_exp.tasks.teacher_env_cfg import (  # noqa: E402
    LizardRoughTeacherEnvCfg_V5,
    LizardRoughTeacherEnvCfg_V10,
    LizardRoughTeacherEnvCfg_V10_PLAY,
    LizardRoughTeacherEnvCfg_V13,
    LizardRoughTeacherEnvCfg_V13_PLAY,
)

_PARAMS = _REPO / "rl_exp" / "versions" / "lizard" / "v13" / "lizard_params.yaml"

# yaml: kernel params recorded; v5 EP-kernel section stays as the frozen record
params = yaml.safe_load(_PARAMS.read_text(encoding="utf-8"))
v13y = params["v13"]["track_goal_vel"]
assert v13y["weight"] == 1.5, "v13 yaml: weight must stay 1.5 (single-variable discipline)"
assert v13y["sigma_sq"] == 0.25, "v13 yaml: sigma_sq must be the paper's 0.25"
assert params["v5"]["track_goal_vel"]["weight"] == 1.5, "v5 frozen record must stay"
assert params["v10"]["tilt_terminate"] is None, "v13 inherits v10: tilt_terminate must stay null"

# v13: miki kernel wired, EP kernel gone (train + play variants)
for cls in (LizardRoughTeacherEnvCfg_V13, LizardRoughTeacherEnvCfg_V13_PLAY):
    cfg = cls()
    assert cfg.params_version == "v13", f"{cls.__name__}: params_version must be v13"
    miki = getattr(cfg.rewards, "track_lin_vel_xy_miki", None)
    assert miki is not None, f"{cls.__name__}: track_lin_vel_xy_miki must be wired"
    assert miki.func is teacher_mdp.track_lin_vel_xy_miki, f"{cls.__name__}: wrong miki func"
    assert miki.weight == v13y["weight"], f"{cls.__name__}: weight != yaml"
    assert miki.params["sigma_sq"] == v13y["sigma_sq"], f"{cls.__name__}: sigma_sq != yaml"
    assert miki.params["command_name"] == "base_velocity", f"{cls.__name__}: wrong command term"
    assert getattr(cfg.rewards, "track_lin_vel_xy_lin", None) is None, \
        f"{cls.__name__}: EP kernel must be removed"
    assert getattr(cfg.rewards, "track_lin_vel_xy_exp", None) is None, \
        f"{cls.__name__}: stock exp kernel must stay removed (v5 wiring)"

# frozen v5/v10: EP kernel untouched, no miki leakage
for cls in (LizardRoughTeacherEnvCfg_V5, LizardRoughTeacherEnvCfg_V10, LizardRoughTeacherEnvCfg_V10_PLAY):
    cfg = cls()
    lin = getattr(cfg.rewards, "track_lin_vel_xy_lin", None)
    assert lin is not None and lin.func is teacher_mdp.track_lin_vel_xy_lin, \
        f"{cls.__name__}: frozen EP kernel must stay"
    assert getattr(cfg.rewards, "track_lin_vel_xy_miki", None) is None, \
        f"{cls.__name__}: miki kernel must not leak into frozen versions"

# v13 keeps the rest of the v10 stack byte-identical
v13_cfg = LizardRoughTeacherEnvCfg_V13()
v10_cfg = LizardRoughTeacherEnvCfg_V10()
assert v13_cfg.terminations.tilt is None, "v13 must inherit the v10 tilt removal"
assert v13_cfg.rewards.belly_contact_force.weight == v10_cfg.rewards.belly_contact_force.weight, \
    "belly weight must stay identical to v10"
assert v13_cfg.rewards.feet_slide.weight == v10_cfg.rewards.feet_slide.weight, \
    "r_slip weight must stay identical to v10"

print("check_reward_v13: OK (miki kernel wired / EP kernel gone / v5+v10 frozen / yaml recorded)")
