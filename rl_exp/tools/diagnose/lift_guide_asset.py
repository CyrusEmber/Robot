# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

"""Prepare an isolated USD with a passive vertical world-to-base guide."""

import argparse
import json
from pathlib import Path
import sys

from pxr import Gf, Sdf, Usd, UsdGeom, UsdPhysics

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from rl_exp.tools.runrecord.binding import sha256_file as digest  # noqa: E402


def create(source, out, carrier=False):
    source, out = source.resolve(), out.resolve()
    if out.exists() or not out.is_relative_to((ROOT / "rl_exp/out").resolve()):
        raise ValueError("output must be a fresh file below rl_exp/out")
    source_hash = digest(source)
    stage = Usd.Stage.Open(str(source))
    if stage is None:
        raise ValueError("cannot open source USD")
    fixed = [p for p in stage.Traverse() if p.IsA(UsdPhysics.FixedJoint)
             and len(UsdPhysics.FixedJoint(p).GetBody0Rel().GetTargets()) == 0]
    if len(fixed) != 1:
        raise ValueError("expected exactly one world-fixed joint")
    old = UsdPhysics.FixedJoint(fixed[0])
    child = old.GetBody1Rel().GetTargets()
    if len(child) != 1 or str(child[0]).split("/")[-1] != "base_link":
        raise ValueError("world joint must connect base_link")
    joint_path = fixed[0].GetPath()
    if carrier:
        carrier_path = child[0].GetParentPath().AppendChild("lift_guide_carrier")
        if stage.GetPrimAtPath(carrier_path):
            raise ValueError("carrier already exists")
        carrier_prim = UsdGeom.Xform.Define(stage, carrier_path).GetPrim()
        UsdPhysics.RigidBodyAPI.Apply(carrier_prim)
        mass = UsdPhysics.MassAPI.Apply(carrier_prim)
        mass.CreateMassAttr(0.001)
        mass.CreateDiagonalInertiaAttr(Gf.Vec3f(1e-6, 1e-6, 1e-6))
        old.GetBody1Rel().SetTargets([carrier_path])
        old.CreateJointEnabledAttr(True)
        joint_path = carrier_path.GetParentPath().AppendChild("lift_vertical_joint")
    else:
        stage.RemovePrim(joint_path)
    joint = UsdPhysics.PrismaticJoint.Define(stage, joint_path)
    if carrier:
        joint.CreateBody0Rel().SetTargets([carrier_path])
    joint.CreateBody1Rel().SetTargets([Sdf.Path(str(child[0]))])
    joint.CreateAxisAttr("Z")
    joint.CreateLocalPos0Attr(Gf.Vec3f(0., 0., 0.))
    joint.CreateLocalPos1Attr(Gf.Vec3f(0., 0., 0.))
    joint.CreateLocalRot0Attr(Gf.Quatf(1., Gf.Vec3f(0., 0., 0.)))
    joint.CreateLocalRot1Attr(Gf.Quatf(1., Gf.Vec3f(0., 0., 0.)))
    if joint.GetPrim().HasAPI(UsdPhysics.DriveAPI, "linear"):
        raise ValueError("guide must not have a linear drive")
    out.parent.mkdir(parents=True, exist_ok=True)
    if not stage.GetRootLayer().Export(str(out)):
        raise RuntimeError("USD export failed")
    if digest(source) != source_hash:
        raise ValueError("source changed during export")
    reopened = Usd.Stage.Open(str(out))
    saved = UsdPhysics.PrismaticJoint(reopened.GetPrimAtPath(joint_path))
    if not saved or saved.GetAxisAttr().Get() != "Z" or saved.GetBody1Rel().GetTargets() != child:
        raise ValueError("exported guide did not read back")
    return {"source": str(source), "source_sha256": source_hash, "asset": str(out),
            "asset_sha256": digest(out), "joint": str(joint_path), "child": str(child[0]),
            "axis": "Z", "linear_drive": False, "carrier": carrier,
            "scope": "isolated USD declaration; no runtime or reaction-force evidence"}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--usd", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--carrier", action="store_true")
    args = parser.parse_args()
    print(json.dumps(create(args.usd, args.out, args.carrier), indent=2))
