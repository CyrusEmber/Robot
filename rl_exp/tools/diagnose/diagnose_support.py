# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

"""v10 支撑异常诊断（versions/lizard/v10/DIAGNOSE.md Phase 1-3 的实现器）。

固定 checkpoint、不训练、不改奖励。一次仿真会话跑完全部 case：
  Phase 1a  平地默认关节目标（zero-action）5 s——资产/出生/PD 闸
  Phase 1b  checkpoint 接管、零速度命令 10 s——策略静态稳定闸
  Phase 2   平地直行 0.3/0.5/1.0 m/s × 3 个 reset 抽样，10 s
  Phase 3   单级台阶 5/10/15/20 cm 上/下，0.3 m/s 正对，30 s × 3

地形网格（num_steps=0 技巧，见 mesh_terrains.py 的 num_steps 公式）：
platform_width > size - 2*border 使金字塔台阶退化为恰好一级台阶；出生点 =
格中心台面，沿 +x 走 3.5 m 到台阶沿。所有高度在各自列中同时测试，
"先低后高停止升档" 体现为报告里的通过率边界，不重排网格。

判据（DIAGNOSE.md 预定）：
  头颈承重 = 胸/颈 link 法向力 > 10% 体重，持续 > 0.5 s
  着地     = 四脚法向力 > 1 N（Phase 1 零命令/零动作本该四脚承重：只看 tilt 会漏掉
             "站得住但两脚悬空"——首版诊断就漏了这一条，见 DIAGNOSE.md 结果）
  fall     = 几何口径（tilt>40° 或 clearance<0.6×初始站高，持续 0.5 s，
             沿用 locomotion_eval_v1，与终止项解耦）
  移动     = Phase 2 报 overshoot_frac（fwd/命令−1；跟踪核只罚低速、超速被 clamp 成
             满分，偏差只会朝正方向跑）/ fwd_std（抖动）/ slip_y（yaw 帧横向速度=相对
             机身侧滑）/ yaw_drift,turn_rate（库算 yaw=机身转向）/ drift_x,drift_y,
             v_world（世界系判据）/ foot_duty（逐脚占空比）。
             口径纪律（2026-09-11 校验，见 `--phases 0` 输出）：
             * 四元数布局 **xyzw**（`utils/math.py:453`）：一切旋转走 lib
               （quat_apply / quat_apply_inverse / yaw_quat / euler_xyz_from_quat），
               不手写分量。首版按 wxyz 手写 → yaw 差 177.6°、tilt 漏掉 roll。
             * 体重 = `data.body_mass.sum() * g`（706 N），不是某一时刻的足部接触力之和
               （0.5 s 时读到 856 N，+21% 偏高）。
             * 脚序 `[rr, rl, rf, lf]`，`rl = 左后`、`lf = 左前`（出生步 base 系实测
               +x 头侧、+y 左；命名前对 `<侧><前后>`、后对 `<前后><侧>`）。
             * json 时序按 SUBSAMPLE 下采样；"某脚全程 0 力"必须回到全 50 Hz 口径核对
               （rl 实测：全频率 duty 2%/均值 1.02 N，下采样后成 0/0）。

Usage（repo 根目录）:
    "E:/IsaacLab/env_isaaclab/Scripts/python.exe" rl_exp\\tools\\diagnose\\diagnose_support.py --headless
    ... --phases 2            # 只跑 Phase 2
    ... --video               # 录视频（AppLauncher 视口，侧视需手录）

Output: rl_exp/tools/diagnose/out/<label>/ 下 per-case json + summary.md。
"""

from __future__ import annotations

import argparse
import datetime
import importlib.metadata
import json
import math
import pathlib
import sys

_REPO_ROOT = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO_ROOT / "ablation_harness"))

from isaaclab.app import AppLauncher

parser = argparse.ArgumentParser(description="v10 支撑异常诊断 (fixed ckpt, no training).")
parser.add_argument("--task", type=str, default="Lizard-Rough-v10")
parser.add_argument(
    "--checkpoint", type=str,
    default=r"E:\IsaacLab\logs\rsl_rl\lizard_rough_teacher_v10\2026-09-09_18-15-19\model_14999.pt",
)
parser.add_argument("--phases", type=str, default="1,2,3", help="逗号分隔的 phase 号，如 '1,3'。")
parser.add_argument("--heights", type=str, default="0.05,0.10,0.15,0.20", help="台阶高度 [m]。")
parser.add_argument("--speeds", type=str, default="0.3,0.5,1.0", help="Phase 2 直行速度 [m/s]。")
parser.add_argument("--approach", type=float, default=0.3, help="Phase 3 接近速度 [m/s]。")
parser.add_argument("--reps", type=int, default=3, help="每个 case 的 reset 重抽样次数。")
parser.add_argument("--base_seed", type=int, default=1000)
parser.add_argument("--label", type=str, default=None, help="输出目录名，默认 diag_<task>_<时间戳>。")
AppLauncher.add_app_launcher_args(parser)
args_cli = parser.parse_args()
simulation_app = AppLauncher(args_cli).app

import gymnasium as gym  # noqa: E402
import torch  # noqa: E402

import isaaclab_tasks  # noqa: F401, E402  (gym task registration)
import isaaclab.sim as sim_utils  # noqa: E402
import isaaclab.terrains as terrain_gen  # noqa: E402
from isaaclab.terrains import TerrainGeneratorCfg, TerrainImporterCfg  # noqa: E402
from isaaclab.utils.string import string_to_callable  # noqa: E402
from isaaclab.utils.math import euler_xyz_from_quat, quat_apply, quat_apply_inverse, yaw_quat  # noqa: E402
from isaaclab_rl.rsl_rl import RslRlVecEnvWrapper, handle_deprecated_rsl_rl_cfg  # noqa: E402
from rsl_rl.runners import OnPolicyRunner  # noqa: E402

import metrics  # noqa: E402  (harness 纯函数库)
from components.dr_controller import apply_eval_mode  # noqa: E402

# --- 几何常量（单级台阶网格） ---
# num_steps = (size - 2*border - platform_width) // (2*step_width) + 1（floor 除法）：
# platform_width 必须严格 > terrain_size（= size - 2*border）才得 num_steps=0 单级台阶；
# 恰好相等时 floor 出 0 + 1 = 两级台阶（首版实测踩过此坑，离线 trimesh 校验抓出）。
TILE = 16.0
SUB_BORDER = 4.25                        # terrain_size = 7.5
PLATFORM_W = 7.7                         # > 7.5 -> num_steps=0 -> 恰一级台阶
EDGE_DIST = (TILE - 2 * SUB_BORDER) / 2  # 出生点(格中心)到台阶沿 = 3.75 m
CROSS_MARGIN = 1.0                       # 过沿后再走 1 m 算"通过"

# --- 判据常量（口径见 locomotion_eval_v1.yaml / DIAGNOSE.md） ---
FALL_TILT_DEG = 40.0
FALL_CLEARANCE_RATIO = 0.6
FALL_SUSTAIN_S = 0.5
NECK_LOAD_FRAC = 0.10                    # 头/胸/颈承重 = 法向力 > 10% 体重
BELLY_FORCE_N = 10.0                     # base(腹) 接触阈值 [N]
FOOT_CONTACT_N = 1.0
SUBSAMPLE = 5                            # json 时序按 10 Hz 存（统计用 50 Hz 全量）

SPINE_BODIES = ["chest_yaw", "chest_pitch", "neck_yaw", "neck_pitch"]
LEDGER_KEYS = ("track_lin_vel", "belly", "feet_slide")  # 奖励账本关注项（子串匹配）
GRAVITY = 9.81


def build_terrain(heights: list[float]) -> tuple[TerrainImporterCfg, list[str]]:
    """单级台阶网格：flat + 每 height 的 up(坑底出生爬上)/down(台面出生走下) 两列。"""

    def step_cfg(h: float, invert: bool):
        cls = (
            terrain_gen.MeshInvertedPyramidStairsTerrainCfg if invert
            else terrain_gen.MeshPyramidStairsTerrainCfg
        )
        return cls(
            proportion=1.0,
            step_height_range=(h, h),
            step_width=1.0,
            platform_width=PLATFORM_W,
            border_width=SUB_BORDER,
            holes=False,
        )

    names = ["flat"]
    sub_terrains = {"flat": terrain_gen.MeshPlaneTerrainCfg(proportion=1.0)}
    for h in heights:
        tag = str(int(round(h * 100)))
        names += [f"up_{tag}", f"down_{tag}"]
        sub_terrains[f"up_{tag}"] = step_cfg(h, invert=True)
        sub_terrains[f"down_{tag}"] = step_cfg(h, invert=False)

    generator = TerrainGeneratorCfg(
        size=(TILE, TILE),
        border_width=5.0,
        num_rows=1,
        num_cols=len(sub_terrains),
        curriculum=True,                  # 等比例 -> 列序 = dict 插入序（suites.py 三锁）
        difficulty_range=(1.0, 1.0),
        seed=123,
        use_cache=False,
        sub_terrains=sub_terrains,
    )
    importer = TerrainImporterCfg(
        prim_path="/World/ground",
        terrain_type="generator",
        terrain_generator=generator,
        max_init_terrain_level=0,
        collision_group=-1,
        physics_material=sim_utils.RigidBodyMaterialCfg(
            friction_combine_mode="multiply",
            restitution_combine_mode="multiply",
            static_friction=1.0,
            dynamic_friction=1.0,
        ),
        debug_vis=False,
    )
    return importer, names


def body_tilt_deg(quat: torch.Tensor) -> torch.Tensor:
    """body z 轴与世界 z 的夹角 [deg]（走 lib 的 quat_apply，不手写分量）。

    手写分量必须知道四元数布局；本 IsaacLab 是 **xyzw**（`utils/math.py:453` 等），
    首版按 wxyz 手写 → 该公式对 roll 完全不敏感（纯 roll 时恒等于 0°），
    见 DIAGNOSE.md 实现备注 10。
    """
    z_b = quat_apply(quat, torch.tensor([0.0, 0.0, 1.0], device=quat.device).expand(*quat.shape[:-1], 3))
    return torch.acos(z_b[..., 2].clamp(-1.0, 1.0)).rad2deg()


def max_sustain_s(mask: torch.Tensor, step_dt: float) -> float:
    """(T,) bool 最长连续 True 时长 [s]。"""
    best = cur = 0
    for v in mask.tolist():
        cur = cur + 1 if v else 0
        best = max(best, cur)
    return best * step_dt


def first_cross(mask: torch.Tensor) -> int | None:
    idx = mask.nonzero(as_tuple=False)
    return int(idx[0, 0]) if idx.numel() else None


class Case:
    """一次 rollout：常速命令注入 + 50 Hz 快照（eval.py 的 pre-step 模式）。"""

    def __init__(self, name, seconds, cmd, seed, policy_kind):
        self.name, self.seconds, self.cmd, self.seed = name, seconds, cmd, seed
        self.policy_kind = policy_kind  # "zero" | "policy"


def run_case(case: Case, ctx: dict) -> dict:
    wrapper, mbenv, robot, cmd_term, policy = (
        ctx["wrapper"], ctx["mbenv"], ctx["robot"], ctx["cmd_term"], ctx["policy"])
    device, step_dt = ctx["device"], ctx["step_dt"]

    torch.manual_seed(case.seed)
    obs = wrapper.reset()
    if isinstance(obs, tuple):  # rsl_rl wrapper 的 reset 返回 (obs, extras)
        obs = obs[0]
    num_steps = int(round(case.seconds / step_dt))
    cmd_t = torch.tensor(case.cmd, device=device).expand(mbenv.num_envs, 3)
    first_done = torch.full((mbenv.num_envs,), num_steps, dtype=torch.long, device=device)

    def zero_policy(o):
        return torch.zeros(o.shape[0], mbenv.action_manager.total_action_dim, device=device)

    pol = zero_policy if case.policy_kind == "zero" else policy
    series: dict[str, list] = {k: [] for k in (
        "fwd_speed", "tilt_root_deg", "clearance", "x", "y", "tilt_spine_deg",
        "fz_spine", "fz_base", "fz_feet", "feet_down", "foot_z", "reward",
        "lat_speed", "vel_w_x", "vel_w_y", "vel_yaw_x", "vel_yaw_y", "yaw_deg",
    )}
    for step in range(num_steps):
        cmd_term.vel_command_b[:] = cmd_t

        # pre-step 快照（step 内 reset 掉的 env 读到的是 respawn 值，口径同 eval.py）
        data = robot.data
        contact = ctx["contact"]
        q = data.body_quat_w.torch[:, ctx["body_ids"]["spine"]].clone()
        fz = contact.data.net_forces_w.torch  # (N, num_sensors, 3)
        tilt_spine = body_tilt_deg(q)
        vel_yaw_b = quat_apply_inverse(yaw_quat(data.root_quat_w.torch), data.root_lin_vel_w.torch)
        snap = {
            "fwd_speed": data.root_lin_vel_b.torch[:, 0].clone(),
            # 体坐标横向速度：与 fwd 的比值 = 蟹行角（比值与坐标系约定无关）
            "lat_speed": data.root_lin_vel_b.torch[:, 1].clone(),
            # 世界系速度/位置：横向漂移的独立判据（体坐标约定会骗人，世界位移不会）
            "vel_w_x": data.root_lin_vel_w.torch[:, 0].clone(),
            "vel_w_y": data.root_lin_vel_w.torch[:, 1].clone(),
            # yaw 帧速度（奖励核用的那套，lib 函数）+ 库算 yaw 角：把"机身转向"与
            # "相对机身侧滑"拆开——世界横移两者都含
            "vel_yaw_x": vel_yaw_b[:, 0].clone(),
            "vel_yaw_y": vel_yaw_b[:, 1].clone(),
            "yaw_deg": euler_xyz_from_quat(data.root_quat_w.torch)[2].rad2deg().clone(),
            "tilt_root_deg": torch.acos((-data.projected_gravity_b.torch[:, 2]).clamp(0.0, 1.0)).rad2deg(),
            "x": data.root_pos_w.torch[:, 0].clone(),
            "y": data.root_pos_w.torch[:, 1].clone(),
            "tilt_spine_deg": tilt_spine,
            "fz_spine": fz[:, ctx["sensor_ids"]["spine"], 2].clone(),
            "fz_base": fz[:, ctx["sensor_ids"]["base"], 2].clone(),
            "fz_feet": fz[:, ctx["sensor_ids"]["feet"], 2].clone(),
            # 脚 body 世界 z（几何口径，与接触力互证）：flat 列地面 z=0 -> 即离地高度
            "foot_z": data.body_pos_w.torch[:, ctx["body_ids"]["feet"], 2].clone(),
        }
        snap["feet_down"] = (snap["fz_feet"] > FOOT_CONTACT_N).sum(dim=1)
        if ctx["center_ray"] is not None:
            snap["clearance"] = (
                data.root_pos_w.torch[:, 2]
                - ctx["scanner"].data.ray_hits_w.torch[:, ctx["center_ray"], 2]
            )

        with torch.inference_mode():
            actions = pol(obs)
        obs, _, _, _ = wrapper.step(actions)

        snap["reward"] = mbenv.reward_manager._step_reward.clone()  # step 内刚算的加权项率
        for k in series:
            if k in snap:  # clearance 等可选快照缺传感器时跳过
                series[k].append(snap[k].cpu())

        done_now = mbenv.termination_manager.dones
        newly = done_now & (first_done == num_steps)
        if bool(newly.any()):
            first_done[newly.nonzero(as_tuple=False).squeeze(-1)] = step

    valid = torch.arange(num_steps).unsqueeze(1) <= first_done.cpu().unsqueeze(0)  # (T, N)
    return {"series": series, "first_done": first_done.tolist(), "valid": valid}


def stack(series: dict, key: str) -> torch.Tensor:
    return torch.stack(series[key])


def analyze_stand(res: dict, col: int, step_dt: float, stand_height: float,
                  weight_n: float, foot_names: list[str]) -> dict:
    v = res["valid"][:, col]
    tilt = stack(res["series"], "tilt_root_deg")[:, col][v]
    x = stack(res["series"], "x")[:, col][v]
    fz_b = stack(res["series"], "fz_base")[:, col][v]
    feet = stack(res["series"], "fz_feet")[:, col][v]          # (T, 4) 逐脚法向力
    feet_down = stack(res["series"], "feet_down")[:, col][v]
    foot_z = stack(res["series"], "foot_z")[:, col][v]         # (T, 4) 逐脚世界 z
    bad = tilt > FALL_TILT_DEG
    if res["series"]["clearance"]:
        clr = stack(res["series"], "clearance")[:, col][v]
        bad = bad | (clr < FALL_CLEARANCE_RATIO * stand_height)
        min_clr = round(clr.min().item(), 3)
    else:
        min_clr = None
    fell = bool(metrics.sustained_any(bad.unsqueeze(1), max(1, int(round(FALL_SUSTAIN_S / step_dt)))).any())
    return {
        "max_tilt_deg": round(tilt.max().item(), 1),
        "min_clearance": min_clr,
        "drift_m": round((x[-1] - x[0]).item(), 3) if x.numel() else 0.0,
        "max_belly_fz_n": round(fz_b.max().item(), 1),
        # 着地闸（零命令/零动作本该四脚承重；站立闸只看 tilt 会漏掉两只脚悬空）
        "feet_down_mean": round(feet_down.float().mean().item(), 2),
        "feet_down_min": int(feet_down.min().item()),
        "lift_frac": round((feet_down < 4).float().mean().item(), 3),   # 非四脚着地占比
        "air_frac": round((feet_down == 0).float().mean().item(), 3),   # 全脚离地占比
        "foot_z_min": [round(z, 3) for z in foot_z.min(dim=0).values.tolist()],
        "foot_load_frac": [round(f, 3) for f in (feet.mean(dim=0) / weight_n).tolist()],
        "foot_names": list(foot_names),
        "fell": fell,
    }


def analyze_flat(res: dict, col: int, step_dt: float, weight_n: float,
                 term_names: list[str], term_idx: dict, foot_names: list[str],
                 cmd_speed: float) -> dict:
    v = res["valid"][:, col]
    fwd = stack(res["series"], "fwd_speed")[:, col][v]
    lat = stack(res["series"], "lat_speed")[:, col][v]
    y = stack(res["series"], "y")[:, col][v]
    xw = stack(res["series"], "x")[:, col][v]
    vx = stack(res["series"], "vel_w_x")[:, col][v]
    vy = stack(res["series"], "vel_w_y")[:, col][v]
    vyaw = stack(res["series"], "vel_yaw_y")[:, col][v]
    yaw = stack(res["series"], "yaw_deg")[:, col][v]
    tilt = stack(res["series"], "tilt_root_deg")[:, col][v]
    fz_sp = stack(res["series"], "fz_spine")[:, col][v]     # (T, S)
    fz_b = stack(res["series"], "fz_base")[:, col][v]
    feet = stack(res["series"], "fz_feet")[:, col][v]        # (T, 4)
    feet_down = stack(res["series"], "feet_down")[:, col][v]
    rew = stack(res["series"], "reward")[:, col][v]          # (T, terms)
    neck_mask = fz_sp.max(dim=1).values > NECK_LOAD_FRAC * weight_n
    t_neck, t_lift = first_cross(neck_mask), first_cross(feet_down < 2)
    ledger = {term_idx[k]: round(rew[:, i].mean().item(), 3) for k, i in term_idx.items()}
    return {
        "fwd_speed_mean": round(fwd.mean().item(), 3),
        # 超速偏差：跟踪核只罚低速（超速被 clamp 成满分），所以偏差只会朝正方向跑
        "overshoot_frac": round(fwd.mean().item() / cmd_speed - 1.0, 3) if cmd_speed > 0 else None,
        "fwd_speed_std": round(fwd.std().item(), 3) if fwd.numel() > 1 else 0.0,
        "lat_speed_mean": round(lat.mean().item(), 3),
        "lat_speed_absmax": round(lat.abs().max().item(), 3) if lat.numel() else 0.0,
        # 蟹行角 = 速度方向相对体 x 轴（前进方向）的偏角；>0 说明真正在斜着走
        "crab_deg_mean": round(math.degrees(math.atan2(lat.mean().item(), fwd.mean().item())), 1),
        "v_world_mean": round(math.hypot(vx.mean().item(), vy.mean().item()), 3),
        # 世界位移：横向漂移的最终判据（手写 yaw 已在自检中证伪，见 docstring 移动段）
        "drift_x_m": round((xw[-1] - xw[0]).item(), 2) if xw.numel() else 0.0,
        "drift_y_m": round((y[-1] - y[0]).item(), 2) if y.numel() else 0.0,
        # 蟹行拆分：slip_y = yaw 帧（奖励核同款）横向分量 = 相对机身侧滑；
        # turn_rate = 库算 yaw 的角速度均值 = 机身转向。世界横移 = 两者叠加。
        "slip_y_mean": round(vyaw.mean().item(), 3),
        "yaw_drift_deg": round((yaw[-1] - yaw[0]).item(), 1) if yaw.numel() else 0.0,
        "turn_rate_deg_s": round((yaw[-1] - yaw[0]).item() / max(1e-9, (yaw.numel() - 1) * step_dt), 2)
                           if yaw.numel() > 1 else 0.0,
        "tilt_max_deg": round(tilt.max().item(), 1),
        "neck_support_frac": round(neck_mask.float().mean().item(), 4),
        "neck_support_max_s": round(max_sustain_s(neck_mask, step_dt), 2),
        "belly_gt10n_frac": round((fz_b > BELLY_FORCE_N).float().mean().item(), 4),
        "feet_below2_frac": round((feet_down < 2).float().mean().item(), 4),
        "first_event": ("neck_load" if t_neck is not None and (t_lift is None or t_neck <= t_lift)
                        else "feet_lift" if t_lift is not None else "none"),
        "foot_load_frac": [round(x, 3) for x in (feet.mean(dim=0) / weight_n).tolist()],
        "foot_duty": [round(x, 3) for x in (feet > FOOT_CONTACT_N).float().mean(dim=0).tolist()],
        "foot_names": list(foot_names),
        "ledger": ledger,
    }


def analyze_step(res: dict, col: int, step_dt: float) -> dict:
    v = res["valid"][:, col]
    x = stack(res["series"], "x")[:, col][v]
    fwd = stack(res["series"], "fwd_speed")[:, col][v]
    fz_b = stack(res["series"], "fz_base")[:, col][v]
    fz_sp = stack(res["series"], "fz_spine")[:, col][v]
    progress = x - x[0]
    crossed = bool((progress >= EDGE_DIST + CROSS_MARGIN).any())
    post = progress > EDGE_DIST - 0.3  # 台阶沿前 0.3 m 起算越障窗口
    belly = (fz_b > BELLY_FORCE_N) & post
    spine_post = (fz_sp > FOOT_CONTACT_N) & post.unsqueeze(1)
    return {
        "progress_m": round(progress.max().item(), 2),
        "crossed": crossed,
        "belly_contact_s": round(belly.float().sum().item() * step_dt, 2),
        "fwd_speed_during_belly": round(fwd[belly].mean().item(), 3) if bool(belly.any()) else None,
        "spine_contact_s": round(spine_post.any(dim=1).float().sum().item() * step_dt, 2),
        "spine_bodies_touched": [
            SPINE_BODIES[i] for i in spine_post.any(dim=0).nonzero(as_tuple=False).squeeze(-1).tolist()
        ],
    }


def series_to_json(res: dict, columns: list[str]) -> dict:
    """10 Hz 抽样时序（统计已用 50 Hz 全量算完，json 只留回看用）。"""
    scalar_keys = ["fwd_speed", "tilt_root_deg", "clearance", "x", "y", "fz_base",
                   "lat_speed", "vel_w_x", "vel_w_y", "vel_yaw_y", "yaw_deg"]
    n0 = len(res["series"]["t"]) if "t" in res["series"] else len(res["series"]["fwd_speed"])
    idx = list(range(0, n0, SUBSAMPLE))
    out: dict = {"columns": columns, "series": {}}
    for col, name in enumerate(columns):
        d: dict = {}
        for k in scalar_keys:
            if res["series"].get(k):
                d[k] = [round(res["series"][k][i][col].item(), 3) for i in idx]
        d["tilt_spine_deg"] = [[round(x, 1) for x in res["series"]["tilt_spine_deg"][i][col].tolist()]
                               for i in idx]
        d["fz_spine"] = [[round(x, 1) for x in res["series"]["fz_spine"][i][col].tolist()] for i in idx]
        d["fz_feet"] = [[round(x, 1) for x in res["series"]["fz_feet"][i][col].tolist()] for i in idx]
        d["foot_z"] = [[round(x, 3) for x in res["series"]["foot_z"][i][col].tolist()] for i in idx]
        d["feet_down"] = [int(res["series"]["feet_down"][i][col].item()) for i in idx]
        out["series"][name] = d
    return out


def measure_check(ctx: dict, seconds: float = 4.0) -> dict:
    """Phase 0 测量校验：一次短跑把"量本身对不对"钉死，再谈结论。

    校验项（每项都打印残差/对照，不靠"看起来对"）：
      1. 四元数布局：lib 的 quat_apply/ yaw_quat / euler_xyz_from_quat 与数据是否自洽
         （lib 是 xyzw，手写 wxyz 会错——首版就错在这里）
      2. 体重：真实总质量 × g，并用静立稳态的足部接触力之和交叉校验
      3. 左右/前后命名：脚 body 在 base 系的位置（+x=头侧/前, +y=左）
      4. 接触采样：全 50 Hz 与 json 下采样（每 SUBSAMPLE 帧）两套口径对照——
         "某脚全程 0 力"可能只是降采样假象
      5. 横向漂移分解：yaw 帧侧滑（相对机身）与机身转向分开报

    Returns: dict（同时写入 out_dir 供文档引用）
    """
    wrapper, mbenv, robot, cmd_term = ctx["wrapper"], ctx["mbenv"], ctx["robot"], ctx["cmd_term"]
    contact, foot_ids = ctx["contact"], ctx["body_ids"]["feet"]
    device, step_dt = ctx["device"], ctx["step_dt"]
    foot_names = ctx["foot_names"]
    policy = ctx["policy"]

    obs = wrapper.reset()
    if isinstance(obs, tuple):
        obs = obs[0]
    cmd_term.vel_command_b[:] = torch.zeros(mbenv.num_envs, 3, device=device)

    n = int(round(seconds / step_dt))
    hist = {k: [] for k in ("fz", "pos_b", "vel_b", "vel_w", "q", "grav_b", "vel_yaw")}
    for step in range(n):
        d = robot.data
        q = d.root_quat_w.torch.clone()
        rel_w = d.body_pos_w.torch[:, foot_ids] - d.root_pos_w.torch[:, None]
        q_exp = q[:, None, :].expand(-1, len(foot_ids), -1)
        hist["q"].append(q)
        hist["fz"].append(contact.data.net_forces_w.torch[:, ctx["sensor_ids"]["feet"], 2].clone())
        # 脚位置转到 base 系（首步 = 出生姿态，判前后左右命名）；不转会把四个脚堆在一个象限
        hist["pos_b"].append(quat_apply_inverse(q_exp, rel_w).clone())
        hist["vel_b"].append(d.root_lin_vel_b.torch.clone())
        hist["vel_w"].append(d.root_lin_vel_w.torch.clone())
        hist["vel_yaw"].append(quat_apply_inverse(yaw_quat(q), d.root_lin_vel_w.torch).clone())
        hist["grav_b"].append(d.projected_gravity_b.torch.clone())
        with torch.inference_mode():
            obs, _, _, _ = wrapper.step(policy(obs))

    fz_all = torch.stack(hist["fz"])[:, 0]                    # env 0, (T,4)，全 50 Hz
    q = torch.stack(hist["q"])[:, 0]
    fz_ds = fz_all[::SUBSAMPLE]                               # 下采样口径（= json 里存的）
    pos_b = torch.stack(hist["pos_b"])[0, 0]                  # 出生步的 4 只脚（base 系）
    pos_b_end = torch.stack(hist["pos_b"])[-1, 0]              # 末步（看有没有变姿态）
    vel_yaw = torch.stack(hist["vel_yaw"])[:, 0]

    out: dict = {}
    # 1) 四元数布局：lib 自洽性（两式必须一致，否则布局/调用有错）
    z_w = torch.tensor([0.0, 0.0, 1.0], device=device)
    g_from_q = quat_apply_inverse(q, -z_w.expand(q.shape[0], 3))  # 世界重力方向投到 body 系
    vel_b_all = torch.stack(hist["vel_b"])[:, 0]
    vel_w_all = torch.stack(hist["vel_w"])[:, 0]
    res_grav_v = (g_from_q - torch.stack(hist["grav_b"])[:, 0]).abs().amax(dim=1)
    # 全姿态旋转后必须等于体速度（判据）；yaw-only 帧在机身有俯仰/横滚时**本该**不等
    res_full_v = (quat_apply_inverse(q, vel_w_all) - vel_b_all).abs().amax(dim=1)
    res_yaw_v = (torch.stack(hist["vel_yaw"])[:, 0] - vel_b_all).abs().amax(dim=1)
    stat = lambda t: {  # noqa: E731
        "median": round(t.median().item(), 5), "mean": round(t.mean().item(), 5),
        "max": round(t.max().item(), 5), "max_at_step": int(t.argmax().item()),
    }
    yaw_lib = euler_xyz_from_quat(q)[2].rad2deg()
    # 手写 wxyz 分支（首版用的）作对照——故意留着证明它错在哪
    yaw_hand = torch.atan2(2.0 * (q[:, 0] * q[:, 3] + q[:, 1] * q[:, 2]),
                           1.0 - 2.0 * (q[:, 2] ** 2 + q[:, 3] ** 2)).rad2deg()
    tilt_lib = body_tilt_deg(q)
    tilt_hand = torch.acos((1.0 - 2.0 * (q[:, 1] ** 2 + q[:, 2] ** 2)).clamp(-1, 1)).rad2deg()
    out["quat"] = {
        "residual_projected_gravity": stat(res_grav_v),
        "residual_body_vs_world_vel_full_rot": stat(res_full_v),
        "residual_yawframe_vs_body_vel_expected_nonzero": stat(res_yaw_v),
        "note": "median 才是判据：出生落地冲击会把 max 拉高；yaw 帧残差在机身有俯仰时本就非零",
        "yaw_lib_deg": round(yaw_lib.mean().item(), 2),
        "yaw_hand_wxyz_deg": round(yaw_hand.mean().item(), 2),
        "yaw_hand_minus_lib_deg": round((yaw_hand.mean() - yaw_lib.mean()).item(), 2),
        "tilt_lib_deg": round(tilt_lib.mean().item(), 2),
        "tilt_hand_wxyz_deg": round(tilt_hand.mean().item(), 2),
    }
    # 2) 体重
    mass_kg = float(robot.data.body_mass.torch[0].sum().item())
    weight_n = mass_kg * GRAVITY
    settled = fz_all[int(0.7 * len(fz_all)):].sum(dim=1).mean().item()   # 末尾 30% 视为稳态
    out["weight"] = {
        "mass_kg": round(mass_kg, 3),
        "mass_g_n": round(weight_n, 1),
        "settled_foot_sum_n": round(settled, 1),
        "ratio": round(settled / weight_n, 4),
        "foot_body_mass_kg": [round(m, 2) for m in robot.data.body_mass.torch[0, foot_ids].tolist()],
    }
    # 3) 命名：出生步脚位置（base 系：+x 头侧=前，+y 左）
    out["naming_spawn_base_frame"] = {nm: [round(v, 3) for v in pos_b[i].tolist()]
                                      for i, nm in enumerate(foot_names)}
    out["naming_end_base_frame"] = {nm: [round(v, 3) for v in pos_b_end[i].tolist()]
                                    for i, nm in enumerate(foot_names)}
    # 4) 接触采样口径：全 50 Hz vs 下采样
    out["contact_sampling"] = {
        nm: {
            "duty_full": round((fz_all[:, i] > FOOT_CONTACT_N).float().mean().item(), 4),
            "mean_n_full": round(fz_all[:, i].mean().item(), 2),
            "duty_downsampled": round((fz_ds[:, i] > FOOT_CONTACT_N).float().mean().item(), 4),
            "mean_n_downsampled": round(fz_ds[:, i].mean().item(), 2),
        } for i, nm in enumerate(foot_names)
    }
    # 5) 漂移分解
    out["drift_split"] = {
        "yaw_frame_vy_mean": round(vel_yaw[:, 1].mean().item(), 3),
        "body_vy_mean": round(vel_b_all[:, 1].mean().item(), 3),
        "world_vy_mean": round(vel_w_all[:, 1].mean().item(), 3),
    }
    return out


def main():
    heights = [float(h) for h in args_cli.heights.split(",")]
    phases = set(args_cli.phases.split(","))
    speeds = [float(s) for s in args_cli.speeds.split(",")]

    out_dir = _REPO_ROOT / "rl_exp" / "tools" / "diagnose" / "out" / (
        args_cli.label or f"diag_{args_cli.task}_{datetime.datetime.now():%m%d_%H%M%S}"
    )
    out_dir.mkdir(parents=True, exist_ok=True)

    terrain_cfg, columns = build_terrain(heights)
    spec = gym.spec(args_cli.task)
    env_cfg = string_to_callable(spec.kwargs["env_cfg_entry_point"])()
    env_cfg.scene.terrain = terrain_cfg
    env_cfg.scene.num_envs = len(columns)
    env_cfg.episode_length_s = 30.0
    env_cfg.seed = args_cli.base_seed
    env_cfg.curriculum.terrain_levels = None
    if args_cli.device is not None:
        env_cfg.sim.device = args_cli.device
    apply_eval_mode(env_cfg, "nominal")
    # 诊断专用分歧：出生 yaw 钉死 0（正对 +x 台阶）。基类默认 yaw ±π 随机会让
    # 体坐标命令往任意方向走（首跑实测：down_20 倒走 −6.5 m）。eval 协议保留
    # 随机 yaw 是因其 completion 方向无关；台阶通过率必须正对才可判。
    env_cfg.events.reset_base.params["pose_range"]["yaw"] = (0.0, 0.0)

    gym_env = gym.make(args_cli.task, cfg=env_cfg)
    mbenv = gym_env.unwrapped
    wrapper = RslRlVecEnvWrapper(gym_env)
    robot = mbenv.scene["robot"]
    contact = mbenv.scene.sensors["contact_forces"]
    device = mbenv.device

    spine_ids, _ = robot.find_bodies(SPINE_BODIES, preserve_order=True)
    foot_ids, foot_names = robot.find_bodies([".*_foot"], preserve_order=True)
    sensor_ids = {
        "spine": contact.find_sensors(SPINE_BODIES, preserve_order=True)[0],
        "feet": contact.find_sensors([".*_foot"], preserve_order=True)[0],
        "base": contact.find_sensors(["base_link"], preserve_order=True)[0],
    }
    scanner = mbenv.scene.sensors.get("height_scanner", None)
    center_ray = None
    if scanner is not None:
        n_rays = int(scanner.data.ray_hits_w.torch.shape[1])
        if n_rays % 2 == 0:
            raise ValueError(f"需要奇数射线网格，得到 {n_rays}。")
        center_ray = n_rays // 2

    # 策略：checkpoint（家族 runner cfg，同 eval.py 的加载方式）
    agent_cfg = string_to_callable(spec.kwargs["rsl_rl_cfg_entry_point"])()
    agent_cfg = handle_deprecated_rsl_rl_cfg(agent_cfg, importlib.metadata.version("rsl-rl-lib"))
    agent_cfg.seed = args_cli.base_seed
    runner = OnPolicyRunner(wrapper, agent_cfg.to_dict(), log_dir=None, device=agent_cfg.device)
    runner.load(args_cli.checkpoint)
    policy = runner.get_inference_policy(device=device)

    ctx = {
        "wrapper": wrapper, "mbenv": mbenv, "robot": robot, "cmd_term":
            mbenv.command_manager.get_term("base_velocity"),
        "contact": contact, "scanner": scanner, "center_ray": center_ray,
        "policy": policy, "device": mbenv.device, "step_dt": mbenv.step_dt,
        "body_ids": {"spine": spine_ids, "feet": foot_ids},
        "foot_names": foot_names,
        "sensor_ids": sensor_ids,
    }

    # 四元数约定探针 + 站高 + 体重：零动作走 0.5 s 让接触力稳定（直立，四脚承重和 = 体重）
    obs = wrapper.reset()
    if isinstance(obs, tuple):
        obs = obs[0]
    zero = torch.zeros(mbenv.num_envs, mbenv.action_manager.total_action_dim, device=mbenv.device)
    for _ in range(25):
        obs, _, _, _ = wrapper.step(zero)
    q0 = robot.data.body_quat_w.torch[:, spine_ids]
    stand_height = float(robot.data.root_pos_w.torch[:, 2].mean().item())
    # 体重的唯一可信来源 = 实际总质量 × g；接触力之和只作交叉校验（脚下未必都在承重、
    # 力有高频波动）——首版用"0.5 s 后某一时刻的足部接触力之和"当体重，是错的。
    mass_kg = float(robot.data.body_mass.torch[0].sum().item())
    weight_n = mass_kg * GRAVITY
    foot_sum_n = float(contact.data.net_forces_w.torch[:, sensor_ids["feet"], 2].sum(dim=1).mean().item())
    term_names = list(mbenv.reward_manager._term_names)
    term_idx = {k: i for i, n in enumerate(term_names)
                for k in LEDGER_KEYS if k in n}
    print(f"[DIAG] mass={mass_kg:.2f} kg -> weight={weight_n:.1f} N "
          f"(foot_body_mass_kg={[f'{m:.2f}' for m in robot.data.body_mass.torch[0, foot_ids].tolist()]})")
    print(f"[DIAG] instant foot contact sum={foot_sum_n:.1f} N (ratio {foot_sum_n / weight_n:.3f}) "
          f"stand_height={stand_height:.3f} m — 稳态交叉校验见 --phases 0")
    print(f"[DIAG] ledger terms: {[term_names[i] for i in term_idx.values()]}")

    if "0" in phases:
        mc = measure_check(ctx)
        with open(out_dir / "p0_measure_check.json", "w", encoding="utf-8") as f:
            json.dump(mc, f, indent=1, ensure_ascii=False)
        print(f"[DIAG] measure check -> {out_dir / 'p0_measure_check.json'}")
        if phases == {"0"}:
            gym_env.close()
            return

    cases: list[Case] = []
    if "1" in phases:
        cases.append(Case("p1a_zero_action_5s", 5.0, (0.0, 0.0, 0.0), args_cli.base_seed + 1, "zero"))
        cases.append(Case("p1b_policy_still_10s", 10.0, (0.0, 0.0, 0.0), args_cli.base_seed + 2, "policy"))
    if "2" in phases:
        for rep in range(args_cli.reps):
            for v in speeds:
                cases.append(Case(f"p2_flat_v{v:g}_r{rep}", 10.0, (v, 0.0, 0.0),
                                  args_cli.base_seed + 100 + rep * 10 + int(v * 10), "policy"))
    if "3" in phases:
        for rep in range(args_cli.reps):
            cases.append(Case(f"p3_steps_r{rep}", 30.0, (args_cli.approach, 0.0, 0.0),
                              args_cli.base_seed + 500 + rep, "policy"))

    col_env = {name: i for i, name in enumerate(columns)}
    results: list[dict] = []
    for case in cases:
        print(f"[DIAG] running {case.name} ...", flush=True)
        res = run_case(case, ctx)
        rec = {"case": case.name, "cmd": case.cmd, "seed": case.seed, "stats": {}}
        for name, c in col_env.items():
            if case.name.startswith("p1"):
                rec["stats"][name] = analyze_stand(res, c, ctx["step_dt"], stand_height,
                                                    weight_n, ctx["foot_names"])
            elif name == "flat":
                rec["stats"][name] = analyze_flat(res, c, ctx["step_dt"], weight_n, term_names,
                                                  term_idx, ctx["foot_names"],
                                                  math.hypot(case.cmd[0], case.cmd[1]))
            else:
                rec["stats"][name] = analyze_step(res, c, ctx["step_dt"])
        with open(out_dir / f"{case.name}.json", "w", encoding="utf-8") as f:
            json.dump({**rec, "series_json": series_to_json(res, columns)}, f,
                      indent=1, ensure_ascii=False)
        results.append(rec)
        show = rec["stats"].get("flat") or rec["stats"].get("down_20") or rec["stats"].get("up_20")
        print(f"[DIAG] {case.name}: {json.dumps(show, ensure_ascii=False)}")

    gym_env.close()

    lines = [f"# v10 支撑诊断 summary（{datetime.datetime.now():%F %T}）", ""]
    p1 = [r for r in results if r["case"].startswith("p1")]
    if p1:
        lines += ["## Phase 1 站立闸（flat 列；fell=fell 判据见文件头）",
                  "",
                  "脚列口径：feet_down=法向力>1N 的脚数（稳定段均值/最小值）；lift_frac=非四脚着地"
                  "占比；air_frac=全脚离地占比；foot_z_min=逐脚最低世界 z（flat 地面 z=0，即离地"
                  "最低点）；foot_load_frac=逐脚载荷占体重比（顺序见 foot_names）",
                  "",
                  "| case | max_tilt_deg | min_clearance | drift_m | max_belly_fz_n | feet_down | lift_frac | air_frac | foot_z_min | foot_load_frac | foot_names | fell |",
                  "|---|---|---|---|---|---|---|---|---|---|---|---|"]
        for r in p1:
            s = r["stats"]["flat"]
            lines.append(f"| {r['case']} | {s['max_tilt_deg']} | {s['min_clearance']} | "
                         f"{s['drift_m']} | {s['max_belly_fz_n']} | "
                         f"{s['feet_down_mean']}/{s['feet_down_min']} | {s['lift_frac']} | "
                         f"{s['air_frac']} | {s['foot_z_min']} | {s['foot_load_frac']} | "
                         f"{','.join(s['foot_names'])} | {s['fell']} |")
    p2 = [r for r in results if r["case"].startswith("p2")]
    if p2:
        lines += ["", "## Phase 2 平地直行（flat 列；first_event: neck_load=先低头承重 / feet_lift=先失稳）",
                  "",
                  "移动列口径：overshoot_frac=fwd 均值/命令−1（跟踪核只罚低速，超速被 clamp 成满分）；"
                  "fwd_std=速度抖动；drift_x/drift_y=世界位移、v_world=世界速度均值（横向漂移判据）；"
                  "slip_y=yaw 帧（奖励核同款）横向速度=相对机身侧滑；yaw_drift/turn_rate=库算 yaw 的"
                  "漂移与角速度=机身转向；crab=体坐标 atan2(lat,fwd)（slip 与 turn 的合量）；"
                  "foot_duty/foot_load_frac 顺序见 foot_names",
                  "",
                  "| case | cmd | fwd_mean | overshoot | fwd_std | slip_y | yaw_drift | turn_rate | drift_x | drift_y | crab | v_world | tilt_max | feet<2 | foot_duty | foot_load_frac | neck_frac | belly_frac | ledger |",
                  "|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|"]
        for r in p2:
            s = r["stats"]["flat"]
            lines.append(f"| {r['case']} | {math.hypot(r['cmd'][0], r['cmd'][1]):g} | "
                         f"{s['fwd_speed_mean']} | {s['overshoot_frac']} | {s['fwd_speed_std']} | "
                         f"{s['slip_y_mean']} | {s['yaw_drift_deg']}° | {s['turn_rate_deg_s']} | "
                         f"{s['drift_x_m']} | {s['drift_y_m']} | {s['crab_deg_mean']}° | "
                         f"{s['v_world_mean']} | {s['tilt_max_deg']} | {s['feet_below2_frac']} | "
                         f"{s['foot_duty']} | {s['foot_load_frac']} | {s['neck_support_frac']} | "
                         f"{s['belly_gt10n_frac']} | {json.dumps(s['ledger'])} |")
    p3 = [r for r in results if r["case"].startswith("p3")]
    if p3:
        lines += ["", "## Phase 3 单级台阶（0.3 m/s 正对；crossed=过沿后再走 ≥1 m）", "",
                  "| height | dir | progress_m | crossed | belly_s | fwd_during_belly | spine_touched |",
                  "|---|---|---|---|---|---|---|"]
        for h in heights:
            tag = str(int(round(h * 100)))
            for d in ("up", "down"):
                name = f"{d}_{tag}"
                progs, cross_n, bel, fw, sp = [], 0, [], [], set()
                for r in p3:
                    s = r["stats"][name]
                    progs.append(f"{s['progress_m']:g}")
                    cross_n += int(s["crossed"])
                    bel.append(f"{s['belly_contact_s']:g}")
                    if s["fwd_speed_during_belly"] is not None:
                        fw.append(f"{s['fwd_speed_during_belly']:g}")
                    sp.update(s["spine_bodies_touched"])
                lines.append(f"| {h * 100:.0f}cm | {d} | {'/'.join(progs)} | {cross_n}/{len(p3)} | "
                             f"{'/'.join(bel)} | {','.join(fw) or '-'} | {','.join(sorted(sp)) or '-'} |")
        lines += ["", "（通过率边界 = 最高的 crossed ≥ 2/3 的档位；更高档视为几何上限，"
                  "补动量档跑 --speeds 覆盖或 --approach 调速后对照）"]

    summary = "\n".join(lines) + "\n"
    with open(out_dir / "summary.md", "w", encoding="utf-8") as f:
        f.write(summary)
    print(summary)
    print(f"[DIAG] output -> {out_dir}")


if __name__ == "__main__":
    main()
    simulation_app.close()
