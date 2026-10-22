# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause
"""Read candidate velocity-cap configuration and backend evidence, without physics.

The three pinned records are fixed-base loaded tracking, free-base standing and
the training-consistent TGS/false velocity probe. No true-timing data is consumed.
Matching limits [rad/s] proves configuration/readback consistency only, never
hard saturation, a speed/load envelope, or adoption of a frozen recipe.
"""
from __future__ import annotations

import argparse
from collections import Counter
import copy
import json
import math
from pathlib import Path
import re
import shutil
import sys
import xml.etree.ElementTree as ET

REPO = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(REPO))
from rl_exp.tools.runrecord import binding  # noqa: E402

REFERENCES = (
    ("rl_exp/out/lizard2_b_joint_force_probe_20261021/report.json",
     "13929c53eccdb51d454ade60cf071c3eaa614bf5c90684dd2e06f4017d2485ef"),
    ("rl_exp/out/lizard2_b_standing_force_20261022_run02/report.json",
     "5a4c6a3f4572ab8db566637c64c67933ee5aa3857092b1fe7ed1b102724453c6"),
    ("rl_exp/out/lizard2_velocity_legacy_20261022_run02/report.json",
     "798335b96355a631dc498fda6eff2be7eb92bf1c61de628372617d35c9122916"),
)


def require(condition, message):
    if not condition:
        raise ValueError(message)


def configured_caps(manifest: dict, names: list[str]) -> dict[str, float]:
    """Resolve both implicit actuator fields by actual joint name [rad/s]."""
    cfg = manifest["config"]
    caps = {}
    prefix = "scene.robot.actuators."
    groups = [key[:-len(".joint_names_expr")] for key in cfg
              if key.startswith(prefix) and key.endswith(".joint_names_expr")]
    require(bool(groups), "no actuator groups")
    for group in groups:
        selected = [name for name in names if any(re.fullmatch(pattern, name)
                    for pattern in cfg[group + ".joint_names_expr"])]
        require(bool(selected), f"empty actuator group: {group}")
        require(not (set(selected) & caps.keys()), "overlapping actuator groups")
        fields = [cfg.get(group + suffix) for suffix in (".velocity_limit", ".velocity_limit_sim")]
        require(all(isinstance(value, dict) and set(value) == set(selected) for value in fields),
                "both explicit cap fields must cover exactly the selected joints")
        require(fields[0] == fields[1], "legacy/simulator cap fields differ")
        for name in selected:
            value = float(fields[1][name])
            require(math.isfinite(value) and value > 0., "invalid configured cap")
            caps[name] = value
    require(set(caps) == set(names), "actuator cap coverage differs from runtime")
    return caps


def compare_caps(names: list[str], backend: list[float], configured: dict, urdf: dict) -> None:
    """Require name-bound equality of configuration, URDF and backend caps [rad/s]."""
    require(len(names) == len(set(names)) == len(backend) == 30, "runtime cap width/name mismatch")
    require(set(names) == set(configured) == set(urdf), "joint set mismatch")
    for name, value in zip(names, backend):
        require(math.isfinite(value) and value > 0., "invalid backend cap")
        require(value == configured[name] == urdf[name], "cap mismatch: " + name)


def audit() -> dict:
    """Audit the original pinned local records without starting a simulator."""
    cases, canonical, urdf_hash = [], None, None
    negative_cases = []
    for relative, digest in REFERENCES:
        path = REPO / relative
        require(binding.sha256_file(path) == digest, "reference changed: " + relative)
        report = json.loads(path.read_text(encoding="utf-8"))
        require(report["completed"], "incomplete reference")
        key = "tracking_manifest" if "tracking_manifest" in report else "manifest"
        manifest_path = Path(report[key])
        require(binding.sha256_file(manifest_path) == report[key + "_sha256"], "manifest changed")
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        target = manifest["target_binding"]
        for field in ("target", "urdf"):
            require(binding.sha256_file(Path(target[field])) == manifest["sha256"][field], "asset changed: " + field)
        if urdf_hash is None:
            urdf_hash = manifest["sha256"]["urdf"]
        require(manifest["sha256"]["urdf"] == urdf_hash, "records belong to different URDFs")
        urdf = {joint.get("name"): float(joint.find("limit").get("velocity"))
                for joint in ET.parse(target["urdf"]).getroot().findall("joint") if joint.get("type") != "fixed"}
        names, backend = report["joint_names"], report["readbacks"]["velocity_caps"]
        configured = configured_caps(manifest, names)
        compare_caps(names, backend, configured, urdf)
        if canonical is None:
            canonical = dict(zip(names, backend))
        require(dict(zip(names, backend)) == canonical, "case caps differ by joint")
        if "force_timing" in report:
            require(report["force_timing"] == "legacy" and report["readbacks"]["force_timing"] is False,
                    "velocity record is not training-consistent false")
            require(report["readbacks"]["solver_type"] == "TGS", "velocity record is not TGS")
        cases.append({"path": relative, "sha256": digest, "manifest": str(manifest_path),
                      "manifest_sha256": report[key + "_sha256"], "usd_sha256": manifest["sha256"]["target"],
                      "joint_names": names, "backend_caps_rad_s": backend})
        if not negative_cases:
            for defect in ("missing_sim_field", "backend_cap_changed", "joint_axis_swapped"):
                bad_manifest, bad_backend, bad_names = copy.deepcopy(manifest), backend.copy(), names.copy()
                if defect == "missing_sim_field":
                    del bad_manifest["config"]["scene.robot.actuators.legs.velocity_limit_sim"]
                elif defect == "backend_cap_changed":
                    bad_backend[0] += 1.
                else:
                    i = next(i for i, value in enumerate(backend) if value != backend[0])
                    bad_names[0], bad_names[i] = bad_names[i], bad_names[0]
                try:
                    compare_caps(bad_names, bad_backend, configured_caps(bad_manifest, bad_names), urdf)
                except ValueError:
                    negative_cases.append(defect)
                else:
                    raise ValueError("corrupt cap data accepted: " + defect)
    return {"completed": True, "scope": "configuration/backend readback only; hard-limit behavior undecided",
            "urdf_sha256": urdf_hash, "cases": cases, "caps_by_joint_rad_s": canonical,
            "cap_counts": dict(Counter(canonical.values())), "negative_cases_rejected": negative_cases,
            "physics_runs_added": 0, "true_timing_records_read": 0}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    out = args.out.resolve()
    source = out.with_suffix(out.suffix + ".source.py")
    require(out.is_relative_to(REPO / "rl_exp/out") and not out.exists() and not source.exists(),
            "choose new output paths under rl_exp/out")
    result = audit()
    result["code_sha256"] = binding.sha256_file(Path(__file__))
    out.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(__file__, source)
    with out.open("x", encoding="utf-8") as handle:
        handle.write(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))
    print("VELOCITY_LIMIT_READBACK_AUDIT_OK", result["cap_counts"], result["negative_cases_rejected"])


if __name__ == "__main__":
    main()
