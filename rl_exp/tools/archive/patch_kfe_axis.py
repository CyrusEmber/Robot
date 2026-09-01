# -*- coding: utf-8 -*-
"""Patch lizard.urdf: kfe joints axis Z->Y and symmetric limits (vertical shank stance)."""

import pathlib
import re

# file lives at rl_exp/tools/archive/ -> exp root is parents[2]
URDF = pathlib.Path(__file__).resolve().parents[2] / "lizard.urdf"
src = URDF.read_text(encoding="utf-8")

changed = 0


def patch(match):
    global changed
    block = match.group(0)
    new = re.sub(r'<axis xyz="[^"]*"/>', '<axis xyz="1 0 0"/>', block)
    new = re.sub(r'lower="-2\.2" upper="0\.2"', 'lower="-1.6" upper="1.6"', new)
    if new != block:
        changed += 1
    return new


out = re.sub(r'<joint name="[^"]*kfe_joint"[^>]*>.*?</joint>', patch, src, flags=re.S)
URDF.write_text(out, encoding="utf-8")
print("PATCHED %d kfe joints" % changed)
