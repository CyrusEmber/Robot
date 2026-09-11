# -*- coding: utf-8 -*-
"""Smoke test for the Lizard-Rough-v3 teacher env: three obs groups + v3 wiring.

Thin shell: protocol + expected dims live in teacher_smoke_runner.py
(SMOKE_SPEC["v3"]). Validates end-to-end what check_obs_layout.py asserts
statically: obs groups proprio/extero/priv 90/208/83, extero term order
lf/rf/rl/rr (the network reshape contract), tilt termination + foot_clearance
reward active, all obs/reward finite. PLAY-only contract (v3-era).
"""
from teacher_smoke_runner import main

if __name__ == "__main__":
    raise SystemExit(main("v3"))
