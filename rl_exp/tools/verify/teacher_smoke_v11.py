# -*- coding: utf-8 -*-
"""Smoke test for the Lizard-Rough-v11 teacher env: obs groups + joint SIR wiring.

Thin shell: protocol + expected dims live in teacher_smoke_runner.py
(SMOKE_SPEC["v11"]). v11 = v10 recipe (tilt termination removed, only
time_out) + the joint particle terrain curriculum: PLAY drops joint SIR and
ParticleVelocityCommand falls back to the (0, 3) uniform range sample; TRAIN
swaps in the param-sampled terrain grid (4 x 120, one sub-terrain per
parameter combination) + the joint_sir term; commands come from the
particle's velocity bucket (+- jitter, via train_extras).
"""
from teacher_smoke_runner import main

if __name__ == "__main__":
    raise SystemExit(main("v11"))
