# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

# -*- coding: utf-8 -*-
"""Contact ownership: which body carries a collision, and does the penalty stack see it?

Item 1 of the leg-axis ledger (``work/active/asset-leg-axis-capability-mismatch.md``) left one thing
unverified: the URDF side says the tibia's collision lives on the ``*_hfe`` body and the four
``*_kfe`` carry none, but nothing read the **USD** side or what actually contacts at runtime. A
penalty computed over bodies that have no collider reads 0.0 forever and looks like a passing gate.

Three readings, one per row of the table:

1. **USD side** -- the spawned prim tree (what PhysX loads), not the .usda text: for every body, its
   collision prims, their ``physics:approximation`` and their bbox size.
2. **URDF side** -- the same bodies' ``<collision>`` meshes and bbox sizes, so a mesh swapped
   between links (femur vs tibia) shows up as a size mismatch rather than as a name one trusts.
3. **Runtime** -- the bodies the penalty stack names, and the bodies a settled zero-action stand
   actually pushes into the floor. A body in the second set but in neither penalty set is a body
   nothing punishes.

Run:

    E:\\IsaacLab\\env_isaaclab\\Scripts\\python.exe rl_exp\\tools\\verify\\check_contact_ownership.py ^
        --task Lizard-Baseline-Flat-v2

Exit code is 0 only when the arrangement is coherent: every penalty body has a collider, every
contacting body is covered by a penalty term or is a foot, and the run measured contact at all.
Task-parameterised (the family and URDF come off the task's own spawn path), so the same command
runs on any family -- a retired line is not refused here because building an env is not training.
"""

import argparse
import pathlib
import sys
import xml.etree.ElementTree as ET

from isaaclab.app import AppLauncher

parser = argparse.ArgumentParser()
parser.add_argument("--task", default="Lizard-Baseline-Flat-v2")
parser.add_argument("--num_envs", type=int, default=8)
parser.add_argument("--steps", type=int, default=100, help="control steps of zero action to observe")
parser.add_argument("--threshold", type=float, default=1.0, help="contact force counted as contact [N]")
parser.add_argument("--json", help="write the full report here")
AppLauncher.add_app_launcher_args(parser)
args_cli = parser.parse_args()
app_launcher = AppLauncher(args_cli)
simulation_app = app_launcher.app

import gymnasium as gym  # noqa: E402
import torch  # noqa: E402

from pxr import Usd, UsdPhysics  # noqa: E402

from rl_exp.tools.verify.baseline_runtime import resolve_task_cfg  # noqa: E402

PROBLEMS: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    """One gate: printed either way, collected when it fails."""
    print(f"[{'ok' if ok else 'FAIL'}] {name}{'  ' + detail if detail else ''}")
    if not ok:
        PROBLEMS.append(name)


def urdf_collision(urdf: pathlib.Path) -> dict:
    """Link -> collision mesh path (or None), straight off the URDF."""
    out = {}
    for link in ET.parse(urdf).getroot().findall("link"):
        mesh = link.find("collision/geometry/mesh")
        out[link.get("name")] = (urdf.parent / mesh.get("filename")).resolve() if mesh is not None else None
    return out


def obj_extent(path: pathlib.Path) -> list[float]:
    """Bbox size of an .obj [m], or zeros when it cannot be read."""
    pts = [list(map(float, ln.split()[1:4])) for ln in path.read_text().splitlines()
           if ln.startswith("v ")]
    if not pts:
        return [0.0, 0.0, 0.0]
    lo = [min(p[i] for p in pts) for i in range(3)]
    hi = [max(p[i] for p in pts) for i in range(3)]
    return [round(hi[i] - lo[i], 4) for i in range(3)]


def usd_collisions(robot_prim) -> dict:
    """Body -> [{prim, approximation, points, extent}] from the live stage.

    A collision prim belongs to its nearest rigid-body ancestor, so geometry nested in a scope is
    still attributed to the body PhysX puts it on.
    """
    out: dict[str, list[dict]] = {}
    for prim in Usd.PrimRange(robot_prim):
        if not prim.HasAPI(UsdPhysics.CollisionAPI):
            continue
        body = prim
        while body and not body.HasAPI(UsdPhysics.RigidBodyAPI):
            body = body.GetParent()
        if not body:
            continue
        points = prim.GetAttribute("points")
        pts = points.Get() if points else None
        extent = [0.0, 0.0, 0.0]
        if pts:
            arr = [[float(p[0]), float(p[1]), float(p[2])] for p in pts]
            extent = [round(max(p[i] for p in arr) - min(p[i] for p in arr), 4) for i in range(3)]
        approx = prim.GetAttribute("physics:approximation")
        out.setdefault(body.GetName(), []).append({
            "prim": str(prim.GetPath()).rsplit("/", 2)[-2:],
            "approximation": approx.Get() if approx else None,
            "points": len(pts) if pts else 0,
            "extent": extent,
        })
    return out


def penalised_bodies(env) -> dict:
    """Terms that name bodies -> the body names they resolved to.

    ``body_ids`` is filled when the term's ``SceneEntityCfg`` is resolved; reading the regex back
    would say what was asked for, not what it matched. A term the recipe does not have is skipped.
    """
    sensor = env.scene.sensors["contact_forces"]
    out = {}
    for term_name in ("undesired_contacts", "belly_contact_force"):
        try:
            params = env.reward_manager.get_term_cfg(term_name).params
        except KeyError:
            continue
        cfg = next((v for v in params.values() if hasattr(v, "body_ids")), None)
        if cfg is None:
            continue
        ids = list(cfg.body_ids)
        out[term_name] = [sensor.body_names[i] for i in ids] if ids else list(cfg.body_names)
    return out


def main() -> int:
    cfg = resolve_task_cfg(args_cli.task)
    cfg.scene.num_envs = args_cli.num_envs
    env = gym.make(args_cli.task, cfg=cfg).unwrapped
    robot = env.scene["robot"]
    sensor = env.scene.sensors["contact_forces"]
    num_envs = args_cli.num_envs

    usd_path = pathlib.Path(str(cfg.scene.robot.spawn.usd_path))
    family = usd_path.parent.name
    urdf = pathlib.Path(__file__).resolve().parents[2] / "versions" / family / f"{family}.urdf"
    if not urdf.exists():
        raise SystemExit(f"no urdf beside the task's asset: {urdf} (task {args_cli.task})")
    print(f"ASSET family={family} usd={usd_path.name} urdf={urdf.name} envs={num_envs}")

    urdf_links = urdf_collision(urdf)

    import omni.usd

    # The live prim tree, not the .usda text: what PhysX loads is what the stage says after spawn.
    stage = omni.usd.get_context().get_stage()
    leaf = str(cfg.scene.robot.prim_path).rsplit("/", 1)[-1]
    robot_prim = next(p for p in stage.Traverse() if p.HasAPI(UsdPhysics.ArticulationRootAPI))
    while robot_prim and robot_prim.GetName() != leaf:
        robot_prim = robot_prim.GetParent()
    if not robot_prim:
        raise SystemExit(f"no prim named {leaf!r} above the articulation root: {stage}")
    usd_bodies = usd_collisions(robot_prim)

    terms = penalised_bodies(env)
    selected = {n for names in terms.values() for n in names}
    # A penalty body with no collider reads 0.0 forever: the term is present, the gate is open, and
    # nothing ever fires. The URDF says the tibia's collision sits on `*_hfe` and the four `*_kfe`
    # carry none -- if the USD agrees, the kfe half of the selection is exactly that kind of dead body.
    dead = sorted(n for n in selected if not usd_bodies.get(n))
    check("every penalty body carries a collider", not dead,
          f"colliders missing: {dead}" if dead else f"{len(selected)} bodies: {sorted(selected)}")

    # Zero action: hold the default pose and count the peak force per body. Who actually pushes the
    # floor is the question the configured pattern cannot answer about itself.
    peak = torch.zeros(len(sensor.body_names), device=env.device)
    action = torch.zeros(num_envs, env.action_space.shape[-1], device=env.device)
    for _ in range(args_cli.steps):
        env.step(action)
        peak = torch.maximum(peak, sensor.data.net_forces_w_history.torch.norm(dim=-1).amax(dim=(0, 1)))
    peak_by_body = {name: round(float(peak[i]), 3) for i, name in enumerate(sensor.body_names)}
    touching = sorted(n for n, f in peak_by_body.items() if f > args_cli.threshold)
    check("the stand measured contact at all", bool(touching), f"max {max(peak_by_body.values()):.2f} N")

    feet = {n for n in robot.body_names if n.endswith("_foot")}
    blind = [n for n in touching if n not in selected and n not in feet]
    check("no contacting body is invisible to the penalty stack", not blind,
          f"unpunished: {blind}" if blind else f"touching: {touching}")

    # Bodies that carry no collider on either side cannot be the penetrating side, so a penalty
    # that names them is a term with nothing to read.
    no_collider = sorted(n for n in robot.body_names
                         if not usd_bodies.get(n) and not urdf_links.get(n))
    print(f"  no collider (neither USD nor URDF): {no_collider}")

    # --- the table: USD vs URDF, with what each body does at runtime --------------------------
    print(f"{'body':<18} {'usd approx':<12} {'usd verts':>9} {'usd extent':<24} "
          f"{'urdf extent':<24} {'penal':<6} {'peak N':>8}")
    report = {"task": args_cli.task, "family": family, "usd": str(usd_path), "urdf": str(urdf),
              "robot_prim": str(robot_prim.GetPath()), "steps": args_cli.steps,
              "threshold": args_cli.threshold, "terms": terms, "no_collider": no_collider,
              "touching": touching, "blind": blind, "bodies": {}}
    for body in sorted(set(sensor.body_names)):
        prims = usd_bodies.get(body, [])
        mesh = urdf_links.get(body)
        extent = obj_extent(mesh) if mesh else [0.0, 0.0, 0.0]
        if not prims and not mesh:
            continue
        usd_extent = prims[0]["extent"] if prims else [0.0, 0.0, 0.0]
        match = (max(abs(a - b) for a, b in zip(usd_extent, extent)) < 0.01) if mesh and prims else False
        row = {"usd_prims": prims, "urdf_mesh": str(mesh) if mesh else None,
               "urdf_extent": extent, "extent_match": match, "penalised": body in selected,
               "peak_n": peak_by_body.get(body)}
        report["bodies"][body] = row
        print(f"{body:<18} {(prims[0]['approximation'] if prims else '-'):<12} "
              f"{(prims[0]['points'] if prims else 0):>9} {str(usd_extent):<24} {str(extent):<24} "
              f"{('yes' if body in selected else 'no'):<6} {peak_by_body.get(body, 0.0):>8}")

    if args_cli.json:
        import json
        pathlib.Path(args_cli.json).write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(f"report written: {args_cli.json}")

    env.close()
    if PROBLEMS:
        print(f"CONTACT_OWNERSHIP_FAILED ({len(PROBLEMS)})")
        return 1
    print("CONTACT_OWNERSHIP_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
