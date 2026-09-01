# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

"""Offline unit test for the student belief stack (no sim, plain torch).

Checks: GRU step shapes, alpha range, b_t dim and gated-slot layout, action
shape, BeliefDecoder output dim (208 + 24), load_from_teacher weight/stat
equality and the segment-order identity assertions firing on mismatch.
"""

import torch
from tensordict import TensorDict

from rl_exp.tasks.student_networks import StudentPolicy
from rl_exp.tasks.teacher_networks import SplitEncoderModel

N = 8
DIM = {"proprio": 90, "extero": 208, "priv": 83}
ACTION_DIM = 26
GROUPS = {"actor": ["proprio", "extero", "priv"], "critic": ["proprio", "extero", "priv"]}


def _mock_obs() -> TensorDict:
    return TensorDict({k: torch.randn(N, v) for k, v in DIM.items()}, batch_size=[N])


def test_gru_step_shapes() -> None:
    student = StudentPolicy()
    h = student.belief.init_hidden(N)
    assert h.shape == (2, N, 50), f"hidden shape {h.shape}"
    x = torch.randn(N, 90 + 96)
    b_prime, h_new = student.belief(x, h)
    assert b_prime.shape == (N, 100), f"b_prime shape {b_prime.shape}"
    assert h_new.shape == (2, N, 50), f"new hidden shape {h_new.shape}"
    assert torch.isfinite(b_prime).all()


def test_forward_shapes_and_gate_range() -> None:
    student = StudentPolicy()
    student.eval()
    h = student.belief.init_hidden(N)
    proprio = torch.randn(N, 90)
    extero = torch.randn(N, 208)
    actions, h_new, internals = student(proprio, extero, h)
    assert actions.shape == (N, ACTION_DIM), f"action shape {actions.shape}"
    assert torch.isfinite(actions).all()
    assert internals["alpha"].shape == (N, 96)
    assert (internals["alpha"] >= 0.0).all() and (internals["alpha"] <= 1.0).all(), "alpha out of [0,1]"
    assert internals["b_t"].shape == (N, 120), f"b_t shape {internals['b_t'].shape}"
    assert internals["l_e"].shape == (N, 96)
    # gated slot: changing l_e must change b_t's first 96 slots (g_b output is
    # l_prime-dependent only, so the delta b_t[0:96] - g_b(b') must track l_e * alpha)
    b_t = internals["b_t"]
    g_b_out = student.g_b(internals["b_prime"])
    assert torch.allclose(
        b_t[..., :96], g_b_out[..., :96] + internals["l_e"] * internals["alpha"], atol=1e-6
    ), "gated slot misaligned"


def test_decoder_output_dim() -> None:
    student = StudentPolicy()
    out = student.decoder(torch.randn(N, 120))
    assert out.shape == (N, 208 + 24), f"decoder output {out.shape}"


def test_load_from_teacher_equality() -> None:
    obs = _mock_obs()
    teacher = SplitEncoderModel(
        obs, GROUPS, "actor", ACTION_DIM,
        obs_normalization=True,
        distribution_cfg={"class_name": "GaussianDistribution", "init_std": 1.0},
    )
    student = StudentPolicy()
    student.load_from_teacher(teacher)
    for (k_t, v_t), (k_s, v_s) in zip(teacher.g_e.state_dict().items(), student.g_e.state_dict().items()):
        assert k_t == k_s
        assert torch.equal(v_t, v_s), f"g_e weight {k_t} not transferred"
    for (k_t, v_t), (k_s, v_s) in zip(teacher.mlp.state_dict().items(), student.f_pi.state_dict().items()):
        assert k_t == k_s
        assert torch.equal(v_t, v_s), f"f_pi weight {k_t} not transferred"
    # o_p normalization stats transferred
    for key in ("_mean", "_var", "_std", "count"):
        assert torch.equal(teacher.obs_normalizers["proprio"].state_dict()[key],
                           student.proprio_norm.state_dict()[key]), f"norm stat {key} not transferred"
    # extero normalizer is the student's own (identity-initialized), not the teacher's
    assert student.extero_norm.count == 0
    assert teacher.obs_normalizers["extero"].count == 0


def test_segment_mismatch_raises() -> None:
    obs = _mock_obs()
    teacher = SplitEncoderModel(
        obs, GROUPS, "actor", ACTION_DIM,
        obs_normalization=True,
        distribution_cfg={"class_name": "GaussianDistribution", "init_std": 1.0},
    )
    # student with a different trunk input layout (points/foot shrunk -> latent mismatch)
    student = StudentPolicy(proprio_dim=91)
    try:
        student.load_from_teacher(teacher)
        raise AssertionError("segment mismatch should raise")
    except ValueError:
        pass


def main() -> int:
    tests = [
        test_gru_step_shapes,
        test_forward_shapes_and_gate_range,
        test_decoder_output_dim,
        test_load_from_teacher_equality,
        test_segment_mismatch_raises,
    ]
    for t in tests:
        t()
        print(f"  ok {t.__name__}")
    print("ALL_STUDENT_NETWORK_TESTS_PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
