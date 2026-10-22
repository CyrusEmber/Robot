# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

# -*- coding: utf-8 -*-
"""Author the lizard2 default-stance candidate from the SSOT blend, and leave the SSOT alone.

Reads ``lizard_stance.blend``, writes ``lizard2_stance_candidate.blend`` plus four orthographic
renderings. Acceptance order: ``acceptance/records/2026-10-08-lizard2-blender-body-candidate.md``.

The requirement is a *direction* table, not an angle table (方向从近端关节指向远端关节):

    front upper (humerus, ``*_haa.head -> *_hfe.head``)   backward + laterally abducted
    front lower (forearm, ``*_hfe.head -> *_kfe.head``)   forward, tilted, not vertical
    rear upper  (femur,   ``*_haa.head -> *_hfe.head``)   forward  + laterally abducted
    rear lower  (shank,   ``*_hfe.head -> *_kfe.head``)   backward, tilted, not vertical

Only the vertical (hip yaw) axis can put fore-aft into a sprawled leg, so the fore/hind contrast
requires baking a leg-plane yaw. The pose is therefore parameterised per leg as:

    theta  [deg] : the baked leg-plane yaw. Azimuth of an in-plane segment = 90 - theta for the
                   upper segment and theta - 90 for the lower one, so a front leg with theta > 0
                   points its humerus backward, and a rear leg with theta < 0 points its femur
                   forward. Positive theta tilts toward the tail, negative toward the head.
    phi    [deg] : the ABSOLUTE in-plane depression of one segment, measured from horizontal
                   inside the leg's own flexion plane (positive = pointing down). Not a joint
                   angle: the joint's baked rest angle is the difference of consecutive phis
                   (phi2 - phi1 = the elbow/knee fold; phi3 - phi2 = the ankle). Naming a phi
                   absolute is what makes the direction table checkable -- a relative-angle
                   parameterisation would let the four directions drift while the bones look fine.
    phi3   [deg] : the metatarsal segment (``*_kfe.head -> *_foot.head``). The record gives no
                   direction requirement for it; phi3 = phi2 puts the ankle at its zero fold.

Consequences worth stating before reading the numbers (they are the reason this is a *candidate*):
the hinge axes ``haa/hfe/kfe`` are world-X in the frozen asset and must follow the baked yaw to
stay perpendicular to the flexion plane (``generate_urdf.py``'s ``lizard2_candidate`` spec derives
them from this pose); and the baked yaw moves the stance off the middle of the hip's travel, so
the fore/aft sweep around it is asymmetric (q = 0 stays the numeric midpoint of [-0.6, +0.6], the
body direction it maps to changes).

Only the left legs are authored; each right leg is rebuilt as the exact mirror of its left
counterpart about the body mid-plane, at the mesh-data level, so the mirror residual is zero by
construction instead of "small". Meshes are rigidly bone-parented: editing a bone's rest head/tail
carries its meshes with it, and the exporter reads ``matrix_world @ bone.head_local``, so the pose
must be baked into rest geometry (a pose-mode rotation would leave the export untouched).

Run:
    E:\\SteamLibrary\\steamapps\\common\\Blender\\blender.exe --background \\
        --python rl_exp/blender/scripts/lizard2_stance_candidate.py
"""

import importlib.util
import math
import os
import sys

import bmesh
import bpy
from mathutils import Matrix, Vector

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_file_binding_spec = importlib.util.spec_from_file_location(
    "file_binding", os.path.join(_SCRIPT_DIR, "..", "..", "tools", "runrecord", "binding.py"))
file_binding = importlib.util.module_from_spec(_file_binding_spec)
_file_binding_spec.loader.exec_module(file_binding)
#: The ``.blend`` assets stay one level up: this folder holds scripts, not assets.
_ASSET_DIR = os.path.dirname(_SCRIPT_DIR)
BLEND_IN = os.path.join(_ASSET_DIR, "lizard_stance.blend")
BLEND_OUT = os.path.join(_ASSET_DIR, "lizard2_stance_candidate.blend")

# Engineering trial values, not measurements: the r1 record's §4 has the default stance as "not
# formed", so there is no animal number to copy. Only the LEFT legs are authored here.
FRONT = {"theta": 20.0, "phi": (40.0, 115.0, 115.0)}
REAR = {"theta": -20.0, "phi": (40.0, 115.0, 115.0)}
#: body mid-plane [m]. 0.0 is the URDF mirror convention (left's y negated) and the body's own
#: midline; the frozen front pair mirrors about y = -0.00194, so this moves it by ~2 mm.
MIRROR_Y = 0.0

LEG_BONES = ("haa", "hfe", "kfe", "foot")
LEFT_LEGS = {"lf": FRONT, "rl": REAR}
#: right leg -> the left counterpart it is rebuilt from
MIRROR_OF = {"rf": "lf", "rr": "rl"}

TOL = 1e-5
RENDER_VIEWS = (
    ("side", Vector((-1.80, 0.0, -0.40)), Vector((-1.80, 6.0, -0.40)), 4.40, (1400, 800)),
    ("side_legs", Vector((-1.35, 0.0, -0.60)), Vector((-1.35, 6.0, -0.60)), 2.30, (1400, 800)),
    ("front", Vector((-0.80, 0.0, -0.36)), Vector((6.0, 0.0, -0.36)), 2.80, (1400, 800)),
    ("top", Vector((-1.80, 0.0, -0.40)), Vector((-1.80, 0.0, 6.0)), 4.50, (1400, 800)),
)


def seg_dir(phi, theta):
    """Unit world direction of an in-plane segment: ``phi`` depression [deg], ``theta`` yaw [deg].

    In-plane the segment is ``(0, cos phi, -sin phi)`` with +y outward on the left; the yaw rotates
    it about the vertical (``dir_world = (-cos phi sin theta, cos phi cos theta, -sin phi)``).
    """
    p, t = math.radians(phi), math.radians(theta)
    return Vector((-math.cos(p) * math.sin(t), math.cos(p) * math.cos(t), -math.sin(p)))


def side_tilt(direction):
    """Fore-aft tilt of a segment away from vertical [deg]; + = forward, - = backward."""
    return math.degrees(math.atan2(direction.x, -direction.z))


def load():
    bpy.ops.wm.open_mainfile(filepath=BLEND_IN)
    scene = bpy.context.scene
    arm = next(o for o in scene.objects if o.type == "ARMATURE")
    arm_mw = arm.matrix_world.copy()
    bones = {b.name: b for b in arm.data.bones}
    on_bone = {}
    for obj in scene.objects:
        if obj.type == "MESH" and obj.parent_type == "BONE":
            on_bone.setdefault(obj.parent_bone, []).append(obj)
    return scene, arm, arm_mw, bones, on_bone


def leg_roles(arm_mw, bones, on_bone):
    """``{leg: {joint: (ball_or_pad, segment_or_None)}}``, derived from the current blend.

    The joint marker is the mesh whose object origin sits on the bone's head; the segment mesh is
    whatever else is parented to that bone (``kfe`` has none -- the metatarsal carries no cylinder).
    Deriving this beats re-using ``fix_bones.py``'s LEG_MAP, which names pre-v8 meshes that no
    longer sit where its table says.
    """
    roles = {}
    for leg in ("lf", "rf", "rl", "rr"):
        entry = {}
        for joint in LEG_BONES:
            bone = bones["%s_%s" % (leg, joint)]
            head = arm_mw @ bone.head_local
            objs = on_bone.get("%s_%s" % (leg, joint), [])
            marker = [o for o in objs if (o.matrix_world.translation - head).length < 1e-4]
            assert len(marker) == 1, (leg, joint, [o.name for o in objs], "joint marker not unique")
            rest = [o for o in objs if o is not marker[0]]
            if joint == "foot":
                assert not rest, (leg, joint, "the foot bone carried a segment mesh")
                entry[joint] = (marker[0], None)
            else:
                entry[joint] = (marker[0], rest[0] if rest else None)
        count = sum(1 for joint in LEG_BONES for obj in entry[joint] if obj is not None)
        assert count == 6, (leg, count, "expected 3 joint markers + 2 segments + 1 pad")
        roles[leg] = entry
    return roles


def rigid_about(pivot_old, pivot_new, rotation):
    """World transform ``p -> pivot_new + R (p - pivot_old)``."""
    return Matrix.Translation(pivot_new) @ rotation.to_matrix().to_4x4() @ Matrix.Translation(-pivot_old)


def main():
    scene, arm, arm_mw, bones, on_bone = load()
    roles = leg_roles(arm_mw, bones, on_bone)
    arm_inv = arm_mw.inverted()

    old_head = {n: (arm_mw @ b.head_local).copy() for n, b in bones.items()}
    old_world = {o.name: o.matrix_world.copy() for o in scene.objects if o.type == "MESH"}

    # ---- left legs: new joint centres and the per-bone rigid transform that carries the meshes
    new_head = dict(old_head)
    leg_xform = {}
    for leg, params in LEFT_LEGS.items():
        phi = params["phi"]
        dirs = [seg_dir(phi[0], params["theta"]), seg_dir(phi[1], params["theta"]),
                seg_dir(phi[2], params["theta"])]
        pts = [old_head["%s_haa" % leg]]
        for i in range(3):
            length = (old_head["%s_%s" % (leg, LEG_BONES[i + 1])]
                      - old_head["%s_%s" % (leg, LEG_BONES[i])]).length
            pts.append(pts[-1] + dirs[i] * length)
        for i, joint in enumerate(LEG_BONES):
            new_head["%s_%s" % (leg, joint)] = pts[i].copy()

        xform = {}
        for i, joint in enumerate(LEG_BONES):
            bone = "%s_%s" % (leg, joint)
            if joint == "foot":
                # the pad keeps its orientation (its sole is level) and only moves to the new centre
                xform[bone] = Matrix.Translation(pts[3] - old_head[bone])
            else:
                old_dir = old_head["%s_%s" % (leg, LEG_BONES[i + 1])] - old_head[bone]
                xform[bone] = rigid_about(old_head[bone], pts[i], old_dir.rotation_difference(dirs[i]))
        leg_xform[leg] = xform

    # ---- rear pads: the SSOT's two rear pad meshes sit 4.41 mm shallower (bottom relative to their
    # own joint origin) than the two front ones, whose bottom matches the frozen asset's collision
    # hulls (-0.079023) -- the 2026-09-28 rl hull repair went into the frozen meshes, never back
    # into the blend, so regenerating from the blend silently reverts it. Drop the left-rear pad's
    # geometry by the measured difference (local translation: the joint origin, i.e. the bone head,
    # does not move) so the four contact planes coincide. Touches no joint centre, bone length or
    # segment direction -- it is the pad's depth, reported on its own line in the record.
    mirror = Matrix.Diagonal((1.0, -1.0, 1.0, 1.0)).to_4x4()
    mirror.translation = Vector((0.0, 2.0 * MIRROR_Y, 0.0))
    for leg, src in MIRROR_OF.items():
        for joint in LEG_BONES:
            new_head["%s_%s" % (leg, joint)] = mirror @ new_head["%s_%s" % (src, joint)]

    def pad_bottom(obj):
        """Pad sole height relative to its own object origin (the joint centre)."""
        return min((obj.matrix_world @ v.co).z for v in obj.data.vertices) - obj.matrix_world.translation.z

    front_pad, rear_pad = roles["lf"]["foot"][0], roles["rl"]["foot"][0]
    pad_gap = pad_bottom(front_pad) - pad_bottom(rear_pad)
    print("rear pad depth gap = %+.6f m (front %.6f, rear %.6f)"
          % (pad_gap, pad_bottom(front_pad), pad_bottom(rear_pad)))
    if abs(pad_gap) > 1e-4:
        drop = rear_pad.matrix_world.to_3x3().inverted() @ Vector((0.0, 0.0, pad_gap))
        for vert in rear_pad.data.vertices:
            vert.co += drop
        rear_pad.data.update()
        print("  rear pad moved %+.6f m along world z (local %s)"
              % (pad_gap, tuple(round(v, 6) for v in drop)))

    # ---- bone rest data first (editing a bone carries its meshes), meshes placed afterwards
    local_up = arm_inv.to_3x3()
    bpy.context.view_layer.objects.active = arm
    bpy.ops.object.mode_set(mode="EDIT")
    eb = arm.data.edit_bones
    for leg in ("lf", "rf", "rl", "rr"):
        for i, joint in enumerate(LEG_BONES):
            bone = eb["%s_%s" % (leg, joint)]
            bone.head = arm_inv @ new_head["%s_%s" % (leg, joint)]
            if joint == "foot":
                # build_rig.py's convention: the foot bone points outward (+y on the left)
                outward = Vector((0.0, 0.1 if leg.startswith("l") else -0.1, 0.0))
                bone.tail = bone.head + (local_up @ outward)
            else:
                bone.tail = arm_inv @ new_head["%s_%s" % (leg, LEG_BONES[i + 1])]
    bpy.ops.object.mode_set(mode="OBJECT")
    bpy.context.view_layer.update()

    # ---- left meshes
    for leg, xform in leg_xform.items():
        for joint in LEG_BONES:
            marker, segment = roles[leg][joint]
            for obj in (o for o in (marker, segment) if o is not None):
                obj.matrix_world = xform["%s_%s" % (leg, joint)] @ old_world[obj.name]

    # ---- right meshes: rebuilt as the exact mirror of the left counterpart, data level.
    # geometry(dst) = MIRROR @ geometry(src); the object matrix must stay right-handed, so the fixed
    # reflection R = diag(1,-1,1) rides on the DATA (its winding reversed to keep outward normals)
    # and the product MIRROR @ left @ R stays det > 0.
    local_reflection = Matrix.Diagonal((1.0, -1.0, 1.0, 1.0)).to_4x4()
    for leg, src in MIRROR_OF.items():
        for joint in LEG_BONES:
            src_marker, src_segment = roles[src][joint]
            for src_obj, dst_obj in zip((src_marker, src_segment), roles[leg][joint]):
                if src_obj is None:
                    continue
                mirrored = src_obj.data.copy()
                for vert in mirrored.vertices:
                    vert.co.y = -vert.co.y
                bm = bmesh.new()
                bm.from_mesh(mirrored)
                bmesh.ops.reverse_faces(bm, faces=bm.faces[:])
                bm.to_mesh(mirrored)
                bm.free()
                mirrored.update()
                dst_obj.data = mirrored
                dst_obj.matrix_world = mirror @ src_obj.matrix_world @ local_reflection
    bpy.context.view_layer.update()

    # ---- self-check on the scene as it now stands
    fails = []
    joint_gap = 0.0
    for leg in ("lf", "rf", "rl", "rr"):
        for joint in LEG_BONES:
            got = arm.matrix_world @ arm.data.bones["%s_%s" % (leg, joint)].head_local
            want = new_head["%s_%s" % (leg, joint)]
            joint_gap = max(joint_gap, (got - want).length)
            if (got - want).length > TOL:
                fails.append("bone %s_%s off by %.2e" % (leg, joint, (got - want).length))
            obj = roles[leg][joint][0]
            if (obj.matrix_world.translation - want).length > TOL:
                fails.append("marker %s off by %.2e" % (obj.name, (obj.matrix_world.translation - want).length))

    print("=== LEG DIRECTION TABLE (world; +tilt = forward) ===")
    print("%-4s %-12s %8s %8s %9s %9s %10s" % ("leg", "segment", "elev[deg]", "azim[deg]", "tilt[deg]", "len[m]", "sole z"))
    for leg in ("lf", "rf", "rl", "rr"):
        for i, joint in enumerate(("haa", "hfe", "kfe")):
            a, b = new_head["%s_%s" % (leg, joint)], new_head["%s_%s" % (leg, LEG_BONES[i + 1])]
            d = b - a
            horiz = math.hypot(d.x, d.y)
            print("%-4s %-12s %8.2f %8.2f %9.2f %9.5f" % (
                leg, "%s->%s" % (LEG_BONES[i], LEG_BONES[i + 1]), math.degrees(math.atan2(d.z, horiz)),
                math.degrees(math.atan2(d.y, d.x)), side_tilt(d), d.length))
        pad = roles[leg]["foot"][0]
        print("%-4s %-12s %8s %8s %9s %9s %10.5f" % (leg, "pad sole", "-", "-", "-", "-",
                                                     min((pad.matrix_world @ v.co).z for v in pad.data.vertices)))

    print("=== MIRROR RESIDUAL (right vs left reflected about y=%.5f) ===" % MIRROR_Y)
    joint_res, vert_res = 0.0, 0.0
    for leg, src in MIRROR_OF.items():
        for joint in LEG_BONES:
            lhs = new_head["%s_%s" % (leg, joint)]
            rhs = new_head["%s_%s" % (src, joint)]
            rhs = Vector((rhs.x, 2.0 * MIRROR_Y - rhs.y, rhs.z))
            joint_res = max(joint_res, (lhs - rhs).length)
            for lhs_obj, rhs_obj in zip(roles[leg][joint], roles[src][joint]):
                if rhs_obj is None:
                    continue
                assert len(lhs_obj.data.vertices) == len(rhs_obj.data.vertices), (lhs_obj.name, rhs_obj.name)
                for ov, tv in zip(lhs_obj.data.vertices, rhs_obj.data.vertices):
                    p_l = lhs_obj.matrix_world @ ov.co
                    p_r = rhs_obj.matrix_world @ tv.co
                    p_r = Vector((p_r.x, 2.0 * MIRROR_Y - p_r.y, p_r.z))
                    vert_res = max(vert_res, (p_l - p_r).length)
    print("  joint centres %.3e m | mesh vertices %.3e m (12 meshes/right pair, vertex order preserved)"
          % (joint_res, vert_res))
    if max(joint_res, vert_res) > 1e-5:
        fails.append("mirror residual joint %.3e vertex %.3e" % (joint_res, vert_res))

    neg = [o.name for o in scene.objects if o.type == "MESH" and o.matrix_world.determinant() < 0.0]
    print("left-handed mesh matrices: %s | bone-head placement residual: %.3e m" % (neg or "none", joint_gap))
    if neg:
        fails.append("negative-determinant objects %s" % neg)

    print("=== PAD SOLE (contact patch) ===")
    soles = []
    for leg in ("lf", "rf", "rl", "rr"):
        pad = roles[leg]["foot"][0]
        world = pad.matrix_world
        wco = [world @ v.co for v in pad.data.vertices]
        bottom = min(c.z for c in wco)
        # the asset's sole is a curved cap (a domed hull, not a flat face), so the patch is read as
        # the lowest 2 mm band -- the same band check_leg_reachability.py fits its facing normal to
        band = [c for c in wco if c.z <= bottom + 0.002]
        extent = max(max(c.x for c in band) - min(c.x for c in band),
                     max(c.y for c in band) - min(c.y for c in band))
        # a left pad is only ever TRANSLATED, so its orientation must come out bit-identical; a
        # right pad's is the exact mirror of its left counterpart (asserted vertex-wise below), so
        # the delta printed for it is the source pad's own mirror tilt -- reported, not asserted
        delta = max(abs(world.to_3x3()[i][j] - old_world[pad.name].to_3x3()[i][j])
                    for i in range(3) for j in range(3))
        soles.append(bottom)
        print("  %-3s sole z=%+.6f | lowest-2mm band spans %.3f m horizontally (level within %.2f deg) "
              "| pad rotation delta %.1e" % (leg, bottom, extent, math.degrees(math.atan2(0.002, extent)), delta))
        if leg.startswith("l") and delta > 1e-6:
            fails.append("%s pad rotated (delta %.2e) -- its sole is no longer the source's sole"
                         % (leg, delta))
    print("  sole z spread = %.3e m" % (max(soles) - min(soles)))
    if max(soles) - min(soles) > 1e-4:
        fails.append("soles not co-planar: %s" % soles)

    bpy.ops.wm.save_as_mainfile(filepath=BLEND_OUT)
    print("saved=%s" % BLEND_OUT)

    render(scene)
    print("=== SELF-CHECK %s ===" % ("FAILED" if fails else "OK"))
    for line in fails:
        print("  FAIL %s" % line)
    print("=== DONE ===")


def render(scene):
    """Orthographic workbench renderings beside the candidate: the review evidence the record asks for."""
    scene.render.engine = "BLENDER_WORKBENCH"
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    cam_data = bpy.data.cameras.new("candidate_view")
    cam_data.type = "ORTHO"
    cam = bpy.data.objects.new("candidate_view", cam_data)
    scene.collection.objects.link(cam)
    scene.camera = cam
    for name, position, target, scale, resolution in RENDER_VIEWS:
        cam.location = position
        cam.rotation_euler = (target - position).to_track_quat("-Z", "Y").to_euler()
        cam_data.ortho_scale = scale
        scene.render.resolution_x, scene.render.resolution_y = resolution
        scene.render.filepath = os.path.join(_ASSET_DIR, "lizard2_stance_candidate_%s.png" % name)
        bpy.ops.render.render(write_still=True)
        print("rendered=%s" % scene.render.filepath)


def contract_self_check(without_fix=False):
    """Run the real exporter on old source and memory-only palm topology; never author assets."""
    import hashlib
    import pathlib

    # Include source, candidate assets, exported meshes and frozen declarations in the no-write check.
    root = pathlib.Path(_SCRIPT_DIR).parents[1]
    watched = [root / name for name in ("blender", "assets", "versions")]

    def snapshot():
        return {str(p): file_binding.sha256_file(p)
                for directory in watched for p in directory.rglob("*") if p.is_file()}

    before = snapshot()

    def no_write(event, args):
        if event == "open":
            mode, flags = args[1:3]
            if (mode and any(c in mode for c in "wax+")) or (flags and flags & (
                    os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND)):
                raise AssertionError(f"contract probe attempted write: {args[0]}")
        if event in ("os.remove", "os.rename", "os.mkdir", "os.rmdir"):
            raise AssertionError(f"contract probe attempted {event}: {args}")

    sys.dont_write_bytecode = True
    sys.addaudithook(no_write)
    exporter = os.path.join(_SCRIPT_DIR, "generate_urdf.py")
    code = pathlib.Path(exporter).read_text(encoding="utf-8")
    if without_fix:
        # Narrow inverse in memory: exactly the consumer validation call, no working-tree reset.
        original = "binding = validate_build_contract(bones, SPEC)"
        assert code.count(original) == 1
        code = code.replace(original, "binding = {}")

    def consume(robot, memory=False):
        old_argv = sys.argv
        sys.argv = [exporter, "--", "--robot", robot, "--contract_check"]
        if memory:
            sys.argv.append("--memory_scene")
        namespace = {"__file__": exporter, "__name__": "__main__"}
        try:
            try:
                exec(compile(code, exporter, "exec"), namespace)
            except SystemExit as exc:
                assert exc.code == 0, exc.code
        finally:
            sys.argv = old_argv
        return namespace

    # The existing geometry-role reader and exporter both consume the real old .blend, read-only.
    scene, arm, arm_mw, bones, on_bone = load()
    assert len(leg_roles(arm_mw, bones, on_bone)) == 4
    for robot in ("lizard", "lizard2", "lizard2_candidate", "lizard2_candidate_split"):
        exported = consume(robot, memory=True)
        if robot == "lizard2_candidate_split":
            for leg, bound in exported["binding"].items():
                assert tuple(bound["roles"]) == exported["leg_names"].CHAIN_ROOTS
                for role, item in bound["roles"].items():
                    assert item["source_bone"] == (None if role == "hip" else f"{leg}_{role}")
                assert bound["end_link"] == exported["leg_names"].end_link(
                    leg, exported["leg_names"].SPLIT_NAMING)
    try:
        consume("lizard2_palm_contract", memory=True)
    except ValueError as exc:
        print("NEGATIVE old long source under palm:", exc)
    else:
        raise AssertionError("old long source accepted under palm; distal silently discarded")

    # Fresh, meshless, arbitrary-coordinate armature: topology contract ONLY, never candidate geometry.
    ns = consume("lizard2", memory=True)
    names = ns["leg_names"]

    def fixture(change=None):
        data = bpy.data.armatures.new("palm_contract_only")
        sample = bpy.data.objects.new("palm_contract_only", data)
        scene.collection.objects.link(sample)
        for obj in list(scene.objects):
            if obj.type == "ARMATURE" and obj is not sample:
                scene.collection.objects.unlink(obj)
        bpy.context.view_layer.objects.active = sample
        sample.select_set(True)
        bpy.ops.object.mode_set(mode="EDIT")
        eb = data.edit_bones
        base = eb.new("base_link")
        base.head, base.tail = (0, 0, 0), (0, 0, 1)
        for leg in names.LEGS:
            parent = base
            for index, role in enumerate(names.roots_of(names.PALM_NAMING, leg)):
                bone = eb.new(names.link_name(leg, role))
                bone.head, bone.tail = (index + 1, 0, 0), (index + 1, 0, 1)
                bone.parent = parent
                parent = bone
        if change:
            change(eb)
        bpy.ops.object.mode_set(mode="OBJECT")
        bpy.context.view_layer.update()
        return sample

    sample = fixture()
    ns = consume("lizard2_palm_contract", memory=True)
    assert len(ns["binding"]) == 4
    for leg, binding in ns["binding"].items():
        assert len(binding["roles"]) == 4
        assert binding["end_link"] == names.end_link(leg, names.PALM_NAMING)
        assert binding["end_joint"] == binding["end_link"] + "_joint"
    print("POSITIVE memory-only four-revolute palm topology; geometry_proven=False")

    def extra(eb, name, parent):
        bone = eb.new(name)
        bone.head, bone.tail = (0, 0, 0), (0, 0, 1)
        bone.parent = eb[parent]

    cases = {
        "wrong order": lambda eb: setattr(eb["lf_elbow"], "parent", eb["base_link"]),
        "cross-leg": lambda eb: setattr(eb["lf_shoulder_swing"], "parent", eb["rl_hip_swing"]),
        "missing palm": lambda eb: eb.remove(eb["lf_wrist"]),
        "retained foot": lambda eb: extra(eb, "lf_foot", "lf_wrist"),
        "retained finger": lambda eb: extra(eb, "lf_finger", "lf_wrist"),
        "retained toe": lambda eb: extra(eb, "rl_toe", "rl_ankle"),
        "unnamed distal child": lambda eb: extra(eb, "distal_activity", "lf_wrist"),
        "mixed front/rear binding": lambda eb: setattr(eb["lf_wrist"], "name", "lf_ankle"),
    }
    for label, change in cases.items():
        fixture(change)
        try:
            consume("lizard2_palm_contract", memory=True)
        except ValueError as exc:
            print("NEGATIVE %s: %s" % (label, exc))
        else:
            raise AssertionError("malformed topology accepted: " + label)
    # Also refuse an explicit source/target mismatch before any truncating mapping.
    fixture()
    ns = consume("lizard2_palm_contract", memory=True)
    bad_spec = dict(ns["SPEC"], source_naming="shared")
    try:
        ns["validate_build_contract"](ns["bones"], bad_spec)
    except ValueError as exc:
        print("NEGATIVE source/target mismatch:", exc)
    else:
        raise AssertionError("source/target mismatch accepted")
    after = snapshot()
    assert before == after, "watched asset tree changed"
    print("P1 PASS: old consumers=3; split rename consumer=1; palm positive=1; negatives=10; "
          "asset files hashed=%d unchanged; Python writes forbidden; geometry_proven=False" % len(before))


def spatial_export_self_check(blend, build_report, output_dir, *, build_report_sha256,
                              regression_only=None):
    """Exercise the real saved-source export and prewrite rejection in Blender."""
    import json
    from pathlib import Path
    import xml.etree.ElementTree as ET
    sys.path.insert(0, str(Path(_SCRIPT_DIR).parents[1] / "tools/diagnose"))
    from artifact_paths import artifact_path

    exporter = Path(_SCRIPT_DIR) / "generate_urdf.py"
    output = Path(output_dir).resolve()
    root = Path(_SCRIPT_DIR).parents[1] / "out"
    assert root.resolve() in output.parents and not output.exists()
    report_path = artifact_path(Path(build_report).resolve())
    report = json.loads(report_path.read_text(encoding="utf-8"))
    reference = artifact_path(Path(report["candidate_urdf"]).resolve())
    blend = artifact_path(Path(blend).resolve())
    protected = {p: file_binding.sha256_file(p)
                 for directory in (report_path.parent, Path(_ASSET_DIR),
                                   Path(_SCRIPT_DIR).parents[1] / "assets",
                                   Path(_SCRIPT_DIR).parents[1] / "versions",
                                   Path(_SCRIPT_DIR).parents[1] / "lizard2_candidate")
                 for p in directory.rglob("*") if p.is_file() and p.suffix != ".py"}
    assert file_binding.sha256_file(report_path) == build_report_sha256
    code = exporter.read_text(encoding="utf-8")
    original_open = bpy.ops.wm.open_mainfile

    def consume(destination, robot="lizard2_palm_spatial", source=blend, mutate=None,
                reference_mutation=None, approved_sha=build_report_sha256):
        old_argv = sys.argv
        sys.argv = [str(exporter), "--", "--robot", robot, "--blend", str(source),
                    "--build_report", str(report_path), "--out_dir", str(destination)]
        if approved_sha is not None:
            sys.argv.extend(("--build_report_sha256", approved_sha))
        namespace = {"__file__": str(exporter), "__name__": "__main__"}
        # Replace only the load boundary: validation/export still run the normal write entry.
        def load_then_mutate(**kwargs):
            result = original_open(**kwargs)
            if reference_mutation:
                reference_mutation(namespace["REFERENCE_ROOT"])
            if mutate:
                mutate()
                bpy.context.view_layer.update()
            return result
        load_statement = "bpy.ops.wm.open_mainfile(filepath=_BLEND_IN)"
        assert code.count(load_statement) == 1
        test_code = code.replace(load_statement, "load_then_mutate(filepath=_BLEND_IN)")
        if regression_only:
            test_code = test_code.replace("os.makedirs(OUT_DIR, exist_ok=False)",
                                          "raise AssertionError('prewrite accepted ' + regression_only)")
            namespace["regression_only"] = regression_only
        namespace["load_then_mutate"] = load_then_mutate
        try:
            exec(compile(test_code, str(exporter), "exec"), namespace)
        finally:
            sys.argv = old_argv

    def reject(label, **kwargs):
        destination = output.with_name(output.name + "_negative_" + label)
        assert not destination.exists()
        try:
            consume(destination, **kwargs)
        except ValueError as exc:
            print("SPATIAL NEGATIVE %s: %s" % (label, exc))
        else:
            raise AssertionError("write entry accepted " + label)
        assert not destination.exists(), "negative created output: " + label

    def bad_mass(tree):
        tree.find("link/inertial/mass").set("value", "nan")

    def forged_report():
        # Real tampered JSON bytes; retain original externally supplied approval hash.
        # No source file mutation: replace only this report's read at the trust boundary.
        from unittest.mock import patch
        import io
        forged = dict(report, total_mass_kg=-123,
                      candidate_sha256=file_binding.sha256_file(reference),
                      candidate_blend_sha256=file_binding.sha256_file(Path(blend)),
                      candidate_files_sha256={name: file_binding.sha256_file(report_path.parent / name)
                                              for name in report["candidate_files_sha256"]})
        forged_bytes = json.dumps(forged).encode("utf-8")
        original_open_path = Path.open
        def open_path(path, mode="r", *args, **kwargs):
            if path.resolve() == report_path:
                return io.BytesIO(forged_bytes) if "b" in mode else io.StringIO(forged_bytes.decode("utf-8"))
            return original_open_path(path, mode, *args, **kwargs)
        import builtins
        original_builtin_open = builtins.open
        def builtin_open(path, mode="r", *args, **kwargs):
            if isinstance(path, (str, os.PathLike)) and Path(path).resolve() == report_path:
                return io.BytesIO(forged_bytes) if "b" in mode else io.StringIO(forged_bytes.decode("utf-8"))
            return original_builtin_open(path, mode, *args, **kwargs)
        with patch.object(Path, "open", open_path), patch.object(builtins, "open", builtin_open):
            reject("forgedreport", mutate=None)

    if regression_only:
        assert regression_only in ("forgedreport", "nonfinite_mass")
        if regression_only == "forgedreport":
            forged_report()
        else:
            reject("nonfinite_mass", reference_mutation=bad_mass)
        return

    consume(output)
    actual = ET.parse(output / "lizard2_palm_spatial.urdf").getroot()
    expected = ET.parse(reference).getroot()
    assert len(actual.findall("link")) == 31 and len(actual.findall("joint")) == 30
    def attributes(element):
        return [(node.tag, dict(node.attrib)) for node in element.iter()]
    expected_links = {node.get("name"): node for node in expected.findall("link")}
    for node in actual.findall("link"):
        assert attributes(node.find("inertial")) == attributes(expected_links[node.get("name")].find("inertial"))
    expected_joints = {node.get("name"): node for node in expected.findall("joint")}
    for node in actual.findall("joint"):
        assert attributes(node) == attributes(expected_joints[node.get("name")])
    for mesh in actual.iter("mesh"):
        assert (output / mesh.get("filename")).is_file()
    assert json.loads((output / "export.json").read_text())["mass_policy"] == "reference_full_link_inertial"
    print("SPATIAL POSITIVE: actual meshes; links=31 joints=30; full inertials/joints unchanged")

    def arm():
        return next(o for o in bpy.context.scene.objects if o.type == "ARMATURE")
    def edit(change):
        bpy.context.view_layer.objects.active = arm()
        bpy.ops.object.mode_set(mode="EDIT")
        change(arm().data.edit_bones)
        bpy.ops.object.mode_set(mode="OBJECT")
    def wrong_mesh():
        obj = next(o for o in bpy.context.scene.objects if o.type == "MESH")
        obj.parent_bone = "lf_wrist" if obj.parent_bone != "lf_wrist" else "base_link"
    def changed_geometry():
        obj = next(o for o in bpy.context.scene.objects if o.type == "MESH")
        obj.data.vertices[0].co.x += .01
        obj.data.update()
    def wrong_basis():
        arm().pose.bones["lf_shoulder_twist"].matrix_basis = Matrix.Rotation(.1, 4, "X")
    cases = {
        "missingaxis": lambda: edit(lambda eb: eb.remove(eb["lf_shoulder_twist"])),
        "mesh_ownership": wrong_mesh,
        "geometry": changed_geometry,
        "basis": wrong_basis,
        "pivot": lambda: edit(lambda eb: setattr(eb["lf_shoulder_twist"], "head", eb["lf_shoulder_twist"].head + Vector((.01, 0, 0)))),
        "body_parent": lambda: edit(lambda eb: setattr(eb["neck_pitch"], "parent", eb["base_link"])),
    }
    for label in (*cases, "wrongtarget", "wrongsource"):
        reject(label, robot="lizard2_palm_contract" if label == "wrongtarget" else "lizard2_palm_spatial",
               source=BLEND_IN if label == "wrongsource" else blend, mutate=cases.get(label))
    forged_report()
    for label, value in (("missingapproval", None), ("malformedapproval", "unknown"),
                         ("wrongapproval", "0" * 64)):
        reject(label, approved_sha=value)
    # Approved bytes authenticated above; probe declaration schema without touching disk.
    from unittest.mock import patch
    original_read = Path.read_text
    for label in ("missingdeclsource", "missingdeclurdf", "malformeddigest", "unknownactual"):
        modified = json.loads(json.dumps(report))
        declared = modified["candidate_files_sha256"]
        if label.startswith("missingdecl"):
            name = "palm_spatial.blend" if label == "missingdeclsource" else "palm_spatial.urdf"
            declared.pop(name)
            modified.pop("candidate_blend_sha256" if label == "missingdeclsource" else "candidate_sha256")
        elif label == "malformeddigest":
            declared["palm_spatial.blend"] = "unknown"
        else:
            declared["absent_source.obj"] = None
        def read(path, *args, **kwargs):
            return json.dumps(modified) if path.resolve() == report_path else original_read(path, *args, **kwargs)
        with patch.object(Path, "read_text", read):
            reject(label)
    inertial_cases = {"nonfinite_mass": bad_mass}
    for key in ("xyz", "rpy"):
        for bad in ("nan 0 0", "inf 0 0", "0 0"):
            inertial_cases[key + "_" + bad.replace(" ", "_")] = (
                lambda tree, key=key, bad=bad: tree.find("link/inertial/origin").set(key, bad))
    for key in ("ixx", "ixy", "ixz", "iyy", "iyz", "izz"):
        inertial_cases["nonfinite_" + key] = (
            lambda tree, key=key: tree.find("link/inertial/inertia").set(key, "nan"))
    inertial_cases["missing_tensor_key"] = lambda tree: tree.find("link/inertial/inertia").attrib.pop("iyz")
    inertial_cases["zero_mass"] = lambda tree: tree.find("link/inertial/mass").set("value", "0")
    for label, change in inertial_cases.items():
        reject(label, reference_mutation=change)
    # Actual writer must preserve nonzero cross terms, not merely an all-zero reference.
    sentinel = output.with_name(output.name + "_tensor_sentinel")
    def cross_terms(tree):
        tensor = tree.find("link/inertial/inertia")
        for key in ("ixy", "ixz", "iyz"):
            tensor.set(key, "0.000001")
    consume(sentinel, reference_mutation=cross_terms)
    serialized = ET.parse(sentinel / "lizard2_palm_spatial.urdf").find("link/inertial/inertia")
    assert all(serialized.get(key) == "0.000001" for key in ("ixy", "ixz", "iyz"))
    assert all(file_binding.sha256_file(p) == value for p, value in protected.items())
    results = {"status": "PASS", "positive": 2, "negatives": 16 + len(inertial_cases),
               "build_report_sha256": build_report_sha256,
               "code_sha256": {p.name: file_binding.sha256_file(p) for p in (exporter, Path(__file__))},
               "protected_files": len(protected), "protected_sha256": {str(p): h for p, h in protected.items()},
               "negative_outputs_absent": True, "nonzero_offdiagonal_writer": "PASS"}
    (output / "self_check.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
    print("SPATIAL PASS:", json.dumps({k: v for k, v in results.items() if k != "protected_sha256"}))


def palm_body75_vertical(options):
    """Rigidly repose the actual latest low-palms blend; preserve sizes and sole heights [m]."""
    import hashlib
    import json
    from pathlib import Path
    from mathutils import Quaternion
    from mathutils.bvhtree import BVHTree

    repo = Path(_ASSET_DIR).parents[1]
    tail_ground = getattr(options, "tail_ground", False)
    variant = "lizard2_palm_p2_sample_claw_all_lowered_body75_vertical"
    source = Path(_ASSET_DIR) / ((variant if tail_ground else "lizard2_palm_p2_sample_claw_all_lowered") + "/sample_neutral.blend")
    output = Path(options.output_dir).resolve()
    if output != Path(_ASSET_DIR).resolve() / (variant + ("_tail_ground" if tail_ground else "")):
        raise ValueError("body75 output must be isolated " + variant + ("_tail_ground" if tail_ground else ""))
    if not options.check_only and output.exists():
        raise FileExistsError("Refuse overwrite: " + str(output))
    protected = {p for p in Path(_ASSET_DIR).rglob("*") if p.is_file() and output not in p.parents}
    for folder in ("assets", "versions", "lizard2_candidate", "meshes"):
        protected.update(p for p in (repo / "rl_exp" / folder).rglob("*") if p.is_file())
    def hashes():
        return {str(p.relative_to(repo)): file_binding.sha256_file(p) for p in sorted(protected)}
    before_hashes = hashes()
    bpy.ops.wm.open_mainfile(filepath=str(source))
    scene = bpy.context.scene
    arm = next(o for o in scene.objects if o.type == "ARMATURE")
    mw = arm.matrix_world.copy()
    inv = mw.inverted()
    def vertices(obj):
        evaluated = obj.evaluated_get(bpy.context.evaluated_depsgraph_get())
        mesh = evaluated.to_mesh()
        try:
            return [evaluated.matrix_world @ v.co for v in mesh.vertices]
        finally:
            evaluated.to_mesh_clear()
    def center(points):
        return sum(points, Vector()) / len(points)
    def eps(points):
        return 64 * 2 ** -23 * max(1.0, *(abs(x) for p in points for x in p))
    def ends(name):
        b = arm.data.bones[name]
        return mw @ b.head_local, mw @ b.tail_local
    def cap_groups(obj, direction):
        groups = [list(f.vertices) for f in obj.data.polygons if len(f.vertices) > 4]
        assert len(groups) == 2, "Expected two physical cylinder caps"
        v = vertices(obj)
        return sorted(groups, key=lambda ids: center([v[i] for i in ids]).dot(direction))
    reflection = Matrix.Diagonal((1, -1, 1, 1))
    old_bones = {b.name: (*ends(b.name), b.matrix_local.copy(), b.parent.name if b.parent else None)
                 for b in arm.data.bones}
    nonleg_bones = [n for n in old_bones if not n.startswith(("lf_", "rf_", "rl_", "rr_"))]
    old_basis = {n: arm.pose.bones[n].matrix_basis.copy() for n in nonleg_bones}
    evaluated_arm = arm.evaluated_get(bpy.context.evaluated_depsgraph_get())
    old_pose = {n: (evaluated_arm.matrix_world @ evaluated_arm.pose.bones[n].head,
                    evaluated_arm.matrix_world @ evaluated_arm.pose.bones[n].tail,
                    evaluated_arm.matrix_world @ evaluated_arm.pose.bones[n].matrix)
                for n in nonleg_bones}
    old_vertices = {o.name: vertices(o) for o in scene.objects if o.type == "MESH"}
    objects = {o.name: o for o in scene.objects if o.type == "MESH"}
    old_world = {n: o.matrix_world.copy() for n, o in objects.items()}
    bindings = {n: (o.parent, o.parent_type, o.parent_bone) for n, o in objects.items()}
    roots = [b.name for b in arm.data.bones if b.parent is None]
    assert roots == ["base_link"], "Body reference must be actual unique root base_link"
    samples = {}
    for leg in ("lf", "rf", "rl", "rr"):
        roles = ("shoulder_swing", "shoulder_abduct", "elbow", "wrist") if leg.endswith("f") else (
            "hip_swing", "hip_abduct", "knee", "ankle")
        names = [leg + "_" + role for role in roles]
        attached = [[o for o in objects.values() if o.parent_bone == name] for name in names]
        palm = next(o for o in attached[3] if len(o.data.vertices) == 72)
        cylinders = [next(o for o in attached[i] if sum(len(f.vertices) > 4 for f in o.data.polygons) == 2) for i in (1, 2)]
        points = [ends(names[i])[0] for i in (1, 2, 3)]
        groups = [cap_groups(o, points[i + 1] - points[i]) for i, o in enumerate(cylinders)]
        samples[leg] = {"names": names, "palm": palm.name, "cylinders": [o.name for o in cylinders],
                        "caps": groups, "old_points": points, "attached": [[o.name for o in row] for row in attached]}
    soles = {leg: min(p.z for p in old_vertices[s["palm"]]) for leg, s in samples.items()}
    ground = -.9711321443319321 if tail_ground else sum(soles.values()) / 4
    old_height = old_bones["base_link"][0].z - ground
    assert old_height > 0
    def grounded_tail():
        """Fit actual evaluated 3D support faces, then bake only the six tail frames."""
        nonlocal arm, scene, objects
        evaluated = arm.evaluated_get(bpy.context.evaluated_depsgraph_get())
        actual_frames = {b.name: evaluated.matrix_world @ evaluated.pose.bones[b.name].matrix
                         for b in arm.data.bones}
        tail_names = [b.name for b in arm.data.bones if b.name.startswith("tail")]
        pitch = [n for n in tail_names if n.endswith("pitch")]
        assert pitch == ["tail1_pitch", "tail2_pitch", "tail3_pitch"]
        source_frames = {n: tuple(v.copy() for v in old_pose[n]) for n in tail_names}
        source_channels = {b.name: b.matrix_basis.copy() for b in arm.pose.bones}
        source_topology = {n: ([tuple(e.vertices) for e in o.data.edges],
                               [tuple(f.vertices) for f in o.data.polygons],
                               [v.co.copy() for v in o.data.vertices]) for n, o in objects.items()}
        attached = {n: [key for key in objects if bindings[key][2] == n] for n in tail_names}
        cylinders = {n: next(key for key in attached[n]
                      if sum(len(f.vertices) > 4 for f in objects[key].data.polygons) == 2) for n in pitch}
        bound = eps([p for n in objects for p in old_vertices[n]])
        candidates = {}
        face_evidence = {}
        down = Vector((0, 0, -1))
        for n in pitch:
            h, t, frame = source_frames[n]
            axis = (t - h).normalized()
            azimuth = math.atan2(axis.y, axis.x)
            up = (Vector((0, 0, 1)) - axis * axis.z).normalized()
            side = axis.cross(up).normalized()
            bm = bmesh.new()
            for p in old_vertices[cylinders[n]]:
                bm.verts.new(p - h)
            bm.verts.ensure_lookup_table()
            bmesh.ops.convex_hull(bm, input=list(bm.verts), use_existing_faces=False)
            bm.normal_update()
            rows = []
            for face in bm.faces:
                normal = face.normal.copy()
                if normal.dot(up) >= 0:
                    continue
                roll = math.degrees(math.atan2(normal.dot(side), -normal.dot(up)))
                if abs(roll) > 15:
                    continue
                rotation = normal.rotation_difference(down)
                direction = rotation @ axis
                yaw = azimuth - math.atan2(direction.y, direction.x)
                rotation = Quaternion((0, 0, 1), yaw) @ rotation
                direction = rotation @ axis
                angle = math.degrees(math.atan2(direction.z, math.hypot(direction.x, direction.y)))
                if not -20 < angle < 0:
                    continue
                local = [rotation @ (p - h) for key in attached[n] for p in old_vertices[key]]
                clearance = -min(p.z for p in local)
                cv = [rotation @ (p - h) for p in old_vertices[cylinders[n]]]
                near = [p for p in cv if abs(p.z + clearance) <= bound]
                span = max((p.dot(direction) for p in near), default=0) - min((p.dot(direction) for p in near), default=0)
                # A true face/edge has axial extent, unlike a lone tip; no pass-fraction threshold.
                if len(near) < 2 or span <= bound:
                    continue
                if any(abs(row["angle_deg"] - angle) < 1e-4 and abs(row["roll_deg"] - roll) < 1e-4 for row in rows):
                    continue
                rows.append({"rotation": rotation, "angle_deg": angle, "roll_deg": roll,
                             "head": clearance, "tip": clearance + arm.data.bones[n].length * direction.z,
                             "span_m": span, "normal": list(normal)})
            bm.free()
            candidates[n] = rows
            face_evidence[n] = [{k: v for k, v in row.items() if k != "rotation"} for row in rows]
        bridge = "tail3_yaw"
        bridge_axis = (source_frames[bridge][1] - source_frames[bridge][0]).normalized()
        bridge_length = arm.data.bones[bridge].length
        feasible = []
        for a in candidates[pitch[1]]:
            for z in candidates[pitch[2]]:
                dz = z["head"] - a["tip"]
                if abs(dz) <= bridge_length:
                    feasible.append((abs(a["roll_deg"]) + abs(z["roll_deg"]), a, z, dz))
        print("TAIL_3D_SUPPORTS", json.dumps(face_evidence, indent=2))
        pair_contact = bool(feasible)
        if not feasible:
            # User asks distal grounding, not two exact supports. Keep tail3 on its real
            # long face; tail2 descends gently towards it, measured without claiming support.
            third = min(candidates[pitch[2]], key=lambda row: (-row["span_m"], abs(row["roll_deg"])))
            base = min(candidates[pitch[1]], key=lambda row: abs(row["roll_deg"]))
            h, t, _ = source_frames[pitch[1]]
            axis = (base["rotation"] @ (t - h)).normalized()
            tilt_axis = Vector((-axis.y, axis.x, 0)).normalized()
            alternatives = []
            for step in range(1, 301):
                rotation = Quaternion(tilt_axis, math.radians(step / 100)) @ base["rotation"]
                direction = (rotation @ (t - h)).normalized()
                clearance = -min((rotation @ (p - h)).z for key in attached[pitch[1]] for p in old_vertices[key])
                tip = clearance + arm.data.bones[pitch[1]].length * direction.z
                gap = third["head"] - tip
                if abs(gap) < bridge_length:
                    row = dict(base, rotation=rotation, head=clearance, tip=tip,
                               angle_deg=math.degrees(math.atan2(direction.z, math.hypot(direction.x, direction.y))),
                               support_claim=False)
                    alternatives.append((step, row, gap))
            if not alternatives:
                raise ValueError("Actual 3D distal support and gentle tail2 approach search failed; no scene mutation")
            _, second, dz = alternatives[0]
        else:
            _, second, third, dz = min(feasible, key=lambda row: row[0])
        moves = {n: Matrix.Identity(4) for n in objects}
        frames = {}
        root = source_frames["tail1_yaw"][0]
        frames["tail1_yaw"] = source_frames["tail1_yaw"][2].copy()
        head1 = source_frames["tail1_yaw"][1].copy()
        yaw2 = source_frames["tail2_yaw"][1] - source_frames["tail2_yaw"][0]
        target1tip = ground + second["head"] - yaw2.z
        h, t, frame = source_frames[pitch[0]]
        source_axis = (t - h).normalized()
        slope = (target1tip - head1.z) / arm.data.bones[pitch[0]].length
        assert -1 < slope < 0, "Fixed root/first pitch cannot reach support height"
        horizontal = Vector((source_axis.x, source_axis.y, 0)).normalized()
        direction1 = horizontal * math.sqrt(1 - slope * slope) + Vector((0, 0, slope))
        rotations = {pitch[0]: source_axis.rotation_difference(direction1),
                     pitch[1]: second["rotation"], pitch[2]: third["rotation"]}
        heads = {pitch[0]: head1}
        tip1 = head1 + direction1 * arm.data.bones[pitch[0]].length
        heads[pitch[1]] = tip1 + yaw2
        tip2 = heads[pitch[1]] + rotations[pitch[1]] @ (source_frames[pitch[1]][1] - source_frames[pitch[1]][0])
        bridge_horizontal = Vector((bridge_axis.x, bridge_axis.y, 0)).normalized()
        bridge_vector = bridge_horizontal * math.sqrt(bridge_length ** 2 - dz ** 2) + Vector((0, 0, dz))
        heads[pitch[2]] = tip2 + bridge_vector
        for n in pitch:
            h, t, frame = source_frames[n]
            transform = rigid_about(h, heads[n], rotations[n])
            frames[n] = transform @ frame
            for key in attached[n]:
                moves[key] = transform
        for n, head, vector in (("tail2_yaw", tip1, yaw2), (bridge, tip2, bridge_vector)):
            h, t, frame = source_frames[n]
            rotation = (t - h).rotation_difference(vector)
            transform = rigid_about(h, head, rotation)
            frames[n] = transform @ frame
            for key in attached[n]:
                moves[key] = transform
        for key in attached["tail1_yaw"]:
            moves[key] = Matrix.Identity(4)
        # World frames come from actual source pose, not guessed cap/bone directions.
        for n in tail_names:
            parent = arm.data.bones[n].parent.name
            if parent not in tail_names:
                rest_parent = mw @ arm.data.bones[parent].matrix_local
                correction = rest_parent @ old_pose[parent][2].inverted()
            else:
                correction = Matrix.Identity(4)
            frames[n] = correction @ frames[n]
        tail_meshes = {key for n in tail_names for key in attached[n]}
        report = {"status": "STATIC_GEOMETRY_PASS_PENDING_REVIEW", "source": str(source.relative_to(repo)),
                  "ground_z_m": ground, "body_height_m": old_height,
                  "float32_coordinate_bound_m": bound,
                  "protected_files": len(before_hashes),
                  "pair_surface_support": pair_contact,
                  "construction": "Actual 3D evaluated convex support planes within 15 degrees axial roll; original pitch azimuths and tail1/tail2 yaw retained. Tail3 real underside rests; tail2 gently approaches, not claimed as axial support. Tail-only source actual frames baked, no mesh edits or scaling.",
                  "tail1_slope_deg": math.degrees(math.asin(slope)),
                  "tail3_bridge_vector_m": list(bridge_vector),
                  "source_tail_frames": {n: {"head_m": list(h), "tail_m": list(t),
                      "matrix": [list(row) for row in matrix], "basis": [list(row) for row in old_basis[n]]}
                      for n, (h, t, matrix) in source_frames.items()},
                  "actual_3d_support_candidates": face_evidence,
                  "selected_supports": {n: {k: v for k, v in row.items() if k != "rotation"}
                                        for n, row in ((pitch[1], second), (pitch[2], third))},
                  "negative_checks": {}, "protected_sha256_before": before_hashes,
                  "approval": "Static tail candidate only; no ROM, physics, export, adoption or full self-collision approval."}
        def geometry_contact():
            result = {}
            for n in pitch:
                h, t, _ = source_frames[n]
                expected_axis = (moves[cylinders[n]].to_3x3() @ (t - h)).normalized()
                v = vertices(objects[cylinders[n]])
                all_v = [p for key in attached[n] for p in vertices(objects[key])]
                minimum = min(p.z for p in all_v)
                assert minimum >= ground - bound, "tail mesh penetrates floor: " + n
                contacts = [p for p in v if abs(p.z - ground) <= bound]
                span = max((p.dot(expected_axis) for p in contacts), default=0) - min((p.dot(expected_axis) for p in contacts), default=0)
                if n == pitch[2] or (pair_contact and n == pitch[1]):
                    assert contacts and span > bound, "distal tail lacks surface/edge ground support: " + n
                result[n] = {"all_attached_min_clearance_m": minimum - ground,
                             "cylinder_min_clearance_m": min(p.z for p in v) - ground,
                             "contact_vertices": len(contacts), "contact_axial_span_m": span}
            for key in tail_meshes:
                assert min(p.z for p in vertices(objects[key])) >= ground - bound, "tail mesh penetrates floor: " + key
            return result
        def check():
            contact = geometry_contact()
            evaluated = arm.evaluated_get(bpy.context.evaluated_depsgraph_get())
            pose_residuals, mesh_residuals = {}, {}
            for n, (h, t, matrix, parent) in old_bones.items():
                bone = arm.data.bones[n]
                assert (bone.parent.name if bone.parent else None) == parent, "bone parent changed: " + n
                assert abs(bone.length - (t - h).length) <= bound, "bone length changed: " + n
                if n not in tail_names:
                    assert max(abs(bone.matrix_local[i][j] - matrix[i][j]) for i in range(4) for j in range(4)) == 0, "non-tail rest changed: " + n
                    assert max(abs(arm.pose.bones[n].matrix_basis[i][j] - source_channels[n][i][j]) for i in range(4) for j in range(4)) == 0, "non-tail pose changed: " + n
                    actual = evaluated.matrix_world @ evaluated.pose.bones[n].matrix
                    residual = max(abs(actual[i][j] - actual_frames[n][i][j]) for i in range(4) for j in range(4))
                    assert residual == 0, "non-tail actual frame changed: " + n
                    pose_residuals[n] = residual
                else:
                    expected = moves[cylinders[n]] @ source_frames[n][2] if n in pitch else frames[n]
                    actual = evaluated.matrix_world @ evaluated.pose.bones[n].matrix
                    assert max(abs(actual[i][j] - expected[i][j]) for i in range(4) for j in range(4)) <= bound, "tail actual frame mismatch: " + n
                    pb = evaluated.pose.bones[n]
                    parent_pose = evaluated.pose.bones[parent]
                    assert (evaluated.matrix_world @ pb.head - evaluated.matrix_world @ parent_pose.tail).length <= bound, "tail joint disconnected: " + n
            assert abs(ends("base_link")[0].z - ground - old_height) <= bound, "body75 height changed"
            for leg, sample in samples.items():
                h, t = ends(sample["names"][2])
                assert math.hypot(t.x - h.x, t.y - h.y) <= bound and t.z < h.z, "lower leg not vertical: " + leg
                assert abs(min(p.z for p in vertices(objects[sample["palm"]])) - soles[leg]) <= bound, "sole height changed: " + leg
            assert (evaluated.matrix_world @ evaluated.pose.bones["tail1_yaw"].head - root).length <= bound, "tail root moved"
            for n in pitch:
                pose = evaluated.pose.bones[n]
                assert pose.tail.z < pose.head.z, "tail segment upturn: " + n
            for key, obj in objects.items():
                edges, faces, local = source_topology[key]
                assert edges == [tuple(e.vertices) for e in obj.data.edges] and faces == [tuple(f.vertices) for f in obj.data.polygons], "mesh topology changed: " + key
                assert len(local) == len(obj.data.vertices) and all((a - b.co).length == 0 for a, b in zip(local, obj.data.vertices)), "mesh data changed: " + key
                assert (obj.parent.name if obj.parent else None, obj.parent_type, obj.parent_bone) == binding_names[key], "mesh binding changed: " + key
                actual = vertices(obj)
                residual = max((p - moves[key] @ q).length for p, q in zip(actual, old_vertices[key]))
                assert residual <= eps(actual), "rigid mesh invariant failed: " + key
                if key not in tail_meshes:
                    assert residual == 0, "non-tail actual mesh changed: " + key
                mesh_residuals[key] = residual
            report["tail_contact"] = contact
            report["actual_tail_frames"] = {n: {"head_m": list(evaluated.matrix_world @ evaluated.pose.bones[n].head),
                "tail_m": list(evaluated.matrix_world @ evaluated.pose.bones[n].tail),
                "matrix": [list(row) for row in evaluated.matrix_world @ evaluated.pose.bones[n].matrix]}
                for n in tail_names}
            report["non_tail_frame_residuals"] = pose_residuals
            report["rigid_vertex_residuals_m"] = mesh_residuals
            report["bone_lengths_m"] = {n: {"source": (t - h).length, "new": arm.data.bones[n].length}
                                         for n, (h, t, _, _) in old_bones.items()}
        binding_names = {n: (parent.name if parent else None, kind, bone) for n, (parent, kind, bone) in bindings.items()}
        for key in tail_meshes:
            objects[key].parent = None
        bpy.context.view_layer.objects.active = arm
        bpy.ops.object.mode_set(mode="EDIT")
        for n in tail_names:
            bone = arm.data.edit_bones[n]
            bone.use_connect = False
            bone.matrix = inv @ frames[n]
            bone.length = (old_bones[n][1] - old_bones[n][0]).length
        bpy.ops.object.mode_set(mode="OBJECT")
        for n in tail_names:
            arm.pose.bones[n].matrix_basis = Matrix.Identity(4)
        bpy.context.view_layer.update()
        for key in tail_meshes:
            obj = objects[key]
            parent, kind, bone = bindings[key]
            obj.parent, obj.parent_type, obj.parent_bone = parent, kind, bone
            obj.matrix_parent_inverse = Matrix.Identity(4)
            bpy.context.view_layer.update()
            obj.matrix_world = moves[key] @ old_world[key]
        bpy.context.view_layer.update()
        check()
        # Real evaluated geometry mutations; saved objects restored, then full checks repeated.
        def mutation(offset):
            saved = {key: objects[key].matrix_world.copy() for key in tail_meshes}
            for key in tail_meshes:
                objects[key].matrix_world = Matrix.Translation((0, 0, offset)) @ saved[key]
            bpy.context.view_layer.update()
            return saved
        for label, shift, message in (("raised_tail", .02, "distal tail lacks"),
                                       ("lowered_tail", -.02, "tail mesh penetrates")):
            saved = mutation(shift)
            try:
                geometry_contact()
            except AssertionError as exc:
                assert str(exc).startswith(message), "tail mutation masked: " + str(exc)
                report["negative_checks"][label] = str(exc)
            else:
                raise AssertionError("Tail mutation not rejected: " + label)
            finally:
                for key, matrix in saved.items():
                    objects[key].matrix_world = matrix
                bpy.context.view_layer.update()
            check()
        if options.regression_without_fix:
            mutation(.02)
            geometry_contact()
        assert hashes() == before_hashes, "Protected artifacts changed"
        if options.check_only:
            if (output / "sample_neutral.blend").exists():
                bpy.ops.wm.open_mainfile(filepath=str(output / "sample_neutral.blend"))
                scene = bpy.context.scene
                arm = next(o for o in scene.objects if o.type == "ARMATURE")
                objects = {n: bpy.data.objects[n] for n in old_vertices}
                check()
            print("TAIL_GROUND CHECK_ONLY PASS", json.dumps({k: report[k] for k in ("tail_contact", "negative_checks")}))
            return
        output.mkdir()
        bpy.ops.wm.save_as_mainfile(filepath=str(output / "sample_neutral.blend"))
        bpy.ops.wm.open_mainfile(filepath=str(output / "sample_neutral.blend"))
        scene = bpy.context.scene
        arm = next(o for o in scene.objects if o.type == "ARMATURE")
        objects = {n: bpy.data.objects[n] for n in old_vertices}
        check()
        report["saved_reopened_independent_baseline_check"] = "PASS"
        scene.render.engine = "BLENDER_WORKBENCH"
        scene.render.resolution_x, scene.render.resolution_y = 1400, 900
        scene.render.resolution_percentage = 100
        scene.render.image_settings.file_format = "PNG"
        scene.display.shading.light = "STUDIO"
        scene.display.shading.color_type = "OBJECT"
        scene.display.shading.show_shadows = False
        scene.display.shading.show_cavity = True
        scene.display.shading.background_type = "WORLD"
        scene.world.color = (.035, .035, .035)
        data = bpy.data.cameras.new("TAIL_GROUND_DIAGNOSTIC_CAMERA")
        data.type = "ORTHO"
        camera = bpy.data.objects.new(data.name, data)
        scene.collection.objects.link(camera)
        scene.camera = camera
        mesh = bpy.data.meshes.new("TAIL_GROUND_DIAGNOSTIC_FLOOR")
        mesh.from_pydata([(-5, -2, ground), (1, -2, ground), (1, 2, ground), (-5, 2, ground)], [], [(0, 1, 2, 3)])
        floor = bpy.data.objects.new(mesh.name, mesh)
        scene.collection.objects.link(floor)
        floor.color = (.18, .18, .18, 1)
        full = [p for key in objects for p in vertices(objects[key])]
        close = [p for key in tail_meshes for p in vertices(objects[key])]
        report["pngs"] = []
        for name, direction, points, scale in (("full_side_ground", Vector((0, -1, 0)), full, 5.2),
                ("tail_close_ground", Vector((0, -1, .08)), close, 2.2),
                ("full_oblique_ground", Vector((1.3, -2, 1)), full, 5.2),
                ("full_top", Vector((0, 0, 1)), full, 5.2)):
            target = Vector(tuple((min(p[i] for p in points) + max(p[i] for p in points)) / 2 for i in range(3)))
            camera.location = target + direction.normalized() * 8
            camera.rotation_euler = (target - camera.location).to_track_quat("-Z", "Y").to_euler()
            data.ortho_scale = scale
            floor.hide_render = name == "full_top"
            scene.render.filepath = str(output / (name + ".png"))
            bpy.ops.render.render(write_still=True)
            report["pngs"].append(str((output / (name + ".png")).relative_to(repo)))
        report["blend"] = str((output / "sample_neutral.blend").relative_to(repo))
        report["protected_sha256_after"] = hashes()
        assert before_hashes == report["protected_sha256_after"]
        (output / "measurements.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        print("TAIL_GROUND OUTPUT PASS", json.dumps(report["tail_contact"]), output)

    if tail_ground:
        return grounded_tail()
    delta = Vector((0, 0, -old_height / 4))
    report = {"status": "PROVISIONAL_NOT_ACCEPTED", "source": str(source.relative_to(repo)),
              "body_reference": "Actual unique root base_link world rest head Z minus horizontal plane at mean of four evaluated palm sole minima; same fixed plane old/new",
              "ground_z_m": ground, "old_sole_z_m": soles,
              "sole_offsets_from_ground_m": {leg: z - ground for leg, z in soles.items()},
              "old_body_height_m": old_height, "target_body_height_m": old_height * .75,
              "body_translation_m": list(delta), "rest": {}, "turns": [], "negative_checks": {},
              "protected_sha256_before": before_hashes,
              "arithmetic_bound": "64 float32 ulps times max(1, absolute coordinates); not approved anatomical tolerance",
              "construction": "Latest actual blend; single rigid body/neck/tail translation, fixed bone lengths and palm geometry. Upper XY yaw/sign retained, solved Z; lower direction world (0,0,-1). Footprints may shift XY; old per-palm sole Z offsets retained.",
              "approval": "Only -10/0/+10 single elbow/wrist/knee/ankle diagnostics. No ROM, physics, export, adoption or full self-collision acceptance."}
    transforms = {n: Matrix.Translation(delta) for n in objects}
    new_bones = {n: (h + delta, t + delta) for n, (h, t, _, _) in old_bones.items()}
    for leg, s in samples.items():
        names, old = s["names"], s["old_points"]
        lengths = [(old[i + 1] - old[i]).length for i in range(2)]
        root = old[0] + delta
        elbow_z = old[2].z + lengths[1]
        upper_z = elbow_z - root.z
        if abs(upper_z) >= lengths[0]:
            raise ValueError("Unreachable fixed-length vertical lower: " + leg)
        yaw = old[1] - old[0]
        yaw.z = 0
        yaw.normalize()
        upper = yaw * math.sqrt(lengths[0] ** 2 - upper_z ** 2) + Vector((0, 0, upper_z))
        p = [root, root + upper]
        p.append(p[1] + Vector((0, 0, -lengths[1])))
        s["points"] = p
        s["axis"] = upper.cross(Vector((0, 0, -1))).normalized()
        if leg in MIRROR_OF:
            s["axis"] = -(reflection.to_3x3() @ samples[MIRROR_OF[leg]]["axis"])
        new_bones[names[0]] = (p[0], p[0] + old_bones[names[0]][1] - old_bones[names[0]][0])
        for i in (1, 2):
            new_bones[names[i]] = (p[i - 1], p[i])
            rotation = (old[i] - old[i - 1]).rotation_difference(p[i] - p[i - 1])
            for n in s["attached"][i]:
                transforms[n] = rigid_about(old[i - 1], p[i - 1], rotation)
        new_bones[names[3]] = (p[2], p[2] + old_bones[names[3]][1] - old_bones[names[3]][0])
        for n in s["attached"][3]:
            transforms[n] = Matrix.Translation(p[2] - old[2])
    nonleg = [n for n, (_, _, bone) in bindings.items() if not bone.startswith(("lf_", "rf_", "rl_", "rr_"))]
    if min((p + delta).z for n in nonleg for p in old_vertices[n]) <= ground:
        raise ValueError("Rigidly lowered body/neck/tail intersects ground; stop")
    # Detach before changing rest. Rebind unchanged mesh data via desired world transforms.
    for o in objects.values():
        o.parent = None
    bpy.context.view_layer.objects.active = arm
    bpy.ops.object.mode_set(mode="EDIT")
    for n, (h, t) in new_bones.items():
        b = arm.data.edit_bones[n]
        b.use_connect = False
        b.head, b.tail = inv @ h, inv @ t
    for s in samples.values():
        for n in s["names"][1:]:
            b = arm.data.edit_bones[n]
            b.align_roll((inv.to_3x3() @ s["axis"]).cross((b.tail - b.head).normalized()))
    bpy.ops.object.mode_set(mode="OBJECT")
    for s in samples.values():
        for n in s["names"]:
            arm.pose.bones[n].matrix_basis = Matrix.Identity(4)
    # Nonleg pose channels stay untouched: assigning matrix_basis decomposes it and rounds rotations.
    for n, o in objects.items():
        parent, kind, bone = bindings[n]
        o.parent, o.parent_type, o.parent_bone = parent, kind, bone
        o.matrix_parent_inverse = Matrix.Identity(4)
        bpy.context.view_layer.update()
        o.matrix_world = transforms[n] @ old_world[n]
    bpy.context.view_layer.update()
    def overlap(a, b):
        trees = []
        for n in (a, b):
            o = objects[n]
            evaluated = o.evaluated_get(bpy.context.evaluated_depsgraph_get())
            mesh = evaluated.to_mesh()
            try:
                trees.append(BVHTree.FromPolygons([evaluated.matrix_world @ v.co for v in mesh.vertices],
                                                 [list(f.vertices) for f in mesh.polygons]))
            finally:
                evaluated.to_mesh_clear()
        return len(trees[0].overlap(trees[1]))
    def measure(leg):
        s = samples[leg]
        cap_centers = []
        cap_residuals = []
        for n, bone, groups in zip(s["cylinders"], s["names"][1:3], s["caps"]):
            v = vertices(objects[n])
            c = [center([v[i] for i in group]) for group in groups]
            cap_centers.append(c)
            b = arm.pose.bones[bone]
            cap_residuals.extend([(c[0] - mw @ b.head).length, (c[1] - mw @ b.tail).length])
        b = arm.pose.bones[s["names"][2]]
        d = (mw @ b.tail - mw @ b.head).normalized()
        axis = (cap_centers[1][1] - cap_centers[1][0]).normalized()
        pv = vertices(objects[s["palm"]])
        root = mw @ arm.pose.bones[s["names"][3]].head
        return {"lower_bone_head_m": list(mw @ b.head), "lower_bone_tail_m": list(mw @ b.tail),
                "lower_angle_to_horizontal_deg": math.degrees(math.atan2(abs(d.z), math.hypot(d.x, d.y))),
                "lower_cap_axis_angle_to_horizontal_deg": math.degrees(math.atan2(abs(axis.z), math.hypot(axis.x, axis.y))),
                "lower_horizontal_component": math.hypot(d.x, d.y),
                "lower_cap_centers_m": [list(c) for c in cap_centers[1]],
                "cap_endpoint_residuals_m": cap_residuals,
                "palm_root_residual_m": (center(pv[:12]) - root).length,
                "sole_z_m": min(p.z for p in pv),
                "lower_palm_BVH_surface_overlap_pairs": overlap(s["cylinders"][1], s["palm"]),
                "nonleg_ground_clearance_m": min(p.z for n in nonleg for p in vertices(objects[n])) - ground}
    def check():
        current_height = ends("base_link")[0].z - ground
        bound = eps([old_bones["base_link"][0]])
        assert abs(current_height - .75 * old_height) <= bound, "body ground height not 75%"
        evaluated_arm = arm.evaluated_get(bpy.context.evaluated_depsgraph_get())
        pose_checks = {}
        for n, (h, t, matrix) in old_pose.items():
            b = evaluated_arm.pose.bones[n]
            basis = arm.pose.bones[n].matrix_basis
            basis_residual = max(abs(basis[i][j] - old_basis[n][i][j]) for i in range(4) for j in range(4))
            assert basis_residual == 0, "nonleg pose basis changed: " + n
            a, z = evaluated_arm.matrix_world @ b.head, evaluated_arm.matrix_world @ b.tail
            current = evaluated_arm.matrix_world @ b.matrix
            head_residual, tail_residual = (a - h - delta).length, (z - t - delta).length
            axes_residual = max(abs(current[i][j] - matrix[i][j]) for i in range(3) for j in range(3))
            assert max(head_residual, tail_residual, axes_residual) <= eps([h, t, a, z]), "nonleg evaluated frame changed: " + n
            pose_checks[n] = {"source_basis": [list(row) for row in old_basis[n]],
                "new_basis": [list(row) for row in basis], "basis_residual": basis_residual,
                "source_basis_identity_residual": max(abs(old_basis[n][i][j] - (i == j)) for i in range(4) for j in range(4)),
                "source_head_m": list(h), "source_tail_m": list(t),
                "new_head_m": list(a), "new_tail_m": list(z),
                "head_translation_residual_m": head_residual, "tail_translation_residual_m": tail_residual,
                "source_world_axes": [list(row)[:3] for row in matrix][:3],
                "new_world_axes": [list(row)[:3] for row in current][:3], "world_axes_residual": axes_residual,
                "source_pose_minus_rest_head_m": list(h - old_bones[n][0]),
                "new_pose_minus_rest_head_m": list(a - ends(n)[0])}
        report["nonleg_pose_preserved"] = pose_checks
        old_actual_height = old_pose["base_link"][0].z - ground
        actual_height = (evaluated_arm.matrix_world @ evaluated_arm.pose.bones["base_link"].head).z - ground
        report["root_rest_vs_actual"] = {"source_rest_height_m": old_height,
            "source_actual_height_m": old_actual_height, "source_actual_minus_rest_m": old_actual_height - old_height,
            "new_rest_height_m": ends("base_link")[0].z - ground, "new_actual_height_m": actual_height,
            "new_actual_minus_rest_m": actual_height - (ends("base_link")[0].z - ground),
            "actual_height_ratio": actual_height / old_actual_height,
            "reference": "Unchanged source root rest head and fixed sole plane; actual evaluated offset inherited, not redefined"}
        assert abs(actual_height - old_actual_height - delta.z) <= eps([old_pose["base_link"][0]]), "actual root translation changed"
        for leg, s in samples.items():
            h, t = ends(s["names"][2])
            assert math.hypot(t.x - h.x, t.y - h.y) <= bound and t.z < h.z, "lower leg not vertical: " + leg
        for n, (h, t, _, parent) in old_bones.items():
            a, b = ends(n)
            assert abs((a - b).length - (h - t).length) <= bound, "bone length changed: " + n
            assert (arm.data.bones[n].parent.name if arm.data.bones[n].parent else None) == parent
            if not n.startswith(("lf_", "rf_", "rl_", "rr_")):
                assert max((a - h - delta).length, (b - t - delta).length) <= bound, "nonleg rest not rigidly translated"
        for n, o in objects.items():
            assert (o.parent, o.parent_type, o.parent_bone) == bindings[n], "mesh binding changed"
            v = vertices(o)
            assert len(v) == len(old_vertices[n])
            residual = max((p - transforms[n] @ q).length for p, q in zip(v, old_vertices[n]))
            assert residual <= eps(v), "mesh shape/rest transform drift: " + n
        for leg, s in samples.items():
            m = measure(leg)
            assert abs(m["sole_z_m"] - soles[leg]) <= bound, "sole height changed"
            assert max(m["cap_endpoint_residuals_m"] + [m["palm_root_residual_m"]]) <= bound, "physical caps disconnected"
            c = [Vector(v) for v in m["lower_cap_centers_m"]]
            assert math.hypot(c[1].x - c[0].x, c[1].y - c[0].y) <= bound, "physical lower cylinder tilted"
            assert m["nonleg_ground_clearance_m"] > 0, "body intersects floor"
            a, b = ends(s["names"][1])
            old = s["old_points"][1] - s["old_points"][0]
            d = b - a
            assert d.x * old.x > 0 and d.y * old.y > 0, "upper sagittal/outward sign changed"
            assert abs(d.x * old.y - d.y * old.x) <= bound, "upper yaw changed"
        report["mirror_vertex_residuals_m"] = {}
        for right, left in MIRROR_OF.items():
            for la, ra in zip(samples[left]["attached"], samples[right]["attached"]):
                for ln, rn in zip(la, ra):
                    a, b = vertices(objects[ln]), vertices(objects[rn])
                    residual = max((reflection @ p - q).length for p, q in zip(a, b))
                    assert residual <= eps(a + b), "mirror geometry drift"
                    report["mirror_vertex_residuals_m"][rn] = residual
    check()
    nonzero = next(n for n, basis in old_basis.items()
                   if max(abs(basis[i][j] - (i == j)) for i in range(4) for j in range(4)) > eps([old_bones[n][0]]))
    pose = arm.pose.bones[nonzero]
    channels = (pose.location.copy(), pose.scale.copy(), pose.rotation_euler.copy(),
                pose.rotation_quaternion.copy(), tuple(pose.rotation_axis_angle))
    pose.matrix_basis = Matrix.Identity(4)
    bpy.context.view_layer.update()
    try:
        check()
    except AssertionError as exc:
        assert str(exc) == "nonleg pose basis changed: " + nonzero, "pose mutation masked: " + str(exc)
        report["negative_checks"]["nonleg_nonzero_basis_reset"] = str(exc)
    else:
        raise AssertionError("Actual nonleg pose reset not rejected: " + nonzero)
    finally:
        pose.location, pose.scale, pose.rotation_euler, pose.rotation_quaternion, pose.rotation_axis_angle = channels
        bpy.context.view_layer.update()
    check()
    # Real rest-bone mutations on BOTH front sides; named assertions run before mirror/mesh checks.
    saved_rest = {n: ends(n) for s in samples.values() for n in s["names"][2:3]} | {"base_link": ends("base_link")}
    def mutate(label, bad):
        bpy.context.view_layer.objects.active = arm
        bpy.ops.object.mode_set(mode="EDIT")
        names = ["base_link"] if label == "height_unchanged" else [samples[l]["names"][2] for l in ("lf", "rf")]
        for n in names:
            h, t = saved_rest[n]
            shift = -delta if label == "height_unchanged" else Vector((.02, 0, 0))
            b = arm.data.edit_bones[n]
            b.head, b.tail = inv @ h, inv @ (t + shift if bad else t)
            if label == "height_unchanged":
                b.head = inv @ (h + shift if bad else h)
        bpy.ops.object.mode_set(mode="OBJECT")
        bpy.context.view_layer.update()
    for label, message in (("height_unchanged", "body ground height not 75%"), ("tilted_lower", "lower leg not vertical:")):
        mutate(label, True)
        try:
            check()
        except AssertionError as exc:
            assert str(exc).startswith(message), "mutation masked by unrelated assertion: " + str(exc)
            report["negative_checks"][label] = str(exc)
        else:
            raise AssertionError("Actual mutation not rejected: " + label)
        finally:
            mutate(label, False)
        check()
    if options.regression_without_fix:
        mutate("height_unchanged", True)
        check()
    neutral = {n: vertices(o) for n, o in objects.items()}
    turn_vertices = {}
    for leg, s in samples.items():
        report["rest"][leg] = measure(leg)
        for name in s["names"][2:]:
            pivot = ends(name)[0]
            axis = s["axis"]
            local = arm.data.bones[name].matrix_local.to_3x3().inverted() @ (inv.to_3x3() @ axis)
            downstream = {name} | {b.name for b in arm.data.bones[name].children_recursive}
            for angle in (-10, 0, 10):
                pose = arm.pose.bones[name]
                pose.rotation_mode = "QUATERNION"
                pose.rotation_quaternion = Quaternion(local, math.radians(angle))
                bpy.context.view_layer.update()
                transform = rigid_about(pivot, pivot, Quaternion(axis, math.radians(angle)))
                residuals = {}
                for row in s["attached"]:
                    for n in row:
                        expected = transform if bindings[n][2] in downstream else Matrix.Identity(4)
                        v = vertices(objects[n])
                        residuals[n] = max((p - expected @ q).length for p, q in zip(v, neutral[n]))
                        assert residuals[n] <= eps(v), "turn drift: " + n
                m = measure(leg)
                m.update(joint=name, leg=leg, angle_deg=angle, rigid_vertex_residuals_m=residuals)
                report["turns"].append(m)
                turn_vertices[(leg, s["names"].index(name), angle)] = {
                    n: vertices(objects[n]) for row in s["attached"] for n in row}
                pose.matrix_basis = Matrix.Identity(4)
                bpy.context.view_layer.update()
    report["same_angle_mirror_turn_residuals_m"] = {}
    for right, left in MIRROR_OF.items():
        for i in (2, 3):
            for angle in (-10, 0, 10):
                residual = max((reflection @ p - q).length
                    for lr, rr in zip(samples[left]["attached"], samples[right]["attached"])
                    for ln, rn in zip(lr, rr)
                    for p, q in zip(turn_vertices[(left, i, angle)][ln], turn_vertices[(right, i, angle)][rn]))
                assert residual <= eps([p for row in samples[left]["attached"] for n in row for p in neutral[n]]), "same-angle mirror turn drift"
                report["same_angle_mirror_turn_residuals_m"][f"{right}_{i}_{angle}"] = residual
    check()
    exporter = str(Path(_SCRIPT_DIR) / "generate_urdf.py")
    argv = sys.argv
    sys.argv = [exporter, "--", "--robot", "lizard2_palm_contract", "--contract_check", "--memory_scene"]
    namespace = {"__file__": exporter, "__name__": "__main__"}
    try:
        try:
            exec(compile(Path(exporter).read_text(encoding="utf-8"), exporter, "exec"), namespace)
        except SystemExit as exc:
            assert exc.code == 0
    finally:
        sys.argv = argv
    assert len(namespace["binding"]) == 4
    report["real_exporter_memory_contract"] = "PASS; no export"
    report["collision_limits"] = "Evaluated lower-cylinder/palm BVH surface crossings only, neutral + all24 single-joint snapshots; no depth/containment, trimming/filtering, full self-collision, ROM or physics acceptance. Nonleg vertex floor clearance also measured."
    report["new_body_height_m"] = ends("base_link")[0].z - ground
    report["body_height_ratio"] = report["new_body_height_m"] / old_height
    report["bone_lengths_m"] = {n: {"old": (h - t).length, "new": (ends(n)[0] - ends(n)[1]).length,
        "residual": abs((h - t).length - (ends(n)[0] - ends(n)[1]).length)}
        for n, (h, t, _, _) in old_bones.items()}
    report["palm_rigid_translation_checks"] = {leg: {
        "translation_m": list(s["points"][2] - s["old_points"][2]),
        "vertex_shape_residual_m": max((p - q - (s["points"][2] - s["old_points"][2])).length
            for p, q in zip(vertices(objects[s["palm"]]), old_vertices[s["palm"]]))}
        for leg, s in samples.items()}
    report["nonleg_translation_vertex_residuals_m"] = {n: max((p - q - delta).length for p, q in zip(vertices(objects[n]), old_vertices[n])) for n in nonleg}
    report["nonleg_object_positions"] = {n: {
        "source_world_origin_m": list(old_world[n].translation),
        "new_evaluated_world_origin_m": list(objects[n].evaluated_get(bpy.context.evaluated_depsgraph_get()).matrix_world.translation),
        "translation_residual_m": (objects[n].evaluated_get(bpy.context.evaluated_depsgraph_get()).matrix_world.translation - old_world[n].translation - delta).length,
        "source_origin_minus_evaluated_joint_head_m": list(old_world[n].translation - old_pose[bindings[n][2]][0]) if bindings[n][2] in old_pose else None}
        for n in nonleg}
    report["nonleg_alignment_scope"] = "Source evaluated frames, bases and mesh positions preserved under delta; inherited pose/rest and mesh-origin/joint offsets reported, not corrected or certified anatomical alignment."
    assert hashes() == before_hashes, "Protected artifacts changed"
    if options.check_only:
        print("BODY75 CHECK_ONLY PASS", json.dumps({k: report[k] for k in ("body_height_ratio", "negative_checks", "rest")}))
        return
    output.mkdir()
    binding_names = {n: (parent.name if parent else None, kind, bone) for n, (parent, kind, bone) in bindings.items()}
    bpy.ops.wm.save_as_mainfile(filepath=str(output / "sample_neutral.blend"))
    bpy.ops.wm.open_mainfile(filepath=str(output / "sample_neutral.blend"))
    scene = bpy.context.scene
    arm = next(o for o in scene.objects if o.type == "ARMATURE")
    objects = {n: bpy.data.objects[n] for n in old_vertices}
    # Object/armature handles are invalid after reopen; preserve baseline binding names independently.
    bindings = {n: (bpy.data.objects[parent] if parent else None, kind, bone)
                for n, (parent, kind, bone) in binding_names.items()}
    check()
    report["reopened_independent_baseline_geometry_check"] = "PASS actual saved vertices and rest bones vs preflight latest blend snapshots"
    scene.render.engine = "BLENDER_WORKBENCH"
    scene.render.resolution_x, scene.render.resolution_y = 1400, 900
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.display.shading.light = "STUDIO"
    scene.display.shading.color_type = "OBJECT"
    scene.display.shading.show_shadows = False
    scene.display.shading.show_cavity = True
    scene.display.shading.background_type = "WORLD"
    scene.world.color = (.035, .035, .035)
    data = bpy.data.cameras.new("BODY75_DIAGNOSTIC_CAMERA")
    data.type = "ORTHO"
    camera = bpy.data.objects.new(data.name, data)
    scene.collection.objects.link(camera)
    scene.camera = camera
    # Ground overlay only, added after neutral save; not part of robot/export geometry.
    mesh = bpy.data.meshes.new("BODY75_DIAGNOSTIC_GROUND")
    mesh.from_pydata([(-5, -2, ground), (1, -2, ground), (1, 2, ground), (-5, 2, ground)], [], [(0, 1, 2, 3)])
    floor = bpy.data.objects.new(mesh.name, mesh)
    scene.collection.objects.link(floor)
    floor.color = (.18, .18, .18, 1)
    curve = bpy.data.curves.new("BODY75_DIAGNOSTIC_GROUND_CROSS", "CURVE")
    curve.dimensions, curve.bevel_depth = "3D", .004
    for a, b in (((-5, 0, ground), (1, 0, ground)), ((-1.5, -2, ground), (-1.5, 2, ground))):
        spline = curve.splines.new("POLY")
        spline.points.add(1)
        spline.points[0].co, spline.points[1].co = (*a, 1), (*b, 1)
    ground_cross = bpy.data.objects.new(curve.name, curve)
    scene.collection.objects.link(ground_cross)
    ground_cross.color = (.9, .5, .15, 1)
    full = [p for v in neutral.values() for p in v]
    target = Vector(tuple((min(p[i] for p in full) + max(p[i] for p in full)) / 2 for i in range(3)))
    views = [("full_side_ground", Vector((0, -1, 0))), ("full_front_ground", Vector((1, 0, 0))),
             ("full_oblique_ground", Vector((1.3, -2, 1))), ("full_top", Vector((0, 0, 1)))]
    report["pngs"] = []
    for name, direction in views:
        camera.location = target + direction.normalized() * 8
        camera.rotation_euler = (target - camera.location).to_track_quat("-Z", "Y").to_euler()
        data.ortho_scale = 5.2
        floor.hide_render = name == "full_top"
        scene.render.filepath = str(output / (name + ".png"))
        bpy.ops.render.render(write_still=True)
        report["pngs"].append(str((output / (name + ".png")).relative_to(repo)))
    report["blend"] = str((output / "sample_neutral.blend").relative_to(repo))
    report["protected_sha256_after"] = hashes()
    assert before_hashes == report["protected_sha256_after"]
    (output / "measurements.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print("BODY75 OUTPUT PASS", output, "ratio", report["body_height_ratio"])


def palm_p2_sample(args):
    """Build isolated native-mesh P2 samples; opt in to four mirrored limbs and lowered claw bodies."""
    import argparse
    import hashlib
    import json
    from pathlib import Path

    parser = argparse.ArgumentParser(description=palm_p2_sample.__doc__)
    parser.add_argument("--p2_sample", action="store_true")
    parser.add_argument("--output_dir", required=True)
    parser.add_argument("--diagnostic_angles", required=True, help="Explicit approved degrees, comma separated")
    parser.add_argument("--regression_without_fix", action="store_true")
    parser.add_argument("--palm_shape", choices=("halfpad", "claw"), default="halfpad")
    parser.add_argument("--all_legs", action="store_true", help="Mirror built left limbs into original right objects")
    parser.add_argument("--sole_at_ball_bottom", action="store_true", help="Lower claw body, retaining root ring at pivot")
    parser.add_argument("--body75_vertical", action="store_true", help="Latest four low palms; body ground height 75%, vertical lower bones")
    parser.add_argument("--tail_ground", action="store_true", help="Generate isolated natural distal tail support from latest saved body75; actual 3D meshes, tail-only rigid frames")
    parser.add_argument("--check_only", action="store_true", help="Memory-only regression; no output directory created")
    options = parser.parse_args(args)
    if options.tail_ground and not options.body75_vertical:
        raise ValueError("--tail_ground requires --body75_vertical")
    if (options.all_legs or options.sole_at_ball_bottom) and options.palm_shape != "claw":
        raise ValueError("--all_legs and --sole_at_ball_bottom require --palm_shape claw")
    angles = [float(x) for x in options.diagnostic_angles.split(",")]
    if angles != [-10.0, 0.0, 10.0]:
        raise ValueError("P2 approval covers diagnostic -10/0/+10 degrees ONLY")
    if options.body75_vertical:
        if not (options.all_legs and options.sole_at_ball_bottom and options.palm_shape == "claw"):
            raise ValueError("--body75_vertical requires --palm_shape claw --all_legs --sole_at_ball_bottom")
        palm_body75_vertical(options)
        return
    output = Path(options.output_dir).resolve()
    if output.parent != Path(_ASSET_DIR).resolve() or not output.name.startswith("lizard2_palm_p2_sample"):
        raise ValueError("P2 output must be a new lizard2_palm_p2_sample* directory beside source")
    if not options.check_only and output.exists():
        raise FileExistsError("Refuse overwrite: " + str(output))
    repo = Path(_ASSET_DIR).parents[1]
    protected = [Path(BLEND_IN), Path(BLEND_OUT)]
    baseline_dir = Path(_ASSET_DIR) / "lizard2_palm_p2_sample"
    claw_dir = Path(_ASSET_DIR) / "lizard2_palm_p2_sample_claw"
    for directory in (baseline_dir, claw_dir):
        if directory.exists():
            protected.extend(p for p in directory.iterdir() if p.is_file())
    if not options.check_only and output in (baseline_dir.resolve(), claw_dir.resolve()):
        raise ValueError("Existing P2 artifact directories are read-only")
    if options.palm_shape == "claw":
        baseline = json.loads((baseline_dir / "measurements.json").read_text(encoding="utf-8"))
    for folder in ("assets", "versions", "lizard2_candidate", "meshes"):
        protected.extend(p for p in (repo / "rl_exp" / folder).rglob("*") if p.is_file())
    hashes = {str(p.relative_to(repo)): file_binding.sha256_file(p) for p in protected}
    report = {"status": "PROVISIONAL_SAMPLE_NOT_ACCEPTED", "angles_deg": angles,
              "approval": "diagnostic turns only; no position/mesh tolerances, ROM, physics or adoption approval",
              "units": "world coordinates and distances m; angles deg; body forward +X",
              "source": str(Path(BLEND_IN).relative_to(repo)), "protected_sha256_before": hashes,
              "construction": "lf/rl ONLY. Native upper/lower bone lengths; approved candidate directions. "
              "Cylinder native cap rings fitted to bone endpoints, radial offsets preserved. "
              "Evaluated source pad bisected at its body-X vertex centroid, forward half capped at source cross-section. "
              "Cap centroid translated to wrist/ankle. No new primitive limb mesh, no scaling of pad. "
              "Old unmeshed kfe->foot segment and foot bone removed; source kfe marker retained at new wrist. "
              "No four-limb exporter contract claim.", "rest": {}, "turns": [], "negative_checks": {}}
    scene, arm, arm_mw, bones, on_bone = load()
    roles = leg_roles(arm_mw, bones, on_bone)
    report["source_sample_pose_basis"] = {name: [list(row) for row in arm.pose.bones[name].matrix_basis]
                                          for leg in LEFT_LEGS for name in (f"{leg}_{j}" for j in LEG_BONES)}
    report["pose_handling"] = "Source contains nonzero pose basis despite rest-aligned object geometry. " \
        "Only rebuilt lf/rl pose basis is cleared; other limbs and trunk are unchanged."
    arm_inv = arm_mw.inverted()
    original_bones = {n: (b.head_local.copy(), b.tail_local.copy(), b.matrix_local.copy(),
                          b.parent.name if b.parent else None) for n, b in bones.items()}
    original_world = {o.name: o.matrix_world.copy() for o in scene.objects if o.type == "MESH"}
    original_right = {}

    def vertices(obj):
        evaluated = obj.evaluated_get(bpy.context.evaluated_depsgraph_get())
        mesh = evaluated.to_mesh()
        try:
            return [evaluated.matrix_world @ v.co for v in mesh.vertices]
        finally:
            evaluated.to_mesh_clear()

    for leg in ("rf", "rr"):
        for pair in roles[leg].values():
            for obj in pair:
                if obj is not None:
                    original_right[obj.name] = vertices(obj)

    # Floating arithmetic sanity only: not an anatomical position/mesh acceptance tolerance.
    # Blender stores geometry as float32. Bound scales with coordinates, not observed residuals.
    def roundoff(points):
        return 64 * (2 ** -23) * max(1.0, *(abs(x) for p in points for x in p))

    def center(points):
        return sum(points, Vector()) / len(points)

    def encode(p):
        return list(p)

    def bake_world(obj):
        evaluated = obj.evaluated_get(bpy.context.evaluated_depsgraph_get())
        mesh = bpy.data.meshes.new_from_object(evaluated, depsgraph=bpy.context.evaluated_depsgraph_get())
        mesh.transform(evaluated.matrix_world)
        obj.modifiers.clear()
        obj.parent = None
        obj.matrix_world = Matrix.Identity(4)
        obj.data = mesh
        return mesh

    samples = {}
    source_lines = {}
    source_meshes = {}
    for leg in LEFT_LEGS:
        source_meshes[leg] = []
        for pair in roles[leg].values():
            for obj in pair:
                if obj is not None:
                    evaluated = obj.evaluated_get(bpy.context.evaluated_depsgraph_get())
                    data = bpy.data.meshes.new_from_object(evaluated, depsgraph=bpy.context.evaluated_depsgraph_get())
                    data.transform(evaluated.matrix_world)
                    source_meshes[leg].append(data)
    for leg, params in LEFT_LEGS.items():
        old = [arm_mw @ bones[f"{leg}_{j}"].head_local for j in LEG_BONES]
        source_lines[leg] = old + [arm_mw @ bones[f"{leg}_foot"].tail_local]
        dirs = [seg_dir(params["phi"][i], params["theta"]) for i in range(2)]
        points = [old[0].copy()]
        for i in range(2):
            points.append(points[-1] + dirs[i] * (old[i + 1] - old[i]).length)
        native = ("shoulder_swing", "shoulder_abduct", "elbow", "wrist") if leg == "lf" else (
            "hip_swing", "hip_abduct", "knee", "ankle")
        names = [f"{leg}_{r}" for r in native]
        axis = dirs[0].cross(dirs[1]).normalized()
        mesh_objects = []
        endpoints = []
        source_measure = {}
        for i, joint in enumerate(("haa", "hfe")):
            marker, segment = roles[leg][joint]
            rotation = (old[i + 1] - old[i]).rotation_difference(dirs[i])
            transform = rigid_about(old[i], points[i], rotation)
            marker_world = transform @ original_world[marker.name]
            mesh = bake_world(segment)
            source_axis = (old[i + 1] - old[i]).normalized()
            projections = [(v.co - old[i]).dot(source_axis) for v in mesh.vertices]
            caps = [list(face.vertices) for face in mesh.polygons if len(face.vertices) > 4]
            assert len(caps) == 2, "Expected two real native cylinder cap polygons"
            caps.sort(key=lambda ids: center([mesh.vertices[k].co for k in ids]).dot(source_axis))
            cap_centers = [center([mesh.vertices[k].co for k in ids]) for ids in caps]
            lo, hi = [(c - old[i]).dot(source_axis) for c in cap_centers]
            length = (old[i + 1] - old[i]).length
            source_measure[joint] = {"axial_min_from_head_m": lo, "axial_max_from_head_m": hi,
                                      "cap_centers_m": [encode(c) for c in cap_centers],
                                      "bone_length_m": length, "distal_surface_gap_m": length - hi}
            # Native cap-ring centers and topology, not object origins or extreme single vertices.
            # Axial fit plus interpolated transverse recentering; preserve native radial offsets.
            for v, distance in zip(mesh.vertices, projections):
                fraction = (distance - lo) / (hi - lo)
                native_center = cap_centers[0].lerp(cap_centers[1], fraction)
                transverse = native_center - (old[i] + source_axis * distance)
                v.co += source_axis * (length * fraction - distance) - transverse
                v.co = transform @ v.co
            mesh.update()
            ends = caps
            endpoints.append((segment, ends))
            marker.parent = None
            marker.matrix_world = marker_world
            mesh_objects.extend([(marker, names[i + 1]), (segment, names[i + 1])])
        wrist_marker = roles[leg]["kfe"][0]
        wrist_marker.parent = None
        wrist_marker.matrix_world = Matrix.Translation(points[2] - old[2]) @ original_world[wrist_marker.name]
        mesh_objects.append((wrist_marker, names[3]))
        palm = roles[leg]["foot"][0]
        old_pad = vertices(palm)
        old_center = center(old_pad)
        old_bounds = [[min(p[i] for p in old_pad), max(p[i] for p in old_pad)] for i in range(3)]
        mesh = bake_world(palm)
        bm = bmesh.new()
        bm.from_mesh(mesh)
        cut = bmesh.ops.bisect_plane(bm, geom=list(bm.verts) + list(bm.edges) + list(bm.faces),
                                   dist=0.000001, plane_co=old_center, plane_no=Vector((1, 0, 0)),
                                   clear_inner=True, clear_outer=False)
        boundary = [e for e in cut["geom_cut"] if isinstance(e, bmesh.types.BMEdge) and e.is_boundary]
        if not boundary:
            raise AssertionError("Source pad cut has no root boundary")
        bmesh.ops.holes_fill(bm, edges=boundary, sides=0)
        bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
        bm.to_mesh(mesh)
        bm.free()
        cap_ids = [v.index for v in mesh.vertices if abs(v.co.x - old_center.x) <= 0.000002]
        assert len(cap_ids) >= 3, "No physical proximal cap"
        cap_center = center([mesh.vertices[i].co for i in cap_ids])
        for v in mesh.vertices:
            v.co += points[2] - cap_center
        mesh.update()
        halfpad_mesh = mesh.copy() if options.palm_shape == "claw" else None
        palm_bone_length = max(v.co.x for v in mesh.vertices) - points[2].x
        if options.palm_shape == "claw":
            # Trial recipe, NOT animal measurements or approved dimensions. No modifiers:
            # explicit rounded cross-sections keep physical root indices stable.
            length = palm_bone_length * 1.5
            width, thickness = length * 0.8, length * 0.22
            sections = ((0, .38, 1), (.18, .55, 1.05), (.48, .95, 1.15),
                        (.78, 1, 1.1), (.94, .94, 1), (1, .72, .9))
            ring = ((0, -.5), (.8, -.5), (1, -.3), (1, 0), (1, .3), (.8, .5),
                    (0, .5), (-.8, .5), (-1, .3), (-1, 0), (-1, -.3), (-.8, -.5))
            coords = []
            ball_bottom = min(p.z for p in vertices(wrist_marker))
            body_shift = ball_bottom - (points[2].z - thickness / 2) if options.sole_at_ball_bottom else 0.0
            for x, breadth, roof in sections:
                for y, z in ring:
                    # Root centroid remains pivot; next ring joins lowered body without another joint.
                    height = z * thickness * (roof if z > 0 else 1)
                    height += body_shift if x > 0 else 0.0
                    coords.append(points[2] + Vector((x * length, y * breadth * width / 2, height)))
            count = len(ring)
            faces = [tuple(reversed(range(count)))]
            for section in range(len(sections) - 1):
                for i in range(count):
                    a, b = section * count + i, section * count + (i + 1) % count
                    faces.append((a, b, b + count, a + count))
            faces.append(tuple(range((len(sections) - 1) * count, len(coords))))
            mesh = bpy.data.meshes.new("P2_claw_no_digits")
            mesh.from_pydata(coords, [], faces)
            mesh.update()
            palm.data = mesh
            cap_ids = list(range(count))
            report["palm_shape"] = "claw"
            report["construction"] = "P2 unchanged except palm mesh: six capped rounded cross-sections; " \
                "flat plantar middle, mildly arched roof, narrow root at unchanged wrist/ankle. No digits."
            report["trial_recipe_NOT_approved"] = {
                "length_from_halfpad": 1.5, "width_from_length": .8, "thickness_from_length": .22,
                "sections_x_width_roof_factors": sections, "ring_y_z_factors": ring}
        mesh_objects.append((palm, names[3]))
        samples[leg] = {"points": points, "axis": axis, "names": names, "objects": mesh_objects,
                        "palm_bone_length": palm_bone_length, "halfpad_mesh": halfpad_mesh,
                        "endpoints": endpoints, "palm": palm, "cap_ids": cap_ids,
                        "marker": wrist_marker, "root_parent": original_bones[f"{leg}_haa"][3],
                        "body_shift": body_shift if options.palm_shape == "claw" else 0.0}
        report["rest"][leg] = {"old_joint_heads_m": [encode(p) for p in old],
                              "new_joint_heads_m": [encode(p) for p in points],
                              "wrist_world_shift_m": (points[2] - old[2]).length,
                              "wrist_vs_reposed_old_kfe_shift_m": 0.0,
                              "removed_ghost_length_m": (old[3] - old[2]).length,
                              "removed_foot_head_m": encode(old[3]), "native_pad_bounds_m": old_bounds,
                              "native_pad_midpoint_m": encode(old_center), "native_cylinder": source_measure,
                              "hinge_axis_world": encode(axis), "role_chain": names,
                              "upper_direction": encode(dirs[0]), "lower_direction": encode(dirs[1]),
                              "upper_side_tilt_deg": side_tilt(dirs[0]), "lower_side_tilt_deg": side_tilt(dirs[1])}

    reflection = Matrix.Identity(4)
    reflection[1][1], reflection[1][3] = -1, 2 * MIRROR_Y
    if options.all_legs:
        for right, left in MIRROR_OF.items():
            source = samples[left]
            mapped = {}
            for joint in LEG_BONES:
                for left_obj, right_obj in zip(roles[left][joint], roles[right][joint]):
                    if left_obj is None:
                        continue
                    # Original right object names matter to BALL_MESHES. Reflect data, not object scale.
                    mesh = bake_world(left_obj).copy()
                    mesh.transform(reflection)
                    bm = bmesh.new()
                    bm.from_mesh(mesh)
                    bmesh.ops.reverse_faces(bm, faces=list(bm.faces))
                    bm.to_mesh(mesh)
                    bm.free()
                    mesh.update()
                    right_obj.modifiers.clear()
                    right_obj.parent = None
                    right_obj.matrix_world = Matrix.Identity(4)
                    right_obj.data = mesh
                    mapped[left_obj.name] = right_obj
            native_points = [arm_mw @ bones[f"{right}_{j}"].head_local for j in LEG_BONES]
            samples[right] = dict(source, points=[reflection @ p for p in source["points"]],
                axis=-(reflection.to_3x3() @ source["axis"]),
                names=[n.replace(left + "_", right + "_", 1) for n in source["names"]],
                objects=[(mapped[obj.name], name.replace(left + "_", right + "_", 1))
                         for obj, name in source["objects"]],
                endpoints=[(mapped[obj.name], ids) for obj, ids in source["endpoints"]],
                palm=mapped[source["palm"].name], marker=mapped[source["marker"].name],
                root_parent=original_bones[f"{right}_haa"][3])
            report["rest"][right] = {
                "mirror_source": left, "new_joint_heads_m": [encode(p) for p in samples[right]["points"]],
                "hinge_axis_world": encode(samples[right]["axis"]), "role_chain": samples[right]["names"],
                "native_upper_lower_lengths_m": [(native_points[i + 1] - native_points[i]).length for i in range(2)],
                "mirrored_upper_lower_lengths_m": [(source["points"][i + 1] - source["points"][i]).length for i in range(2)]}
        report["pose_handling"] = "Clear all rebuilt leg bases; trunk unchanged. Right geometry reflected from built left, not guessed yaw."
    if options.sole_at_ball_bottom:
        report["construction"] = "Six claw sections: root ring centroid at unchanged pivot; first transition joins lowered body. " \
            "Distal ring Z offset from actual evaluated ball bottom; X/Y outline and dorsal curvature unchanged."
    report["all_legs"] = options.all_legs
    report["sole_at_ball_bottom"] = options.sole_at_ball_bottom

    # All affected meshes are detached before rest edits; explicitly bind preserved world geometry after.
    bpy.context.view_layer.objects.active = arm
    bpy.ops.object.mode_set(mode="EDIT")
    eb = arm.data.edit_bones
    for leg, sample in samples.items():
        p, names, axis = sample["points"], sample["names"], sample["axis"]
        eb.remove(eb[f"{leg}_foot"])
        for old_name, new_name in zip(("haa", "hfe", "kfe"), names[1:]):
            eb[f"{leg}_{old_name}"].name = new_name
        swing = eb.new(names[0])
        swing.head = arm_inv @ p[0]
        # Display stub only, same native old foot display length; no extra physical segment.
        swing.tail = swing.head + arm_inv.to_3x3() @ Vector((0, 0, 0.1))
        swing.parent = eb[sample["root_parent"]]
        previous = swing
        palm_length = sample["palm_bone_length"]
        for i, name in enumerate(names[1:]):
            bone = eb[name]
            bone.use_connect = False
            bone.head = arm_inv @ p[i]
            tail = p[i + 1] if i < 2 else p[2] + Vector((palm_length, 0, 0))
            bone.tail = arm_inv @ tail
            local_axis = arm_inv.to_3x3() @ axis
            bone.align_roll(local_axis.cross((bone.tail - bone.head).normalized()))
            bone.parent = previous
            previous = bone
    bpy.ops.object.mode_set(mode="OBJECT")
    for sample in samples.values():
        for name in sample["names"]:
            arm.pose.bones[name].matrix_basis = Matrix.Identity(4)
    bpy.context.view_layer.update()
    for sample in samples.values():
        for obj, name in sample["objects"]:
            world = obj.matrix_world.copy()
            obj.parent = arm
            obj.parent_type = "BONE"
            obj.parent_bone = name
            obj.matrix_parent_inverse = Matrix.Identity(4)
            bpy.context.view_layer.update()
            obj.matrix_world = world
    bpy.context.view_layer.update()
    if options.palm_shape == "claw":
        with bpy.data.libraries.load(str(baseline_dir / "sample_neutral.blend"), link=False) as (src, dst):
            dst.armatures = src.armatures
        prior_arm = dst.armatures[0]
        expected_names = set(prior_arm.bones.keys())
        if options.all_legs:
            expected_names.difference_update(f"{leg}_{j}" for leg in MIRROR_OF for j in LEG_BONES)
            expected_names.update(n for leg in MIRROR_OF for n in samples[leg]["names"])
        assert expected_names == set(arm.data.bones.keys()), "P2 joint count/names changed"
        for bone in arm.data.bones:
            if options.all_legs and bone.name.startswith(tuple(leg + "_" for leg in MIRROR_OF)):
                continue
            prior = prior_arm.bones[bone.name]
            assert bone.head_local == prior.head_local and bone.tail_local == prior.tail_local, "P2 bone points changed"
            assert bone.matrix_local == prior.matrix_local, "P2 bone axis changed"
            assert (bone.parent.name if bone.parent else None) == (prior.parent.name if prior.parent else None)
        bpy.data.armatures.remove(prior_arm)
        report["baseline_bone_points_axes_parents"] = "EXACTLY_UNCHANGED"
        for leg, sample in samples.items():
            if leg not in LEFT_LEGS:
                continue
            assert report["rest"][leg]["new_joint_heads_m"] == baseline["rest"][leg]["new_joint_heads_m"]
            source_lines[leg] = sample["points"] + [sample["points"][2] + Vector((sample["palm_bone_length"], 0, 0))]
            source_meshes[leg] = []
            for obj, parent in sample["objects"]:
                if obj is sample["palm"]:
                    data = sample["halfpad_mesh"]
                else:
                    data = bpy.data.meshes.new_from_object(obj.evaluated_get(bpy.context.evaluated_depsgraph_get()),
                                                          depsgraph=bpy.context.evaluated_depsgraph_get())
                    data.transform(obj.matrix_world)
                source_meshes[leg].append(data)
            report["rest"][leg]["before_halfpad_world_bounds_m"] = [
                [min(v.co[i] for v in sample["halfpad_mesh"].vertices),
                 max(v.co[i] for v in sample["halfpad_mesh"].vertices)] for i in range(3)]
            report["rest"][leg]["baseline_palm_world_bounds_m"] = baseline["rest"][leg]["palm_world_bounds_m"]
            bm = bmesh.new()
            bm.from_mesh(sample["palm"].data)
            assert all(e.is_manifold and e.is_contiguous for e in bm.edges), "claw not watertight/oriented"
            volume = bm.calc_volume(signed=True)
            assert volume > 0, "claw inward winding"
            bm.free()
            report["rest"][leg]["claw_topology"] = {"watertight_consistent_outward": True, "signed_volume_m3": volume,
                "physical_cap_vertex_ids": sample["cap_ids"], "sections": len(sections)}

    def surface_overlap(lower, palm):
        from mathutils.bvhtree import BVHTree
        trees = []
        for obj in (lower, palm):
            evaluated = obj.evaluated_get(bpy.context.evaluated_depsgraph_get())
            mesh = evaluated.to_mesh()
            try:
                trees.append(BVHTree.FromPolygons([evaluated.matrix_world @ v.co for v in mesh.vertices],
                    [list(face.vertices) for face in mesh.polygons]))
            finally:
                evaluated.to_mesh_clear()
        return len(trees[0].overlap(trees[1]))

    def measure(leg):
        sample = samples[leg]
        n = sample["names"]
        root = arm_mw @ arm.pose.bones[n[3]].head
        lower_tail = arm_mw @ arm.pose.bones[n[2]].tail
        palm_points = vertices(sample["palm"])
        body_points = [p for i, p in enumerate(palm_points) if i not in sample["cap_ids"]]
        cap = center([palm_points[i] for i in sample["cap_ids"]])
        cap_vectors = [palm_points[i] - cap for i in sample["cap_ids"]]
        cap_normal = next(a.cross(b).normalized() for a in cap_vectors for b in cap_vectors
                          if a.cross(b).length > 1e-8)
        marker_points = vertices(sample["marker"])
        mesh_ends = []
        for segment, indices in sample["endpoints"]:
            v = vertices(segment)
            mesh_ends.append([center([v[i] for i in group]) for group in indices])
        return {"computed_body_z_shift_m": sample["body_shift"],
                "actual_ball_world_min_z_m": min(p.z for p in marker_points),
                "palm_min_z_minus_ball_min_z_m": min(p.z for p in palm_points) - min(p.z for p in marker_points),
                "palm_body_min_z_minus_ball_min_z_m": min(p.z for p in body_points) - min(p.z for p in marker_points),
                "lower_palm_BVH_surface_overlap_pairs": surface_overlap(sample["endpoints"][1][0], sample["palm"]),
                "bone_root_m": encode(root), "lower_bone_tail_m": encode(lower_tail),
                "physical_cap_center_m": encode(cap), "cap_root_residual_m": (cap - root).length,
                "lower_mesh_distal_center_m": encode(mesh_ends[1][1]),
                "lower_mesh_distal_to_root_m": (mesh_ends[1][1] - root).length,
                "lower_mesh_distal_signed_distance_to_cap_plane_m": (mesh_ends[1][1] - cap).dot(cap_normal),
                "physical_root_cap_planarity_residual_m": max(abs(v.dot(cap_normal)) for v in cap_vectors),
                "physical_cap_normal_world": encode(cap_normal),
                "upper_mesh_head_to_bone_m": (mesh_ends[0][0] - arm_mw @ arm.pose.bones[n[1]].head).length,
                "upper_mesh_tail_to_elbow_m": (mesh_ends[0][1] - arm_mw @ arm.pose.bones[n[2]].head).length,
                "lower_mesh_head_to_elbow_m": (mesh_ends[1][0] - arm_mw @ arm.pose.bones[n[2]].head).length,
                "joint_marker_vertex_centroid_m": encode(center(marker_points)),
                "marker_centroid_to_root_m": (center(marker_points) - root).length,
                "segment_end_centers_m": [[encode(p) for p in pair] for pair in mesh_ends],
                "palm_body_x_from_root_m": [min(p.x - root.x for p in palm_points),
                                             max(p.x - root.x for p in palm_points)],
                "palm_world_bounds_m": [[min(p[i] for p in palm_points), max(p[i] for p in palm_points)]
                                         for i in range(3)],
                "palm_vertices": len(palm_points), "palm_faces": len(sample["palm"].data.polygons),
                "numeric_roundoff_bound_m_NOT_acceptance": roundoff(palm_points)}

    def mechanical_check():
        if options.all_legs:
            assert set(samples) == {"lf", "rf", "rl", "rr"}, "incomplete four-leg geometry"
            for right, left in MIRROR_OF.items():
                for (obj, _), (other, _) in zip(samples[left]["objects"], samples[right]["objects"]):
                    a, b = vertices(obj), vertices(other)
                    assert len(a) == len(b) and max((reflection @ p - q).length for p, q in zip(a, b)) <= roundoff(a), "unmirrored right mesh"
                    assert other.matrix_world.to_3x3().determinant() > 0, "negative object determinant"
                for l_name, r_name in zip(samples[left]["names"], samples[right]["names"]):
                    l_bone, r_bone = arm.data.bones[l_name], arm.data.bones[r_name]
                    assert (reflection @ (arm_mw @ l_bone.head_local) - arm_mw @ r_bone.head_local).length <= roundoff(a)
                    assert (reflection @ (arm_mw @ l_bone.tail_local) - arm_mw @ r_bone.tail_local).length <= roundoff(a)
        for leg, sample in samples.items():
            names = sample["names"]
            for parent, child in zip(names, names[1:]):
                assert arm.data.bones[child].parent.name == parent, "wrong role parent: " + child
            assert not arm.data.bones[names[-1]].children, "retained toe/distal joint"
            assert all(f"{leg}_{j}" not in arm.data.bones for j in LEG_BONES), "retained old chain"
            for obj, name in sample["objects"]:
                assert obj.parent == arm and obj.parent_type == "BONE" and obj.parent_bone == name, "wrong mesh parent"
            assert all(segment is not None and len(segment.data.polygons) > 0
                       for segment, indices in sample["endpoints"]), "missing physical segment"
            if options.palm_shape == "claw":
                bm = bmesh.new()
                bm.from_mesh(sample["palm"].data)
                assert all(e.is_manifold and e.is_contiguous for e in bm.edges), "palm not closed/oriented"
                volume = bm.calc_volume(signed=True)
                bm.free()
                assert volume > 0, "inward reflected palm"
            m = measure(leg)
            eps = m["numeric_roundoff_bound_m_NOT_acceptance"]
            assert m["cap_root_residual_m"] <= eps, "physical palm root mismatch: " + str(m)
            if options.sole_at_ball_bottom:
                assert abs(m["palm_body_min_z_minus_ball_min_z_m"]) <= eps, "high distal body sole: not aligned to actual ball bottom"
                assert abs(m["palm_min_z_minus_ball_min_z_m"]) <= eps, "high sole: not aligned to actual ball bottom"
            assert m["palm_body_x_from_root_m"][0] >= -eps, "centered palm crosses behind pivot"
            assert m["palm_body_x_from_root_m"][1] > eps, "no forward palm length"
            assert m["lower_mesh_distal_to_root_m"] <= eps, "lower mesh ends before wrist"
            assert max(m[key] for key in ("upper_mesh_head_to_bone_m", "upper_mesh_tail_to_elbow_m",
                                         "lower_mesh_head_to_elbow_m")) <= eps, "physical segment cap mismatch"

    for leg in samples:
        report["rest"][leg].update(measure(leg))
        if options.palm_shape == "claw":
            bounds = report["rest"][leg]["palm_world_bounds_m"]
            report["rest"][leg]["raw_length_width_thickness_m"] = [hi - lo for lo, hi in bounds]
            coords = vertices(samples[leg]["palm"])
            report["rest"][leg]["raw_section_x_width_thickness_m"] = [
                [center(coords[s * count:(s + 1) * count]).x - samples[leg]["points"][2].x,
                 max(p.y for p in coords[s * count:(s + 1) * count]) - min(p.y for p in coords[s * count:(s + 1) * count]),
                 max(p.z for p in coords[s * count:(s + 1) * count]) - min(p.z for p in coords[s * count:(s + 1) * count])]
                for s in range(len(sections))]
    if options.regression_without_fix:
        # Narrow inverse of the cap placement fix, memory only; actual geometry, not a fake fixture.
        sample = samples["lf"]
        length = max(v.co.x for v in sample["palm"].data.vertices) - sample["points"][2].x
        for v in sample["palm"].data.vertices:
            v.co.x -= length / 2
        sample["palm"].data.update()
        bpy.context.view_layer.update()
    mechanical_check()

    def reject(label, mutate, restore):
        mutate()
        bpy.context.view_layer.update()
        try:
            mechanical_check()
        except AssertionError as exc:
            report["negative_checks"][label] = str(exc)
        else:
            raise AssertionError("Regression failed to detect: " + label)
        finally:
            restore()
            bpy.context.view_layer.update()
        mechanical_check()

    palm = samples["lf"]["palm"]
    if options.sole_at_ball_bottom:
        saved_coords = {leg: [v.co.copy() for v in s["palm"].data.vertices] for leg, s in samples.items()}
        def sole_restore(high):
            for leg, sample in samples.items():
                for i, v in enumerate(sample["palm"].data.vertices):
                    v.co = saved_coords[leg][i]
                    if high and i not in sample["cap_ids"]:
                        v.co.z -= sample["body_shift"]
                sample["palm"].data.update()
        sole_restore(True)
        bpy.context.view_layer.update()
        report["distal_body_high_sole_negative"] = {leg: measure(leg) for leg in samples}
        sole_restore(False)
        bpy.context.view_layer.update()
        reject("old_high_sole", lambda: sole_restore(True), lambda: sole_restore(False))
        for leg, sample in samples.items():
            sole_restore(True)
            bpy.context.view_layer.update()
            report["rest"][leg]["before_high_sole_lower_palm_BVH_surface_overlap_pairs"] = surface_overlap(
                sample["endpoints"][1][0], sample["palm"])
            sole_restore(False)
            bpy.context.view_layer.update()
    if options.all_legs:
        saved_right = samples["rf"]
        reject("old_twoleg_incomplete", lambda: samples.pop("rf"), lambda: samples.__setitem__("rf", saved_right))
        saved = [v.co.copy() for v in saved_right["palm"].data.vertices]
        def unmirror(bad):
            for v, co in zip(saved_right["palm"].data.vertices, saved):
                v.co = co + (Vector((0, .01, 0)) if bad else Vector())
            saved_right["palm"].data.update()
        reject("unmirrored_right", lambda: unmirror(True), lambda: unmirror(False))
    reject("wrong_mesh_parent", lambda: setattr(palm, "parent_bone", samples["lf"]["names"][2]),
           lambda: setattr(palm, "parent_bone", samples["lf"]["names"][3]))
    segment, indices = samples["lf"]["endpoints"][1]
    reject("missing_segment", lambda: samples["lf"]["endpoints"].__setitem__(1, (None, indices)),
           lambda: samples["lf"]["endpoints"].__setitem__(1, (segment, indices)))
    saved_inverse = palm.matrix_parent_inverse.copy()
    reject("stale_inverse", lambda: setattr(palm, "matrix_parent_inverse", Matrix.Translation((0.01, 0, 0))),
           lambda: setattr(palm, "matrix_parent_inverse", saved_inverse))
    # Distal topology negative uses the actual sample armature, not P1's synthetic fixture.
    def toe(add):
        bpy.context.view_layer.objects.active = arm
        bpy.ops.object.mode_set(mode="EDIT")
        eb = arm.data.edit_bones
        if add:
            child = eb.new("rl_toe")
            child.head, child.tail = (0, 0, 0), (0, 0, 0.1)
            child.parent = eb[samples["rl"]["names"][3]]
        else:
            eb.remove(eb["rl_toe"])
        bpy.ops.object.mode_set(mode="OBJECT")
    reject("retained_toe", lambda: toe(True), lambda: toe(False))

    neutral = {obj.name: vertices(obj) for sample in samples.values() for obj, name in sample["objects"]}
    turn_geometry = {}
    for leg, sample in samples.items():
        for name in sample["names"][2:]:
            pivot = arm_mw @ arm.data.bones[name].head_local
            axis_local = arm.data.bones[name].matrix_local.to_3x3().inverted() @ (
                arm_inv.to_3x3() @ sample["axis"])
            downstream = {b.name for b in arm.data.bones[name].children_recursive} | {name}
            for angle in angles:
                pose = arm.pose.bones[name]
                pose.rotation_mode = "QUATERNION"
                from mathutils import Quaternion
                pose.rotation_quaternion = Quaternion(axis_local, math.radians(angle))
                bpy.context.view_layer.update()
                rotation = Matrix.Rotation(math.radians(angle), 4, sample["axis"])
                expected = Matrix.Translation(pivot) @ rotation @ Matrix.Translation(-pivot)
                residuals = {}
                for obj, parent in sample["objects"]:
                    transform = expected if parent in downstream else Matrix.Identity(4)
                    got = vertices(obj)
                    residuals[obj.name] = max((actual - transform @ rest).length
                                             for actual, rest in zip(got, neutral[obj.name]))
                    assert residuals[obj.name] <= roundoff(got), "mesh drifts under turn: " + obj.name
                measurement = measure(leg)
                if options.sole_at_ball_bottom:
                    sole_restore(True)
                    bpy.context.view_layer.update()
                    measurement["before_high_sole_lower_palm_BVH_surface_overlap_pairs"] = surface_overlap(
                        sample["endpoints"][1][0], sample["palm"])
                    sole_restore(False)
                    bpy.context.view_layer.update()
                measurement.update({"leg": leg, "joint": name, "angle_deg": angle,
                                    "rigid_vertex_residuals_m": residuals})
                report["turns"].append(measurement)
                turn_geometry[(leg, name, angle)] = {obj.name: vertices(obj) for obj, parent in sample["objects"]}
                pose.rotation_quaternion = Quaternion()
                bpy.context.view_layer.update()
    mechanical_check()
    if options.all_legs:
        # Independent oracle: reflected evaluated LEFT motion, never reconstructed from right axis/roll.
        def mirrored_motion(right, left, left_name, right_name, angle, right_geometry):
            left_geometry = turn_geometry[(left, left_name, angle)]
            residuals = {}
            for (left_obj, _), (right_obj, _) in zip(samples[left]["objects"], samples[right]["objects"]):
                expected = [reflection @ p for p in left_geometry[left_obj.name]]
                actual = right_geometry[right_obj.name]
                assert len(expected) == len(actual), "mirrored motion vertex count mismatch"
                residuals[right_obj.name] = max((p - q).length for p, q in zip(expected, actual))
                assert residuals[right_obj.name] <= roundoff(expected + actual), "same-angle mirrored motion mismatch: " + right_name
            return residuals

        report["same_angle_mirrored_motion"] = []
        for right, left in MIRROR_OF.items():
            for left_name, right_name in zip(samples[left]["names"][2:], samples[right]["names"][2:]):
                for angle in angles:
                    residuals = mirrored_motion(right, left, left_name, right_name, angle,
                                                turn_geometry[(right, right_name, angle)])
                    report["same_angle_mirrored_motion"].append({"leg": right, "joint": right_name,
                        "angle_deg": angle, "reflected_left_vertex_residuals_m": residuals})
                    if angle == 0:
                        continue
                    # Actual wrong-hand pose: reverse only right rotation axis, leave bones/meshes untouched.
                    pose = arm.pose.bones[right_name]
                    saved_pose = pose.matrix_basis.copy()
                    axis_local = arm.data.bones[right_name].matrix_local.to_3x3().inverted() @ (
                        arm_inv.to_3x3() @ samples[right]["axis"])
                    label = "mirror_axis_without_fix_%s_%g" % (right_name, angle)
                    try:
                        pose.rotation_quaternion = Quaternion(-axis_local, math.radians(angle))
                        bpy.context.view_layer.update()
                        wrong_geometry = {obj.name: vertices(obj) for obj, _ in samples[right]["objects"]}
                        try:
                            mirrored_motion(right, left, left_name, right_name, angle, wrong_geometry)
                        except AssertionError as exc:
                            assert str(exc).startswith("same-angle mirrored motion mismatch:"), str(exc)
                            drift = max((reflection @ p - q).length
                                for (left_obj, _), (right_obj, _) in zip(samples[left]["objects"], samples[right]["objects"])
                                for p, q in zip(turn_geometry[(left, left_name, angle)][left_obj.name], wrong_geometry[right_obj.name]))
                            report["negative_checks"][label] = {"rejected_by": str(exc), "vertex_drift_m": drift}
                        else:
                            raise AssertionError("Regression failed to detect: " + label)
                    finally:
                        pose.matrix_basis = saved_pose
                        bpy.context.view_layer.update()
                    mechanical_check()
    # A rest-aligned matrix can still drift only on turning: freeze palm world transform after pose.
    name = samples["lf"]["names"][3]
    pose = arm.pose.bones[name]
    saved_basis = palm.matrix_basis.copy()
    rest_world = palm.matrix_world.copy()
    pose.rotation_quaternion = Quaternion(arm.data.bones[name].matrix_local.to_3x3().inverted() @
                                         (arm_inv.to_3x3() @ samples["lf"]["axis"]), math.radians(10))
    bpy.context.view_layer.update()
    palm.matrix_world = rest_world
    bpy.context.view_layer.update()
    drift = max((a - b).length for a, b in zip(vertices(palm), turn_geometry[("lf", name, 10.0)][palm.name]))
    assert drift > roundoff(vertices(palm)), "turn-only stale matrix negative not detected"
    report["negative_checks"]["turn_only_stale_matrix"] = {"vertex_drift_m": drift}
    pose.rotation_quaternion = Quaternion()
    palm.matrix_basis = saved_basis
    bpy.context.view_layer.update()
    mechanical_check()

    right_residual = max((a - b).length for obj_name, old_points in original_right.items()
                         for a, b in zip(vertices(bpy.data.objects[obj_name]), old_points))
    if not options.all_legs:
        assert right_residual == 0, "untouched right meshes changed"
    for n, (head, tail, matrix, parent) in original_bones.items():
        if n.startswith(tuple(leg + "_" for leg in samples)):
            continue
        b = arm.data.bones[n]
        assert b.head_local == head and b.tail_local == tail and b.matrix_local == matrix, "other bone changed"
    report["right_vs_native_vertex_residual_m"] = right_residual
    if not options.all_legs:
        report["untouched_right_vertex_residual_m"] = right_residual
    if options.all_legs:
        exporter = os.path.join(_SCRIPT_DIR, "generate_urdf.py")
        old_argv = sys.argv
        sys.argv = [exporter, "--", "--robot", "lizard2_palm_contract", "--contract_check", "--memory_scene"]
        namespace = {"__file__": exporter, "__name__": "__main__"}
        try:
            try:
                exec(compile(Path(exporter).read_text(encoding="utf-8"), exporter, "exec"), namespace)
            except SystemExit as exc:
                assert exc.code == 0
        finally:
            sys.argv = old_argv
        assert len(namespace["binding"]) == 4
        report["real_exporter_memory_contract"] = "PASS four native palm terminal bindings; no export"
    report["collision_limits"] = "BVHTree evaluated lower-cylinder/palm surface intersections only, neutral and 24 single-joint snapshots. " \
        "Pair counts are not penetration depths or clearance. Containment not detected. Root surfaces still intersect; " \
        "no shank trimming, ball rescaling, collision filtering, ROM, full-cycle, physics or self-collision acceptance."
    report["mechanical_invariants"] = "PASS only topology, physical cap construction and float32 rigid-parent arithmetic; NOT P2 geometry acceptance"
    after = {str(p.relative_to(repo)): file_binding.sha256_file(p) for p in protected}
    assert hashes == after, "protected source/adopted/export/frozen files changed"
    report["protected_sha256_after"] = after
    print("P2 MECHANICAL CHECK OK; %d real limbs; %d single-joint measurements; negatives=%d; NOT ACCEPTED" %
          (len(samples), len(report["turns"]), len(report["negative_checks"])))
    if options.check_only:
        if options.sole_at_ball_bottom:
            print("P2 DISTAL BODY SOLE: " + json.dumps({leg: {
                "palm_body_min_z_minus_ball_min_z_m": m["palm_body_min_z_minus_ball_min_z_m"],
                "numeric_roundoff_bound_m_NOT_acceptance": m["numeric_roundoff_bound_m_NOT_acceptance"]}
                for leg, m in report["rest"].items()}, sort_keys=True))
            print("P2 DISTAL BODY NEGATIVE: " + json.dumps({"rejected_by": report["negative_checks"]["old_high_sole"],
                "palm_body_min_z_minus_ball_min_z_m": {leg: m["palm_body_min_z_minus_ball_min_z_m"]
                    for leg, m in report["distal_body_high_sole_negative"].items()}}, sort_keys=True))
        if options.all_legs:
            print("P2 SAME-ANGLE MIRROR: " + json.dumps(report["same_angle_mirrored_motion"], sort_keys=True))
            print("P2 WRONG-HAND ACTUAL POSE NEGATIVES: " + json.dumps({label: result
                for label, result in report["negative_checks"].items() if label.startswith("mirror_axis_without_fix_")}, sort_keys=True))
        print("P2 COLLISION SNAPSHOTS: %d/%d still intersect; NOT collision acceptance" % (
            sum(m["lower_palm_BVH_surface_overlap_pairs"] > 0 for m in report["turns"]), len(report["turns"])))
        print("P2 CHECK_ONLY: no files written; protected hashed=%d unchanged" % len(hashes))
        return
    output.mkdir()
    arm["p2_sample"] = ("four mirrored palms; PROVISIONAL lowered body, root at pivot" if options.all_legs else
                        "lf and rl native palm only; rf/rr untouched old chain; NOT EXPORTABLE as four-limb palm")
    arm["p2_approval"] = report["approval"]
    scene["p2_report"] = "measurements.json"
    scene["p2_status"] = report["status"]
    bpy.ops.wm.save_as_mainfile(filepath=str(output / "sample_neutral.blend"))
    if options.all_legs:
        object_names = {leg: [(obj.name, parent) for obj, parent in s["objects"]] for leg, s in samples.items()}
        bpy.ops.wm.open_mainfile(filepath=str(claw_dir / "sample_neutral.blend"))
        prior_arm = next(o for o in bpy.context.scene.objects if o.type == "ARMATURE")
        prior_bones = {b.name: (b.head_local.copy(), b.tail_local.copy(), b.matrix_local.copy())
                       for b in prior_arm.data.bones if b.name.startswith(("lf_", "rl_"))}
        prior_vertices = {name: vertices(bpy.data.objects[name]) for leg in LEFT_LEGS for name, _ in object_names[leg]}
        for label in ("actual_old_twoleg_blend", "actual_old_high_sole_blend"):
            try:
                if label == "actual_old_twoleg_blend":
                    assert all(n in prior_arm.data.bones for s in samples.values() for n in s["names"]), "old sample retains native right chain"
                else:
                    old_palm = prior_vertices[object_names["lf"][-1][0]]
                    old_ball = prior_vertices[object_names["lf"][-2][0]]
                    assert abs(min(p.z for p in old_palm) - min(p.z for p in old_ball)) <= roundoff(old_palm), "old sole above actual ball bottom"
            except AssertionError as exc:
                report["negative_checks"][label] = str(exc)
                print("NEGATIVE", label, str(exc))
            else:
                raise AssertionError("Actual old baseline unexpectedly satisfies lowered four-leg contract")
        bpy.ops.wm.open_mainfile(filepath=str(output / "sample_neutral.blend"))
        scene = bpy.context.scene
        arm = next(o for o in scene.objects if o.type == "ARMATURE")
        for leg, sample in samples.items():
            sample["objects"] = [(bpy.data.objects[name], parent) for name, parent in object_names[leg]]
            sample["palm"] = sample["objects"][-1][0]
            sample["marker"] = sample["objects"][-2][0]
            sample["endpoints"] = [(sample["objects"][i][0], ids)
                                   for i, (_, ids) in zip((1, 3), sample["endpoints"])]
        for name, (head, tail, matrix) in prior_bones.items():
            bone = arm.data.bones[name]
            assert bone.head_local == head and bone.tail_local == tail and bone.matrix_local == matrix, "old claw left bone changed"
        for leg in LEFT_LEGS:
            for obj, _ in samples[leg]["objects"]:
                got, old = vertices(obj), prior_vertices[obj.name]
                axes = (0, 1) if obj is samples[leg]["palm"] else (0, 1, 2)
                assert len(got) == len(old)
                residual = max(abs(a[i] - b[i]) for a, b in zip(got, old) for i in axes)
                assert residual <= roundoff(got), "old claw accepted outline/limb changed"
        palm = samples["lf"]["palm"]
        mechanical_check()
        report["neutral_reopen_and_old_claw_left_geometry"] = "PASS exact left bones/axes; unchanged non-palm world vertices and palm XY outline (float32 arithmetic)"
    # Diagnostic-only collection: overlay geometry never enters the source armature/meshes.
    overlay = bpy.data.collections.new("P2_DIAGNOSTICS_NOT_EXPORT_OR_COLLISION")
    scene.collection.children.link(overlay)
    scene.render.engine = "BLENDER_WORKBENCH"
    scene.render.resolution_x, scene.render.resolution_y = 1100, 750
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.display.shading.light = "STUDIO"
    scene.display.shading.color_type = "OBJECT"
    scene.display.shading.show_shadows = False
    scene.display.shading.show_cavity = True
    scene.display.shading.background_type = "WORLD"
    scene.world.color = (0.035, 0.035, 0.035)
    camera_data = bpy.data.cameras.new("P2_camera")
    camera_data.type = "ORTHO"
    camera = bpy.data.objects.new("P2_camera", camera_data)
    overlay.objects.link(camera)
    scene.camera = camera
    def label_material(name, color):
        material = bpy.data.materials.new(name)
        material.diffuse_color = color
        return material
    label_white = label_material("P2_label_white", (1, 1, 1, 1))
    pngs = []

    def overlay_link(obj):
        for collection in list(obj.users_collection):
            collection.objects.unlink(obj)
        overlay.objects.link(obj)
        obj["diagnostic_only"] = True
        return obj

    def line(a, b, color, radius=0.006):
        curve = bpy.data.curves.new("diagnostic_line", "CURVE")
        curve.dimensions = "3D"
        curve.bevel_depth = radius
        spline = curve.splines.new("POLY")
        spline.points.add(1)
        spline.points[0].co, spline.points[1].co = (*a, 1), (*b, 1)
        obj = bpy.data.objects.new("diagnostic_line", curve)
        overlay.objects.link(obj)
        obj.color = color
        obj["diagnostic_only"] = True

    def ball(p, color):
        bpy.ops.mesh.primitive_uv_sphere_add(segments=12, ring_count=6, radius=0.015, location=p)
        obj = overlay_link(bpy.context.object)
        obj.color = color

    def text(label, position, size=0.035):
        font = bpy.data.curves.new("diagnostic_label", "FONT")
        font.body, font.size = label, size
        font.materials.append(label_white)
        obj = bpy.data.objects.new("diagnostic_label", font)
        overlay.objects.link(obj)
        obj.location = position
        obj.rotation_euler = camera.rotation_euler
        obj.color = (1, 1, 1, 1)
        obj["diagnostic_only"] = True

    def clear_overlay():
        for obj in list(overlay.objects):
            if obj is not camera:
                bpy.data.objects.remove(obj, do_unlink=True)

    if options.all_legs:
        full_points = [p for obj in scene.objects if obj.type == "MESH" for p in vertices(obj)]
        target = Vector(tuple((min(p[i] for p in full_points) + max(p[i] for p in full_points)) / 2 for i in range(3)))
        views = [("all_top", target, Vector((0, 0, 1)), 5.2, None),
                 ("all_oblique", target, Vector((1.3, -2, 1.6)), 5.2, None)]
        for leg in ("lf", "rf", "rl", "rr"):
            views.append((leg + "_root", samples[leg]["points"][2] + Vector((.1, 0, -.025)),
                          Vector((.5, 1 if leg in LEFT_LEGS else -1, .35)), .75, leg))
        for name, target, direction, scale, leg in views:
            clear_overlay()
            keep = {obj.name for obj, _ in samples[leg]["objects"]} if leg else None
            for obj in scene.objects:
                if obj.type == "MESH":
                    obj.hide_render = keep is not None and obj.name not in keep
                    obj.color = (.25, .65, .7, 1)
            camera.location = target + direction.normalized() * 5
            camera.rotation_euler = (target - camera.location).to_track_quat("-Z", "Y").to_euler()
            camera_data.ortho_scale = scale
            scene.render.filepath = str(output / (name + ".png"))
            bpy.ops.render.render(write_still=True)
            pngs.append(str((output / (name + ".png")).relative_to(repo)))
    for leg, sample in (() if options.all_legs else samples.items()):
        for view in ("side", "oblique", "turns"):
            clear_overlay()
            keep = {obj.name for obj, parent in sample["objects"]}
            for obj in scene.objects:
                if obj.type in ("MESH", "ARMATURE"):
                    obj.hide_render = obj.name not in keep
            p = sample["points"]
            target = center(p)
            direction = Vector((0, -1, 0)) if view != "oblique" else Vector((1.3, -2, 1.3))
            camera.location = target + direction.normalized() * 4
            camera.rotation_euler = (target - camera.location).to_track_quat("-Z", "Y").to_euler()
            camera_data.ortho_scale = 1.8 if view == "turns" else 3.2
            right = camera.rotation_euler.to_matrix() @ Vector((1, 0, 0))
            old_offset = -right * 0.75 if view != "turns" else Vector()
            new_offset = right * 0.75 if view != "turns" else Vector()
            if view != "turns":
                for obj, parent in sample["objects"]:
                    obj.hide_render = True
                    mesh = bpy.data.meshes.new_from_object(obj.evaluated_get(bpy.context.evaluated_depsgraph_get()),
                                                          depsgraph=bpy.context.evaluated_depsgraph_get())
                    mesh.transform(obj.matrix_world)
                    display = bpy.data.objects.new("P2_new_mesh", mesh)
                    overlay.objects.link(display)
                    display.location = new_offset
                    display.color = (0.25, 0.65, 0.7, 1)
                    display["diagnostic_only"] = True
                for mesh in source_meshes[leg]:
                    display = bpy.data.objects.new("P2_source_mesh", mesh)
                    overlay.objects.link(display)
                    display.location = old_offset
                    display.color = (0.65, 0.42, 0.22, 1)
                    display["diagnostic_only"] = True
            # Offset lines toward camera so bone geometry remains visible through opaque meshes.
            front = (camera.location - target).normalized() * 0.5
            old_front, new_front = front + old_offset, front + new_offset
            if view != "turns":
                up = camera.rotation_euler.to_matrix() @ Vector((0, 1, 0))
                text("BEFORE halfpad" if options.palm_shape == "claw" else "SOURCE", target + old_front + up * 0.58, 0.06)
                text("AFTER claw" if options.palm_shape == "claw" else "P2 SAMPLE", target + new_front + up * 0.58, 0.06)
            old = source_lines[leg]
            for i in range(len(old) - 1):
                line(old[i] + old_front, old[i + 1] + old_front, (1, 0.35, 0.05, 1))
                ball(old[i] + old_front, (1, 0.35, 0.05, 1))
            for i in range(2):
                line(p[i] + new_front, p[i + 1] + new_front, (0.05, 1, 0.3, 1))
            palm_tip = arm_mw @ arm.data.bones[sample["names"][3]].tail_local
            line(p[2] + new_front, palm_tip + new_front, (0.1, 0.8, 1, 1))
            for i, role in enumerate(("root", "elbow" if leg == "lf" else "knee", "wrist" if leg == "lf" else "ankle")):
                ball(p[i] + new_front, (0.1, 0.8, 1, 1))
                text(role, p[i] + new_front + Vector((0.015, 0, 0.025)))
            if options.palm_shape != "claw":
                text("OLD ghost kfe > foot", old[2] + old_front + Vector((-0.15, 0, -0.16)), 0.03)
            if view == "turns":
                # True evaluated vertex edges from independent -10/+10 single-joint snapshots.
                for name, angle, color in ((sample["names"][2], -10.0, (1, 0.8, 0.1, 1)),
                                           (sample["names"][2], 10.0, (1, 0.1, 0.6, 1)),
                                           (sample["names"][3], -10.0, (0.2, 0.4, 1, 1)),
                                           (sample["names"][3], 10.0, (0.7, 0.3, 1, 1))):
                    coords = turn_geometry[(leg, name, angle)][sample["palm"].name]
                    # Cut root and silhouette edges only: bounded diagnostic wire, actual mesh vertices.
                    cap_ids = set(sample["cap_ids"])
                    for edge in sample["palm"].data.edges:
                        a, b = edge.vertices
                        if a in cap_ids and b in cap_ids:
                            line(coords[a] + front, coords[b] + front, color, 0.003)
                    line(center([coords[i] for i in cap_ids]) + front,
                         max(coords, key=lambda v: v.x) + front, color, 0.003)
                text("elbow/knee: -10 yellow +10 pink\nwrist/ankle: -10 blue +10 purple", target + front + Vector((-0.7, 0, 0.4)), 0.03)
            else:
                up = camera.rotation_euler.to_matrix() @ Vector((0, 1, 0))
                text("green NEW bones; orange OLD bones\ncyan palm rooted +body X; raw measurements only",
                     target + front - right * 0.55 + up * 0.78, 0.045)
            scene.render.filepath = str(output / f"{leg}_{view}.png")
            bpy.ops.render.render(write_still=True)
            pngs.append(str((output / f"{leg}_{view}.png").relative_to(repo)))
    for obj in scene.objects:
        obj.hide_render = False
    report["pngs"] = pngs
    report["blend"] = str((output / "sample_neutral.blend").relative_to(repo))
    # Protected files checked again after save/render, not just construction.
    assert hashes == {str(p.relative_to(repo)): file_binding.sha256_file(p) for p in protected}
    (output / "measurements.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print("P2 OUTPUT " + str(output))


def palm_limit_probe(args):
    """Scan proposed joint ranges on the saved palm candidate without exporting assets."""
    import argparse
    import hashlib
    import itertools
    import json
    from pathlib import Path
    from mathutils import Quaternion
    from mathutils.bvhtree import BVHTree

    parser = argparse.ArgumentParser(description=palm_limit_probe.__doc__)
    parser.add_argument("--limit_probe", action="store_true")
    parser.add_argument("--output_dir", required=True)
    parser.add_argument("--blend", type=Path)
    parser.add_argument("--boundary_samples", type=int, default=0)
    options = parser.parse_args(args)
    source = (options.blend or Path(_ASSET_DIR) / "lizard2_palm_p2_sample_claw_all_lowered_body75_vertical_tail_ground/sample_neutral.blend").resolve()
    output = Path(options.output_dir).resolve()
    if output.parent != Path(_ASSET_DIR).resolve() or not output.name.startswith("lizard2_palm_limit_probe_"):
        raise ValueError("Limit probe requires an isolated lizard2_palm_limit_probe_* output")
    if output.exists():
        raise FileExistsError("Refuse overwrite: " + str(output))
    protected = {p: file_binding.sha256_file(p)
                 for p in Path(_ASSET_DIR).rglob("*") if p.is_file()}
    bpy.ops.wm.open_mainfile(filepath=str(source))
    arm = next(o for o in bpy.context.scene.objects if o.type == "ARMATURE")
    bpy.context.view_layer.update()
    names = [b.name for b in arm.data.bones]
    parents = {b.name: b.parent.name if b.parent else None for b in arm.data.bones}
    pivots = {n: arm.matrix_world @ arm.pose.bones[n].head for n in names}
    frames = {n: arm.matrix_world @ arm.pose.bones[n].matrix for n in names}
    assert all(max(abs(arm.pose.bones[n].matrix_basis[i][j] - (i == j))
                   for i in range(4) for j in range(4)) == 0 for n in names), "Probe requires baked neutral pose"
    exporter = os.path.join(_SCRIPT_DIR, "generate_urdf.py")
    old_argv = sys.argv
    namespace = {"__file__": exporter, "__name__": "__main__"}
    try:
        sys.argv = [exporter, "--", "--robot", "lizard2_palm_contract", "--contract_check", "--memory_scene"]
        try:
            exec(compile(Path(exporter).read_text(encoding="utf-8"), exporter, "exec"), namespace)
        except SystemExit as exc:
            assert exc.code == 0
    finally:
        sys.argv = old_argv
    balls = namespace["BALL_MESHES"]
    geometry, visual, palm_normals = {}, {}, {}
    for obj in bpy.context.scene.objects:
        if obj.type != "MESH":
            continue
        assert obj.parent_type == "BONE" and obj.parent_bone in names, "Unbound mesh: " + obj.name
        evaluated = obj.evaluated_get(bpy.context.evaluated_depsgraph_get())
        mesh = evaluated.to_mesh()
        try:
            mesh.calc_loop_triangles()
            points = [evaluated.matrix_world @ v.co for v in mesh.vertices]
            triangles = [tuple(t.vertices) for t in mesh.loop_triangles]
            data = {"object": obj.name, "points": points, "triangles": triangles}
            visual.setdefault(obj.parent_bone, []).append(data)
            if obj.name not in balls:
                geometry.setdefault(obj.parent_bone, []).append(data)
            if obj.parent_bone.endswith(("_wrist", "_ankle")) and obj.name not in balls:
                surfaces = []
                for face in mesh.polygons:
                    v = [points[i] for i in face.vertices]
                    normal = sum((a.cross(b) for a, b in zip(v, v[1:] + v[:1])), Vector())
                    if normal.length and normal.normalized().z < -.99:
                        surfaces.append((normal.length, -normal.normalized()))
                assert surfaces, "No actual downward sole face: " + obj.name
                palm_normals[obj.parent_bone] = max(surfaces, key=lambda row: row[0])[1]
        finally:
            evaluated.to_mesh_clear()
    axes, limits, knee_facts = {}, {}, {}
    for leg in ("lf", "rf", "rl", "rr"):
        roots = namespace["leg_names"].roots_of(namespace["leg_names"].PALM_NAMING, leg)
        chain = [leg + "_" + r for r in roots]
        u = (pivots[chain[2]] - pivots[chain[1]]).normalized()
        v = (pivots[chain[3]] - pivots[chain[2]]).normalized()
        hinge = u.cross(v).normalized()
        if leg in MIRROR_OF:
            left = axes[MIRROR_OF[leg] + "_" + roots[1]]
            hinge = Vector((-left.x, left.y, -left.z))
        axes[chain[0]] = Vector((0, 0, -1 if leg in MIRROR_OF else 1))
        for n in chain[1:]:
            axes[n] = hinge.copy()
        for n, width in zip(chain, (.6, .6, 1.2, math.pi / 6)):
            limits[n] = (-width, width)
        fold = math.atan2(hinge.dot(u.cross(v)), u.dot(v))
        knee_facts[chain[2]] = {"neutral_fold_deg": math.degrees(fold),
            "straight_q_deg": -math.degrees(fold), "full_fold_q_deg": 180 - math.degrees(fold),
            "extension_margin_deg": math.degrees(fold - 1.2)}
    for n in names:
        if n == "base_link" or n in axes:
            continue
        assert n.endswith(("_yaw", "_pitch")), "Unspecified role: " + n
        axes[n] = (Vector((0, 0, 1)) if n.endswith("_yaw") else
                   (frames[n].to_3x3() @ Vector((1, 0, 0))).normalized())
        width = .6 if n.endswith("_yaw") else .5
        limits[n] = (-width, width)
    ground = -.9711321443319321
    bound = 64 * 2 ** -23 * max(1.0, *(abs(x) for rows in visual.values()
                  for row in rows for p in row["points"] for x in p))
    def motion(pose):
        result = {}
        for n in names:
            parent = result[parents[n]] if parents[n] else Matrix.Identity(4)
            q = pose.get(n, 0)
            local = (Matrix.Translation(pivots[n]) @ Matrix.Rotation(q, 4, axes[n])
                     @ Matrix.Translation(-pivots[n])) if q else Matrix.Identity(4)
            result[n] = parent @ local
        return result
    def bending_ok(n, q):
        fold = math.radians(knee_facts[n]["neutral_fold_deg"]) + q
        return 0 < fold < math.pi
    negatives = {}
    for n in knee_facts:
        q = math.radians(knee_facts[n]["straight_q_deg"]) - .01
        assert not bending_ok(n, q), "Reverse-bending oracle failed"
        pb = arm.pose.bones[n]
        mode, quat = pb.rotation_mode, pb.rotation_quaternion.copy()
        pb.rotation_mode = "QUATERNION"
        pb.rotation_quaternion = Quaternion(frames[n].to_3x3().inverted() @ axes[n], q)
        bpy.context.view_layer.update()
        upper = arm.pose.bones[parents[n]]
        u = (arm.matrix_world @ pb.head - arm.matrix_world @ upper.head).normalized()
        v = (arm.matrix_world @ pb.tail - arm.matrix_world @ pb.head).normalized()
        actual_fold = math.atan2(axes[n].dot(u.cross(v)), u.dot(v))
        assert actual_fold < 0, "Actual Blender reverse pose not rejected: " + n
        negatives[n] = {"reverse_q_deg": math.degrees(q), "actual_signed_fold_deg": math.degrees(actual_fold),
                        "rejected": True}
        pb.rotation_quaternion, pb.rotation_mode = quat, mode
        bpy.context.view_layer.update()
    physical_residual = 0.0
    for n in axes:
        q = limits[n][1]
        pb = arm.pose.bones[n]
        mode, quat = pb.rotation_mode, pb.rotation_quaternion.copy()
        pb.rotation_mode = "QUATERNION"
        pb.rotation_quaternion = Quaternion(frames[n].to_3x3().inverted() @ axes[n], q)
        bpy.context.view_layer.update()
        transform = motion({n: q})
        for child in [n] + [b.name for b in arm.data.bones[n].children_recursive]:
            for row in visual.get(child, []):
                obj = bpy.data.objects[row["object"]]
                evaluated = obj.evaluated_get(bpy.context.evaluated_depsgraph_get())
                mesh = evaluated.to_mesh()
                try:
                    residual = max((evaluated.matrix_world @ v.co - transform[child] @ p).length
                                   for v, p in zip(mesh.vertices, row["points"]))
                    physical_residual = max(physical_residual, residual)
                    assert residual <= bound, "Actual Blender motion differs: " + n
                finally:
                    evaluated.to_mesh_clear()
        pb.rotation_quaternion, pb.rotation_mode = quat, mode
        bpy.context.view_layer.update()
    poses = [("neutral", {})]
    for n, (lo, hi) in limits.items():
        poses.extend((n + ":" + str(q), {n: q}) for q in (lo, lo / 2, hi / 2, hi))
    for leg in ("lf", "rf", "rl", "rr"):
        chain = [n for n in names if n.startswith(leg + "_")]
        for values in itertools.product((-1, 1), repeat=len(chain)):
            poses.append((leg + ":corner:" + str(values),
                          {n: limits[n][1] * s for n, s in zip(chain, values)}))
    if options.boundary_samples:
        if options.boundary_samples < 2:
            raise ValueError("boundary_samples must be at least 2")
        for n, (lo, hi) in limits.items():
            for step in range(1, options.boundary_samples + 1):
                poses.extend(("boundary:" + n + ":" + str(q), {n: q})
                             for q in (lo * step / options.boundary_samples,
                                       hi * step / options.boundary_samples))
    def tree_distance(a, b):
        paths = []
        for n in (a, b):
            path = [n]
            while parents[path[-1]] is not None:
                path.append(parents[path[-1]])
            paths.append(path)
        common = next(n for n in paths[0] if n in paths[1])
        return paths[0].index(common) + paths[1].index(common)
    rows, pair_counts = [], {}
    for label, pose in poses:
        transforms = motion(pose)
        trees, bounds = {}, {}
        for n, objects in geometry.items():
            points, triangles = [], []
            for obj in objects:
                start = len(points)
                points.extend(transforms[n] @ p for p in obj["points"])
                triangles.extend(tuple(start + i for i in t) for t in obj["triangles"])
            trees[n] = BVHTree.FromPolygons(points, triangles, all_triangles=True, epsilon=0)
            bounds[n] = (Vector(tuple(min(p[i] for p in points) for i in range(3))),
                         Vector(tuple(max(p[i] for p in points) for i in range(3))))
        hits = []
        for a, b in itertools.combinations(trees, 2):
            amin, amax = bounds[a]
            bmin, bmax = bounds[b]
            if any(amax[i] < bmin[i] or bmax[i] < amin[i] for i in range(3)):
                continue
            count = len(trees[a].overlap(trees[b]))
            if count:
                adjacent = parents[a] == b or parents[b] == a
                hits.append({"links": [a, b], "surface_pairs": count, "direct_joint_pair": adjacent,
                             "tree_distance_joints": tree_distance(a, b)})
                pair_counts[(a, b)] = pair_counts.get((a, b), 0) + 1
        facing = {n: (transforms[n].to_3x3() @ normal).z for n, normal in palm_normals.items()}
        ground_min = {n: box[0].z - ground for n, box in bounds.items()}
        rows.append({"label": label, "q_rad": pose, "mesh_surface_crossings": hits,
                     "flipped_or_vertical_palms": {n: v for n, v in facing.items() if v <= 0},
                     "floor_penetration_fixed_base_m": {n: v for n, v in ground_min.items() if v < -bound},
                     "reverse_bending": [n for n in knee_facts if not bending_ok(n, pose.get(n, 0))]})
    assert protected == {p: file_binding.sha256_file(p) for p in protected}, "Source artifacts changed"
    report = {"status": "PROPOSED_RANGES_NOT_ACCEPTED", "source": str(source),
        "source_sha256": protected[source], "ground_z_m": ground, "naming": "palm",
        "source_neutral_floor_clearance_m": {n: min(p.z - ground for obj in objects for p in obj["points"])
                                              for n, objects in geometry.items()},
        "axis_convention": "Functional proposal: left swing world +Z/right -Z; limb hinges from left upper cross lower, right axial reflection -R; spine yaw world +Z, pitch actual bone local +X. All axes world-neutral, transported by parents.",
        "candidate_limits_rad": limits, "candidate_axes_world": {n: list(v) for n, v in axes.items()},
        "knee_facts": knee_facts, "reverse_bending_negative_checks": negatives,
        "actual_blender_motion_max_vertex_residual_m": physical_residual,
        "float32_arithmetic_bound_m": bound, "samples": rows,
        "crossing_pair_sample_counts": [{"links": list(pair), "samples": count} for pair, count in pair_counts.items()],
        "protected_files_unchanged": len(protected),
        "limits": "Finite single-joint and leg-box-corner scan, not continuous-box proof; BVH surface crossing only, misses pure containment. Direct joint crossings retained, no filter assumed. Ground violations use fixed base; they do not prove all floating-base motions impossible. No exporter/USD, anatomical ROM, control margin, PD or actual contact filtering validated."}
    output.mkdir()
    (output / "measurements.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    print("LIMIT_PROBE", output, "samples", len(rows), "physical_residual_m", physical_residual)
    print("KNEE_FACTS", json.dumps(knee_facts))
    print("VIOLATIONS", json.dumps({"surface": sum(bool(r["mesh_surface_crossings"]) for r in rows),
          "nonadjacent_surface": sum(any(not h["direct_joint_pair"] for h in r["mesh_surface_crossings"]) for r in rows),
          "flipped_palms": sum(bool(r["flipped_or_vertical_palms"]) for r in rows),
          "fixed_base_floor": sum(bool(r["floor_penetration_fixed_base_m"]) for r in rows)}))


if __name__ == "__main__":
    args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    if "--limit_probe" in args:
        try:
            palm_limit_probe(args)
        except Exception:
            import traceback
            traceback.print_exc()
            raise SystemExit(1)
    elif "--p2_sample" in args:
        try:
            palm_p2_sample(args)
        except Exception:
            import traceback
            traceback.print_exc()
            raise SystemExit(1)
    elif "--contract_self_check" in args:
        try:
            contract_self_check("--regression_without_fix" in args)
        except Exception:
            import traceback
            traceback.print_exc()
            raise SystemExit(1)
    else:
        main()
