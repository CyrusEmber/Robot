# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause
"""Bounded low-cap comparison consumers for palm_speed_probe [SI].

Only the approved left rear knee experiment is represented here. Lower caps
are runtime diagnostic overrides, never new defaults or hardware ratings.
"""
from __future__ import annotations

import numpy as np

EXPERIMENT = "lower_cap_comparison"
JOINT = "rl_knee_joint"
READERS = dict(kp="get_dof_stiffnesses", kd="get_dof_dampings",
               effort_caps="get_dof_max_forces", velocity_caps="get_dof_max_velocities")
CRITERIA = dict(speed_cap_rad_s=2., speed_upper_rad_s=2.1, speed_lower_rad_s=1.8,
                speed_plateau_s=.04, baseline_load_nm=5.1, baseline_excitation_s=.04,
                effort_cap_nm=5., effort_lower_nm=4.9, effort_upper_nm=5.1,
                effort_plateau_s=.02, response_rad=1e-4, position_margin_rad=.2,
                effort_trial_speed_max_rad_s=8., state_atol=float(64*np.finfo(np.float32).eps))


def require(condition, message):
    if not condition:
        raise ValueError(message)


def schedule(settings, base_case):
    """Return the three authorized cases and their collection budget [SI]."""
    result = [dict(base_case, name=name, velocity_target_mode="zero", velocity_cap_rad_s=v, effort_cap_nm=f)
              for name, v, f in (("A_baseline", 10., 180.), ("B_lower_speed_cap", 2., 180.),
                                 ("C_lower_effort_cap", 10., 5.))]
    require(base_case["ramp_s"] == .36 and base_case["steps"] == 2088, "cap trial trajectory changed")
    settings = dict(settings, max_cases=3, max_steps=6264,
                    scope="left-knee low-cap response only; not original-cap capability", cap_criteria=CRITERIA)
    return settings, result


def expected_readbacks(base, case, axis):
    """Derive the complete expected runtime override, including unchanged gains."""
    result = {key: np.asarray(base[key], dtype=np.float32).copy() for key in READERS}
    result["velocity_caps"][axis] = case["velocity_cap_rad_s"]
    result["effort_caps"][axis] = case["effort_cap_nm"]
    return result


def check_readbacks(actual, expected):
    for key in READERS:
        require(np.array_equal(actual[key], expected[key]), "unexpected runtime readback: "+key)


def match_state(actual, expected):
    require(np.allclose(actual, expected, atol=CRITERIA["state_atol"], rtol=0),
            "paired initial/settled state differs")


class Runtime:
    """Write and authenticate low caps through the existing simulator API [SI]."""

    def __init__(self, robot, backend, torch, device, base, axis):
        self.robot, self.backend, self.torch, self.device = robot, backend, torch, device
        self.base = {key: np.asarray(base[key], dtype=np.float32) for key in READERS}
        self.axis, self.settled_state, self.initial_state = axis, None, None
        require(self.base["velocity_caps"][axis] == 10. and self.base["effort_caps"][axis] == 180.,
                "unexpected original knee caps")

    def read(self):
        return {key: self.backend(getattr(self.robot.root_view, getter)()) for key, getter in READERS.items()}

    def write(self, desired):
        for key, method in (("velocity_caps", "write_joint_velocity_limit_to_sim_index"),
                            ("effort_caps", "write_joint_effort_limit_to_sim_index")):
            tensor = self.torch.as_tensor(desired[key][None].copy(), device=self.device, dtype=self.torch.float32)
            getattr(self.robot, method)(limits=tensor, full_data=True)
        actual = self.read()
        check_readbacks(actual, desired)
        return {key: value.tolist() for key, value in actual.items()}

    def restore(self):
        return self.write(self.base)

    def initial(self, q, v):
        state = np.stack((q, v))
        if self.initial_state is None:
            self.initial_state = state.copy()
        match_state(state, self.initial_state)

    def activate(self, case, q, v):
        state = np.stack((q, v))
        if self.settled_state is None:
            self.settled_state = state.copy()
        match_state(state, self.settled_state)
        before = self.read()
        check_readbacks(before, self.base)
        return dict(t_s=5., settled_q_rad=q.tolist(), settled_velocity_rad_s=v.tolist(),
                    before={key: value.tolist() for key, value in before.items()},
                    after=self.write(expected_readbacks(self.base, case, self.axis)))

    def sample(self, case, active):
        desired = expected_readbacks(self.base, case, self.axis) if active else self.base
        actual = self.read()
        check_readbacks(actual, desired)
        return {"runtime_"+key: value for key, value in actual.items()}


def longest(mask):
    best = count = 0
    for value in mask:
        count = count+1 if value else 0
        best = max(best, count)
    return best*.005


def metrics(data, axis):
    """Compute excitation and bound diagnostics from actual sampled motion [SI]."""
    times = data["t_s"]
    moving = times > 5.+1e-9
    q = data["q_rad"][:, axis]
    fd = abs(data["position_delta_velocity_rad_s"][:, axis])
    load = abs(data["projected_joint_effort_nm"][:, axis])
    # The first complete 20 ms window after the override excludes pre-override samples.
    speed20 = abs(q[4:]-q[:-4])/.02
    active20 = times[4:] >= 5.02-1e-9
    c = CRITERIA
    return dict(baseline_speed_excitation_s=longest(moving & (fd > c["speed_upper_rad_s"])),
                baseline_load_excitation_s=longest(moving & (load > c["baseline_load_nm"])),
                max_step_speed_rad_s=float(fd[moving].max()) if moving.any() else None,
                max_backend_speed_rad_s=float(abs(data["velocity_rad_s"][moving, axis]).max()) if moving.any() else None,
                max_20ms_speed_rad_s=float(speed20[active20].max()) if active20.any() else None,
                speed_plateau_s=longest(active20 & (speed20 >= c["speed_lower_rad_s"]) &
                                       (speed20 <= c["speed_upper_rad_s"])),
                max_step_average_load_nm=float(load[moving].max()) if moving.any() else None,
                effort_plateau_s=longest(moving & (load >= c["effort_lower_nm"]) & (load <= c["effort_upper_nm"])))


def baseline_excited(data, axis):
    values = metrics(data, axis)
    return all(values[key]+1e-10 >= CRITERIA["baseline_excitation_s"]
               for key in ("baseline_speed_excitation_s", "baseline_load_excitation_s"))


def check_case(data, case, base, axis, binding):
    """Verify per-frame overrides and the original safety stops [SI]."""
    count = len(data["t_s"])
    require(count > 0, "empty cap trial")
    active = data["t_s"] > 5.+1e-9
    expected = expected_readbacks(base, case, axis)
    for key in READERS:
        values = np.broadcast_to(np.asarray(base[key]), (count, 30)).copy()
        values[active] = expected[key]
        require(np.array_equal(data["runtime_"+key], values), "wrong per-frame override: "+key)
    q, v, fd = data["q_rad"], data["velocity_rad_s"], data["position_delta_velocity_rad_s"]
    others = [i for i in range(30) if i != axis]
    valid = ((abs(q[:, axis]) <= 1.) & (abs(q[:, others]).max(axis=1) <= .35) &
             (np.maximum(abs(v[:, axis]), abs(fd[:, axis])) <= 9.) &
             np.all(abs(v[:, others]) < np.asarray(base["velocity_caps"])[others]*.5, axis=1) &
             (abs(data["projected_joint_effort_nm"][:, axis]) <= 144.) & (data["contact_n"] <= 1.))
    bad = np.flatnonzero(~valid)
    require(len(bad) == 0 or (not case["completed"] and len(bad) == 1 and bad[0] == count-1),
            "safety stop ignored or incomplete case mislabeled")
    incoming = data["incoming_child_joint_wrench"]
    manual = np.stack([incoming[:, binding["joints"][name]["child_index"],
                                   binding["joints"][name]["torque_component"]]
                       for name in binding["joint_names"]], axis=1)
    require(np.array_equal(manual, data["manual_axis_projection_nm"]), "raw wrench projection changed")
    projected = data["projected_joint_effort_nm"]
    require(np.allclose(projected, manual, rtol=0,
                       atol=64*np.finfo(np.float32).eps*max(1., float(abs(projected).max()))),
            "projected/raw joint load differs")
    require(not data["explicit_actuation_input_nm"].any(), "explicit effort appeared")
    return dict(safety_stop_at_last_sample=bool(len(bad)))


def verdict(datas, cases, axis, binding, completed):
    """Separate a valid low-cap response, failed criteria and missing evidence."""
    result = dict(full_window=bool(completed and len(datas) == 3 and all(c["completed"] for c in cases)),
                  cases=[metrics(data, axis) for data in datas], baseline_excited=False,
                  speed_response="unjudged", effort_response="unjudged", passed=False)
    if not datas or not cases[0]["completed"]:
        return result
    result["baseline_excited"] = baseline_excited(datas[0], axis)
    if not result["baseline_excited"]:
        return result
    c = CRITERIA
    for index, data in enumerate(datas[1:], 1):
        n = min(len(data["t_s"]), len(datas[0]["t_s"]))
        match_state(data["q_rad"][:min(n, 1000)], datas[0]["q_rad"][:min(n, 1000)])
        match_state(data["velocity_rad_s"][:min(n, 1000)], datas[0]["velocity_rad_s"][:min(n, 1000)])
        require(np.array_equal(data["target_rad"][:n], datas[0]["target_rad"][:n]), "paired target differs")
        if not cases[index]["completed"]:
            continue
        values = result["cases"][index]
        if index == 1:
            passed = (values["max_20ms_speed_rad_s"] <= c["speed_upper_rad_s"] and
                      values["speed_plateau_s"]+1e-10 >= c["speed_plateau_s"])
            result["speed_response"] = "passed" if passed else "criteria_unmet"
        else:
            active = data["t_s"] > 5.+1e-9
            limits = np.asarray(binding["position_limits_rad"])[axis]
            margin = np.minimum(data["q_rad"][active, axis]-limits[0], limits[1]-data["q_rad"][active, axis])
            contribution_clear = (float(margin.min()) > c["position_margin_rad"] and
                max(values["max_step_speed_rad_s"], values["max_backend_speed_rad_s"]) < c["effort_trial_speed_max_rad_s"] and
                not np.asarray(binding["friction_properties"]).any() and
                not np.asarray(binding["armatures"]).any() and not binding["tendon_prims"])
            response = float(abs(data["q_rad"][:n, axis]-datas[0]["q_rad"][:n, axis]).max())
            result.update(effort_contribution_clear=bool(contribution_clear), effort_trial_min_margin_rad=float(margin.min()),
                          effort_q_response_vs_A_rad=response)
            passed = (values["max_step_average_load_nm"] <= c["effort_upper_nm"] and
                      values["effort_plateau_s"]+1e-10 >= c["effort_plateau_s"] and response > c["response_rad"])
            result["effort_response"] = ("passed" if passed else "criteria_unmet") if contribution_clear else "unjudged"
    result["passed"] = result["full_window"] and all(result[key] == "passed" for key in ("speed_response", "effort_response"))
    return result


def self_check():
    """Exercise real cap consumers against synthetic bounds and corruptions."""
    import copy
    import json
    json.dumps(CRITERIA, allow_nan=False)
    count, axis = 2088, 0
    times = np.arange(1, count+1)*.005
    phase = np.maximum(times-5., 0.)
    names = [JOINT]+[f"other_{i}" for i in range(29)]
    base = {key: np.full(30, value, dtype=np.float32) for key, value in
            (("kp", 220.), ("kd", 14.95), ("velocity_caps", 10.), ("effort_caps", 180.))}
    from types import SimpleNamespace
    fake_values = {key: value.copy() for key, value in base.items()}
    view = SimpleNamespace(**{getter: (lambda key=key: fake_values[key].copy()) for key, getter in READERS.items()})

    def write_fake(key, *, limits, full_data):
        require(full_data and limits.shape == (1, 30), "wrong cap setter dimensions")
        fake_values[key] = limits[0].copy()

    robot = SimpleNamespace(root_view=view,
        write_joint_velocity_limit_to_sim_index=lambda **kwargs: write_fake("velocity_caps", **kwargs),
        write_joint_effort_limit_to_sim_index=lambda **kwargs: write_fake("effort_caps", **kwargs))
    torch = SimpleNamespace(float32=np.float32, as_tensor=lambda a, **kwargs: np.asarray(a, dtype=np.float32))
    runtime = Runtime(robot, lambda a: a, torch, "cpu", base, axis)
    runtime.restore()
    intervention = dict(velocity_cap_rad_s=2., effort_cap_nm=180.)
    runtime.activate(intervention, np.zeros(30), np.zeros(30))
    require(fake_values["velocity_caps"][axis] == 2., "runtime intervention missing")
    runtime.sample(intervention, True)
    runtime.restore()
    check_readbacks(fake_values, base)
    # A no-op backend write must fail the real Runtime readback check.
    robot.write_joint_velocity_limit_to_sim_index = lambda **kwargs: None
    try:
        runtime.activate(intervention, np.zeros(30), np.zeros(30))
    except ValueError:
        pass
    else:
        raise ValueError("runtime accepted an ignored cap write")
    binding = dict(joint_names=names, position_limits_rad=[[-1.2, 1.2]]*30,
                   friction_properties=np.zeros((30, 3)).tolist(), armatures=[0.]*30, tendon_prims=[],
                   joints={name: dict(child_index=i, torque_component=3) for i, name in enumerate(names)})
    _, cases = schedule({}, dict(ramp_s=.36, steps=count, duration_s=10.44, nominal_target_peak_rad_s=4.))
    datas = []
    for index, case in enumerate(cases):
        case["completed"] = True
        q = np.zeros((count, 30))
        q[:, axis] = .5*np.sin(phase*8.)*(1., .5, .9)[index]
        fd = np.diff(np.concatenate((np.zeros((1, 30)), q)), axis=0)/.005
        load = np.zeros_like(q)
        load[:, axis] = 8.*np.sin(phase*12.)
        if index == 2:
            load = np.clip(load, -5., 5.)
        incoming = np.zeros((count, 31, 6)); incoming[:, :30, 3] = load
        data = dict(t_s=times, q_rad=q, velocity_rad_s=fd, position_delta_velocity_rad_s=fd,
                    target_rad=np.zeros_like(q), projected_joint_effort_nm=load,
                    incoming_child_joint_wrench=incoming, manual_axis_projection_nm=load.copy(),
                    explicit_actuation_input_nm=np.zeros_like(q), contact_n=np.zeros(count))
        desired = expected_readbacks(base, case, axis)
        for key in READERS:
            data["runtime_"+key] = np.broadcast_to(base[key], q.shape).copy()
            data["runtime_"+key][times > 5.+1e-9] = desired[key]
        check_case(data, case, base, axis, binding)
        datas.append(data)
    require(verdict(datas, cases, axis, binding, True)["passed"], "positive cap response rejected")
    for defect in ("stale_cap", "extra_joint", "changed_pd", "fake_projection"):
        bad = copy.deepcopy(datas[1])
        if defect == "stale_cap":
            bad["runtime_velocity_caps"][1000:, axis] = 10.
        elif defect == "extra_joint":
            bad["runtime_velocity_caps"][1000:, 1] = 2.
        elif defect == "changed_pd":
            bad["runtime_kp"][1000:, axis] += 1.
        else:
            bad["projected_joint_effort_nm"][1000:, axis] += 1.
        try:
            check_case(bad, cases[1], base, axis, binding)
        except ValueError:
            pass
        else:
            raise ValueError("corrupt cap evidence accepted: "+defect)
    bad = copy.deepcopy(datas)
    for key in ("q_rad", "velocity_rad_s", "position_delta_velocity_rad_s"):
        bad[1][key] = datas[0][key].copy()
    require(verdict(bad, cases, axis, binding, True)["speed_response"] == "criteria_unmet",
            "unconstrained speed response accepted")
    require(not verdict(datas, cases, axis, binding, False)["passed"], "missing full trial accepted")
    bad = copy.deepcopy(datas)
    bad[2]["projected_joint_effort_nm"][:] = 0.
    require(verdict(bad, cases, axis, binding, True)["effort_response"] == "criteria_unmet",
            "unexcited effort response accepted")
    print("LOW_CAP_CONSUMER_SELF_CHECK_OK", flush=True)
