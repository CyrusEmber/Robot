# -*- coding: utf-8 -*-
"""Static gate for the v14.4 fall handling (no sim: plain python + torch).

v14.4 keeps exactly one termination (versions/lizard/v14/NOTES.md):
  * roll-over -- the ZYX roll of the **base quaternion** past ``roll_limit_deg``,
    held for ``dwell_s``, with a nose-vertical guard;
and head load-bearing moved off the termination side onto the per-step
``head_load_penalty`` reward (proportional to the vertical contact force through
the neck chain: no threshold, no attitude gate).

This gate checks (a) the predicate on synthetic attitudes built from ZYX angles
-- both sides, the mixed pitch+roll pose gravity under-read, the monotone past
vertical band and the belly-up end, pure yaw / pure pitch silence, and the
pitch-guard window; (b) the invariant the eval note leans on, swept over a grid
and computed the *other* way (gravity): gate => tilt >= roll limit > 40 deg;
(c) the dwell counter (accumulate / clear / reset); (d) the penalty's arithmetic
(sign, vertical-only, proportional); (e) the wiring straight from the constructed
configclasses (V14/PLAY carry both terms while the v10 tilt removal and time_out
survive; v13 stays frozen); (f) the yaml records the knobs.
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

from isaaclab.utils.math import quat_apply_inverse, quat_from_euler_xyz  # noqa: E402

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
assert roll["pitch_guard_deg"] == 80.0, "v14 yaml: pitch_guard_deg must stay 80"
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
PITCH_GUARD = roll["pitch_guard_deg"]
_UP = torch.tensor([[0.0, 0.0, -1.0]])


def _quat(roll_deg: float, pitch_deg: float = 0.0, yaw_deg: float = 0.0) -> torch.Tensor:
    """Base attitude from ZYX angles [deg], shape (1, 4) as (w, x, y, z)."""
    return quat_from_euler_xyz(
        torch.tensor([math.radians(roll_deg)]),
        torch.tensor([math.radians(pitch_deg)]),
        torch.tensor([math.radians(yaw_deg)]),
    )


def _over(q: torch.Tensor) -> bool:
    return bool(teacher_mdp.roll_over_trigger(q, R_LIM, PITCH_GUARD).item())


def _tilt_deg(q: torch.Tensor) -> float:
    """Total tilt off upright [deg], read back through gravity (independent route)."""
    pg_z = float(quat_apply_inverse(q, _UP)[0, 2])
    return math.degrees(math.acos(min(1.0, max(-1.0, -pg_z))))


assert not _over(_quat(0.0)), "upright must not fire"
assert not _over(_quat(60.0)), "roll 60 deg is inside the 70 deg limit"
for sign in (1.0, -1.0):
    assert _over(_quat(sign * 80.0)), f"roll {80.0 * sign:+.0f} deg must fire (both sides)"
# the pose the gravity form under-read: |pg_b.y| = sin(80) cos(30) = sin(58)
assert not _over(_quat(60.0, 30.0)), "pitch 30 + roll 60 is inside the limit"
assert _over(_quat(80.0, 30.0)), "pitch 30 + roll 80 must fire (raw |pg_b.y| read it as 58)"
assert _over(_quat(80.0, -30.0)), "the same mixed pose nose-up must fire too"
# monotone over the whole turn: the gravity form released everything past 110 deg
for r in (90.0, 110.0, 120.0, 150.0, 180.0, -120.0):
    assert _over(_quat(r)), f"roll {r:+.0f} deg must fire (monotone, past vertical included)"
# belly-up reached by a nose-over reads roll 180 in ZYX -> inside the gate
assert _over(_quat(0.0, 180.0)), "back-down must fire from v14.4 on (downed = crash)"
# what must stay silent: heading changes and pitch alone
for yaw in (0.0, 45.0, 90.0, 180.0, -90.0):
    assert not _over(_quat(0.0, 0.0, yaw)), f"pure yaw {yaw:+.0f} deg must not fire"
for pitch in (-60.0, -40.0, 40.0, 60.0):
    assert not _over(_quat(0.0, pitch)), f"pure pitch {pitch:+.0f} deg must not fire"
# nose-vertical window: ZYX is singular there, so the guard silences it
assert not _over(_quat(0.0, 90.0)), "nose-vertical alone must not fire"
assert not _over(_quat(100.0, 85.0)), "roll inside the pitch-guard window must not fire"

# --- the invariant the eval note leans on: gate => tilt >= limit > harness 40 deg ---
_fired = 0
for r_deg in range(-170, 180, 10):
    for p_deg in (-80.0, -50.0, -20.0, 0.0, 20.0, 50.0, 80.0):
        q = _quat(float(r_deg), p_deg)
        if not _over(q):
            continue
        _fired += 1
        tilt = _tilt_deg(q)
        assert tilt >= R_LIM - 1e-3, \
            f"gate fired at roll {r_deg} pitch {p_deg} but tilt is only {tilt:.1f} deg"
assert _fired > 0, "the invariant sweep fired nothing -- it is not covering anything"

# --- dwell counter (stub env: no sim, no scene) ---
_STEP_DT = 0.02
_DWELL_STEPS = int(round(roll["dwell_s"] / _STEP_DT))
_SIDE = _quat(80.0)
_qbuf = _quat(0.0)
_stub = types.SimpleNamespace(
    scene={"robot": types.SimpleNamespace(
        data=types.SimpleNamespace(root_quat_w=types.SimpleNamespace(torch=_qbuf)),
        device=_qbuf.device,
    )},
    step_dt=_STEP_DT, num_envs=1,
)
_term = teacher_mdp.RollOverTerm(cfg=types.SimpleNamespace(params={}), env=_stub)


def _run(q: torch.Tensor, steps: int) -> list[bool]:
    """Feed one attitude ``steps`` times; the term reads the shared buffer."""
    _qbuf.copy_(q)
    return [bool(_term(env=_stub, roll_limit_deg=R_LIM, pitch_guard_deg=PITCH_GUARD,
                       dwell_s=roll["dwell_s"]).item())
            for _ in range(steps)]


assert _run(_SIDE, _DWELL_STEPS - 1) == [False] * (_DWELL_STEPS - 1), \
    f"dwell must hold off for the first {_DWELL_STEPS - 1} steps"
assert _run(_SIDE, 1) == [True], f"dwell must fire on step {_DWELL_STEPS}"
assert _run(_quat(0.0), 1) == [False], "the counter must clear when the condition clears"
assert _run(_SIDE, _DWELL_STEPS - 1) == [False] * (_DWELL_STEPS - 1), \
    "a cleared counter must restart from zero"
_term.reset()
assert _run(_SIDE, 1) == [False], "reset() must zero the dwell counter"

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
    assert term.params["pitch_guard_deg"] == roll["pitch_guard_deg"], "pitch guard != yaml"
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

print("check_terminations_v14: OK (quaternion roll, monotone past vertical / pitch-guard window / "
      "gate => tilt >= limit sweep / dwell / head-load penalty arithmetic / both terms wired / "
      "v10 tilt removal kept / v13 frozen / yaml)")
