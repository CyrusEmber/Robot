# -*- coding: utf-8 -*-
"""Bake the natural lizard stance into lizard.urdf as the ZERO pose (v2).

Zero pose = thigh sprawled out-down, shank vertical, blade flat.
Key insight: joint origin xyz values (parent-relative offsets along the chain)
are INVARIANT under baking rotations into rpy -- only rpy, axes and kfe limits
change. Per side s (+1 right / -1 left), THETA = thigh splay:

* haa origin rpy = (0, s*THETA, 0)            axis "0 1 0" (world-Y lift)
* hfe origin rpy = (0, s*(pi/2-THETA), 0)     axis "-s 0 0" (world-Z stride)
* kfe origin rpy = 0                          axis "0 1 0" (world-Y shank fold), limits +-1.6
* foot origin rpy = shank-relative constant    axis "0 0 1" (world-X blade pitch)
  (plate normal local-X maps to world -Z = blade lying FLAT on the ground;
  constant w.r.t. the shank frame, so the blade follows the shank):
  right legs rpy = 0, left legs rpy = (0, pi, 0)
"""

import math
import pathlib
import re

URDF = pathlib.Path(__file__).resolve().parent / "lizard.urdf"
THETA = 0.35
FOLD = math.pi / 2 - THETA

src = URDF.read_text(encoding="utf-8")

changed = 0
for leg in ("lf", "rf", "rl", "rr"):
    s = 1.0 if leg[0] == "r" else -1.0
    plan = {
        "%s_haa_joint" % leg: ((0.0, s * THETA, 0.0), (0.0, 1.0, 0.0), None),
        "%s_hfe_joint" % leg: ((0.0, s * FOLD, 0.0), (-s, 0.0, 0.0), None),
        "%s_kfe_joint" % leg: ((0.0, 0.0, 0.0), (0.0, 1.0, 0.0), ("-1.6", "1.6")),
        "%s_foot_joint" % leg: ((0.0, math.pi, 0.0) if s < 0 else (0.0, 0.0, 0.0), (0.0, 0.0, 1.0), None),
    }
    for name, (rpy, axis, limits) in plan.items():
        pattern = r'(<joint name="%s"[^>]*>.*?</joint>)' % re.escape(name)
        match = re.search(pattern, src, flags=re.S)
        if match is None:
            raise ValueError("joint not found: %s" % name)
        block = match.group(1)
        new_block = re.sub(
            r'<origin xyz="([^"]+)" rpy="[^"]*"/>',
            lambda m: '<origin xyz="%s" rpy="%.6f %.6f %.6f"/>' % (m.group(1), *rpy),
            block,
            count=1,
        )
        new_block = re.sub(
            r'<axis xyz="[^"]*"/>',
            '<axis xyz="%.6f %.6f %.6f"/>' % axis,
            new_block,
            count=1,
        )
        if limits is not None:
            new_block = re.sub(
                r'lower="[-\d.]+" upper="[-\d.]+"',
                'lower="%s" upper="%s"' % limits,
                new_block,
                count=1,
            )
        src = src.replace(block, new_block)
        changed += 1

URDF.write_text(src, encoding="utf-8")
print("STANCE_V2_PATCHED %d joints" % changed)
