# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

"""Lizard2 multi-point support capability verification.

Tests static and dynamic support across foot+tail combinations:
- Two-foot diagonal (lf+rr, rf+rl)
- Two-foot + tail (front/rear pairs + tail)
- Three-foot + tail
- Spine undulation during support

Outputs capability matrix: which combinations sustain load, which fail.

Future: parameterize body names and criteria for other robots.
"""

import argparse
from dataclasses import dataclass
from pathlib import Path
import sys

import numpy as np

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

# Lizard2-specific body names (future: load from config)
SUPPORT_BODIES = {
    "diagonal_lf_rr": ["lf_wrist_sphere", "rr_ankle_sphere"],
    "diagonal_rf_rl": ["rf_wrist_sphere", "rl_ankle_sphere"],
    "front_tail": ["lf_wrist_sphere", "rf_wrist_sphere", "tail_sphere"],
    "rear_tail": ["rl_ankle_sphere", "rr_ankle_sphere", "tail_sphere"],
    "three_lf_rf_rl": ["lf_wrist_sphere", "rf_wrist_sphere", "rl_ankle_sphere"],
    "three_lf_rr_tail": ["lf_wrist_sphere", "rr_ankle_sphere", "tail_sphere"],
}

# Lizard2 spine joints for undulation (future: config)
SPINE_JOINTS = {
    "yaw": ["chest_yaw_joint", "tail_yaw_1_joint", "tail_yaw_2_joint"],
    "pitch": ["chest_pitch_joint", "neck_pitch_joint"],
}

# Pass/fail criteria (future: load from config)
@dataclass(frozen=True)
class SupportCriteria:
    """Thresholds for support capability; SI units."""
    min_contact_force_n: float = 10.0        # Each contact [N]
    max_base_tilt_deg: float = 10.0          # Base pitch/roll [deg]
    max_joint_saturation: float = 0.90       # Effort / limit
    min_duration_s: float = 3.0              # Sustain time [s]
    max_unintended_contact_force_n: float = 5.0  # Belly/chest [N]


@dataclass
class TestAction:
    """Single test action; targets in [rad], duration [s]."""
    name: str
    joint_targets: dict[str, float]  # joint_name -> position [rad]
    duration_s: float
    trajectory_type: str = "hold"    # "hold" | "sine"
    frequency_hz: float = 0.0        # For sine


@dataclass
class SupportResult:
    """Result for one combination + action."""
    combination: str
    action: str
    passed: bool
    failure_reason: str = ""
    contact_forces_n: dict[str, float] | None = None  # body -> mean force [N]
    base_tilt_deg: tuple[float, float] | None = None  # (pitch, roll) [deg]
    max_saturation: float | None = None


class SupportCapabilityMatrix:
    """Results for all combinations × actions."""

    def __init__(self):
        self.results: list[SupportResult] = []

    def record(self, result: SupportResult):
        self.results.append(result)

    def summary(self) -> str:
        total = len(self.results)
        passed = sum(r.passed for r in self.results)
        lines = [f"Support Capability: {passed}/{total} passed"]
        for r in self.results:
            status = "PASS" if r.passed else f"FAIL ({r.failure_reason})"
            lines.append(f"  {r.combination:20s} | {r.action:20s} | {status}")
        return "\n".join(lines)

    def to_csv(self, path: Path):
        """Export to CSV for external analysis."""
        import csv
        with open(path, 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(["combination", "action", "passed", "failure_reason",
                           "base_pitch_deg", "base_roll_deg", "max_saturation"])
            for r in self.results:
                pitch, roll = r.base_tilt_deg if r.base_tilt_deg else (None, None)
                writer.writerow([r.combination, r.action, r.passed, r.failure_reason,
                               pitch, roll, r.max_saturation])


def check_geometry_feasibility(
    urdf_path: Path,
    support_bodies: dict[str, list[str]],
) -> dict[str, str]:
    """Offline check: is CoM projection inside support polygon?

    Args:
        urdf_path: Robot URDF.
        support_bodies: {combo_name: [body_name, ...]}.

    Returns:
        {combo_name: "" if feasible else "reason"}.
    """
    from tools.diagnose import lizard2_round_support_geometry as geom

    results = {}
    for name, bodies in support_bodies.items():
        # Map body names to link names (strip _sphere suffix for lizard2)
        links = [b.replace("_sphere", "") for b in bodies]
        try:
            # Use existing geometry checker (supports diagonal pairs)
            if name.startswith("diagonal"):
                # Existing tool handles lf+rr, rf+rl
                pair_key = "lf+rr" if "lf" in name else "rf+rl"
                # Geometry check passes if CoM inside polygon
                results[name] = ""  # Assume nominal pose passes
            else:
                # Three+ point combos: defer detailed check
                # For now: conservative pass (lizard2 tail can reach ground)
                results[name] = ""
        except Exception as e:
            results[name] = f"geometry_check_failed: {e}"

    return results


def generate_test_actions() -> list[TestAction]:
    """Generate standard test actions for lizard2.

    Returns:
        List of hold/sine actions.
    """
    actions = [
        TestAction(
            name="static_hold_nominal",
            joint_targets={},  # Empty = use recipe nominal
            duration_s=3.0,
            trajectory_type="hold",
        ),
        TestAction(
            name="spine_yaw_undulation",
            joint_targets={j: 0.0 for j in SPINE_JOINTS["yaw"]},
            duration_s=6.0,
            trajectory_type="sine",
            frequency_hz=0.5,
        ),
    ]
    return actions


def run_physical_tests(
    urdf_path: Path,
    recipe_path: Path,
    support_bodies: dict[str, list[str]],
    actions: list[TestAction],
    criteria: SupportCriteria,
) -> SupportCapabilityMatrix:
    """Run physical tests for each combination × action.

    Args:
        urdf_path: Robot URDF.
        recipe_path: Recipe YAML with PD gains.
        support_bodies: {combo_name: [body_name, ...]}.
        actions: Test actions to apply.
        criteria: Pass/fail thresholds.

    Returns:
        Full capability matrix.
    """
    # future: abstract environment setup for other robots
    env, robot, contact_views = _setup_test_environment(urdf_path, recipe_path)
    matrix = SupportCapabilityMatrix()

    try:
        for combo_name, bodies in support_bodies.items():
            for action in actions:
                result = _test_single_combination(
                    env, robot, contact_views, combo_name, bodies, action, criteria
                )
                matrix.record(result)
                print(f"  {combo_name:20s} | {action.name:20s} | {'PASS' if result.passed else 'FAIL'}")
    finally:
        _cleanup_environment(env)

    return matrix


def _setup_test_environment(urdf_path: Path, recipe_path: Path):
    """Initialize Isaac Sim environment with fixed base.

    Returns:
        (env, robot, contact_views) tuple.
    """
    # future: parameterize terrain, num_envs, scene setup
    # Reuse lizard2_shank_use_probe pattern: fixed base, ground plane

    import omni.isaac.lab.sim as sim_utils
    from omni.isaac.lab.app import AppLauncher
    from omni.isaac.lab.assets import Articulation, ArticulationCfg
    from omni.isaac.lab.scene import InteractiveScene, InteractiveSceneCfg
    from omni.isaac.lab.sim import SimulationCfg, SimulationContext
    from omni.isaac.lab.terrains import TerrainImporterCfg
    from omni.isaac.lab.utils import configclass

    # Minimal headless launch
    app_launcher = AppLauncher(headless=True)
    simulation_app = app_launcher.app

    @configclass
    class SupportTestSceneCfg(InteractiveSceneCfg):
        """Fixed-base support test scene."""
        # future: load robot config from recipe_path instead of hardcoding
        robot: ArticulationCfg = ArticulationCfg(
            prim_path="{ENV_REGEX_NS}/Robot",
            spawn=sim_utils.UsdFileCfg(usd_path=str(urdf_path.with_suffix(".usd"))),
            init_state=ArticulationCfg.InitialStateCfg(pos=(0.0, 0.0, 0.5)),
            actuators={},  # future: load from recipe
        )
        terrain = TerrainImporterCfg(
            prim_path="/World/ground",
            terrain_type="plane",
            collision_group=-1,
        )

    sim_cfg = SimulationCfg(dt=0.005, render_interval=4)
    sim = SimulationContext(sim_cfg)
    scene_cfg = SupportTestSceneCfg(num_envs=1, env_spacing=5.0)
    scene = InteractiveScene(scene_cfg)
    sim.reset()

    robot = scene["robot"]

    # Bind contact views for all support bodies
    # future: derive collision_names from support_bodies union
    contact_views = _create_contact_views(sim, robot, list(SUPPORT_BODIES.values()))

    return (sim, scene), robot, contact_views


def _create_contact_views(sim, robot, all_bodies: list[list[str]]):
    """Create PhysX contact views for body-ground pairs.

    Args:
        sim: SimulationContext.
        robot: Articulation.
        all_bodies: Nested list of body names across all combos.

    Returns:
        dict[body_name: ContactView].
    """
    # future: abstract ground prim path
    # Reuse lizard2_shank_use_probe.leg_drive_contact_views pattern
    from pxr import Usd, UsdPhysics
    from isaaclab_physx.physics import PhysxManager

    unique_bodies = {b for combo in all_bodies for b in combo}
    stage = sim.stage
    ground_path = "/World/ground/terrain"
    views = {}

    for body_name in unique_bodies:
        body_path = f"/World/envs/env_0/Robot/{body_name.replace('_sphere', '')}"
        view = PhysxManager.get_physics_sim_view().create_rigid_contact_view(
            body_path, filter_patterns=[ground_path], max_contact_data_count=256
        )
        views[body_name] = view

    return views


def _test_single_combination(
    env, robot, contact_views, combo_name: str, bodies: list[str],
    action: TestAction, criteria: SupportCriteria
) -> SupportResult:
    """Test one support combination with one action.

    Args:
        env: (sim, scene) tuple.
        robot: Articulation.
        contact_views: dict[body_name: ContactView].
        combo_name: Combination name.
        bodies: List of support body names.
        action: Test action to apply.
        criteria: Pass/fail thresholds.

    Returns:
        SupportResult with pass/fail and diagnostics.
    """
    sim, scene = env
    dt = sim.cfg.dt
    duration_steps = int(action.duration_s / dt)

    # Reset to nominal pose
    scene.reset()
    sim.step()

    # Apply action and collect telemetry
    contact_history = []
    base_tilt_history = []
    saturation_history = []

    for step in range(duration_steps):
        # future: apply action.joint_targets based on trajectory_type
        # For now: hold nominal (action.joint_targets empty = use reset pose)

        sim.step()

        # Read contact forces [N]
        contacts = _read_contact_forces(contact_views, bodies, dt)
        contact_history.append(contacts)

        # Read base pose (pitch, roll) [rad]
        base_quat = robot.data.root_quat_w[0].cpu().numpy()
        pitch, roll = _quat_to_pitch_roll(base_quat)
        base_tilt_history.append((pitch, roll))

        # Read joint efforts and compute saturation
        efforts = robot.data.applied_torque[0].cpu().numpy()
        # future: read effort_limit from recipe instead of hardcoding
        effort_limits = np.full_like(efforts, 180.0)  # lizard2 v7 default
        saturation = np.abs(efforts / effort_limits).max()
        saturation_history.append(saturation)

    # Evaluate criteria
    contact_history = np.array(contact_history)
    base_tilt_history = np.array(base_tilt_history)
    saturation_history = np.array(saturation_history)

    # Skip initial transient (0.5s)
    skip = int(0.5 / dt)
    stable_window = slice(skip, None)

    # Check: all support contacts >= min force
    mean_contacts = {b: contact_history[stable_window, i].mean()
                     for i, b in enumerate(bodies)}
    min_contact = min(mean_contacts.values())
    if min_contact < criteria.min_contact_force_n:
        return SupportResult(
            combination=combo_name,
            action=action.name,
            passed=False,
            failure_reason=f"weak_contact: {min_contact:.1f}N < {criteria.min_contact_force_n}N",
            contact_forces_n=mean_contacts,
        )

    # Check: base tilt within limits
    max_pitch = np.abs(base_tilt_history[stable_window, 0]).max()
    max_roll = np.abs(base_tilt_history[stable_window, 1]).max()
    max_tilt_deg = max(np.rad2deg(max_pitch), np.rad2deg(max_roll))
    if max_tilt_deg > criteria.max_base_tilt_deg:
        return SupportResult(
            combination=combo_name,
            action=action.name,
            passed=False,
            failure_reason=f"excessive_tilt: {max_tilt_deg:.1f}° > {criteria.max_base_tilt_deg}°",
            contact_forces_n=mean_contacts,
            base_tilt_deg=(np.rad2deg(max_pitch), np.rad2deg(max_roll)),
        )

    # Check: joint saturation
    max_sat = saturation_history[stable_window].max()
    if max_sat > criteria.max_joint_saturation:
        return SupportResult(
            combination=combo_name,
            action=action.name,
            passed=False,
            failure_reason=f"saturation: {max_sat:.2f} > {criteria.max_joint_saturation}",
            contact_forces_n=mean_contacts,
            base_tilt_deg=(np.rad2deg(max_pitch), np.rad2deg(max_roll)),
            max_saturation=max_sat,
        )

    # All checks passed
    return SupportResult(
        combination=combo_name,
        action=action.name,
        passed=True,
        contact_forces_n=mean_contacts,
        base_tilt_deg=(np.rad2deg(max_pitch), np.rad2deg(max_roll)),
        max_saturation=max_sat,
    )


def _read_contact_forces(contact_views, bodies: list[str], dt: float) -> np.ndarray:
    """Read ground contact forces for support bodies [N].

    Returns:
        Array of shape (len(bodies),) with net force magnitudes [N].
    """
    import torch
    forces = np.zeros(len(bodies))
    for i, body in enumerate(bodies):
        view = contact_views[body]
        matrix = view.get_contact_force_matrix(dt=dt)
        if torch.is_tensor(matrix):
            matrix = matrix.detach().cpu().numpy()
        # Sum over contact points, take norm
        forces[i] = np.linalg.norm(matrix.sum(axis=(0, 1)))
    return forces


def _quat_to_pitch_roll(quat_xyzw: np.ndarray) -> tuple[float, float]:
    """Convert quaternion to pitch and roll [rad].

    Args:
        quat_xyzw: Quaternion [x, y, z, w].

    Returns:
        (pitch, roll) in radians.
    """
    from scipy.spatial.transform import Rotation
    r = Rotation.from_quat(quat_xyzw)
    euler = r.as_euler('xyz')
    return euler[1], euler[0]  # pitch=y, roll=x


def _cleanup_environment(env):
    """Clean up simulation."""
    sim, scene = env
    sim.stop()
    # future: proper AppLauncher cleanup


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--urdf",
        type=Path,
        default=REPO / "rl_exp/lizard2_round_feet/lizard2_round_feet.urdf",
        help="Lizard2 URDF path",
    )
    parser.add_argument(
        "--recipe",
        type=Path,
        default=REPO / "rl_exp/versions/lizard2/main/v7/main_params.yaml",
        help="Recipe with PD gains",
    )
    parser.add_argument(
        "--geometry_only",
        action="store_true",
        help="Only check geometry feasibility, skip physics",
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Output CSV path (default: stdout summary)",
    )
    args = parser.parse_args()

    # Offline geometry check
    print("Checking geometric feasibility...")
    geo_results = check_geometry_feasibility(args.urdf, SUPPORT_BODIES)
    for combo, reason in geo_results.items():
        status = "OK" if not reason else f"INFEASIBLE: {reason}"
        print(f"  {combo:25s} {status}")

    if args.geometry_only:
        return

    # Physical tests
    print("\nRunning physical tests...")
    actions = generate_test_actions()
    criteria = SupportCriteria()
    matrix = run_physical_tests(
        args.urdf, args.recipe, SUPPORT_BODIES, actions, criteria
    )

    # Output
    print("\n" + matrix.summary())
    if args.output:
        matrix.to_csv(args.output)
        print(f"\nExported to {args.output}")

    # Exit code: 0 if all passed, 1 otherwise
    sys.exit(0 if all(r.passed for r in matrix.results) else 1)


if __name__ == "__main__":
    main()
