"""Full-shape equivalence check: every joint origin in the rotated URDF must
equal R_z(-90) applied to the old asset's origin (not just its norm).

Stronger than check_bone_lengths.py (which proved segment lengths): this pins
the whole skeleton shape, joint by joint, component by component.

Usage: python check_skeleton_equivalence.py <old.urdf> <new.urdf>
"""

import re
import sys

R = ((0.0, 1.0, 0.0), (-1.0, 0.0, 0.0), (0.0, 0.0, 1.0))  # R_z(-90 deg)


def rot(v):
    return tuple(sum(R[i][k] * v[k] for k in range(3)) for i in range(3))


def parse(path):
    text = open(path, encoding="utf-8").read()
    return {m.group(1): tuple(float(x) for x in m.group(2).split())
            for m in re.finditer(r'joint name="([^"]+)"[\s\S]*?origin xyz="([^"]+)"', text)}


old = parse(sys.argv[1])
new = parse(sys.argv[2])
assert set(old) == set(new), "joint sets differ: %s" % (set(old) ^ set(new),)

bad = []
for name in old:
    exp = rot(old[name])
    got = new[name]
    if max(abs(e - g) for e, g in zip(exp, got)) > 1e-9:
        bad.append((name, old[name], exp, got))

print("joints checked: %d" % len(old))
print("non-equivalent origins > 1e-9: %d" % len(bad))
for name, o, e, g in bad[:10]:
    print("  %s old=%s expected(R*old)=%s got=%s" % (name, o, e, g))
if not bad:
    print("SKELETON_EQUIVALENT_UNDER_Rz(-90)")
