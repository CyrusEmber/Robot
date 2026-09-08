# -*- coding: utf-8 -*-
"""One-shot v8 joint-name migration across every lizard_params.yaml.

v8 renamed the 26 joints to real anatomy (see blender/rename_flip_v8.py):
the "neck1-3" chain was the tail (antenna tip), the "tail_yaw/tail_pitch"
chain carried the sphere HEAD, and the leg names were front/rear + left/right
swapped. This applies the same map to every yaml's joint_order and the two
spine regex patterns that no longer match ("rear_.*" -> "chest_.*",
"tail_.*" -> "tail[0-9]_.*"; "neck.*_.*" style patterns still match).

Frozen-version yamls (v0-v7) keep their documented ORDER (renamed in place);
the active root yaml and the new v8 copy get the ACTUAL regenerated URDF
order (export_ue.py asserts sequence equality against it).

Usage: python rl_exp/tools/pipeline/migrate_joint_names_v8.py
"""

import pathlib
import re

EXP = pathlib.Path(__file__).resolve().parents[2]
LIZ = EXP / "versions" / "lizard"

RENAME = {
    "rear_yaw": "chest_yaw", "rear_pitch": "chest_pitch",
    "tail_yaw": "neck_yaw", "tail_pitch": "neck_pitch",
    "neck1_yaw": "tail1_yaw", "neck1_pitch": "tail1_pitch",
    "neck2_yaw": "tail2_yaw", "neck2_pitch": "tail2_pitch",
    "neck3_yaw": "tail3_yaw", "neck3_pitch": "tail3_pitch",
}
LEG_SWAP = {"rl": "rf", "rf": "rl", "lf": "rr", "rr": "lf"}
for old, new in LEG_SWAP.items():
    for j in ("haa", "hfe", "kfe", "foot"):
        RENAME["%s_%s" % (old, j)] = "%s_%s" % (new, j)

# actual regenerated URDF joint order (urdf tree order after the rename)
URDF_ORDER = [
    "chest_yaw", "chest_pitch", "neck_yaw", "neck_pitch",
    "rf_haa", "rf_hfe", "rf_kfe", "rf_foot",
    "lf_haa", "lf_hfe", "lf_kfe", "lf_foot",
    "tail1_yaw", "tail1_pitch", "tail2_yaw", "tail2_pitch",
    "tail3_yaw", "tail3_pitch",
    "rr_haa", "rr_hfe", "rr_kfe", "rr_foot",
    "rl_haa", "rl_hfe", "rl_kfe", "rl_foot",
]

PATTERN_FIXES = [
    ('- "rear_.*"', '- "chest_.*"'),
    ('"rear_.*":', '"chest_.*":'),
    ('- "tail_.*"', '- "tail[0-9]_.*"'),
    ('"tail_.*":', '"tail[0-9]_.*":'),
]

HEADER_FIXES = [
    ("# (16 leg joints: HAA/HFE/KNE/FOOT x4, 10 spine joints: rear/tail/neck yaw+pitch).",
     "# (16 leg joints: HAA/HFE/KFE/FOOT x4, 10 spine joints: chest/neck/tail1-3 yaw+pitch)."),
    ("# ground-truth joint order (URDF tree order: spine chain first, then legs lf/rf/rl/rr)",
     "# ground-truth joint order (URDF tree order after the v8 anatomy rename)"),
]


def migrate(text: str, actual_order: bool) -> str:
    for old, new in PATTERN_FIXES:
        text = text.replace(old, new)
    for old, new in HEADER_FIXES:
        text = text.replace(old, new)
    if actual_order:
        m = re.search(r"joint_order:\n((?:  - \w+\n)+)", text)
        assert m, "joint_order block not found"
        block = "joint_order:\n" + "".join("  - %s\n" % n for n in URDF_ORDER) + "\n"
        text = text[:m.start()] + block + text[m.end():]
    else:
        # single-pass rename (swaps collide under sequential re.sub)
        pattern = re.compile(r"\b(%s)\b" % "|".join(RENAME))
        text = pattern.sub(lambda m: RENAME[m.group(1)], text)
    return text


def main():
    targets = sorted(LIZ.glob("v*/lizard_params.yaml")) + [LIZ / "lizard_params.yaml"]
    for path in targets:
        text = path.read_text(encoding="utf-8")
        assert "rear_yaw" in text or "chest_yaw" in text, path
        actual_order = path.name == "lizard_params.yaml" and path.parent == LIZ
        new = migrate(text, actual_order)
        # leg names are a swap (old/new sets identical) -- only spine names are
        # disjoint, so only those can be checked as leftovers
        spine_old = [o for o in RENAME if o.split("_")[0] in ("rear", "neck1", "neck2", "neck3", "tail")]
        leftovers = [o for o in spine_old if re.search(r"\b%s\b" % o, new)]
        assert not leftovers, "%s: old spine names left: %s" % (path, leftovers)
        assert all(n in new for n in URDF_ORDER), "%s: missing new names" % path
        path.write_text(new, encoding="utf-8")
        print("MIGRATED %s (actual_order=%s)" % (path.relative_to(EXP), actual_order))


if __name__ == "__main__":
    main()
