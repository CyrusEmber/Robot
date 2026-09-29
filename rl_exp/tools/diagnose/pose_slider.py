# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

"""Drag one leg joint at a time and watch the pad follow: fixed body, no gravity, no physics.

Why this exists: three of the open questions are about poses rather than rollouts -- whether the four
pads can lie flat at some body height, how far a foot can sweep fore/aft while it does, and which way
a joint actually turns the pad. A rollout answers them only after a policy, a reward and a contact
solver have had their say. This poses the leg by hand instead, using the URDF FK in
:mod:`rl_exp.tools.verify.check_leg_reachability` -- the same numbers the simulator's asset gives,
which that module's own ``--self-check`` calibrates against hand arithmetic.

What it holds fixed, and therefore cannot tell you: the body (no PD, no gravity, no contact), and
only one joint at a time (your hand, not a criterion). "It looks posable" is not "it carries load",
and "the leg looks contorted" stays a judgement here rather than a criterion.

The load-bearing readout is the last line: for the joint you last touched, where its axis points in
the body frame, how far the pad origin moves per radian, which axis the pad *rotates* about per
radian, and how much the tilt actually changes per radian. "The pad joint turns about y while the
tilt is about x" is a fact you read there, not one you infer from two slider positions.

Sliders are clamped to the URDF limits by default; the ``limits`` button lifts them in memory only --
nothing on disk is touched -- and every joint outside its limit is called out on the readout line.

Run it with the IsaacLab env's python (the host interpreter has no matplotlib):

    E:\\IsaacLab\\env_isaaclab\\Scripts\\python.exe rl_exp\\tools\\diagnose\\pose_slider.py

``--self-check`` runs headless under either interpreter: it defers to the FK module's caliber check
and adds the two things this file owns -- the clamp and the pose round trip through JSON.
"""

import argparse
import json
import math
import pathlib
import sys
import time

_REPO = pathlib.Path(__file__).resolve().parents[3]
if str(_REPO) not in sys.path:
    sys.path.insert(0, str(_REPO))

from rl_exp.tools.verify.check_leg_reachability import (  # noqa: E402
    CHAIN,
    DEFAULT_URDF,
    LEGS,
    joint_effect,
    load_chain,
    pad_faces,
    pad_normal_in_link,
    pad_state,
    pad_vertices,
    self_check as fk_self_check,
)

#: Body height at zero action in the settled simulator pose [m] (``2026-09-22-lizard2-stride-at-load``).
DEFAULT_BASE_Z = 0.912
COLORS = {"lf": "tab:blue", "rf": "tab:orange", "rl": "tab:green", "rr": "tab:red"}


def clamp(value: float, bounds: tuple[float, float], free: bool) -> float:
    """A slider's value, held inside the URDF limits unless ``free``."""
    low, high = bounds
    return value if free else min(max(value, low), high)


def _apply(rotation: list[list[float]], vector: list[float]) -> list[float]:
    return [sum(rotation[i][k] * vector[k] for k in range(3)) for i in range(3)]


def _norm(vector: list[float]) -> float:
    return math.sqrt(sum(value * value for value in vector))


def _format_pose(angles: dict, base_z: float, free: bool, margin_deg: float, urdf: pathlib.Path,
                 note: str = "") -> dict:
    """The on-disk pose: the angles, plus what the tool was showing when they were saved."""
    return {
        "base_z": base_z,
        "margin_deg": margin_deg,
        "limits_extended": free,
        "angles_rad": {leg: list(angles[leg]) for leg in LEGS},
        "urdf": str(urdf),
        "note": note,
    }


def read_pose(path: pathlib.Path, fallback_base_z: float) -> tuple[dict, float, bool]:
    """Angles, body height and whether the limits were lifted, from a saved pose."""
    saved = json.loads(path.read_text(encoding="utf-8"))
    missing = [leg for leg in LEGS if leg not in saved["angles_rad"]]
    if missing:
        raise SystemExit(f"{path} has no angles for {missing}")
    angles = {leg: [float(value) for value in saved["angles_rad"][leg]] for leg in LEGS}
    for leg in LEGS:
        if len(angles[leg]) != len(CHAIN):
            raise SystemExit(f"{path}: {leg} has {len(angles[leg])} angles, expected {len(CHAIN)}")
    return angles, float(saved.get("base_z", fallback_base_z)), bool(saved.get("limits_extended", False))


def self_check(urdf: pathlib.Path) -> None:
    """The FK module's caliber check, plus what this file owns: the clamp and the JSON round trip."""
    fk_self_check(urdf)
    bounds = (-0.6, 0.6)
    assert clamp(0.3, bounds, free=False) == 0.3
    assert clamp(-0.9, bounds, free=False) == -0.6 and clamp(0.9, bounds, free=False) == 0.6
    assert clamp(-0.9, bounds, free=True) == -0.9 and clamp(0.9, bounds, free=True) == 0.9
    posed = {leg: [0.1 * (i + 1) for i in range(len(CHAIN))] for leg in LEGS}
    import tempfile
    with tempfile.TemporaryDirectory() as folder:
        path = pathlib.Path(folder) / "pose.json"
        path.write_text(json.dumps(_format_pose(posed, 0.95, True, 20.0, urdf)), encoding="utf-8")
        back, base_z, free = read_pose(path, DEFAULT_BASE_Z)
    assert back == posed and base_z == 0.95 and free is True, (back, base_z, free)
    print("[SELF-CHECK] FK caliber passes, clamps hold at the limit and release in free mode, "
          "and a saved pose reads back as written")


def build(args) -> None:
    import matplotlib

    matplotlib.use(args.backend)
    import matplotlib.pyplot as plt
    from matplotlib.widgets import Button, Slider
    from mpl_toolkits.mplot3d.art3d import Poly3DCollection

    chains = {leg: load_chain(args.urdf, leg) for leg in LEGS}
    normals = {leg: pad_normal_in_link(args.urdf, leg) for leg in LEGS}
    vertices = {leg: pad_vertices(leg) for leg in LEGS}
    faces = {leg: pad_faces(leg) for leg in LEGS}

    angles = {leg: [0.0] * len(CHAIN) for leg in LEGS}
    base_z = args.base_z
    free = args.free
    if args.load is not None:
        angles, base_z, free = read_pose(args.load, args.base_z)

    state = {"active": None, "note": "", "silent": False}
    zero = {leg: pad_state(chains[leg], [0.0] * len(CHAIN), normals[leg], vertices[leg], base_z)["position"]
            for leg in LEGS}

    fig = plt.figure(figsize=(16.0, 10.0))
    ax = fig.add_axes([0.02, 0.05, 0.56, 0.76], projection="3d")

    def outside(leg: str) -> list[str]:
        """One leg's joints sitting past their own limits, with the limit spelled out."""
        found = []
        for index, joint in enumerate(CHAIN):
            low, high = chains[leg][index]["limits"]
            value = angles[leg][index]
            if value < low or value > high:
                found.append(f"{joint} {value:+.2f} > [{low:+.2f},{high:+.2f}]")
        return found

    def leg_lines(leg: str) -> list[str]:
        """The readout for one leg: tilt, clearance, where the pad is, and how legal the pose is."""
        posed = pad_state(chains[leg], angles[leg], normals[leg], vertices[leg], base_z)
        position = posed["position"]
        flag = "  PENETRATES" if posed["lowest_z"] < -1e-4 else ""
        return [
            f"{leg}  tilt {posed['tilt_deg']:6.2f} deg  lowest {posed['lowest_z']:+.4f} m  "
            f"xy ({position[0]:+.3f},{position[1]:+.3f})  "
            f"vs zero ({position[0] - zero[leg][0]:+.3f},{position[1] - zero[leg][1]:+.3f}){flag}",
            f"     {' '.join('%s %+.2f' % (joint, angles[leg][index]) for index, joint in enumerate(CHAIN))}"
            + (f"  OUT OF RANGE: {'; '.join(outside(leg))}" if outside(leg) else ""),
        ]

    def active_line() -> str:
        """What the last-touched joint does to the pad: axis, travel, rotation axis, tilt change."""
        if state["active"] is None:
            return "touch a slider: its axis and what it does to the pad are read out here"
        leg, index = state["active"]
        dp, dn, axis, dtilt = joint_effect(chains[leg], angles[leg], index, normals[leg], vertices[leg])
        rate = _norm(dn)
        if rate < 1e-9:
            rotation = "pad does not rotate (it translates only)"
        else:
            direction = " ".join("%+.2f" % (value / rate) for value in dn)
            rotation = f"pad rotates about [{direction}] at {rate:.3f} rad/rad"
        return (f"{leg} {CHAIN[index]}  axis(body) [{axis[0]:+.2f} {axis[1]:+.2f} {axis[2]:+.2f}]  "
                f"|dp/dq| {_norm(dp):.3f} m/rad  {rotation}  d(tilt)/dq {dtilt:+.1f} deg/rad")

    def caption() -> str:
        mode = "limits lifted (in memory only)" if free else "clamped to the URDF limits"
        head = (f"{'pose':<5} body z {base_z:.3f} m | {mode} | slider range = limits "
                f"{args.margin_deg:+.0f} deg")
        lines = [head, active_line()]
        for leg in LEGS:
            lines.extend(leg_lines(leg))
        if state["note"]:
            lines.append(state["note"])
        return "\n".join(lines)

    def draw(_value=None) -> None:
        ax.clear()
        floor = -base_z
        for step in range(7):
            offset = -0.9 + 0.3 * step
            ax.plot([-0.9, 0.9], [offset, offset], [floor, floor], color="0.75", lw=0.5)
            ax.plot([offset, offset], [-0.9, 0.9], [floor, floor], color="0.75", lw=0.5)
        hips = []
        for leg in LEGS:
            posed = pad_state(chains[leg], angles[leg], normals[leg], vertices[leg], base_z)
            frames = posed["frames"]
            pivots = [[frames[k][i][3] for i in range(3)] for k in range(1, len(CHAIN) + 1)]
            hips.append(pivots[0])
            path = [[0.0, 0.0, 0.0]] + pivots
            ax.plot([p[0] for p in path], [p[1] for p in path], [p[2] for p in path],
                    color=COLORS[leg], lw=2.0, marker="o", markersize=2.5)
            for k in range(len(CHAIN)):
                pivot, raw_axis = pivots[k], chains[leg][k]["axis"]
                axis = _apply([[frames[k][i][j] for j in range(3)] for i in range(3)], raw_axis)
                ax.plot([pivot[0] - 0.05 * axis[0], pivot[0] + 0.05 * axis[0]],
                        [pivot[1] - 0.05 * axis[1], pivot[1] + 0.05 * axis[1]],
                        [pivot[2] - 0.05 * axis[2], pivot[2] + 0.05 * axis[2]],
                        color=COLORS[leg], lw=1.0, alpha=0.7)
            rotation = [[frames[-1][i][j] for j in range(3)] for i in range(3)]
            position = posed["position"]
            triangles = [[[_apply(rotation, vertices[leg][idx])[i] + position[i] for i in range(3)]
                          for idx in face] for face in faces[leg]]
            ax.add_collection3d(Poly3DCollection(triangles, color=COLORS[leg], alpha=0.55))
            ax.plot([position[0], position[0]], [position[1], position[1]], [position[2], -base_z],
                    color="0.4", lw=0.8, ls=":", alpha=0.6)
            ax.plot([position[0], position[0] + 0.1 * posed["normal"][0]],
                    [position[1], position[1] + 0.1 * posed["normal"][1]],
                    [position[2], position[2] + 0.1 * posed["normal"][2]], color="black", lw=1.2)
        ax.plot([p[0] for p in hips] + [hips[0][0]], [p[1] for p in hips] + [hips[0][1]],
                [p[2] for p in hips] + [hips[0][2]], color="0.3", lw=1.0, ls="--")
        ax.set_xlim(-0.9, 0.9)
        ax.set_ylim(-0.9, 0.9)
        ax.set_zlim(-1.15, 0.15)
        ax.set_box_aspect((1.0, 1.0, 0.85))
        ax.set_xlabel("x [m]")
        ax.set_ylabel("y [m]")
        ax.set_zlabel("z [m]")
        ax.view_init(elev=18, azim=-62)
        ax.set_title(caption(), loc="left", fontsize=8, family="monospace", linespacing=1.5)
        for (leg, index), slider in sliders.items():
            low, high = chains[leg][index]["limits"]
            value = angles[leg][index]
            bad = "red" if (value < low - 1e-9 or value > high + 1e-9) else "black"
            slider.label.set_color(bad)
            slider.valtext.set_color(bad)
        fig.canvas.draw_idle()

    sliders = {}
    for row, leg in enumerate(LEGS):
        for index, joint in enumerate(CHAIN):
            low, high = chains[leg][index]["limits"]
            y = 0.925 - (row * len(CHAIN) + index) * 0.0415
            area = fig.add_axes([0.70, y, 0.26, 0.022])
            sliders[(leg, index)] = Slider(area, f"{leg} {joint}", low - args.margin_rad,
                                           high + args.margin_rad, valinit=angles[leg][index],
                                           valfmt="%+.3f")

    def make_callback(leg: str, index: int):
        def changed(value: float) -> None:
            if state["silent"]:
                return
            held = clamp(value, chains[leg][index]["limits"], free)
            if abs(held - value) > 1e-12:
                sliders[(leg, index)].set_val(held)
                return
            angles[leg][index] = held
            state["active"] = (leg, index)
            draw()
        return changed

    for (leg, index), slider in sliders.items():
        slider.on_changed(make_callback(leg, index))

    height = Slider(fig.add_axes([0.70, 0.055, 0.26, 0.022]), "body z [m]", 0.60, 1.20,
                    valinit=base_z, valfmt="%.3f")

    def on_height(value: float) -> None:
        nonlocal base_z
        if state["silent"]:
            return
        base_z = value
        draw()

    height.on_changed(on_height)

    def reset(_event) -> None:
        nonlocal base_z
        state["silent"] = True
        for (leg, index), slider in sliders.items():
            angles[leg][index] = 0.0
            slider.set_val(0.0)
        base_z = args.base_z
        height.set_val(args.base_z)
        state["silent"] = False
        state["active"] = None
        state["note"] = ""
        draw()

    def save(_event) -> None:
        args.out_dir.mkdir(parents=True, exist_ok=True)
        path = args.out_dir / ("pose_%s.json" % time.strftime("%Y%m%d-%H%M%S"))
        path.write_text(json.dumps(_format_pose(angles, base_z, free, args.margin_deg, args.urdf,
                                               note=args.label), indent=2), encoding="utf-8")
        state["note"] = f"saved {path} (limits_extended={free})"
        print(state["note"])
        draw()

    def toggle(_event) -> None:
        nonlocal free
        free = not free
        button_free.label.set_text("limits: free" if free else "limits: clamped")
        beyond = [f"{leg} {joint}" for leg in LEGS for joint in outside(leg)]
        state["note"] = (f"{len(beyond)} joint(s) outside their limits: {'; '.join(beyond)}"
                         if beyond else "")
        draw()

    button_reset = Button(fig.add_axes([0.70, 0.10, 0.08, 0.03]), "reset")
    button_save = Button(fig.add_axes([0.79, 0.10, 0.08, 0.03]), "save")
    button_free = Button(fig.add_axes([0.88, 0.10, 0.10, 0.03]),
                         "limits: free" if free else "limits: clamped")
    button_reset.on_clicked(reset)
    button_save.on_clicked(save)
    button_free.on_clicked(toggle)

    draw()
    plt.show()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--urdf", type=pathlib.Path, default=DEFAULT_URDF)
    parser.add_argument("--base-z", type=float, default=DEFAULT_BASE_Z,
                        help="body height above the ground [m]; the ground is z = -base_z in the body frame")
    parser.add_argument("--margin-deg", type=float, default=20.0,
                        help="how far past each limit the sliders may travel, for the extended-range "
                             "comparison; never written to the asset")
    parser.add_argument("--free", action="store_true", help="start with the limits lifted")
    parser.add_argument("--load", type=pathlib.Path, default=None, help="a pose saved by this tool")
    parser.add_argument("--out-dir", type=pathlib.Path,
                        default=_REPO / "rl_exp" / "tools" / "diagnose" / "out" / "pose_slider")
    parser.add_argument("--label", default="", help="a note to store inside a saved pose")
    parser.add_argument("--backend", default="TkAgg")
    parser.add_argument("--self-check", action="store_true")
    args = parser.parse_args()
    args.margin_rad = math.radians(args.margin_deg)
    if args.self_check:
        self_check(args.urdf)
        return
    build(args)


if __name__ == "__main__":
    main()
