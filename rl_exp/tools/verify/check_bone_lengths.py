"""Compare joint-origin norms (bone lengths) between two lizard URDFs."""
import math
import re
import sys

def parse(path):
    text = open(path, encoding="utf-8").read()
    return [(m.group(1), tuple(float(x) for x in m.group(2).split()))
            for m in re.finditer(r'joint name="([^"]+)"[\s\S]*?origin xyz="([^"]+)"', text)]

old = parse(sys.argv[1])
new = parse(sys.argv[2])
assert len(old) == len(new) and [a for a, _ in old] == [b for b, _ in new], "joint lists differ"
diffs = []
for (name, o), (_, n) in zip(old, new):
    lo = math.sqrt(sum(v * v for v in o))
    ln = math.sqrt(sum(v * v for v in n))
    if abs(lo - ln) > 1e-9:
        diffs.append((name, lo, ln))
print("joints compared: %d" % len(old))
print("bone-length changes > 1e-9: %d" % len(diffs))
for name, lo, ln in diffs[:10]:
    print("  %s old %.9f new %.9f" % (name, lo, ln))
if not diffs:
    print("BONE_LENGTHS_IDENTICAL")
