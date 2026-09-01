# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

"""Offline unit test for SplitEncoderModel (no sim, plain torch + rsl_rl).

Checks: construction from a mock obs TensorDict, forward shapes for actor
(stochastic/deterministic) and critic, gradient flow through all three
streams, per-group normalization updates, named-submodule weight extraction,
and the JIT/ONNX export wrappers.
"""

import torch
from tensordict import TensorDict

from rl_exp.tasks.teacher_networks import SplitEncoderModel

N = 8
DIM = {"proprio": 90, "extero": 208, "priv": 83}
ACTION_DIM = 26


def _mock_obs() -> TensorDict:
    return TensorDict(
        {k: torch.randn(N, v) for k, v in DIM.items()},
        batch_size=[N],
    )


def _mock_groups() -> dict[str, list[str]]:
    groups = ["proprio", "extero", "priv"]
    return {"actor": groups, "critic": groups}


def test_actor_forward_and_gradient() -> None:
    obs = _mock_obs()
    actor = SplitEncoderModel(
        obs, _mock_groups(), "actor", ACTION_DIM,
        obs_normalization=True,
        distribution_cfg={"class_name": "GaussianDistribution", "init_std": 1.0},
    )
    actions = actor(obs, stochastic_output=True)
    assert actions.shape == (N, ACTION_DIM), f"actor action shape {actions.shape}"
    assert torch.isfinite(actions).all()
    det = actor(obs)
    assert det.shape == (N, ACTION_DIM), f"actor deterministic shape {det.shape}"
    assert torch.isfinite(actor.output_entropy).all()
    assert len(actor.output_distribution_params) > 0
    kl = actor.get_kl_divergence(actor.output_distribution_params, actor.output_distribution_params)
    assert torch.allclose(kl, torch.zeros_like(kl), atol=1e-6)
    latent = actor.get_latent(obs)
    assert latent.shape == (N, 210), f"latent shape {latent.shape}"
    # distribution surface used by PPO
    # gradient flow: log_prob covers the mean path (all encoders) and std
    log_prob = actor.get_output_log_prob(actions)
    assert log_prob.shape == (N,), f"log_prob shape {log_prob.shape}"
    log_prob.sum().backward()
    for name, param in actor.named_parameters():
        assert param.grad is not None, f"no gradient for {name}"
        assert torch.isfinite(param.grad).all(), f"non-finite gradient for {name}"


def test_critic_forward() -> None:
    obs = _mock_obs()
    critic = SplitEncoderModel(obs, _mock_groups(), "critic", 1, obs_normalization=True)
    values = critic(obs)
    assert values.shape == (N, 1), f"critic value shape {values.shape}"
    assert torch.isfinite(values).all()


def test_normalization_updates_per_group() -> None:
    obs = _mock_obs()
    actor = SplitEncoderModel(
        obs, _mock_groups(), "actor", ACTION_DIM,
        obs_normalization=True,
        distribution_cfg={"class_name": "GaussianDistribution", "init_std": 1.0},
    )
    before = {k: v.count.clone() for k, v in actor.obs_normalizers.items()}
    shifted = TensorDict(
        {
            "proprio": obs["proprio"] + 10.0,
            "extero": obs["extero"] - 10.0,
            "priv": obs["priv"] + 5.0,
        },
        batch_size=[N],
    )
    actor.train()
    actor.update_normalization(shifted)
    for k in DIM:
        assert actor.obs_normalizers[k].count > before[k], f"group {k} not updated"
        assert not torch.allclose(
            actor.obs_normalizers[k].mean, torch.zeros(DIM[k]), atol=1e-4
        ), f"group {k} mean did not move"


def test_named_submodule_extraction() -> None:
    """g_e / g_p / f_pi (mlp) / normalizers are addressable for ckpt surgery."""
    obs = _mock_obs()
    actor = SplitEncoderModel(
        obs, _mock_groups(), "actor", ACTION_DIM,
        obs_normalization=True,
        distribution_cfg={"class_name": "GaussianDistribution", "init_std": 1.0},
    )
    assert isinstance(actor.g_e, torch.nn.Module)
    assert isinstance(actor.g_p, torch.nn.Module)
    assert isinstance(actor.mlp, torch.nn.Module)
    g_e_out = actor.g_e(torch.randn(N, 52))
    assert g_e_out.shape == (N, 24), f"g_e per-foot output {g_e_out.shape}"
    g_p_out = actor.g_p(torch.randn(N, DIM["priv"]))
    assert g_p_out.shape == (N, 24), f"g_p output {g_p_out.shape}"
    # state_dict round-trips the named submodules
    sd = actor.state_dict()
    for prefix in ("g_e.", "g_p.", "mlp.", "obs_normalizers."):
        assert any(k.startswith(prefix) for k in sd), f"no keys under '{prefix}'"


def test_export_wrappers() -> None:
    obs = _mock_obs()
    actor = SplitEncoderModel(
        obs, _mock_groups(), "actor", ACTION_DIM,
        obs_normalization=True,
        distribution_cfg={"class_name": "GaussianDistribution", "init_std": 1.0},
    )
    actor.eval()
    jit_model = actor.as_jit()
    flat = torch.cat([obs[k] for k in ("proprio", "extero", "priv")], dim=-1)
    out = jit_model(flat)
    assert out.shape == (N, ACTION_DIM), f"jit export output {out.shape}"
    expected = actor.distribution.deterministic_output(actor.mlp(actor.get_latent(obs)))
    assert torch.allclose(out, expected, atol=1e-5), "jit export diverges from model"
    onnx_model = actor.as_onnx(verbose=False)
    assert onnx_model(flat).shape == (N, ACTION_DIM)


def test_contract_enforcement() -> None:
    obs = _mock_obs()
    bad_groups = {"actor": ["proprio", "extero"], "critic": ["proprio", "extero"]}
    try:
        SplitEncoderModel(obs, bad_groups, "actor", ACTION_DIM)
        raise AssertionError("missing obs group should raise")
    except ValueError:
        pass
    bad_extero = TensorDict(
        {"proprio": torch.randn(N, 90), "extero": torch.randn(N, 207), "priv": torch.randn(N, 83)},
        batch_size=[N],
    )
    try:
        SplitEncoderModel(bad_extero, _mock_groups(), "actor", ACTION_DIM)
        raise AssertionError("non-divisible extero dim should raise")
    except ValueError:
        pass


def main() -> int:
    tests = [
        test_actor_forward_and_gradient,
        test_critic_forward,
        test_normalization_updates_per_group,
        test_named_submodule_extraction,
        test_export_wrappers,
        test_contract_enforcement,
    ]
    for t in tests:
        t()
        print(f"  ok {t.__name__}")
    print("ALL_TEACHER_NETWORK_TESTS_PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
