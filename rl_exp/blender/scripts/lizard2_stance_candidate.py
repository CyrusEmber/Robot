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
        --python rl_exp/blender/lizard2_stance_candidate.py
"""

import math
import os

import bmesh
import bpy
from mathutils import Matrix, Vector

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BLEND_IN = os.path.join(_SCRIPT_DIR, "lizard_stance.blend")
BLEND_OUT = os.path.join(_SCRIPT_DIR, "lizard2_stance_candidate.blend")

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
        scene.render.filepath = os.path.join(_SCRIPT_DIR, "lizard2_stance_candidate_%s.png" % name)
        bpy.ops.render.render(write_still=True)
        print("rendered=%s" % scene.render.filepath)


main()
