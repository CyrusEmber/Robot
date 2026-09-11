# -*- coding: utf-8 -*-
"""Smoke test for the Lizard-Rough-v8 teacher env: three obs groups + v8 wiring.

Thin shell: protocol + expected dims live in teacher_smoke_runner.py
(SMOKE_SPEC["v8"]). v8 = v6.2 recipe on the anatomy-correct asset (sphere
head +X, joints renamed chest/neck/tail1-3, legs swapped to anatomy). Same
contract as v6: PLAY (90/208/83 + v5 anti-collapse reward set + spine scale
0.25) + TRAIN 2env (SIR against the REAL terrain importer, 10x20 grid).
"""
from teacher_smoke_runner import main

if __name__ == "__main__":
    raise SystemExit(main("v8"))
