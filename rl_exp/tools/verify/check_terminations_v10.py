# -*- coding: utf-8 -*-
"""Static termination gate for v10 (no sim, plain python).

v10 deleted the tilt termination (false-positive pitch kills: 0.60 of episodes
in v8.1, 0.76 in v6 -- see versions/lizard/v10/NOTES.md). This gate asserts the
wiring straight from the constructed configclasses: V10 and its PLAY variant
must have NO tilt term while time_out survives; the frozen V8 classes must keep
their tilt term untouched; the v10 yaml must record the removal as a null knob
and keep the v3 section as the frozen record.
"""

import pathlib
import sys

import yaml

_REPO = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO))

from rl_exp.tasks.teacher_env_cfg import (  # noqa: E402
    LizardRoughTeacherEnvCfg_V8,
    LizardRoughTeacherEnvCfg_V8_PLAY,
    LizardRoughTeacherEnvCfg_V10,
    LizardRoughTeacherEnvCfg_V10_PLAY,
)

_PARAMS = _REPO / "rl_exp" / "versions" / "lizard" / "v10" / "lizard_params.yaml"

# yaml: removal recorded as a null knob; v3 frozen record intact
params = yaml.safe_load(_PARAMS.read_text(encoding="utf-8"))
assert params["v10"]["tilt_terminate"] is None, "v10 yaml must record tilt_terminate: null"
assert params["v3"]["tilt_terminate"]["gravity_z_limit"] == -0.6, "v3 frozen record must stay"

# v10: tilt gone, time_out alive (train + play variants)
for cls in (LizardRoughTeacherEnvCfg_V10, LizardRoughTeacherEnvCfg_V10_PLAY):
    cfg = cls()
    assert cfg.params_version == "v10", f"{cls.__name__}: params_version must be v10"
    assert cfg.terminations.tilt is None, f"{cls.__name__}: tilt term must be deleted"
    assert cfg.terminations.time_out is not None, f"{cls.__name__}: time_out must stay"

# v8: frozen recipe untouched
for cls in (LizardRoughTeacherEnvCfg_V8, LizardRoughTeacherEnvCfg_V8_PLAY):
    cfg = cls()
    assert cfg.terminations.tilt is not None, f"{cls.__name__}: frozen v8 tilt must stay"

print("check_terminations_v10: OK (v10 tilt deleted / time_out alive / v8 frozen / yaml null knob)")
