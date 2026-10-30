# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

"""Compare an unloaded vertical guide against free fall in a known gravity field.

This calibrates a single rigid body only, not a robot articulation. No contact,
drive, external force, motor, or robot is present. The inferred constraint force
is mass times acceleration minus gravity, not a direct joint reaction readback.
"""

import argparse
import json
from pathlib import Path
import sys
import traceback

from isaaclab.app import AppLauncher

parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument("--out", type=Path, required=True)
parser.add_argument("--break_test", action="store_true", help="Replace the free vertical guide with a fixed joint")
AppLauncher.add_app_launcher_args(parser)
args = parser.parse_args()
if args.out.exists():
    parser.error("output already exists")
app = AppLauncher(args).app

try:
    import numpy as np
    import warp as wp
    from pxr import Gf, Sdf, UsdGeom, UsdPhysics
    from isaaclab.sim import SimulationCfg, SimulationContext
    from isaaclab_physx.physics import PhysxManager

    dt, steps, mass = 0.005, 80, 2.0
    gravity = (2.0, 0.0, -9.81)
    sim = SimulationContext(SimulationCfg(dt=dt, device=args.device, gravity=gravity))
    stage = sim.stage
    for name, x in (("free", -1.), ("guided", 1.)):
        cube = UsdGeom.Cube.Define(stage, f"/World/{name}")
        cube.CreateSizeAttr(0.1)
        cube.AddTranslateOp().Set(Gf.Vec3d(x, 0., 2.))
        body = cube.GetPrim()
        UsdPhysics.RigidBodyAPI.Apply(body)
        UsdPhysics.MassAPI.Apply(body).CreateMassAttr(mass)
    guide = (UsdPhysics.FixedJoint.Define(stage, "/World/vertical_guide") if args.break_test else
             UsdPhysics.PrismaticJoint.Define(stage, "/World/vertical_guide"))
    guide.CreateBody1Rel().SetTargets([Sdf.Path("/World/guided")])
    if not args.break_test:
        guide.CreateAxisAttr("Z")
    guide.CreateLocalPos0Attr(Gf.Vec3f(1., 0., 2.))
    guide.CreateLocalPos1Attr(Gf.Vec3f(0., 0., 0.))
    sim.reset()
    physics = PhysxManager.get_physics_sim_view()
    views = {n: physics.create_rigid_body_view(f"/World/{n}") for n in ("free", "guided")}
    samples = []
    def read():
        return {n: {"pose": wp.to_torch(v.get_transforms())[0].cpu().tolist(),
                    "velocity": wp.to_torch(v.get_velocities())[0].cpu().tolist()} for n, v in views.items()}
    samples.append({"step": 0, "bodies": read()})
    for step in range(1, steps + 1):
        sim.step(render=False)
        samples.append({"step": step, "bodies": read()})
    initial, final = samples[0]["bodies"], samples[-1]["bodies"]
    acceleration = {n: ((np.asarray(final[n]["velocity"][:3]) - np.asarray(initial[n]["velocity"][:3])) / (dt * steps)).tolist() for n in views}
    inferred = {n: (mass * (np.asarray(acceleration[n]) - np.asarray(gravity))).tolist() for n in views}
    checks = {"free_gravity": bool(np.allclose(acceleration["free"], gravity, atol=0.1, rtol=0)),
              "guide_locks_x": abs(acceleration["guided"][0]) < 0.1,
              "guide_free_z": abs(acceleration["guided"][2] - gravity[2]) < 0.1,
              "guide_no_rotation": max(abs(v) for row in samples for v in row["bodies"]["guided"]["velocity"][3:]) < 0.01}
    report = {"scope": "single rigid body and free control, no ground; inferred forces only", "break_test": args.break_test,
              "dt_s": dt, "steps": steps, "mass_kg": mass, "gravity_m_s2": gravity,
              "acceleration_m_s2": acceleration, "inferred_constraint_force_n": inferred,
              "checks": checks, "passed": all(checks.values()), "samples": samples}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("x", encoding="utf-8") as stream:
        json.dump(report, stream, indent=2, allow_nan=False)
    print("GUIDE_CALIBRATION", json.dumps({"passed": report["passed"], "acceleration": acceleration, "force": inferred}), flush=True)
    app.close(exit_code=0 if report["passed"] else 1)
except BaseException:
    traceback.print_exc()
    sys.stdout.flush()
    sys.stderr.flush()
    app.close(exit_code=1)
    raise
