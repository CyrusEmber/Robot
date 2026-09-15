# -*- coding: utf-8 -*-
"""Static gate for the v14.3 fall handling (no sim: plain python + torch).

v14.3 keeps exactly one termination (versions/lizard/v14/NOTES.md):
  * roll-over -- pitch-invariant ``|sin(roll)|`` past ``roll_limit_deg``, held
    for ``dwell_s``;
and head load-bearing moved off the termination side onto the per-step
``head_load_penalty`` reward (proportional to the vertical contact force through
the neck chain: no threshold, no attitude gate).

This gate checks (a) the predicate on synthetic gravity vectors -- the
pitch+roll mix the raw ``|pg_b.y|`` test missed, both roll directions, the roll
band's upper edge, nose-up/nose-down and the v3 slope-crossing false positive;
(b) the dwell counter (accumulate / clear / reset); (c) the penalty's arithmetic
(sign, vertical-only, proportional); (d) the wiring straight from the
constructed configclasses (V14/PLAY carry both terms while the v10 tilt removal
and time_out survive; v13 stays frozen); (e) the yaml records the knobs.
"""

import inspect
import math
import pathlib
import sys
import types

import torch
import yaml

_REPO = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO))

from rl_exp.tasks import teacher_mdp  # noqa: E402
from rl_exp.tasks.teacher_env_cfg import (  # noqa: E402
    LizardRoughTeacherEnvCfg_V13,
    LizardRoughTeacherEnvCfg_V13_PLAY,
    LizardRoughTeacherEnvCfg_V14,
    LizardRoughTeacherEnvCfg_V14_PLAY,
)

_PARAMS = _REPO / "rl_exp" / "versions" / "lizard" / "v14" / "lizard_params.yaml"
params = yaml.safe_load(_PARAMS.read_text(encoding="utf-8"))
v14 = params["v14"]
roll, head = v14["roll_over"], v14["head_load"]

assert roll["roll_limit_deg"] == 70.0, "v14 yaml: roll_limit_deg must stay 70"
assert roll["dwell_s"] == 0.5, "v14 yaml: dwell_s must stay 0.5"
assert head["weight"] == -1.0, "v14 yaml: head-load weight must stay negative"
assert head["force_scale"] == 706.0, "v14 yaml: force_scale must stay the nominal body weight"
assert head["head_body_names"] == [".*neck.*"], "v14 yaml: head_body_names must stay the neck chain"
assert "fall_gate" not in v14, "v14 yaml: the front-plant gate must be gone (v14.3)"
# the carried v13/v10 sections stay frozen (single-variable discipline)
assert params["v13"]["track_goal_vel"]["weight"] == 1.5, "v13 kernel record must stay (weight)"
assert params["v13"]["track_goal_vel"]["sigma_sq"] == 0.25, "v13 kernel record must stay (sigma_sq)"
assert params["v10"]["tilt_terminate"] is None, "v14 inherits v10: tilt_terminate must stay null"

R_LIM = roll["roll_limit_deg"]


def _pitch_roll(pitch_deg: float, roll_deg: float) -> torch.Tensor:
    """projected_gravity_b for a base pitched (nose-down +) then rolled [deg]."""
    p, r = math.radians(pitch_deg), math.radians(roll_deg)
    return torch.tensor([[math.sin(p), -math.sin(r) * math.cos(p), -math.cos(r) * math.cos(p)]])


def _over(pg: torch.Tensor) -> bool:
    return bool(teacher_mdp.roll_over_trigger(pg, R_LIM).item())


assert not _over(_pitch_roll(0.0, 0.0)), "upright must not fire"
assert not _over(_pitch_roll(0.0, 60.0)), "roll 60 deg is inside the 70 deg limit"
for sign in (1.0, -1.0):
    assert _over(_pitch_roll(0.0, sign * 80.0)), f"roll {80.0 * sign:+.0f} deg must fire (both sides)"
# the regression the pitch-invariant form fixes: |pg_b.y| alone reads this as 60 deg
assert not _over(_pitch_roll(30.0, 60.0)), "pitch 30 + roll 60 is inside the limit"
assert _over(_pitch_roll(30.0, 80.0)), "pitch 30 + roll 80 must fire (raw |pg_b.y| read it as 60)"
assert _over(_pitch_roll(0.0, 90.0)), "90 deg roll (on its side) must fire"
assert _over(_pitch_roll(0.0, 100.0)), "100 deg roll must fire (the band's upper half)"
# documented ceiling: past 110 deg |sin(roll)| shrinks again and the pose is
# indistinguishable from a back-down fall, which stays un-gated on purpose
assert not _over(_pitch_roll(0.0, 120.0)), "past 110 deg roll leaves the band (deliberate)"
# poses that must never fire: the v3 gate's false positives, and the un-gated family
assert not _over(_pitch_roll(-90.0, 0.0)), "nose-up 90 deg must not fire"
assert not _over(_pitch_roll(60.0, 0.0)), "nose-down 60 deg alone is no longer a termination"
assert not _over(_pitch_roll(-40.0, 26.0)), "26 deg slope crossing, 40 deg nose-up must not fire"

# --- dwell counter (stub env: no sim, no scene) ---
_STEP_DT = 0.02
_DWELL_STEPS = int(round(roll["dwell_s"] / _STEP_DT))
_SIDE_PG = _pitch_roll(0.0, 80.0)
_pg_buf = _pitch_roll(0.0, 0.0).clone()
_stub = types.SimpleNamespace(
    scene={"robot": types.SimpleNamespace(
        data=types.SimpleNamespace(projected_gravity_b=types.SimpleNamespace(torch=_pg_buf)),
        device=_pg_buf.device,
    )},
    step_dt=_STEP_DT, num_envs=1,
)
_term = teacher_mdp.RollOverTerm(cfg=types.SimpleNamespace(params={}), env=_stub)


def _run(pg: torch.Tensor, steps: int) -> list[bool]:
    """Feed one gravity vector ``steps`` times; the term reads the shared buffer."""
    _pg_buf.copy_(pg)
    return [bool(_term(env=_stub, roll_limit_deg=R_LIM, dwell_s=roll["dwell_s"]).item())
            for _ in range(steps)]


assert _run(_SIDE_PG, _DWELL_STEPS - 1) == [False] * (_DWELL_STEPS - 1), \
    f"dwell must hold off for the first {_DWELL_STEPS - 1} steps"
assert _run(_SIDE_PG, 1) == [True], f"dwell must fire on step {_DWELL_STEPS}"
assert _run(_pitch_roll(0.0, 0.0), 1) == [False], "the counter must clear when the condition clears"
assert _run(_SIDE_PG, _DWELL_STEPS - 1) == [False] * (_DWELL_STEPS - 1), \
    "a cleared counter must restart from zero"
_term.reset()
assert _run(_SIDE_PG, 1) == [False], "reset() must zero the dwell counter"

# --- penalty arithmetic: vertical only, clamped at zero, proportional ---
_num_bodies, _scale = 2, head["force_scale"]
_force_buf = torch.zeros(1, _num_bodies, 3)
_pen_env = types.SimpleNamespace(
    scene=types.SimpleNamespace(sensors={"contact_forces": types.SimpleNamespace(
        data=types.SimpleNamespace(net_forces_w=types.SimpleNamespace(torch=_force_buf)))}),
)
_sensor_cfg = types.SimpleNamespace(name="contact_forces", body_ids=[0, 1])


def _pen(rows: list[tuple[float, float, float]]) -> float:
    _force_buf.copy_(torch.tensor([rows], dtype=torch.float32))
    return float(teacher_mdp.head_load_penalty(_pen_env, _sensor_cfg, _scale).item())


assert _pen([(0.0, 0.0, 0.0), (0.0, 0.0, 0.0)]) == 0.0, "no contact -> no penalty"
assert abs(_pen([(0.0, 0.0, 100.0), (0.0, 0.0, 0.0)]) - 100.0 / _scale) < 1e-6, \
    "penalty = vertical / weight"
assert abs(_pen([(0.0, 0.0, 50.0), (0.0, 0.0, 50.0)]) - 100.0 / _scale) < 1e-6, \
    "head-chain bodies sum"
assert _pen([(300.0, 0.0, 0.0), (0.0, 300.0, 0.0)]) == 0.0, "lateral force transfers no weight"
assert _pen([(0.0, 0.0, -100.0), (0.0, 0.0, 0.0)]) == 0.0, "downward (non-reaction) reads 0"
assert _pen([(0.0, 0.0, 20.0), (0.0, 0.0, 0.0)]) < _pen([(0.0, 0.0, 200.0), (0.0, 0.0, 0.0)]), \
    "penalty must grow with the force (no dead zone)"

# --- wiring ---
for cls in (LizardRoughTeacherEnvCfg_V14, LizardRoughTeacherEnvCfg_V14_PLAY):
    cfg = cls()
    assert cfg.params_version == "v14", f"{cls.__name__}: params_version must be v14"
    term = getattr(cfg.terminations, "roll_over", None)
    assert term is not None, f"{cls.__name__}: roll_over must be wired"
    assert term.func is teacher_mdp.RollOverTerm, f"{cls.__name__}: wrong gate class"
    assert getattr(cfg.terminations, "head_plant_roll", None) is None, \
        f"{cls.__name__}: the front-plant gate must not survive (v14.3)"
    assert term.params["roll_limit_deg"] == roll["roll_limit_deg"], "roll limit != yaml"
    assert term.params["dwell_s"] == roll["dwell_s"], "dwell != yaml"
    pen = getattr(cfg.rewards, "head_load_penalty", None)
    assert pen is not None, f"{cls.__name__}: head_load_penalty must be wired"
    assert pen.func is teacher_mdp.head_load_penalty, f"{cls.__name__}: wrong penalty func"
    assert pen.weight == head["weight"], "penalty weight != yaml"
    assert pen.params["force_scale"] == head["force_scale"], "force_scale != yaml"
    assert list(pen.params["sensor_cfg"].body_names) == head["head_body_names"], "head bodies != yaml"
    # the manager validates term params against __call__ at construction; do it here
    for cfg_term, fn in ((term, teacher_mdp.RollOverTerm), (pen, teacher_mdp.head_load_penalty)):
        args = set(inspect.signature(fn.__call__ if isinstance(fn, type) else fn).parameters)
        assert set(cfg_term.params) <= (args - {"self", "env"}), \
            f"{cls.__name__}: params {set(cfg_term.params)} not accepted by {fn.__name__}"
    assert cfg.terminations.tilt is None, f"{cls.__name__}: the v10 tilt removal must survive"
    assert cfg.terminations.time_out is not None, f"{cls.__name__}: time_out must stay"

# --- v13 stays frozen ---
for cls in (LizardRoughTeacherEnvCfg_V13, LizardRoughTeacherEnvCfg_V13_PLAY):
    cfg = cls()
    assert getattr(cfg.terminations, "roll_over", None) is None, \
        f"{cls.__name__}: the v14 gate must not leak into v13"
    assert getattr(cfg.rewards, "head_load_penalty", None) is None, \
        f"{cls.__name__}: the v14 penalty must not leak into v13"
    assert cfg.terminations.tilt is None, f"{cls.__name__}: v13 must keep the v10 tilt removal"

print("check_terminations_v14: OK (roll band + pitch-invariant form + dwell / head-load penalty "
      "arithmetic / both terms wired / v10 tilt removal kept / v13 frozen / yaml)")
