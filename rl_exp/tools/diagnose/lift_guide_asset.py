# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

"""Prepare an isolated USD with a passive vertical world-to-base guide."""

import argparse
import json
from pathlib import Path
import sys

from pxr import Gf, Sdf, Usd, UsdGeom, UsdPhysics, UsdUtils

ROOT = Path(__file__).resolve().parents[3]
sys.path.insert(0, str(ROOT))
from rl_exp.tools.runrecord.binding import sha256_file as digest  # noqa: E402


def _floating_base(stage):
    roots = [p for p in stage.Traverse() if p.HasAPI(UsdPhysics.ArticulationRootAPI)]
    if (len(roots) != 1 or roots[0].GetName() != "base_link"
            or not roots[0].HasAPI(UsdPhysics.RigidBodyAPI)):
        raise ValueError("expected unique articulation root on rigid base_link")
    for prim in stage.Traverse():
        if prim.IsA(UsdPhysics.PrismaticJoint):
            raise ValueError("floating source already has a prismatic joint")
        if prim.IsA(UsdPhysics.Joint):
            joint = UsdPhysics.Joint(prim)
            if not joint.GetBody0Rel().GetTargets() or not joint.GetBody1Rel().GetTargets():
                raise ValueError("floating source has a world-connected joint")
    return roots[0].GetPath()


def dependencies(path):
    """Hash every resolved USD layer and asset; reject unresolved dependencies."""
    layers, assets, unresolved = UsdUtils.ComputeAllDependencies(str(path))
    if unresolved:
        raise ValueError(f"unresolved USD dependencies: {unresolved}")
    paths = {str(Path(layer.realPath).resolve()) for layer in layers}
    paths.update(str(Path(asset).resolve()) for asset in assets)
    return {name: digest(Path(name)) for name in sorted(paths)}


def audit(source, output):
    """Check floating-source preservation and passive guide declarations, not physics."""
    base = _floating_base(source)
    parent = base.GetParentPath()
    carrier_path = parent.AppendChild("lift_guide_carrier")
    fixed_path = parent.AppendChild("lift_world_fixed_joint")
    guide_path = parent.AppendChild("lift_vertical_joint")
    expected_new = {carrier_path, fixed_path, guide_path}
    original = {p.GetPath() for p in source.TraverseAll()}
    if {p.GetPath() for p in output.TraverseAll()} != original | expected_new:
        raise ValueError("unexpected prim paths")
    # Compare complete composed prim/property metadata, defaults and time samples.
    for prim in source.TraverseAll():
        saved = output.GetPrimAtPath(prim.GetPath())
        if prim.GetAllMetadata() != saved.GetAllMetadata():
            raise ValueError(f"original prim metadata changed: {prim.GetPath()}")
        if {p.GetName() for p in prim.GetProperties()} != {p.GetName() for p in saved.GetProperties()}:
            raise ValueError(f"original properties changed: {prim.GetPath()}")
        for prop in prim.GetProperties():
            other = saved.GetProperty(prop.GetName())
            if prop.GetAllMetadata() != other.GetAllMetadata():
                raise ValueError(f"original property metadata changed: {prop.GetPath()}")
            if isinstance(prop, Usd.Attribute):
                times = prop.GetTimeSamples()
                if (times != other.GetTimeSamples() or prop.Get() != other.Get()
                        or any(prop.Get(t) != other.Get(t) for t in times)
                        or prop.GetConnections() != other.GetConnections()):
                    raise ValueError(f"original attribute changed: {prop.GetPath()}")
            elif prop.GetTargets() != other.GetTargets():
                raise ValueError(f"original relationship changed: {prop.GetPath()}")
    roots = [p.GetPath() for p in output.Traverse() if p.HasAPI(UsdPhysics.ArticulationRootAPI)]
    if roots != [base]:
        raise ValueError("articulation root changed")
    carrier = output.GetPrimAtPath(carrier_path)
    if (not carrier.HasAPI(UsdPhysics.RigidBodyAPI)
            or abs(UsdPhysics.MassAPI(carrier).GetMassAttr().Get() - 0.001) > 1e-10):
        raise ValueError("invalid carrier mass/body")
    if any(p.HasAPI(UsdPhysics.CollisionAPI) for p in Usd.PrimRange(carrier)):
        raise ValueError("carrier must be colliderless")
    for path, schema, body0, body1 in (
        (fixed_path, UsdPhysics.FixedJoint, [], [carrier_path]),
        (guide_path, UsdPhysics.PrismaticJoint, [carrier_path], [base]),
    ):
        prim = output.GetPrimAtPath(path)
        if not prim.IsA(schema):
            raise ValueError("missing guide joint")
        joint = schema(prim)
        if joint.GetBody0Rel().GetTargets() != body0 or joint.GetBody1Rel().GetTargets() != body1:
            raise ValueError("guide connection changed")
        if any("DriveAPI" in s for s in prim.GetAppliedSchemas()):
            raise ValueError("guide must not have drives")
        if any("friction" in a.GetName().lower() for a in prim.GetAuthoredAttributes()):
            raise ValueError("guide must not have friction")
        if (joint.GetLocalPos0Attr().Get() != Gf.Vec3f(0)
                or joint.GetLocalPos1Attr().Get() != Gf.Vec3f(0)
                or joint.GetLocalRot0Attr().Get() != Gf.Quatf(1)
                or joint.GetLocalRot1Attr().Get() != Gf.Quatf(1)):
            raise ValueError("guide frames must be canonical identity")
    guide = UsdPhysics.PrismaticJoint(output.GetPrimAtPath(guide_path))
    if (guide.GetAxisAttr().Get() != "Z" or guide.GetLowerLimitAttr().Get() != -float("inf")
            or guide.GetUpperLimitAttr().Get() != float("inf")):
        raise ValueError("guide must be unbounded Z")
    bodies = [p for p in source.Traverse() if p.HasAPI(UsdPhysics.RigidBodyAPI)]
    return {"original_properties_preserved": True, "robot_bodies": len(bodies),
            "carrier_mass_kg": 0.001,
            "robot_mass_kg": sum(UsdPhysics.MassAPI(p).GetMassAttr().Get() or 0 for p in bodies),
            "revolute_joints": sum(p.IsA(UsdPhysics.RevoluteJoint) for p in output.Traverse()),
            "fixed_joints": sum(p.IsA(UsdPhysics.FixedJoint) for p in output.Traverse()),
            "prismatic_joints": sum(p.IsA(UsdPhysics.PrismaticJoint) for p in output.Traverse()),
            "rigid_bodies": len(bodies) + 1, "articulation_roots": [str(base)],
            "self_collision_attributes": {str(a.GetPath()): a.Get() for p in source.Traverse()
                                          for a in p.GetAttributes() if "selfcollision" in a.GetName().lower()},
            "guide_applied_schemas": output.GetPrimAtPath(guide_path).GetAppliedSchemas(),
            "guide_limits": "unbounded", "guide_drives": [], "guide_friction_authored": False}


def create(source, out, carrier=False, floating_source=False):
    if not carrier and floating_source:
        raise ValueError("floating_source requires explicit carrier=True")
    source, out = source.resolve(), out.resolve()
    if out.exists() or not out.is_relative_to((ROOT / "rl_exp/out").resolve()):
        raise ValueError("output must be a fresh file below rl_exp/out")
    source_hash = digest(source)
    stage = Usd.Stage.Open(str(source))
    if stage is None:
        raise ValueError("cannot open source USD")
    source_dependencies = dependencies(source) if floating_source else None
    # Fail closed on composition requiring relocation; never silently rewrite geometry paths.
    if floating_source and (len(source_dependencies) != 1 or stage.GetRootLayer().subLayerPaths):
        raise ValueError("floating source must be self-contained; resolve external dependencies first")
    original_layer = Sdf.Layer.CreateAnonymous()
    if floating_source:
        original_layer.ImportFromString(stage.GetRootLayer().ExportToString())
    original = Usd.Stage.Open(original_layer) if floating_source else None
    if floating_source:
        child = [_floating_base(stage)]
        joint_path = child[0].GetParentPath().AppendChild("lift_world_fixed_joint")
        new_paths = [joint_path, child[0].GetParentPath().AppendChild("lift_vertical_joint"),
                     child[0].GetParentPath().AppendChild("lift_guide_carrier")]
        if any(stage.GetPrimAtPath(p) for p in new_paths):
            raise ValueError("guide paths already exist")
        old = UsdPhysics.FixedJoint.Define(stage, joint_path)
        old.CreateLocalPos0Attr(Gf.Vec3f(0))
        old.CreateLocalPos1Attr(Gf.Vec3f(0))
        old.CreateLocalRot0Attr(Gf.Quatf(1))
        old.CreateLocalRot1Attr(Gf.Quatf(1))
    else:
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
    layer = stage.GetRootLayer()
    if not layer.Export(str(out)):
        raise RuntimeError("USD export failed")
    if digest(source) != source_hash:
        raise ValueError("source changed during export")
    reopened = Usd.Stage.Open(str(out))
    saved = UsdPhysics.PrismaticJoint(reopened.GetPrimAtPath(joint_path))
    if not saved or saved.GetAxisAttr().Get() != "Z" or saved.GetBody1Rel().GetTargets() != child:
        raise ValueError("exported guide did not read back")
    report = {}
    if floating_source:
        report = audit(original, reopened)
        if dependencies(source) != source_dependencies:
            raise ValueError("source dependencies changed during export")
        output_dependencies = dependencies(out)
        expected = {k: v for k, v in source_dependencies.items() if k != str(source)}
        if any(output_dependencies.get(k) != v for k, v in expected.items()):
            raise ValueError("export did not preserve dependency bindings")
        report.update(floating_source=True, source_dependencies=source_dependencies,
                      output_dependencies=output_dependencies)
    return {**report, "source": str(source), "source_sha256": source_hash, "asset": str(out),
            "asset_sha256": digest(out), "joint": str(joint_path), "child": str(child[0]),
            "axis": "Z", "linear_drive": False, "carrier": carrier,
            "scope": "isolated USD declaration; no runtime or reaction-force evidence"}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--usd", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--carrier", action="store_true")
    parser.add_argument("--floating_source", action="store_true")
    args = parser.parse_args()
    print(json.dumps(create(args.usd, args.out, args.carrier, args.floating_source), indent=2))
