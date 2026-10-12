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

import math
import os
import sys

import bmesh
import bpy
from mathutils import Matrix, Vector

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
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
        return {str(p): hashlib.sha256(p.read_bytes()).hexdigest()
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
    for robot in ("lizard", "lizard2", "lizard2_candidate"):
        consume(robot, memory=True)
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
    print("P1 PASS: old consumers=3; palm positive=1; negatives=10; "
          "asset files hashed=%d unchanged; Python writes forbidden; geometry_proven=False" % len(before))


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
    parser.add_argument("--check_only", action="store_true", help="Memory-only regression; no output directory created")
    options = parser.parse_args(args)
    if (options.all_legs or options.sole_at_ball_bottom) and options.palm_shape != "claw":
        raise ValueError("--all_legs and --sole_at_ball_bottom require --palm_shape claw")
    angles = [float(x) for x in options.diagnostic_angles.split(",")]
    if angles != [-10.0, 0.0, 10.0]:
        raise ValueError("P2 approval covers diagnostic -10/0/+10 degrees ONLY")
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
    hashes = {str(p.relative_to(repo)): hashlib.sha256(p.read_bytes()).hexdigest() for p in protected}
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
    after = {str(p.relative_to(repo)): hashlib.sha256(p.read_bytes()).hexdigest() for p in protected}
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
    assert hashes == {str(p.relative_to(repo)): hashlib.sha256(p.read_bytes()).hexdigest() for p in protected}
    (output / "measurements.json").write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
    print("P2 OUTPUT " + str(output))


if __name__ == "__main__":
    args = sys.argv[sys.argv.index("--") + 1:] if "--" in sys.argv else []
    if "--p2_sample" in args:
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
