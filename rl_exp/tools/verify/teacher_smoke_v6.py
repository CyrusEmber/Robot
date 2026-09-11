# -*- coding: utf-8 -*-
"""Smoke test for the Lizard-Rough-v6 teacher env: three obs groups + v6 wiring.

Thin shell: protocol + expected dims live in teacher_smoke_runner.py
(SMOKE_SPEC["v6"]). v6 = v5 recipe on the axis-corrected asset (head +X),
v6.1 spine unlock riding the yaml spine_scale 0.25. PLAY + TRAIN SIR contract
identical to v5.
"""
from teacher_smoke_runner import main

if __name__ == "__main__":
    raise SystemExit(main("v6"))
