# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause
"""Convert an isolated two-axis candidate URDF into USD, without adopting it."""
import argparse
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[3]
parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--candidate', type=Path, required=True)
from isaaclab.app import AppLauncher
AppLauncher.add_app_launcher_args(parser)
args = parser.parse_args()
source = args.candidate.resolve()
if not source.is_relative_to((ROOT / 'rl_exp/out').resolve()) or not source.is_file():
    parser.error('candidate must be an existing URDF below rl_exp/out')
target = source.with_suffix('.usda')
if target.exists() or (source.parent / source.stem).exists():
    parser.error('refusing to overwrite existing USD')
app = AppLauncher(args).app
try:
    from isaaclab.sim.converters import UrdfConverter, UrdfConverterCfg
    sys.path.insert(0, str(ROOT / 'rl_exp/tools/pipeline'))
    from flatten_usd import flatten_usd
    converter = UrdfConverter(UrdfConverterCfg(
        asset_path=str(source), usd_dir=str(source.parent), usd_file_name=target.name,
        fix_base=False, merge_fixed_joints=False, force_usd_conversion=True, self_collision=True,
        run_asset_transformer=False, run_multi_physics_conversion=False,
        joint_drive=UrdfConverterCfg.JointDriveCfg(target_type='position',
            gains=UrdfConverterCfg.JointDriveCfg.PDGainsCfg(stiffness=0., damping=0.))))
    flatten_usd(converter.usd_path)
    print('CANDIDATE_USD', converter.usd_path, flush=True)
    app.close(exit_code=0)
except BaseException:
    import traceback
    traceback.print_exc()
    app.close(exit_code=1)
    raise
