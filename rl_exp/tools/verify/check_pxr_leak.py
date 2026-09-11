# -*- coding: utf-8 -*-
"""P001/P003 gate: the task cfg import chain must stay pxr-clean (no sim).

Task cfg modules are imported during hydra compose, BEFORE AppLauncher starts
Kit. If that import chain drags pip usd-core pxr (site-packages/pxr) into
sys.modules, Kit boots with two mismatched USD builds sharing the same version
tag and dies with "No to_python (by-value) converter found" (P001:
omni.kit.usd.mdl TfNotice wrapper; P003: omni.physx UsdTimeCode/GfVec3f).
Run this after ANY change to env cfg / mdp module imports; it is part of
run_offline_checks.bat.

Usage: python check_pxr_leak.py
"""

import sys

import rl_exp.tasks.agents.rsl_rl_ppo_cfg  # noqa: F401  (composed alongside env cfg)
import rl_exp.tasks.lizard_env_cfg  # noqa: F401
import rl_exp.tasks.teacher_env_cfg  # noqa: F401

leaked = sorted(m for m in sys.modules if m == "pxr" or m.startswith("pxr."))
if leaked:
    print(f"check_pxr_leak: FAIL -- pxr imported pre-kit by the task cfg chain: {leaked[:5]}")
    print("Hint: see pitfalls.md P001/P003 -- move the class-module import into a lazy")
    print("factory or a string class_type; the commands_cfg module is the clean one.")
    sys.exit(1)

print("check_pxr_leak: OK (task cfg import chain is pxr-clean)")
