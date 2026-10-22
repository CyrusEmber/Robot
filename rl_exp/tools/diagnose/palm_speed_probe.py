# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause
"""Bounded left-knee or left-elbow speed trials with unchanged PD and TGS/false.

Prepare sampled full-body geometry before physics. Five nominal peak target
speeds [rad/s], fixed base/self-weight and 50 Hz position updates. All new runs
use zero velocity targets. The old nonzero-velocity comparison is replay-only.
Actual speed is a measured result, never inferred from the command.
No gain scan, force-timing switch, cap override, training or automatic retry.
"""
from __future__ import annotations

import argparse
import copy
import json
import os
from pathlib import Path
import shutil
import sys
import time
import traceback

import numpy as np
import palm_spatial_runtime as wiring

REPO = wiring.REPO
REFERENCE_SHA = "13929c53eccdb51d454ade60cf071c3eaa614bf5c90684dd2e06f4017d2485ef"
JOINT = "rl_knee_joint"
JOINTS = (JOINT, "lf_elbow_joint")
ELBOW_REPORT_SHA = "9737ba5630e1e735b24ec839aaf30821453ab9ad95da192a0eec882434abe321"
# Historical setting keys retain their spelling for old knee report replay;
# the knee_* stop values apply to the selected active joint in either mode.
SETTINGS = dict(dt_s=.005, control_dt_s=.02, amplitude_rad=.768, settle_s=5.,
                hold_s=1., recover_s=1., max_cases=5, max_steps=12000,
                wall_budget_s=900., knee_stop_rad=1., other_stop_rad=.35,
                knee_speed_stop_rad_s=9., knee_effort_stop_nm=144.,
                stop_contact_n=1., geometry_step_rad=.05,
                scope="fixed-base self-weight speed slice; no full speed/load envelope")
RAMPS = (1.44, .72, .36, .24, .18)


def require(condition, message):
    if not condition:
        raise ValueError(message)


def selected_joint(document):
    """Resolve the active joint, retaining historical knee-only report meaning."""
    joint = document.get("joint", JOINT)
    require(joint in JOINTS, "unsupported speed-probe joint")
    return joint


def target(t, ramp):
    """Position target [rad], positive then negative smooth out/hold/return."""
    t -= SETTINGS["settle_s"]
    if t <= 0.:
        return 0.
    span = 2*ramp + SETTINGS["hold_s"] + SETTINGS["recover_s"]
    sign = 1. if t <= span else -1.
    t = t if sign > 0 else t-span
    if t <= ramp:
        s = t/ramp
    elif t <= ramp + SETTINGS["hold_s"]:
        return sign*SETTINGS["amplitude_rad"]
    elif t <= 2*ramp + SETTINGS["hold_s"]:
        s = (2*ramp + SETTINGS["hold_s"]-t)/ramp
    else:
        return 0.
    return sign*SETTINGS["amplitude_rad"]*(10*s**3-15*s**4+6*s**5)


def target_velocity(t, ramp):
    """Analytic smooth-reference derivative [rad/s], sampled/held at 50 Hz."""
    t -= SETTINGS["settle_s"]
    if t <= 0.:
        return 0.
    span = 2*ramp + SETTINGS["hold_s"] + SETTINGS["recover_s"]
    sign = 1. if t <= span else -1.
    t = t if sign > 0 else t-span
    if t <= ramp:
        s, direction = t/ramp, 1.
    elif t <= ramp+SETTINGS["hold_s"]:
        return 0.
    elif t <= 2*ramp+SETTINGS["hold_s"]:
        s, direction = (2*ramp+SETTINGS["hold_s"]-t)/ramp, -1.
    else:
        return 0.
    return sign*direction*SETTINGS["amplitude_rad"]*30*s*s*(1-s)**2/ramp


def commanded_velocity(t, case):
    mode = case.get("velocity_target_mode", "zero")
    require(mode in ("zero", "reference_derivative"), "unsupported velocity target mode")
    return 0. if mode == "zero" else target_velocity(t, case["ramp_s"])


def cases():
    """Return the complete step budget and nominal continuous target peaks."""
    result = []
    for ramp in RAMPS:
        duration = SETTINGS["settle_s"] + 4*ramp + 2*(SETTINGS["hold_s"]+SETTINGS["recover_s"])
        steps = round(duration/SETTINGS["dt_s"])
        require(abs(steps*SETTINGS["dt_s"]-duration) < 1e-10, "unaligned case duration")
        require(abs(ramp/SETTINGS["control_dt_s"]-round(ramp/SETTINGS["control_dt_s"])) < 1e-10,
                "unaligned control ramp")
        result.append(dict(ramp_s=ramp, duration_s=duration, steps=steps,
                           nominal_target_peak_rad_s=1.875*SETTINGS["amplitude_rad"]/ramp))
    require(len(result) == SETTINGS["max_cases"] and sum(c["steps"] for c in result) <= SETTINGS["max_steps"],
            "physics budget exceeded")
    return result


def experiment_schedule(document):
    """Keep historical staged trials separate from the two-case causal test."""
    kind = document.get("experiment", "staged_speed")
    require(kind in ("staged_speed", "velocity_reference_comparison"), "unsupported experiment")
    settings = dict(SETTINGS)
    if kind == "staged_speed":
        return settings, cases()
    require(selected_joint(document) == "lf_elbow_joint", "comparison only budgeted for left elbow")
    schedule = [dict(cases()[-1], velocity_target_mode=mode)
                for mode in ("zero", "reference_derivative")]
    settings.update(max_cases=2, max_steps=sum(c["steps"] for c in schedule))
    return settings, schedule


def validate_plan(plan):
    settings, schedule = experiment_schedule(plan)
    require(plan["completed"] and plan["settings"] == settings and plan["cases"] == schedule,
            "plan/config mismatch")
    return settings, schedule


def validate_physical_plan(plan):
    """Enforce the current zero-velocity-target drive decision before startup."""
    settings, schedule = validate_plan(plan)
    require(plan.get("experiment", "staged_speed") == "staged_speed" and
            all(c.get("velocity_target_mode", "zero") == "zero" for c in schedule),
            "nonzero velocity targets are historical replay only; current target velocity is always zero")
    return settings, schedule


def load_reference(path):
    require(wiring.binding.sha256_file(path) == REFERENCE_SHA, "reference approval mismatch")
    report = json.loads(path.read_text(encoding="utf-8"))
    require(report["completed"] and report["symmetric_knee_elbow_pd"], "reference incomplete/wrong PD")
    manifest_path = Path(report["tracking_manifest"])
    require(wiring.binding.sha256_file(manifest_path) == report["tracking_manifest_sha256"], "manifest changed")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    for field in ("target", "urdf"):
        require(wiring.binding.sha256_file(Path(manifest["target_binding"][field])) == manifest["sha256"][field],
                "asset changed: " + field)
    return report, manifest_path, manifest


def prepare(args):
    """Use body-precheck on the selected joint's sampled stop interval [rad]."""
    import body_precheck as precheck
    from palm_spatial_inertia import csc
    report, manifest_path, manifest = load_reference(args.reference)
    urdf = Path(manifest["target_binding"]["urdf"])
    model = csc.load_urdf(urdf)
    names = report["joint_names"]
    joint = args.joint or JOINT
    require(set(names) == {n for n, j in model["joints"].items() if j["limits"] is not None}, "joint set mismatch")
    meshes = {name: spec["collision"] for name, spec in model["links"].items() if spec["collision"]}
    direct = {tuple(sorted((j["parent"], j["child"]))) for j in model["joints"].values()}
    connections = {tuple(sorted(p)) for p in manifest["connection_filter"]["pairs"]}
    allowed = [{"pair": list(p), "reason": "existing direct-joint collision exclusion"}
               for p in sorted(direct) if set(p) <= set(meshes)]
    allowed += [{"pair": list(p), "reason": "existing six named connection filters"}
                for p in sorted(connections-direct)]
    chains, covered = {}, set()
    for leg, end in manifest["target_binding"]["end_links"].items():
        path = csc.chain_up(model["joints"], end)
        covered.update(path)
        chains[leg] = dict(root_link="base_link", end_link=end,
                           joint_roles={n: n.removesuffix("_joint") for n in path}, contact_links=[end])
    angles = sorted(set(np.linspace(-1., 1., 41).tolist() + [-SETTINGS["amplitude_rad"], SETTINGS["amplitude_rad"]]))
    root = np.eye(4); root[2, 3] = 2.
    samples = [dict(id=f"{joint}_{i:02d}", phase="single-joint speed preflight",
                    q_rad={n: angle if n == joint else 0. for n in names}, root_transform=root.tolist())
               for i, angle in enumerate(angles)]
    config = dict(inputs=dict(identity=f"{joint} staged speed preflight", units="SI",
        urdf=dict(path=str(urdf), sha256=manifest["sha256"]["urdf"]),
        meshes=[dict(path=str(p), sha256=wiring.binding.sha256_file(p)) for p in meshes.values()],
        threshold_basis=dict(approved_by="user: staged speed trial to 8 rad/s",
                             reference="existing intersection predicate and named connection filters; no positive clearance claim")),
        body=dict(chains=chains, other_joints={n: n for n in names if n not in covered},
                  collision_entities=list(meshes), excluded_entities=[], allowed_pairs=allowed),
        tasks=dict(cases=samples, requirements=[dict(id=kind, check=kind, required=True,
             cases=[c["id"] for c in samples], chains=list(chains),
             params={} if kind == "joint_limits" else dict(clearance_m=0.))
             for kind in ("joint_limits", "self_collision")]))
    result = precheck.run(config, args.out, max_cases=len(samples))
    wiring.write_json(args.out/"geometry_config.json", config)
    wiring.write_json(args.out/"geometry_report.json", result)
    plan = dict(completed=result["status"] == "pass", joint=joint, settings=SETTINGS, cases=cases(),
                reference=str(args.reference), reference_sha256=REFERENCE_SHA,
                manifest=str(manifest_path), manifest_sha256=report["tracking_manifest_sha256"],
                geometry_report_sha256=wiring.binding.sha256_file(args.out/"geometry_report.json"),
                geometry_config_sha256=wiring.binding.sha256_file(args.out/"geometry_config.json"),
                code_sha256=wiring.binding.sha256_file(Path(__file__)),
                geometry_scope="43 sampled selected-joint poses; other joints zero; no continuous safety claim")
    wiring.write_json(args.out/"plan.json", plan)
    require(plan["completed"], "sampled geometry failed; no physics authorized by this plan")
    print("SPEED_PLAN_PREPARED", sum(c["steps"] for c in plan["cases"]), flush=True)


def summarize(data, case, axis):
    """Measure physical-step average speed separately from backend speed [SI]."""
    q, times = data["q_rad"], data["t_s"]
    moving = times > SETTINGS["settle_s"]
    fd = data["position_delta_velocity_rad_s"]
    error = abs(q[:, axis]-data["target_rad"][:, axis])
    ramp = case["ramp_s"]
    span = 2*ramp+2.
    windows = {}
    for sign, offset in (("positive", 5.), ("negative", 5.+span)):
        for label, end in (("hold", offset+ramp+1.), ("returned", offset+2*ramp+2.)):
            mask = (times >= end-.2-1e-8) & (times <= end+1e-8)
            if mask.any():
                windows[sign+"_"+label] = float(error[mask].max())
    peak = float(abs(fd[moving, axis]).max()) if moving.any() else 0.
    return dict(steps=len(times), max_motion_position_delta_speed_rad_s=peak,
                max_motion_backend_speed_rad_s=float(abs(data["velocity_rad_s"][moving, axis]).max()) if moving.any() else 0.,
                nominal_target_peak_rad_s=case["nominal_target_peak_rad_s"],
                measured_peak_to_nominal_ratio=peak/case["nominal_target_peak_rad_s"],
                max_direct_error_rad=float(error.max()), final_window_errors_rad=windows,
                max_abs_position_rad=float(abs(q[:, axis]).max()),
                max_abs_projected_joint_load_nm=float(abs(data["projected_joint_effort_nm"][:, axis]).max()),
                load_scope="step-average projected joint load; not instantaneous motor effort",
                max_contact_n=float(data["contact_n"].max()))


def self_check():
    """Check the real target schedule, sampler budget and speed consumer."""
    plan = cases()
    require(sum(c["steps"] for c in plan) == 11352, "unexpected total budget")
    require(selected_joint({}) == JOINT and selected_joint({"joint": JOINTS[1]}) == JOINTS[1],
            "historical or elbow joint selection differs")
    try:
        selected_joint({"joint": "lf_wrist_joint"})
    except ValueError:
        pass
    else:
        raise ValueError("unbudgeted joint accepted")
    for c in plan:
        ramp = c["ramp_s"]
        require(target(0., ramp) == target(c["duration_s"], ramp) == 0., "trajectory not closed")
        require(abs(target(5.+ramp, ramp)-.768) < 1e-10, "positive target absent")
        require(abs(target(5.+3*ramp+2., ramp)+.768) < 1e-10, "negative target absent")
        ticks = np.arange(0., c["duration_s"]+1e-8, .02)
        issued = np.array([target(t, ramp) for t in ticks])
        require(abs(issued).max() <= .768+1e-12, "target overshoot")
        require(abs(np.diff(issued)/.02).max() <= c["nominal_target_peak_rad_s"]+1e-10,
                "discrete target exceeds nominal smooth-curve peak")
        for t in np.arange(5.01, c["duration_s"]-.01, .013):
            numeric = (target(t+1e-6, ramp)-target(t-1e-6, ramp))/2e-6
            require(abs(numeric-target_velocity(t, ramp)) < 1e-6, "reference derivative differs")
    comparison_settings, comparison = experiment_schedule(dict(joint="lf_elbow_joint", experiment="velocity_reference_comparison"))
    require(comparison_settings["max_steps"] == 3888 and len(comparison) == 2, "comparison budget differs")
    require(commanded_velocity(5.08, comparison[0]) == 0. and commanded_velocity(5.08, comparison[1]) > 7.,
            "velocity comparison has no intervention")
    validate_physical_plan(dict(completed=True, settings=SETTINGS, cases=cases()))
    try:
        validate_physical_plan(dict(completed=True, joint="lf_elbow_joint", experiment="velocity_reference_comparison",
                                    settings=comparison_settings, cases=comparison))
    except ValueError as error:
        require("historical replay only" in str(error), "wrong physical refusal")
    else:
        raise ValueError("historical nonzero velocity experiment accepted for new physics")
    fake = {"q_rad": np.array([[0.], [.01], [.03]]), "t_s": np.array([5.005, 5.01, 5.015]),
            "target_rad": np.zeros((3, 1)), "position_delta_velocity_rad_s": np.array([[0.], [2.], [4.]]),
            "velocity_rad_s": np.full((3, 1), 99.), "projected_joint_effort_nm": np.ones((3, 1)),
            "contact_n": np.zeros(3)}
    values = summarize(fake, plan[0], 0)
    require(values["max_motion_position_delta_speed_rad_s"] == 4. and
            values["max_motion_backend_speed_rad_s"] == 99., "speed channels conflated")
    from tempfile import TemporaryDirectory
    with TemporaryDirectory(dir=REPO/"rl_exp/out", prefix="speed_progress_check_") as temporary:
        directory = Path(temporary)
        for index in range(2):
            save_progress(directory, dict(cases=list(range(index+1))), index)
        require(len(list(directory.glob("progress*.json"))) == 2, "progress snapshots were overwritten")
    print("SPEED_PROBE_SELF_CHECK_OK", flush=True)


def save_progress(out, result, index):
    """Keep a separate immutable progress record after each completed case."""
    wiring.write_json(out/f"progress_{index:02d}.json", result)


def run(args):
    from palm_spatial_tracking import _drive_targets, _entity_snapshot, _joint_force_probe_binding, _joint_force_probe_sample
    from palm_spatial_inertia import csc
    require(args.plan and args.approved_plan_sha256, "approved geometry plan required")
    require(wiring.binding.sha256_file(args.plan) == args.approved_plan_sha256, "plan changed")
    plan = json.loads(args.plan.read_text(encoding="utf-8"))
    joint = selected_joint(plan)
    settings, schedule = validate_physical_plan(plan)
    geometry_path = args.plan.parent/"geometry_report.json"
    require(wiring.binding.sha256_file(geometry_path) == plan["geometry_report_sha256"], "geometry changed")
    require(wiring.binding.sha256_file(args.plan.parent/"geometry_config.json") == plan["geometry_config_sha256"],
            "geometry config changed")
    import body_precheck
    geometry = json.loads(geometry_path.read_text(encoding="utf-8"))
    require(geometry["status"] == "pass", "geometry did not pass")
    body_precheck.revalidate_inputs(geometry)
    prior, manifest, _ = load_reference(Path(plan["reference"]))
    require(wiring.binding.sha256_file(manifest) == plan["manifest_sha256"], "plan manifest changed")
    result = dict(completed=False, status="startup", joint=joint, settings=settings, plan=str(args.plan),
                  experiment=plan.get("experiment", "staged_speed"),
                  plan_sha256=args.approved_plan_sha256, cases=[], physics_steps=0,
                  code_sha256=wiring.binding.sha256_file(Path(__file__)),
                  reference=plan["reference"], reference_sha256=REFERENCE_SHA,
                  manifest=str(manifest), manifest_sha256=plan["manifest_sha256"])
    elapsed_before = 0.
    if args.resume:
        require(result["experiment"] == "staged_speed", "comparison retries are not budgeted")
        require(args.approved_resume_sha256, "resume approval required")
        checked = replay(args.resume, args.approved_resume_sha256)
        prefix = json.loads(args.resume.read_text(encoding="utf-8"))
        require(not checked["completed"] and prefix["error"] == "FileExistsError(17, 'File exists')",
                "only the progress-write interruption can be resumed")
        require(prefix["plan_sha256"] == args.approved_plan_sha256 and len(prefix["cases"]) == 2,
                "resume plan/prefix differs")
        for index, case in enumerate(prefix["cases"]):
            require(case["completed"] and case["index"] == index and
                    all(case[key] == plan["cases"][index][key] for key in plan["cases"][index]), "invalid completed prefix")
        result.update(cases=copy.deepcopy(prefix["cases"]), physics_steps=prefix["physics_steps"],
                      prior_run=dict(report=str(args.resume.resolve()), sha256=args.approved_resume_sha256,
                                     code_sha256=prefix["code_sha256"]))
        elapsed_before = prefix["elapsed_wall_s"]
    app = env = None
    active = None
    start = time.monotonic()
    try:
        from isaaclab.app import AppLauncher
        app = AppLauncher(args).app
        import gymnasium as gym
        import torch
        import warp as wp
        from pxr import UsdPhysics
        from rl_exp.tools.verify.baseline_runtime import resolve_task_cfg, joint_reset_errors
        from isaaclab_rl.rsl_rl import RslRlVecEnvWrapper
        cfg = copy.deepcopy(resolve_task_cfg(wiring.REGISTERED_TASK))
        bound = wiring.obs_protocol.load_diagnostic_target(manifest, cfg, wiring.REGISTERED_TASK)
        require(cfg.sim.dt == .005 and cfg.decimation == 4, "training step rate differs")
        physics = cfg.sim.physics.default if hasattr(cfg.sim.physics, "default") else cfg.sim.physics
        require(physics.solver_type == 1 and physics.enable_external_forces_every_iteration is False,
                "training solver/force timing differs")
        cfg.sim.device, cfg.seed = args.device, 0
        env = gym.make(wiring.REGISTERED_TASK, cfg=cfg)
        wrapper = RslRlVecEnvWrapper(env, clip_actions=None)
        live, robot = env.unwrapped, env.unwrapped.scene["robot"]
        live.reset()
        require(robot.is_fixed_base and not joint_reset_errors(robot), "fixed-base reset invalid")
        names = list(robot.joint_names)
        require(names == prior["joint_names"], "runtime joint order changed")
        backend = lambda value: wp.to_torch(value).cpu().numpy()[0].copy()
        result.update(target_binding=bound, joint_names=names, readbacks={})
        for key, getter in (("kp", "get_dof_stiffnesses"), ("kd", "get_dof_dampings"),
                            ("effort_caps", "get_dof_max_forces"), ("velocity_caps", "get_dof_max_velocities")):
            value = backend(getattr(robot.root_view, getter)())
            require(np.array_equal(value, prior["readbacks"][key]), "changed readback: "+key)
            result["readbacks"][key] = value.tolist()
        scene = live.sim.stage.GetPrimAtPath(cfg.sim.physics_prim_path)
        result["readbacks"].update(force_timing=scene.GetAttribute("physxScene:enableExternalForcesEveryIteration").Get(),
                                  solver=scene.GetAttribute("physxScene:solverType").Get())
        require(result["readbacks"]["force_timing"] is False and result["readbacks"]["solver"] == "TGS", "runtime solver changed")
        gravity = {p.GetName(): p.GetAttribute("physxRigidBody:disableGravity").Get()
                   for p in live.sim.stage.Traverse() if p.HasAPI(UsdPhysics.RigidBodyAPI)}
        require(len(gravity) == 31 and all(v is False for v in gravity.values()), "body gravity not enabled")
        require(tuple(live.sim.cfg.gravity) == (0., 0., -9.81), "scene gravity changed")
        result["readbacks"]["body_disable_gravity"] = gravity
        force_binding = _joint_force_probe_binding(live.sim.stage, robot, backend)
        result["joint_force_probe"] = force_binding
        action_names, ids = [], []
        for term_name in live.action_manager.active_terms:
            term = live.action_manager.get_term(term_name)
            action_names.extend(term._joint_names)
            ids.extend(range(30) if isinstance(term._joint_ids, slice) else map(int, term._joint_ids))
            require(np.all(np.asarray(torch.as_tensor(term._scale).cpu()) == 1) and
                    np.all(np.asarray(torch.as_tensor(term._offset).cpu()) == 0), "action transform changed")
        wiring.exact_channels(names, action_names, ids, names)
        result["action_names"] = action_names
        model = csc.load_urdf(Path(bound["urdf"]))
        knee = names.index(joint)
        others = [i for i in range(30) if i != knee]
        caps = np.asarray(result["readbacks"]["velocity_caps"])
        result["dependencies"] = {}
        for module in (_drive_targets, body_precheck, csc):
            import inspect
            source = Path(inspect.getfile(module))
            dest = args.out/("dependency_"+source.name)
            shutil.copyfile(source, dest)
            result["dependencies"][dest.name] = wiring.binding.sha256_file(source)
        first_case = len(result["cases"])
        for index in range(first_case, len(plan["cases"])):
            case = plan["cases"][index]
            live.reset()
            active = dict(index=index, **case, completed=False, rows=[])
            result["cases"].append(active)
            previous = backend(robot.root_view.get_dof_positions())
            active["initial_q_rad"] = previous.tolist()
            desired = np.zeros(30)
            for step in range(case["steps"]):
                require(elapsed_before+time.monotonic()-start < settings["wall_budget_s"], "wall-clock budget exhausted")
                require(result["physics_steps"] < settings["max_steps"], "physical-step budget exhausted")
                if step % 4 == 0:
                    desired = np.zeros(30)
                    desired[knee] = target(step*.005, case["ramp_s"])
                    action = torch.tensor([[desired[names.index(n)] for n in action_names]],
                                          device=args.device, dtype=torch.float32)
                    live.action_manager.process_action(action)
                live.action_manager.apply_action()
                live.scene.write_data_to_sim()
                drive = _drive_targets(robot, backend, desired)
                live.sim.step(render=False)
                live.scene.update(.005)
                result["physics_steps"] += 1
                q = backend(robot.root_view.get_dof_positions())
                v = backend(robot.root_view.get_dof_velocities())
                fd = (q-previous)/.005
                previous = q.copy()
                force = _joint_force_probe_sample(robot.root_view, backend, force_binding)
                contact = float(torch.linalg.vector_norm(live.scene["contact_forces"].data.net_forces_w, dim=-1).max())
                row = dict(t_s=(step+1)*.005, q_rad=q, velocity_rad_s=v,
                    position_delta_velocity_rad_s=fd, target_rad=desired.copy(),
                    backend_position_target_rad=drive["position_rad"], backend_velocity_target_rad_s=drive["velocity_rad_s"],
                    contact_n=contact, **force)
                active["rows"].append(row)
                require(all(np.isfinite(value).all() for value in row.values()), "non-finite sample")
                require(np.array_equal(q, robot.data.joint_pos.torch[0].cpu().numpy()) and
                        np.array_equal(v, robot.data.joint_vel.torch[0].cpu().numpy()), "backend/cache mismatch")
                require(abs(q[knee]) <= SETTINGS["knee_stop_rad"] and
                        abs(q[others]).max() <= SETTINGS["other_stop_rad"], "position stop")
                require(max(abs(v[knee]), abs(fd[knee])) <= SETTINGS["knee_speed_stop_rad_s"] and
                        np.all(abs(v[others]) < caps[others]*.5), "speed stop")
                require(abs(force["projected_joint_effort_nm"][knee]) <= SETTINGS["knee_effort_stop_nm"],
                        "active-joint load stop")
                require(contact <= 1., "contact stop")
            active["completed"] = True
            active["entities_final"] = _entity_snapshot(robot, model)
            save_case(args.out, active, knee)
            active = None
            print("SPEED_CASE_COMPLETED", index, result["cases"][-1]["summary"], flush=True)
            save_progress(args.out, result, index)
        result.update(completed=True, status="speed_observation_completed", elapsed_wall_s=elapsed_before+time.monotonic()-start)
        wiring.write_json(args.out/"report.json", result)
    except BaseException as error:
        result.update(status="stopped", error=repr(error), traceback=traceback.format_exc(), elapsed_wall_s=elapsed_before+time.monotonic()-start)
        if active is not None and active["rows"]:
            save_case(args.out, active, names.index(joint))
        wiring.write_json(args.out/"failure.json", result)
        traceback.print_exc()
        sys.stdout.flush(); sys.stderr.flush()
        os._exit(1)
    finally:
        if env is not None:
            env.close()
        if app is not None:
            app.close()


def save_case(out, case, knee):
    """Save all raw samples before any result interpretation [SI]."""
    rows = case.pop("rows")
    data = {key: np.asarray([row[key] for row in rows]) for key in rows[0]}
    path = out/f"case_{case['index']:02d}.npz"
    require(not path.exists(), "case output exists")
    np.savez_compressed(path, **data)
    summary = (summarize(data, case, knee) if all(np.isfinite(v).all() for v in data.values())
               else dict(steps=len(rows), non_finite_sample=True))
    case.update(raw=str(path), raw_sha256=wiring.binding.sha256_file(path), summary=summary)


def audit_case(data, case, names, joint=JOINT):
    """Authenticate temporal/column meaning before deriving speed [SI]."""
    knee = names.index(joint)
    count = len(data["t_s"])
    require(count == case["summary"]["steps"] and count <= case["steps"], "sample count mismatch")
    require(all(np.isfinite(value).all() for value in data.values()), "non-finite raw data")
    require(data["q_rad"].shape == (count, 30), "joint columns mismatch")
    require(np.allclose(data["t_s"], np.arange(1, count+1)*.005, atol=1e-12, rtol=0), "time axis mismatch")
    initial = np.array(case["initial_q_rad"], dtype=data["q_rad"].dtype)[None]
    fd = np.diff(np.concatenate((initial, data["q_rad"])), axis=0)/.005
    require(np.array_equal(fd, data["position_delta_velocity_rad_s"]), "position-delta speed mismatch")
    commanded = np.zeros((count, 30))
    commanded[:, knee] = [target((step//4)*.02, case["ramp_s"]) for step in range(count)]
    require(np.array_equal(commanded, data["target_rad"]), "50 Hz target trajectory mismatch")
    require(np.allclose(commanded, data["backend_position_target_rad"], atol=1e-6, rtol=0), "backend target mismatch")
    expected_velocity = np.zeros((count, 30))
    expected_velocity[:, knee] = [commanded_velocity((step//4)*.02, case) for step in range(count)]
    require(np.allclose(expected_velocity, data["backend_velocity_target_rad_s"], atol=1e-6, rtol=0),
            "velocity target changed")
    actual = summarize(data, case, knee)
    require(actual == case["summary"], "saved summary differs from raw measurements")
    return actual


def response_diagnostics(data, case, axis, kp, kd):
    """Explain sampled response [SI]; PD terms are estimates, not telemetry."""
    error = data["target_rad"][:, axis]-data["q_rad"][:, axis]
    velocity = data["velocity_rad_s"][:, axis]
    goal_velocity = data["backend_velocity_target_rad_s"][:, axis]
    p_term, d_term = kp*error, kd*(goal_velocity-velocity)
    k = int(np.argmax(abs(error)))
    moving = data["t_s"] > SETTINGS["settle_s"]
    return dict(post_settle_error_rms_rad=float(np.sqrt(np.mean(error[moving]**2))) if moving.any() else None,
                max_backend_velocity_target_rad_s=float(abs(goal_velocity).max()),
                at_max_error=dict(t_s=float(data["t_s"][k]), error_rad=float(error[k]),
                    velocity_rad_s=float(velocity[k]), velocity_target_rad_s=float(goal_velocity[k]),
                    p_term_estimate_nm=float(p_term[k]), d_term_estimate_nm=float(d_term[k]),
                    pd_sum_estimate_nm=float(p_term[k]+d_term[k]),
                    measured_step_average_projected_load_nm=float(data["projected_joint_effort_nm"][k, axis])),
                scope="post-step algebraic PD estimates; not implicit solver motor effort")


def chest_gravity_diagnostics(data, case, names, manifest):
    """Compare held-window chest load with URDF self-weight [N m, kg, rad]."""
    import xml.etree.ElementTree as ET
    from palm_spatial_inertia import csc
    model = csc.load_urdf(Path(manifest["target_binding"]["urdf"]))
    tree = ET.parse(manifest["target_binding"]["urdf"]).getroot()
    bodies = {link.get("name"): (float(link.find("inertial/mass").get("value")),
              np.fromstring(link.find("inertial/origin").get("xyz"), sep=" "))
              for link in tree.findall("link")}
    chest = "chest_pitch_joint"
    axis_index = names.index(chest)
    descendants = [name for name in bodies if chest in csc.chain_up(model["joints"], name)]

    def frames(q):
        angles = dict(zip(names, q))
        return {name: csc.fk(model["joints"], name, angles) for name in bodies}

    def potential(q):
        poses = frames(q)
        return sum(9.81*mass*(poses[name][:3, :3]@com+poses[name][:3, 3])[2]
                   for name, (mass, com) in bodies.items())

    ramp = case["ramp_s"]
    ends = dict(settle=5., positive_hold=5.+ramp+1., positive_returned=5.+2*ramp+2.,
                negative_hold=5.+3*ramp+3., negative_returned=case["duration_s"])
    windows = {}
    for label, end in ends.items():
        mask = (data["t_s"] >= end-.2-1e-8) & (data["t_s"] <= end+1e-8)
        if not mask.any():
            continue
        q = data["q_rad"][mask].mean(axis=0)
        poses = frames(q)
        spec = model["joints"][chest]
        pivot = poses[spec["child"]][:3, 3]
        axis = poses[spec["child"]][:3, :3]@spec["axis"]
        contributions = {}
        for name in descendants:
            mass, com = bodies[name]
            center = poses[name][:3, :3]@com+poses[name][:3, 3]
            contributions[name] = -float(axis@np.cross(center-pivot, [0., 0., -9.81*mass]))
        compensation = sum(contributions.values())
        step = np.zeros(len(names)); step[axis_index] = 1e-5
        derivative = (potential(q+step)-potential(q-step))/(2e-5)
        measured = float(data["projected_joint_effort_nm"][mask, axis_index].mean())
        windows[label] = dict(samples=int(mask.sum()), gravity_compensation_nm=compensation,
            potential_derivative_nm=float(derivative), gravity_method_difference_nm=float(compensation-derivative),
            measured_mean_projected_load_nm=measured, load_minus_gravity_nm=measured-compensation,
            max_chest_position_delta_speed_rad_s=float(abs(data["position_delta_velocity_rad_s"][mask, axis_index]).max()),
            max_all_joint_position_range_rad=float(np.ptp(data["q_rad"][mask], axis=0).max()),
            gravity_contributions_nm=contributions)
    return dict(downstream_links=descendants, downstream_mass_kg=sum(bodies[n][0] for n in descendants),
                windows=windows, scope="fixed-root identity orientation; self-weight at held-window mean actual q; no contact or dynamic-load prediction")


def replay(path, digest):
    """Re-read saved speed trials and falsify corrupted numerical evidence."""
    require(wiring.binding.sha256_file(path) == digest, "report digest mismatch")
    report = json.loads(path.read_text(encoding="utf-8"))
    require(wiring.binding.sha256_file(Path(report["plan"])) == report["plan_sha256"], "plan changed")
    plan = json.loads(Path(report["plan"]).read_text(encoding="utf-8"))
    settings, schedule = validate_plan(plan)
    require(report["settings"] == settings and report.get("experiment", "staged_speed") ==
            plan.get("experiment", "staged_speed"), "report experiment/settings differ")
    joint = selected_joint(report)
    require(joint == selected_joint(plan),
            "report/plan joint or schedule differs")
    reference, manifest_path, manifest = load_reference(Path(report["reference"]))
    require(report["joint_names"] == reference["joint_names"], "report joint axis changed")
    require(report["manifest"] == str(manifest_path) and report["manifest_sha256"] == reference["tracking_manifest_sha256"],
            "report manifest differs")
    for key in ("kp", "kd", "effort_caps", "velocity_caps"):
        require(report["readbacks"][key] == reference["readbacks"][key], "report readback changed: "+key)
    require(report["readbacks"]["force_timing"] is False and report["readbacks"]["solver"] == "TGS",
            "report solver differs")
    require(wiring.binding.sha256_file(path.parent/"source.py") == report["code_sha256"], "source snapshot changed")
    if report.get("prior_run"):
        prefix = report["prior_run"]
        require(wiring.binding.sha256_file(Path(prefix["report"])) == prefix["sha256"], "prefix report changed")
        require(wiring.binding.sha256_file(Path(prefix["report"]).parent/"source.py") == prefix["code_sha256"],
                "prefix source changed")
    totals, summaries, negatives, constraints, responses, pair_raw, chest_loads = 0, [], [], [], [], [], []
    for index, case in enumerate(report["cases"]):
        require(index < len(schedule) and case["index"] == index and
                all(case[k] == schedule[index][k] for k in schedule[index]),
                "case schedule differs")
        require(wiring.binding.sha256_file(Path(case["raw"])) == case["raw_sha256"], "raw case changed")
        with np.load(case["raw"], allow_pickle=False) as raw:
            data = dict(raw)
        summaries.append(audit_case(data, case, report["joint_names"], joint))
        axis = report["joint_names"].index(joint)
        responses.append(response_diagnostics(data, case, axis, report["readbacks"]["kp"][axis],
                                              report["readbacks"]["kd"][axis]))
        chest_loads.append(chest_gravity_diagnostics(data, case, report["joint_names"], manifest))
        if report.get("experiment") == "velocity_reference_comparison":
            pair_raw.append(data)
        bounds = np.asarray(report["joint_force_probe"]["position_limits_rad"])
        margin = np.minimum(data["q_rad"]-bounds[:, 0], bounds[:, 1]-data["q_rad"])
        projected = data["projected_joint_effort_nm"]
        manual = data["manual_axis_projection_nm"]
        require(np.allclose(projected, manual, atol=64*np.finfo(np.float32).eps*max(1., float(abs(projected).max())), rtol=0),
                "joint load projection differs")
        require(not data["explicit_actuation_input_nm"].any(), "explicit effort input appeared")
        ratios = abs(projected)/np.asarray(report["readbacks"]["effort_caps"])
        peak_step, peak_joint = np.unravel_index(np.argmax(ratios), ratios.shape)
        settled = data["t_s"] > SETTINGS["settle_s"]
        constraints.append(dict(min_position_margin_rad=float(margin.min()),
            max_projected_load_to_cap_ratio=float(ratios.max()),
            global_peak_load_joint=report["joint_names"][peak_joint],
            global_peak_load_t_s=float(data["t_s"][peak_step]),
            global_peak_load_nm=float(projected[peak_step, peak_joint]),
            post_settle_max_load_to_cap_ratio=float(ratios[settled].max()) if settled.any() else None,
            samples_any_axis_above_99pct=int(np.any(ratios >= .99, axis=1).sum()),
            max_backend_speed_to_cap_ratio=float((abs(data["velocity_rad_s"])/np.asarray(report["readbacks"]["velocity_caps"])).max())))
        totals += len(data["t_s"])
        if not negatives:
            for defect in ("fake_achieved_speed", "wrong_target_column", "wrong_time", "wrong_velocity_target"):
                bad = {key: value.copy() for key, value in data.items()}
                if defect == "fake_achieved_speed":
                    bad["position_delta_velocity_rad_s"][:] = case["nominal_target_peak_rad_s"]
                elif defect == "wrong_target_column":
                    bad["target_rad"] = np.roll(bad["target_rad"], 1, axis=1)
                elif defect == "wrong_time":
                    bad["t_s"] += .005
                else:
                    bad["backend_velocity_target_rad_s"][:, report["joint_names"].index(joint)] += 1.
                try:
                    audit_case(bad, case, report["joint_names"], joint)
                except ValueError:
                    negatives.append(defect)
                else:
                    raise ValueError("corrupted speed evidence accepted: "+defect)
    require(totals == report["physics_steps"] and totals <= settings["max_steps"], "total physical budget mismatch")
    if report["completed"]:
        require(len(report["cases"]) == len(schedule) and all(c["completed"] for c in report["cases"]) and
                totals == sum(c["steps"] for c in schedule), "completed verdict without full schedule")
    comparison = None
    if pair_raw:
        source = plan["baseline_source"]
        require(source["sha256"] == ELBOW_REPORT_SHA and
                replay(Path(source["report"]), source["sha256"])["completed"], "comparison baseline changed")
        baseline = json.loads(Path(source["report"]).read_text(encoding="utf-8"))["cases"][-1]
        with np.load(baseline["raw"], allow_pickle=False) as original:
            n = len(pair_raw[0]["t_s"])
            require(np.array_equal(pair_raw[0]["target_rad"], original["target_rad"][:n]),
                    "comparison baseline position trajectory differs")
            reproduction = float(abs(pair_raw[0]["q_rad"]-original["q_rad"][:n]).max())
        comparison = dict(baseline_reproduction_max_q_difference_rad=reproduction)
        if len(pair_raw) == 2:
            n = min(len(d["t_s"]) for d in pair_raw)
            require(np.array_equal(pair_raw[0]["target_rad"][:n], pair_raw[1]["target_rad"][:n]) and
                    np.array_equal(report["cases"][0]["initial_q_rad"], report["cases"][1]["initial_q_rad"]),
                    "paired initial state or position targets differ")
        if report["completed"]:
            comparison.update(max_error_reduction_fraction=1-summaries[1]["max_direct_error_rad"]/summaries[0]["max_direct_error_rad"],
                post_settle_rms_error_reduction_fraction=1-responses[1]["post_settle_error_rms_rad"]/responses[0]["post_settle_error_rms_rad"])
    return dict(completed=report["completed"], joint=joint, physics_steps=totals, summaries=summaries,
                chest_gravity_diagnostics=chest_loads,
                response_diagnostics=responses, velocity_reference_comparison=comparison,
                constraint_readbacks=constraints, negative_cases_rejected=negatives, stop_reason=report.get("error"))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--prepare", action="store_true")
    parser.add_argument("--joint", choices=JOINTS, help="prepare only; execution/replay use the bound plan joint")
    parser.add_argument("--reference", type=Path, default=REPO/"rl_exp/out/lizard2_b_joint_force_probe_20261021/report.json")
    parser.add_argument("--plan", type=Path)
    parser.add_argument("--approved_plan_sha256")
    parser.add_argument("--resume", type=Path)
    parser.add_argument("--approved_resume_sha256")
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--self_check", action="store_true")
    parser.add_argument("--replay", type=Path)
    parser.add_argument("--approved_report_sha256")
    if not any(flag in sys.argv for flag in ("--prepare", "--self_check", "--replay")):
        from isaaclab.app import AppLauncher
        AppLauncher.add_app_launcher_args(parser)
    args = parser.parse_args()
    require(args.joint is None or args.prepare, "--joint is only valid with --prepare")
    if args.self_check:
        self_check()
        return
    if args.replay:
        require(args.approved_report_sha256, "approved report digest required")
        wiring.write_json(args.out.resolve(), replay(args.replay, args.approved_report_sha256))
        print("SPEED_REPLAY_OK", flush=True)
        return
    args.out = args.out.resolve()
    require(args.out.is_relative_to(REPO/"rl_exp/out") and not args.out.exists(), "choose a new output directory")
    args.out.mkdir(parents=True)
    shutil.copyfile(__file__, args.out/"source.py")
    if args.prepare:
        prepare(args)
    else:
        run(args)


if __name__ == "__main__":
    main()
