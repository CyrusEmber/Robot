# -*- coding: utf-8 -*-
"""Static termination gate for v14 (no sim: plain python + torch).

v14 gates the two poses worth cutting (versions/lizard/v14/NOTES.md):
  * front plant -- nose-down past ``pitch_down_limit_deg`` AND head contact
    past ``head_contact_n`` (a nose-down attitude alone must NOT fire);
  * roll-over -- ``|pg_b.y|`` past ``roll_limit_deg`` (gravity direction);
each sustained for ``dwell_s``. This gate checks (a) the predicate on synthetic
gravity vectors and head forces -- 前栽 alone, nose-up, the v3 slope-crossing
false positive, both roll directions; (b) the dwell counter's
accumulate/clear/reset semantics on a stub env; (c) the wiring straight from the
constructed configclasses (V14/PLAY carry the term while the v10 tilt removal
and time_out survive); (d) v13 stays frozen; (e) the yaml records the knobs.
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
gate = params["v14"]["fall_gate"]
assert gate["pitch_down_limit_deg"] == 45.0, "v14 yaml: pitch_down_limit_deg must stay 45"
assert gate["head_contact_n"] == 10.0, "v14 yaml: head_contact_n must stay 10 N"
assert gate["head_body_names"] == [".*neck.*"], "v14 yaml: head_body_names must stay the neck chain"
assert gate["roll_limit_deg"] == 70.0, "v14 yaml: roll_limit_deg must stay 70"
assert gate["dwell_s"] == 0.5, "v14 yaml: dwell_s must stay 0.5"
# the carried v13/v10 sections stay frozen (single-variable discipline)
assert params["v13"]["track_goal_vel"]["weight"] == 1.5, "v13 kernel record must stay (weight)"
assert params["v13"]["track_goal_vel"]["sigma_sq"] == 0.25, "v13 kernel record must stay (sigma_sq)"
assert params["v10"]["tilt_terminate"] is None, "v14 inherits v10: tilt_terminate must stay null"

# --- predicate: front plant needs BOTH nose-down and head contact; nose-UP never fires ---
P_LIM, H_N, R_LIM = gate["pitch_down_limit_deg"], gate["head_contact_n"], gate["roll_limit_deg"]


def _pg(x: float, y: float, z: float) -> torch.Tensor:
    return torch.tensor([[x, y, z]], dtype=torch.float32)


def _f(newton: float) -> torch.Tensor:
    return torch.tensor([[[0.0, 0.0, newton]]], dtype=torch.float32)  # (N, bodies, 3)


def _over(pg: torch.Tensor, newton: float) -> bool:
    return bool(teacher_mdp.head_plant_or_roll_trigger(pg, _f(newton).norm(dim=-1).amax(dim=1),
                                                       P_LIM, H_N, R_LIM).item())


_UPRIGHT = _pg(0.0, 0.0, -1.0)
assert not _over(_UPRIGHT, 0.0), "upright, no head contact"
assert not _over(_UPRIGHT, 400.0), "head resting flat with no nose-down attitude"
assert not _over(_pg(math.sin(math.radians(80.0)), 0.0, -0.17), 0.0), \
    "nose-down alone must not fire (v14.1: head contact is required)"
assert not _over(_pg(math.sin(math.radians(20.0)), 0.0, -0.94), 400.0), \
    "head contact with only a 20 deg nose-down attitude is inside the 45 deg limit"
assert _over(_pg(math.sin(math.radians(60.0)), 0.0, -0.5), 50.0), \
    "nose-down 60 deg WITH head contact must fire (hind feet up, head planted)"
assert not _over(_pg(-math.sin(math.radians(90.0)), 0.0, 0.0), 400.0), \
    "nose-UP 90 deg must not fire (the pose the v3 total-tilt gate killed as a fall)"
assert not _over(_pg(-math.sin(math.radians(40.0)), math.sin(math.radians(26.0)), -0.6), 5.0), \
    "26 deg slope crossing, 40 deg nose-up, light contact must not fire"
assert not _over(_pg(0.0, math.sin(math.radians(60.0)), -0.5), 0.0), \
    "roll 60 deg is inside the 70 deg limit"
for sign in (1.0, -1.0):
    assert _over(_pg(0.0, sign * math.sin(math.radians(80.0)), -0.17), 0.0), \
        f"roll {80.0 * sign:+.0f} deg must fire (both side falls, gravity direction)"

# --- dwell counter (stub env: no sim, no scene) ---
_STEP_DT = 0.02
_DWELL_STEPS = int(round(gate["dwell_s"] / _STEP_DT))
_PLANTED_PG = _pg(math.sin(math.radians(60.0)), 0.0, -0.5)


def _stub_env(pg_buf: torch.Tensor, force_buf: torch.Tensor):
    robot = types.SimpleNamespace(
        data=types.SimpleNamespace(projected_gravity_b=types.SimpleNamespace(torch=pg_buf)),
        device=pg_buf.device,
        find_bodies=lambda keys, preserve_order=False: ([0], ["neck_pitch"]),
    )
    contact = types.SimpleNamespace(
        data=types.SimpleNamespace(net_forces_w=types.SimpleNamespace(torch=force_buf))
    )
    return types.SimpleNamespace(scene={"robot": robot, "contact_forces": contact},
                                 step_dt=_STEP_DT, num_envs=pg_buf.shape[0])


_pg_buf = _UPRIGHT.clone()
_f_buf = _f(0.0).clone()
_env = _stub_env(_pg_buf, _f_buf)
_cfg = types.SimpleNamespace(params={"head_body_names": gate["head_body_names"]})
_term = teacher_mdp.HeadPlantRollTerm(cfg=_cfg, env=_env)
assert _term._head_ids == [0], "head bodies must resolve from head_body_names at construction"


def _run(rows: list[tuple[torch.Tensor, float]]) -> list[bool]:
    """Feed (gravity, head force) rows through the term one step at a time.

    The term reads the buffers captured at construction, so rows are copied
    INTO those buffers in place.
    """
    out = []
    for pg, newton in rows:
        _pg_buf.copy_(pg)
        _f_buf.copy_(_f(newton))
        out.append(bool(_term(env=_env, pitch_down_limit_deg=P_LIM, head_contact_n=H_N,
                              head_body_names=tuple(gate["head_body_names"]),
                              roll_limit_deg=R_LIM, dwell_s=gate["dwell_s"]).item()))
    return out


_PLANT = (_PLANTED_PG, 50.0)
assert _run([_PLANT] * (_DWELL_STEPS - 1)) == [False] * (_DWELL_STEPS - 1), \
    f"dwell must hold off for the first {_DWELL_STEPS - 1} steps"
assert _run([_PLANT]) == [True], f"dwell must fire on step {_DWELL_STEPS}"
assert _run([(_UPRIGHT, 0.0)]) == [False], "the counter must clear when the condition clears"
assert _run([(_PLANTED_PG, 5.0)] * (_DWELL_STEPS - 1)) == [False] * (_DWELL_STEPS - 1), \
    "nose-down with only light head contact must never accumulate"
assert _run([(_PLANTED_PG, 50.0)] * (_DWELL_STEPS - 1)) == [False] * (_DWELL_STEPS - 1), \
    "a cleared counter must restart from zero"
_term.reset()
assert _run([(_PLANTED_PG, 50.0)]) == [False], "reset() must zero the dwell counter"

# --- wiring ---
for cls in (LizardRoughTeacherEnvCfg_V14, LizardRoughTeacherEnvCfg_V14_PLAY):
    cfg = cls()
    assert cfg.params_version == "v14", f"{cls.__name__}: params_version must be v14"
    term = getattr(cfg.terminations, "head_plant_roll", None)
    assert term is not None, f"{cls.__name__}: head_plant_roll must be wired"
    assert term.func is teacher_mdp.HeadPlantRollTerm, f"{cls.__name__}: wrong gate class"
    assert term.params["pitch_down_limit_deg"] == gate["pitch_down_limit_deg"], "pitch limit != yaml"
    assert term.params["head_contact_n"] == gate["head_contact_n"], "head contact N != yaml"
    assert list(term.params["head_body_names"]) == gate["head_body_names"], "head bodies != yaml"
    assert term.params["roll_limit_deg"] == gate["roll_limit_deg"], "roll limit != yaml"
    assert term.params["dwell_s"] == gate["dwell_s"], "dwell != yaml"
    # the manager validates cfg.params against __call__ at construction; do it here
    args = set(inspect.signature(teacher_mdp.HeadPlantRollTerm.__call__).parameters)
    assert set(term.params) <= (args - {"self", "env"}), \
        f"{cls.__name__}: params {set(term.params)} not accepted by __call__"
    assert cfg.terminations.tilt is None, f"{cls.__name__}: the v10 tilt removal must survive"
    assert cfg.terminations.time_out is not None, f"{cls.__name__}: time_out must stay"

# --- v13 stays frozen ---
for cls in (LizardRoughTeacherEnvCfg_V13, LizardRoughTeacherEnvCfg_V13_PLAY):
    cfg = cls()
    assert getattr(cfg.terminations, "head_plant_roll", None) is None, \
        f"{cls.__name__}: the v14 gate must not leak into v13"
    assert cfg.terminations.tilt is None, f"{cls.__name__}: v13 must keep the v10 tilt removal"

print("check_terminations_v14: OK (front plant = nose-down + head contact / roll over gravity / "
      "dwell accumulate+clear+reset / gate wired / v10 tilt removal kept / v13 frozen / yaml)")
