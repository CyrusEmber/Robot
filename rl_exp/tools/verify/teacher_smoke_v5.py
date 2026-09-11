# -*- coding: utf-8 -*-
"""Smoke test for the Lizard-Rough-v5 teacher env: three obs groups + v5 wiring.

Thin shell: protocol + expected dims live in teacher_smoke_runner.py
(SMOKE_SPEC["v5"]). PLAY (90/208/83 + v5 anti-collapse reward set active, exp
tracking retired, no speed curriculum, no SIR) + TRAIN 2env (SIR against the
REAL terrain importer, origins re-pointed inside the 10x20 grid,
Curriculum/terrain_levels finite).
"""
from teacher_smoke_runner import main

if __name__ == "__main__":
    raise SystemExit(main("v5"))
