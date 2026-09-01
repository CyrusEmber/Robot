"""Convert lizard.urdf (SSOT) into USD for Isaac Lab training.

Reads joint drive gains from lizard_params.yaml so the USD drive matches
the actuator config used in training. Output lands in {rl_exp}/assets/,
matching robot.usd_path in lizard_params.yaml.

Usage (from {rl_exp}/tools/pipeline):
    E:\\IsaacLab\\env_isaaclab\\Scripts\\python.exe convert_urdf.py --headless
"""

import argparse
import pathlib

from isaaclab.app import AppLauncher

parser = argparse.ArgumentParser(description="Convert lizard.urdf (SSOT) into USD.")
AppLauncher.add_app_launcher_args(parser)
args_cli = parser.parse_args()

app_launcher = AppLauncher(args_cli)
simulation_app = app_launcher.app

import yaml

from isaaclab.sim.converters import UrdfConverter, UrdfConverterCfg

# file lives at rl_exp/tools/pipeline/ -> exp root is parents[2]
EXP_DIR = pathlib.Path(__file__).resolve().parents[2]


def main():
    with open(EXP_DIR / "lizard_params.yaml", encoding="utf-8") as f:
        params = yaml.safe_load(f)

    urdf_path = str(EXP_DIR / "lizard.urdf")
    dest_path = str(EXP_DIR / "assets")
    legs_params = params["actuators"]["legs"]

    urdf_converter_cfg = UrdfConverterCfg(
        asset_path=urdf_path,
        usd_dir=dest_path,
        usd_file_name="lizard/lizard.usda",
        fix_base=False,
        # keep {leg}_FOOT as separate bodies: contact rewards need them
        merge_fixed_joints=False,
        force_usd_conversion=True,
        self_collision=True,
        # layered asset puts physics in deferred payloads that Isaac Lab does not
        # load at spawn time (articulation collapses to a single body); use flat USD
        run_asset_transformer=False,
        run_multi_physics_conversion=False,
        joint_drive=UrdfConverterCfg.JointDriveCfg(
            gains=UrdfConverterCfg.JointDriveCfg.PDGainsCfg(
                stiffness=legs_params["stiffness"],
                damping=legs_params["damping"],
            ),
            target_type="position",
        ),
    )

    urdf_converter = UrdfConverter(urdf_converter_cfg)
    print("-" * 80)
    print(f"Generated USD file: {urdf_converter.usd_path}")
    print("-" * 80)

    # importer 3.0 nests links under the base body (IsaacLab issue #5126),
    # which breaks contact-sensor body matching; flatten back to v2.x layout
    from flatten_usd import flatten_usd

    flatten_usd(urdf_converter.usd_path)


if __name__ == "__main__":
    main()
    simulation_app.close()
