# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

"""Draw a gait-probe report: per joint, where it actually went and how close to its stops.

Reads the JSON `gait_probe.py` writes, needs no simulator and no checkpoint. Two figures per
speed band:

* one panel per leg joint (4 legs x hip/hfe/blade) with the actual angle, the commanded angle,
  both position limits, and the frames spent inside `--at_stop_rad` of either stop shaded;
* one bar chart of "share of frames at a stop" per joint, which is the limit reading the panels
  only show by eye.

Why this exists: the probe's summary answers "how much torque" and "what p50 angle", but "the leg
stands on the blade's edge" is a question about a *pose over time* -- which joint is pinned, when,
and against which stop. That is a shape, and a shape is read from a picture or from the frames
themselves, not from a table of medians (two p50s need not share a frame).

Frame shading: red = the joint is within the band of a stop, grey = that foot carries less than
the report's own `contact_n` (in the air). So "pinned while carrying weight" and "pinned in the
air" do not look the same.
"""

import argparse
import json
import pathlib
import sys

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

_REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]
# ``rl_exp`` is not an installed package, so the repo root joins sys.path beside the leg table it holds.
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))
from rl_exp.tasks import joint_names  # noqa: E402

#: The chain POSITIONS the probe records per leg (root, first hinge, blade) -- by position, never by
#: word, so the panels follow the binding: a report written for a renamed body draws its own joints
#: instead of three empty rows, and one written for another vocabulary is refused (see :func:`draw_band`).
REPORT_POSITIONS = (0, 2, -1)


def report_tokens(naming: dict[str, tuple[str, ...]], leg: str) -> tuple[str, ...]:
    """The three tokens a leg's panels are drawn for, in this binding's words."""
    roots = joint_names.roots_of(naming, leg)
    return tuple(roots[index] for index in REPORT_POSITIONS)


def report_naming(report: dict, naming: dict[str, tuple[str, ...]] | None = None
                  ) -> dict[str, tuple[str, ...]]:
    """Validate every bound column before drawing; unbound historical reports remain explicit."""
    if "target_binding" not in report:
        if report.get("target_binding_required") is True:
            raise ValueError("target_binding_required report is missing target_binding")
        return joint_names.LEGACY_NAMING if naming is None else naming
    bound = report["target_binding"]
    resolved = joint_names.naming_from_binding(bound, expected=naming)
    if "joint_names" not in bound:
        raise ValueError("target_binding requires declared joint_names")
    declared = bound["joint_names"]
    joint_names.validate_joint_names(declared, resolved, target=bound["target"])
    ends = set(joint_names.contact_body_names(resolved))
    if len(report.get("foot_bodies", [])) != 4 or set(report["foot_bodies"]) != ends:
        raise ValueError("target_binding foot_bodies must carry exactly four end links")
    if not report.get("envs"):
        raise ValueError("target_binding report has no environments")
    expected_joints = {joint_names.joint_name(leg, root) for leg in joint_names.LEGS
                       for root in joint_names.roots_of(resolved, leg)}
    if not expected_joints <= set(declared):
        raise ValueError("target_binding declared joint_names is missing leg joints")
    expected_series = {f"{joint_names.end_link(leg, resolved)}_{root}_{kind}"
                       for leg in joint_names.LEGS for root in joint_names.roots_of(resolved, leg)
                       for kind in ("actual", "target", "vel")}
    expected_spine = {f"{name}_{kind}" for name in declared if name not in expected_joints
                      for kind in ("actual", "target", "vel")}
    for entry in report["envs"]:
        bodies = [foot["body"] for foot in entry["feet"]]
        if len(bodies) != 4 or set(bodies) != ends:
            raise ValueError("target_binding environment must carry exactly four end links")
        if set(entry.get("joint_series", {})) != expected_series:
            raise ValueError("target_binding joint_series columns differ from the per-leg chain")
        if set(entry.get("spine_series", {})) != expected_spine:
            raise ValueError("target_binding spine_series differs from declared joint_names")
        for foot in entry["feet"]:
            for token in report_tokens(resolved, foot["body"].split("_")[0]):
                if f"{token}_limits_rad" not in foot:
                    raise ValueError(f"target_binding summary missing {token}_limits_rad")
    return resolved


def at_stop(actual: list[float], low: float, high: float, band: float) -> list[bool]:
    """Frames where the joint sits within ``band`` of either stop -- the limit reading, per frame."""
    return [min(abs(value - low), abs(value - high)) <= band for value in actual]


def draw_band(entry: dict, contact_n: float, band: float, out_dir: pathlib.Path, tag: str,
              naming: dict[str, tuple[str, ...]]) -> dict:
    """One figure of joint panels + one bar chart. Returns the numbers it drew.

    The tokens are per LEG here, not one set for the figure: a body whose front and rear limbs carry
    different words draws each row in its own words (the column titles are that row's), which is also why
    the presence of each key is checked before anything is plotted -- a report whose keys are in another
    vocabulary would otherwise draw empty rows and look like a figure.
    """
    speed = entry["speed"]
    joint_series = entry["joint_series"]
    feet = entry["feet"]
    tokens_per_foot = [report_tokens(naming, foot["body"].split("_")[0]) for foot in feet]
    missing = []
    for foot, tokens in zip(feet, tokens_per_foot):
        for token in tokens:
            for key in (f"{foot['body']}_{token}_actual", f"{foot['body']}_{token}_target"):
                if key not in joint_series:
                    missing.append(key)
            if f"{token}_limits_rad" not in foot:
                missing.append(f"{token}_limits_rad")
    if missing:
        raise SystemExit("report %s does not carry the naming '%s': no %s (series keys start %s). "
                         "Declare the naming this report was written under (--naming)"
                         % (tag, joint_names.naming_id(naming), missing[0], sorted(joint_series)[:3]))
    summary = {}
    fig, axes = plt.subplots(len(feet), len(REPORT_POSITIONS), figsize=(15.0, 8.4), sharex=True)
    axes = axes.reshape(len(feet), len(REPORT_POSITIONS))
    for row, foot in enumerate(feet):
        body = foot["body"]
        force = entry["series"]["force"][row]
        leg = body.split("_")[0]
        for column, joint in enumerate(tokens_per_foot[row]):
            axis = axes[row][column]
            actual = joint_series[f"{body}_{joint}_actual"]
            target = joint_series[f"{body}_{joint}_target"]
            low, high = foot[f"{joint}_limits_rad"]
            stops = at_stop(actual, low, high, band)
            frames = list(range(len(actual)))
            for frame, stopped, loaded in zip(frames, stops, force):
                if stopped:
                    axis.axvspan(frame, frame + 1, color="tab:red", alpha=0.25, linewidth=0)
                if loaded <= contact_n:
                    axis.axvspan(frame, frame + 1, color="0.5", alpha=0.10, linewidth=0)
            axis.axhline(low, color="k", linewidth=0.8, linestyle=":")
            axis.axhline(high, color="k", linewidth=0.8, linestyle=":")
            axis.plot(frames, target, color="tab:orange", linewidth=0.8, linestyle="--")
            axis.plot(frames, actual, color="tab:blue", linewidth=1.2)
            span = max(high - low, 1e-6)
            axis.set_ylim(min(low, min(actual), min(target)) - 0.1 * span,
                          max(high, max(actual), max(target)) + 0.1 * span)
            axis.tick_params(labelsize=7)
            # Every row titled in its OWN words: under a split naming the front and rear columns are
            # different joints, and one title across four rows would label the rear's with the front's.
            axis.set_title(joint, fontsize=9)
            if column == 0:
                axis.set_ylabel(leg, fontsize=9)
            margin = min(min(abs(value - low), abs(value - high)) for value in actual)
            share = sum(stops) / len(stops)
            summary[f"{leg}_{joint}"] = {
                "actual_min": round(min(actual), 4), "actual_max": round(max(actual), 4),
                "target_min": round(min(target), 4), "target_max": round(max(target), 4),
                "limits": [low, high], "margin_min_rad": round(margin, 4),
                "at_stop_share": round(share, 3),
            }
            axis.text(0.01, 0.04, "at stop %.2f  margin %.3f" % (share, margin),
                      transform=axis.transAxes, fontsize=6.5, color="tab:red")
    axes[-1][0].set_xlabel("frame", fontsize=8)
    fig.suptitle("%s at %.1f m/s | solid blue = actual, dashed orange = target, dotted = limits, "
                 "red = within %.3f rad of a stop, grey = foot in the air"
                 % (tag, speed, band), fontsize=10)
    fig.tight_layout(rect=(0, 0, 1, 0.97))
    panels = out_dir / f"{tag}_{speed:g}mps_panels.png"
    fig.savefig(panels, dpi=130)
    plt.close(fig)

    names = [f"{foot['body'].split('_')[0]}_{tokens[column]}"
             for foot, tokens in zip(feet, tokens_per_foot)
             for column in range(len(REPORT_POSITIONS))]
    shares = [summary[name]["at_stop_share"] for name in names]
    fig, axis = plt.subplots(figsize=(9.0, 4.2))
    axis.bar(range(len(names)), shares, color="tab:red", alpha=0.7)
    axis.set_xticks(range(len(names)), names, rotation=45, ha="right", fontsize=8)
    axis.set_ylabel("share of frames within %.3f rad of a stop" % band, fontsize=9)
    axis.set_title("%s at %.1f m/s: which joints live against their stops" % (tag, speed),
                   fontsize=10)
    axis.grid(axis="y", alpha=0.3)
    fig.tight_layout()
    stops_chart = out_dir / f"{tag}_{speed:g}mps_stops.png"
    fig.savefig(stops_chart, dpi=130)
    plt.close(fig)
    return {"panels": str(panels), "stops": str(stops_chart), "joints": summary}


def self_check() -> None:
    """Hand-computed at-stop cases; no report file, no simulator."""
    # A joint resting exactly on its high stop for 2 of 6 frames, and 0.05 rad inside on one other.
    stops = at_stop([0.0, 0.0, 1.0, 1.0, 0.95, 0.0], -1.0, 1.0, 0.02)
    assert stops == [False, False, True, True, False, False], stops
    assert round(sum(stops) / len(stops), 3) == 0.333
    # 0.05 rad inside is not "at the stop" for a 0.02 band: the band is the whole judgement. The
    # bands here stay off the exact edge on purpose -- 1.0 - 0.95 is 0.05000000000000004 in binary,
    # so a band of exactly 0.05 would test the float, not the rule.
    assert at_stop([0.95], -1.0, 1.0, 0.06) == [True]
    assert at_stop([0.95], -1.0, 1.0, 0.04) == [False]
    # Both stops read as at-stop, and a value OUTSIDE the range is still measured by its distance to
    # the nearer stop -- the reading is "how close", not "inside or outside", so a 0.5 rad overshoot
    # is not "at the stop" while a 0.05 rad one is.
    assert at_stop([-1.0, 1.0], -1.0, 1.0, 0.001) == [True, True]
    assert at_stop([1.5], -1.0, 1.0, 0.6) == [True]
    assert at_stop([1.5], -1.0, 1.0, 0.4) == [False]
    print("[SELF-CHECK] at-stop band edges, both stops and out-of-range all read as hand-computed")


def main() -> None:
    parser = argparse.ArgumentParser(description="Plot a gait-probe report: joints, limits, stops.")
    parser.add_argument("--report", type=pathlib.Path,
                        help="gait_probe report json; required unless --self-check")
    parser.add_argument("--out_dir", type=pathlib.Path,
                        default=pathlib.Path(__file__).resolve().parent / "out" / "joint_plots")
    parser.add_argument("--at_stop_rad", type=float, default=0.02,
                        help="how close to a stop counts as 'at the stop'")
    parser.add_argument("--tag", default=None, help="figure prefix (default: the report's stem)")
    parser.add_argument("--naming", default=None, choices=sorted(joint_names.NAMINGS),
                        help="which words the record carries: 'shared' = every leg one root set (every "
                             "asset today), 'split' = the front/rear rename. Declared, and checked "
                             "against the report's own keys and foot bodies before anything is drawn")
    parser.add_argument("--self-check", action="store_true")
    args = parser.parse_args()
    if args.self_check:
        self_check()
        return
    if args.report is None:
        parser.error("--report is required unless --self-check")

    report = json.loads(args.report.read_text(encoding="utf-8"))
    tag = args.tag or args.report.stem
    naming = report_naming(report, joint_names.naming_for(args.naming) if args.naming else None)
    args.naming = joint_names.naming_id(naming)
    # The foot bodies are checked against the naming before the bands are drawn: the probe records the
    # four legs in its own order, and a report written for another vocabulary would draw rows for feet
    # this binding does not name -- an empty-looking figure rather than an error.
    for leg in joint_names.LEGS:
        end = joint_names.end_link(leg, naming)
        if not any(foot["body"] == end for env in report["envs"] for foot in env["feet"]):
            raise SystemExit("report %s carries no %s: it was not written for the naming '%s' "
                             "(feet: %s)" % (args.report.name, end, args.naming,
                                             sorted({foot["body"] for env in report["envs"]
                                                     for foot in env["feet"]})))
    args.out_dir.mkdir(parents=True, exist_ok=True)
    index = {"report": str(args.report), "at_stop_rad": args.at_stop_rad, "naming": args.naming,
             "binding_validation": ("target_binding" if "target_binding" in report else "historical_unbound"),
             "bands": []}
    for entry in report["envs"]:
        drawn = draw_band(entry, report["contact_n"], args.at_stop_rad, args.out_dir, tag, naming)
        print("\n=== %.1f m/s ===\n  panels %s\n  stops  %s"
              % (entry["speed"], drawn["panels"], drawn["stops"]))
        worst = sorted(drawn["joints"].items(), key=lambda item: -item[1]["at_stop_share"])[:6]
        for name, reading in worst:
            print("  %-10s at_stop %.3f  margin %.4f rad  actual [%.3f, %.3f]  limits %s"
                  % (name, reading["at_stop_share"], reading["margin_min_rad"],
                     reading["actual_min"], reading["actual_max"], reading["limits"]))
        index["bands"].append({"speed": entry["speed"], **drawn})
    (args.out_dir / f"{tag}_index.json").write_text(json.dumps(index, indent=1), encoding="utf-8")
    print("\nJOINT_PLOT_OK (%s) -> %s" % (args.naming, args.out_dir))


if __name__ == "__main__":
    main()
