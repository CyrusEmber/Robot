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
  fall     = 几何口径（tilt>40° 或 clearance<0.6×初始站高，持续 0.5 s，
             沿用 locomotion_eval_v1，与终止项解耦）

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
_WXYZ = True  # body_quat_w 四元数约定，运行时探针校准


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


def quat_tilt_cos(q: torch.Tensor, wxyz: bool) -> torch.Tensor:
    """body z 轴与世界 z 夹角余弦（旋转矩阵 R22）。"""
    if wxyz:
        return 1.0 - 2.0 * (q[..., 1] ** 2 + q[..., 2] ** 2)
    return 1.0 - 2.0 * (q[..., 0] ** 2 + q[..., 3] ** 2)


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
        "fwd_speed", "tilt_root_deg", "clearance", "x", "tilt_spine_deg",
        "fz_spine", "fz_base", "fz_feet", "feet_down", "reward",
    )}
    for step in range(num_steps):
        cmd_term.vel_command_b[:] = cmd_t

        # pre-step 快照（step 内 reset 掉的 env 读到的是 respawn 值，口径同 eval.py）
        data = robot.data
        contact = ctx["contact"]
        q = data.body_quat_w.torch[:, ctx["body_ids"]["spine"]].clone()
        fz = contact.data.net_forces_w.torch  # (N, num_sensors, 3)
        tilt_spine = torch.acos(quat_tilt_cos(q, _WXYZ).clamp(0.0, 1.0)).rad2deg()
        snap = {
            "fwd_speed": data.root_lin_vel_b.torch[:, 0].clone(),
            "tilt_root_deg": torch.acos((-data.projected_gravity_b.torch[:, 2]).clamp(0.0, 1.0)).rad2deg(),
            "x": data.root_pos_w.torch[:, 0].clone(),
            "tilt_spine_deg": tilt_spine,
            "fz_spine": fz[:, ctx["sensor_ids"]["spine"], 2].clone(),
            "fz_base": fz[:, ctx["sensor_ids"]["base"], 2].clone(),
            "fz_feet": fz[:, ctx["sensor_ids"]["feet"], 2].clone(),
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


def analyze_stand(res: dict, col: int, step_dt: float, stand_height: float) -> dict:
    v = res["valid"][:, col]
    tilt = stack(res["series"], "tilt_root_deg")[:, col][v]
    x = stack(res["series"], "x")[:, col][v]
    fz_b = stack(res["series"], "fz_base")[:, col][v]
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
        "fell": fell,
    }


def analyze_flat(res: dict, col: int, step_dt: float, weight_n: float,
                 term_names: list[str], term_idx: dict) -> dict:
    v = res["valid"][:, col]
    fwd = stack(res["series"], "fwd_speed")[:, col][v]
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
        "tilt_max_deg": round(tilt.max().item(), 1),
        "neck_support_frac": round(neck_mask.float().mean().item(), 4),
        "neck_support_max_s": round(max_sustain_s(neck_mask, step_dt), 2),
        "belly_gt10n_frac": round((fz_b > BELLY_FORCE_N).float().mean().item(), 4),
        "feet_below2_frac": round((feet_down < 2).float().mean().item(), 4),
        "first_event": ("neck_load" if t_neck is not None and (t_lift is None or t_neck <= t_lift)
                        else "feet_lift" if t_lift is not None else "none"),
        "foot_load_frac": [round(x, 3) for x in (feet.mean(dim=0) / weight_n).tolist()],
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
    scalar_keys = ["fwd_speed", "tilt_root_deg", "clearance", "x", "fz_base"]
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
        d["feet_down"] = [int(res["series"]["feet_down"][i][col].item()) for i in idx]
        out["series"][name] = d
    return out


def main():
    global _WXYZ
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
    foot_ids, _ = robot.find_bodies([".*_foot"], preserve_order=True)
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
    _WXYZ = quat_tilt_cos(q0, True).mean().item() >= quat_tilt_cos(q0, False).mean().item()
    stand_height = float(robot.data.root_pos_w.torch[:, 2].mean().item())
    weight_n = float(contact.data.net_forces_w.torch[:, sensor_ids["feet"], 2].sum(dim=1).mean().item())
    term_names = list(mbenv.reward_manager._term_names)
    term_idx = {k: i for i, n in enumerate(term_names)
                for k in LEDGER_KEYS if k in n}
    print(f"[DIAG] quat_wxyz={_WXYZ} stand_height={stand_height:.3f} m weight={weight_n:.0f} N")
    print(f"[DIAG] ledger terms: {[term_names[i] for i in term_idx.values()]}")

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
                rec["stats"][name] = analyze_stand(res, c, ctx["step_dt"], stand_height)
            elif name == "flat":
                rec["stats"][name] = analyze_flat(res, c, ctx["step_dt"], weight_n, term_names, term_idx)
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
        lines += ["## Phase 1 站立闸（flat 列；fell=fell 判据见文件头）", "",
                  "| case | max_tilt_deg | min_clearance | drift_m | max_belly_fz_n | fell |",
                  "|---|---|---|---|---|---|"]
        for r in p1:
            s = r["stats"]["flat"]
            lines.append(f"| {r['case']} | {s['max_tilt_deg']} | {s['min_clearance']} | "
                         f"{s['drift_m']} | {s['max_belly_fz_n']} | {s['fell']} |")
    p2 = [r for r in results if r["case"].startswith("p2")]
    if p2:
        lines += ["", "## Phase 2 平地直行（flat 列；first_event: neck_load=先低头承重 / feet_lift=先失稳）",
                  "", "| case | fwd_mean | tilt_max | neck_frac | neck_max_s | belly_frac | feet<2 | first_event | ledger |",
                  "|---|---|---|---|---|---|---|---|---|"]
        for r in p2:
            s = r["stats"]["flat"]
            lines.append(f"| {r['case']} | {s['fwd_speed_mean']} | {s['tilt_max_deg']} | "
                         f"{s['neck_support_frac']} | {s['neck_support_max_s']} | {s['belly_gt10n_frac']} | "
                         f"{s['feet_below2_frac']} | {s['first_event']} | {json.dumps(s['ledger'])} |")
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
