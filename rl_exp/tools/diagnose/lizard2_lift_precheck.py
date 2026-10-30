# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

"""Run the shared whole-body precheck on sampled lizard2 lift IK endpoints."""

import argparse
import json
from pathlib import Path
import sys

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))
from rl_exp.tools.runrecord.binding import sha256_file as digest  # noqa: E402

import body_precheck
from pose_target_solver import geometry, load_model


def prepare(ik, manifest):
    """Create a body_precheck input from bound IK samples and named filters."""
    urdf = Path(ik["urdf"])
    if digest(urdf) != ik["urdf_sha256"]:
        raise ValueError("IK URDF identity changed")
    samples = ik["samples"]
    if not samples or samples[0]["root_rise_m"] != 0 or not all(s["passed"] for s in samples):
        raise ValueError("need a complete passing zero-height-start IK sample")
    model = load_model(urdf)
    meshes = {n: s["collision"] for n, s in model["links"].items() if s["collision"]}
    feet = ["lf_wrist", "rf_wrist", "rl_ankle", "rr_ankle"]
    support = ik["support"]
    if not support or not set(support) <= set(feet):
        raise ValueError("unknown support")
    root_height = max(-float(np.min((geometry.read_obj(meshes[foot]) @
        geometry.fk(model["joints"], foot, samples[0]["q_rad"])[:3, :3].T +
        geometry.fk(model["joints"], foot, samples[0]["q_rad"])[:3, 3])[:, 2])) for foot in support)
    chains, covered = {}, set()
    for foot in feet:
        path = [n for n in geometry.chain_up(model["joints"], foot) if model["joints"][n]["axis"] is not None]
        covered.update(path)
        chains[foot] = {"root_link": "base_link", "end_link": foot,
                        "joint_roles": {n: n for n in path}, "contact_links": [foot]}
    direct = {tuple(sorted((j["parent"], j["child"]))) for j in model["joints"].values()
              if j["parent"] in meshes and j["child"] in meshes}
    named = {tuple(sorted(pair)) for pair in manifest["connection_filter"]["pairs"]}
    if not all(set(pair) <= set(meshes) for pair in named):
        raise ValueError("named connection filter missing from candidate")
    allowed = [{"pair": list(pair), "reason": "existing direct joint or named connection exclusion"}
               for pair in sorted(direct | named)]
    cases = []
    for index, sample in enumerate(samples):
        root = np.eye(4)
        root[2, 3] = root_height + sample["root_rise_m"]
        cases.append({"id": f"sample_{index}", "phase": "lift endpoint", "q_rad": sample["q_rad"],
                      "root_transform": root.tolist()})
    contacts = {n: {"max_penetration_m": 0.005, "max_gap_m": 0.005} for n in support}
    return {"inputs": {"identity": "lizard2 lift endpoint geometry", "units": "SI",
                       "urdf": {"path": str(urdf), "sha256": ik["urdf_sha256"]},
                       "meshes": [{"path": str(p), "sha256": digest(p)} for p in sorted(set(meshes.values()))],
                       "threshold_basis": {"approved_by": "user: execute lift plan",
                           "reference": "lift plan support tolerance; previous standing connection filters"}},
            "body": {"chains": chains, "other_joints": {n: n for n, j in model["joints"].items()
                        if j["axis"] is not None and n not in covered},
                     "collision_entities": list(meshes), "excluded_entities": [], "allowed_pairs": allowed},
            "tasks": {"cases": cases, "requirements": [{"id": name, "check": name, "required": True,
                        "cases": [c["id"] for c in cases], "chains": list(chains), "params": params}
                       for name, params in [("joint_limits", {}), ("self_collision", {"clearance_m": 0.}),
                           ("ground", {"normal": [0., 0., 1.], "height_m": 0., "min_gap_m": 0.001,
                                       "allowed_contacts": contacts})]]}}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--ik", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--out_dir", type=Path, required=True)
    parser.add_argument("--midpoints", action="store_true", help="Also check linearly interpolated node midpoints")
    args = parser.parse_args()
    if args.out_dir.exists():
        parser.error("output directory exists")
    ik = json.loads(args.ik.read_text(encoding="utf-8"))
    manifest = json.loads(args.manifest.read_text(encoding="utf-8"))
    config = prepare(ik, manifest)
    if args.midpoints:
        original = config["tasks"]["cases"]
        cases = []
        for a, b in zip(original, original[1:]):
            cases.append(a)
            middle = {"id": a["id"] + "_mid", "phase": "joint-linear midpoint",
                      "q_rad": {n: (a["q_rad"][n] + b["q_rad"][n]) / 2 for n in a["q_rad"]},
                      "root_transform": np.asarray(a["root_transform"]).copy().tolist()}
            middle["root_transform"][2][3] = (a["root_transform"][2][3] + b["root_transform"][2][3]) / 2
            cases.append(middle)
        cases.append(original[-1])
        config["tasks"]["cases"] = cases
        for requirement in config["tasks"]["requirements"]:
            requirement["cases"] = [case["id"] for case in cases]
    args.out_dir.mkdir(parents=True, exist_ok=False)
    (args.out_dir / "config.json").write_text(json.dumps(config, indent=2, allow_nan=False), encoding="utf-8")
    report = body_precheck.run(config, args.out_dir.resolve())
    report["lift_input"] = {"ik": str(args.ik.resolve()), "ik_sha256": digest(args.ik),
                            "manifest": str(args.manifest.resolve()), "manifest_sha256": digest(args.manifest),
                            "adapter_sha256": digest(Path(__file__).resolve()),
                            "note": "named exclusions copied from prior manifest; runtime filtering not revalidated"}
    (args.out_dir / "report.json").write_text(json.dumps(report, indent=2, allow_nan=False), encoding="utf-8")
    print(report["status"], args.out_dir, flush=True)
    raise SystemExit(0 if report["status"] == "pass" else 1)
