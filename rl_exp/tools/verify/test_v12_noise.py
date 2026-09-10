# -*- coding: utf-8 -*-
"""v12 height-ring noise model offline test (no sim, torch-only mock env).

Covers the noise half of plan versions/lizard/v12/PLAN.md: condition ratios,
per-foot bias gating (offset), per-step noise + outliers (noisy), clean
pass-through (nominal + missing event), mid-episode redraw re-arm, and c_k
amplitude scaling.
"""

import sys

import torch

sys.path.insert(0, ".")

from rl_exp.tasks import teacher_mdp  # noqa: E402

_N = 4096
_PTS = 8
_BASE = torch.linspace(-0.5, 0.5, _N * _PTS).reshape(_N, _PTS)


class _FakeEnv:
    """Minimal env duck-type for the v12 noise terms."""

    def __init__(self, ck=1.0):
        self.num_envs = _N
        self.device = "cpu"
        self.common_step_counter = 0
        self.max_episode_length = 1000
        self.episode_length_buf = torch.zeros(_N, dtype=torch.long)
        # ck = c0 ** (decay ** iteration); decay 0 keeps iteration-0 value
        self._lizard_ck_params = None if ck == 1.0 else {
            "c0": ck, "decay": 0.0, "steps_per_iteration": 10**9
        }


def _call(term, env, **kw):
    args = dict(
        foot_index=0, sigma_w=0.15, sigma_f=0.05, sigma_p=0.02,
        outlier_prob=0.0, outlier_range=(-1.0, 1.0),
    )
    args.update(kw)
    return term.__call__(env, None, 0.0, **args)


def _state(env):
    return getattr(env, teacher_mdp.RING_NOISE_STATE)


def main() -> int:
    problems = []
    term = teacher_mdp.NoisyFootRing.__new__(teacher_mdp.NoisyFootRing)
    orig_scan = teacher_mdp.mdp.height_scan
    teacher_mdp.mdp.height_scan = lambda env, sensor_cfg, offset=0.0: _BASE
    try:
        # 1) missing event state (PLAY / nominal eval) -> clean pass-through
        env = _FakeEnv()
        if not torch.equal(_call(term, env), _BASE):
            problems.append("missing state must return the clean scan")

        # 2) nominal condition -> clean
        env = _FakeEnv()
        teacher_mdp.sample_ring_noise(env, torch.arange(_N), (0.6, 0.3, 0.1))
        _state(env)["cond"][:] = 0
        if not torch.equal(_call(term, env), _BASE):
            problems.append("nominal condition must stay clean")

        # 3) offset condition: constant, persistent, foot-column-gated bias
        env = _FakeEnv()
        teacher_mdp.sample_ring_noise(env, torch.arange(_N), (0.6, 0.3, 0.1))
        st = _state(env)
        st["cond"][:] = 1
        st["w"][:] = torch.tensor([1.0, 2.0, 3.0, 4.0])
        a = _call(term, env, foot_index=1, sigma_w=0.25)
        b = _call(term, env, foot_index=1, sigma_w=0.25)
        if not torch.equal(a, _BASE + 0.5) or not torch.equal(a, b):
            problems.append("offset condition must add a constant, persistent bias")
        if not torch.equal(_call(term, env, foot_index=2, sigma_w=0.25), _BASE + 0.75):
            problems.append("foot_index must select its own foot bias column")

        # 4) noisy condition: std grows with sigma_p and scales with c_k
        stats = {}
        for ck, sigma_p in ((1.0, 0.02), (1.0, 0.08), (0.5, 0.08)):
            env = _FakeEnv(ck=ck)
            teacher_mdp.sample_ring_noise(env, torch.arange(_N), (0.6, 0.3, 0.1))
            st = _state(env)
            st["cond"][:] = 2
            st["w"][:] = 0.0
            out = _call(term, env, sigma_w=0.0, sigma_f=0.0, sigma_p=sigma_p)
            stats[(ck, sigma_p)] = (out - _BASE).std().item()
        if not stats[(1.0, 0.08)] > stats[(1.0, 0.02)]:
            problems.append("noise std must grow with sigma_p")
        if not stats[(1.0, 0.08)] > stats[(0.5, 0.08)]:
            problems.append("noise std must scale with c_k")
        if abs(stats[(1.0, 0.08)] / 0.08 - 1.0) > 0.05:
            problems.append(f"noise std {stats[(1.0, 0.08)]:.4f} != sigma_p 0.08")

        # 5) outliers: prob 1 replaces every sample inside the range
        env = _FakeEnv()
        teacher_mdp.sample_ring_noise(env, torch.arange(_N), (0.6, 0.3, 0.1))
        st = _state(env)
        st["cond"][:] = 2
        st["w"][:] = 0.0
        out = _call(term, env, sigma_w=0.0, sigma_f=0.0, sigma_p=0.0,
                    outlier_prob=1.0, outlier_range=(-1.0, 1.0))
        if torch.equal(out, _BASE) or out.max() > 1.0 or out.min() < -1.0:
            problems.append("outlier_prob 1 must replace every sample within the range")

        # 6) midway redraw: bias persists before half-episode; the crossing
        # fires once; afterwards the state governs (no stale pre-crossing bias)
        env = _FakeEnv()
        teacher_mdp.sample_ring_noise(env, torch.arange(_N), (0.6, 0.3, 0.1))
        st = _state(env)
        st["cond"][:] = 1
        st["w"][:] = 1.0
        env.episode_length_buf[:] = 499
        if not torch.equal(_call(term, env), _BASE + 0.15):
            problems.append("before half-episode the bias must persist")
        env.episode_length_buf[:] = 500
        _call(term, env)  # crossing: redraws cond/w for every env
        if not bool(st["mid_fired"].all()):
            problems.append("crossing half the episode must set mid_fired")
        st["cond"][:] = 1
        st["w"][:] = 2.0
        env.episode_length_buf[:] = 501
        if not torch.equal(_call(term, env), _BASE + 0.30):
            problems.append("post-crossing call must use the state (no second redraw)")

        # 7) condition ratios: 60/30/10 over a big sample
        torch.manual_seed(7)
        env = _FakeEnv()
        teacher_mdp.sample_ring_noise(env, torch.arange(_N), (0.6, 0.3, 0.1))
        st = _state(env)
        for k, want in ((0, 0.6), (1, 0.3), (2, 0.1)):
            got = (st["cond"] == k).float().mean().item()
            if abs(got - want) > 0.02:
                problems.append(f"condition {k} share {got:.3f} != {want}")

        # 8) reset re-arms the mid flag for the resetting envs only
        env.episode_length_buf[:] = 600
        _call(term, env)  # cross half for everyone -> mid_fired all True
        if not bool(_state(env)["mid_fired"].all()):
            problems.append("setup: crossing must arm every env's midway flag")
        teacher_mdp.sample_ring_noise(env, torch.tensor([0, 1, 2]), (0.6, 0.3, 0.1))
        if bool(_state(env)["mid_fired"][:3].any()):
            problems.append("reset must re-arm the midway redraw flag")
        if not bool(_state(env)["mid_fired"][3:].all()):
            problems.append("reset must leave other envs' midway flag alone")
    finally:
        teacher_mdp.mdp.height_scan = orig_scan

    for p in problems:
        print(f"  DRIFT: {p}")
    if problems:
        print(f"V12_NOISE_DRIFT ({len(problems)})")
        return 1
    print("V12_NOISE_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
