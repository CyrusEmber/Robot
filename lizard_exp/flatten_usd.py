"""Flatten URDF-importer-3.0 USD hierarchy (IsaacLab issue #5126 workaround).

The Isaac Sim 6.0 URDF importer nests every link prim under the base link
prim (/robot/Geometry/base/child_link/...). PhysX rigid-body-view pattern
matching, which Isaac Lab contact sensors rely on, only resolves sibling
bodies, so the articulation collapses to a single body at runtime.

This script reparents every rigid-body prim to be a sibling of the base
link (v2.x-style flat hierarchy), then rewrites all path references under
the geometry scope to the new flat paths (Sdf does not fix up relationship
targets for these edits).

Usage:
    python flatten_usd.py <robot.usda>
"""

import re
import sys

from pxr import Sdf, Usd, UsdPhysics


def find_bodies(stage):
    bodies = []
    root_body = None
    for prim in stage.Traverse():
        if not prim.HasAPI(UsdPhysics.RigidBodyAPI):
            continue
        bodies.append(prim.GetPath())
        if prim.HasAPI(UsdPhysics.ArticulationRootAPI):
            root_body = prim.GetPath()
    return bodies, root_body


def flatten_usd(usd_path):
    layer = Sdf.Layer.FindOrOpen(usd_path)
    if layer is None:
        raise FileNotFoundError(f"Cannot open USD layer: {usd_path}")
    stage = Usd.Stage.Open(layer)

    bodies, root_body = find_bodies(stage)
    if root_body is None:
        raise ValueError(f"No articulation root body found in {usd_path}")
    target_parent = root_body.GetParentPath()

    moved = 0
    while True:
        bodies, root_body = find_bodies(stage)
        target_parent = root_body.GetParentPath()
        nested = [b for b in bodies if b != root_body and b.GetParentPath() != target_parent]
        if not nested:
            break
        # move one prim per iteration: its subtree follows, paths of the
        # remaining nested bodies are recomputed on the next pass;
        # index -1 appends at the end of the target parent's child list
        batch = Sdf.BatchNamespaceEdit()
        batch.Add(Sdf.NamespaceEdit.Reparent(nested[0], target_parent, -1))
        layer.Apply(batch)
        moved += 1

    layer.Save()
    _fixup_path_references(usd_path, target_parent)
    print(f"Flattened {usd_path}: moved {moved} bodies to siblings of {root_body.name}")
    return moved


def _fixup_path_references(usd_path, scope_path):
    # after reparenting, joint body0/body1 rels still point at the old nested
    # paths; rewrite every path reference under the geometry scope to the
    # flat leaf path (all bodies are now direct children of the scope)
    with open(usd_path, encoding="utf-8") as f:
        src = f.read()

    pattern = re.compile(r"<(" + re.escape(str(scope_path)) + r"/[^>]+)>")

    def flatten_ref(match):
        leaf = match.group(1).rsplit("/", 1)[-1]
        return f"<{scope_path}/{leaf}>"

    fixed = pattern.sub(flatten_ref, src)
    if fixed != src:
        with open(usd_path, "w", encoding="utf-8") as f:
            f.write(fixed)


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python flatten_usd.py <robot.usda>")
        sys.exit(1)
    flatten_usd(sys.argv[1])
