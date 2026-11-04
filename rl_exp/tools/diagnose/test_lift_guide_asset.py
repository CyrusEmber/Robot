# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

"""Focused pure-USD guide checks; run directly with IsaacLab Python -B."""

from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from pxr import Gf, Usd, UsdGeom, UsdPhysics

import lift_guide_asset as guide


def fixture(fixed=False):
    stage = Usd.Stage.CreateInMemory()
    for name in ("base_link", "foot"):
        prim = UsdGeom.Xform.Define(stage, "/robot/" + name).GetPrim()
        UsdPhysics.RigidBodyAPI.Apply(prim)
        mass = UsdPhysics.MassAPI.Apply(prim)
        mass.CreateMassAttr(1)
        mass.CreateDiagonalInertiaAttr(Gf.Vec3f(1))
    UsdPhysics.ArticulationRootAPI.Apply(stage.GetPrimAtPath("/robot/base_link"))
    joint = UsdPhysics.FixedJoint.Define(stage, "/robot/foot_joint")
    joint.CreateBody0Rel().SetTargets(["/robot/base_link"])
    joint.CreateBody1Rel().SetTargets(["/robot/foot"])
    if fixed:
        joint = UsdPhysics.FixedJoint.Define(stage, "/robot/world")
        joint.CreateBody1Rel().SetTargets(["/robot/base_link"])
    return stage


class GuideTests(unittest.TestCase):
    def prepare(self, stage, **kwargs):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        root = Path(directory.name)
        source, out = root / "source.usda", root / "rl_exp/out/guide.usda"
        stage.GetRootLayer().Export(str(source))
        with patch.object(guide, "ROOT", root):
            result = guide.create(source, out, **kwargs)
        return Usd.Stage.Open(str(source)), Usd.Stage.Open(str(out)), result

    def test_floating_and_mutations(self):
        source, output, report = self.prepare(fixture(), carrier=True, floating_source=True)
        self.assertTrue(report["original_properties_preserved"])
        prim = output.GetPrimAtPath("/robot/lift_vertical_joint")
        for instance in ("linear", "angular"):
            UsdPhysics.DriveAPI.Apply(prim, instance)
            with self.assertRaisesRegex(ValueError, "drives"):
                guide.audit(source, output)
            prim.RemoveAPI(UsdPhysics.DriveAPI, instance)
        inertia = output.GetPrimAtPath("/robot/base_link").GetAttribute("physics:diagonalInertia")
        inertia.Set(Gf.Vec3f(2))
        with self.assertRaisesRegex(ValueError, "original"):
            guide.audit(source, output)
        inertia.Set(Gf.Vec3f(1))
        rel = output.GetPrimAtPath("/robot/foot_joint").GetRelationship("physics:body1")
        rel.SetTargets(["/robot/base_link"])
        with self.assertRaisesRegex(ValueError, "original"):
            guide.audit(source, output)
        rel.SetTargets(["/robot/foot"])
        guide.audit(source, output)
        guide_joint = UsdPhysics.PrismaticJoint(prim)
        guide_joint.CreateUpperLimitAttr(1)
        with self.assertRaisesRegex(ValueError, "unbounded"):
            guide.audit(source, output)
        guide_joint.GetUpperLimitAttr().Clear()
        guide_joint.GetBody0Rel().SetTargets(["/robot/foot"])
        with self.assertRaisesRegex(ValueError, "connection"):
            guide.audit(source, output)
        guide_joint.GetBody0Rel().SetTargets(["/robot/lift_guide_carrier"])
        guide.audit(source, output)

    def test_requires_explicit_carrier(self):
        with self.assertRaisesRegex(ValueError, "explicit carrier"):
            guide.create(Path("unused"), Path("unused"), floating_source=True)

    def test_default_still_rejects_floating(self):
        with self.assertRaisesRegex(ValueError, "exactly one world-fixed"):
            self.prepare(fixture())

    def test_rejects_existing_world_or_prismatic(self):
        with self.assertRaisesRegex(ValueError, "world-connected"):
            self.prepare(fixture(True), carrier=True, floating_source=True)
        stage = fixture()
        UsdPhysics.PrismaticJoint.Define(stage, "/robot/existing")
        with self.assertRaisesRegex(ValueError, "prismatic"):
            self.prepare(stage, carrier=True, floating_source=True)

    def test_legacy_fixed_modes(self):
        for carrier in (False, True):
            _, output, report = self.prepare(fixture(True), carrier=carrier)
            joint = UsdPhysics.PrismaticJoint(output.GetPrimAtPath(report["joint"]))
            self.assertTrue(joint)
            self.assertEqual(joint.GetAxisAttr().Get(), "Z")
            self.assertEqual(len(joint.GetBody0Rel().GetTargets()), int(carrier))
        stage = fixture(True)
        UsdPhysics.FixedJoint.Define(stage, "/robot/other_world")
        with self.assertRaisesRegex(ValueError, "exactly one world-fixed"):
            self.prepare(stage)


if __name__ == "__main__":
    unittest.main()
