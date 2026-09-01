# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

"""Student network modules for Phase 2 distillation (interface lock, no runner wiring).

Implements the Miki et al. 2022 student belief stack against the SAME frozen
f_pi input segmentation as the teacher (teacher_networks.py):

    b'_t, h  = GRU([o_p | l_e], h)        # 2 layers x 50, b' = 100
    alpha_t  = sigmoid(g_a(b'_t))         # {64,64} -> 96
    b_t      = g_b(b'_t) + l_e * alpha_t  # {64,64} -> 120; l_e lives in the
                                           # FIRST 96 slots (teacher l_e slot),
                                           # last 24 = teacher l_priv slot
    a_t      = f_pi([o_p | b_t])          # 90 + 120 = 210 == teacher latent

The f_pi input segment order is FROZEN: [proprio 90 | l_e 96 | priv-slot 24].
The student's b_t reproduces the teacher segmentation exactly, so
``load_from_teacher`` transfers f_pi/g_e weights with zero changes
(same dims in a different order would be a silent mismatch).

This module only delivers the networks and the weight-transfer interface;
the distillation runner (BC + L_re, noise model z^{8x4}, teacher rollouts) is
a Phase 2 deliverment and is not wired here.
"""

from __future__ import annotations

import torch
import torch.nn as nn
from tensordict import TensorDict

from rsl_rl.modules import EmpiricalNormalization
from rsl_rl.modules.mlp import MLP

from rl_exp.tasks.teacher_networks import SplitEncoderModel


class BeliefEncoder(nn.Module):
    """GRU belief encoder: 2 layers x 50 over [o_p | l_e], outputs b' (100) + h.

    b' is the concatenation of BOTH layer hiddens (100 = 2 x 50), per paper.
    """

    def __init__(self, input_dim: int, hidden_dim: int = 50, num_layers: int = 2) -> None:
        """Initialize the GRU.

        Args:
            input_dim: Per-step input dimension (proprio + extero latent).
            hidden_dim: Hidden dimension per GRU layer (paper: 50).
            num_layers: Number of stacked GRU layers (paper: 2).
        """
        super().__init__()
        self.hidden_dim = hidden_dim
        self.num_layers = num_layers
        self.gru = nn.GRU(input_dim, hidden_dim, num_layers=num_layers)

    def forward(self, x: torch.Tensor, hidden_state: torch.Tensor) -> tuple[torch.Tensor, torch.Tensor]:
        """Step the belief GRU.

        Args:
            x: Per-step input [N, input_dim] (normalized [o_p | l_e]).
            hidden_state: GRU hidden state [num_layers, N, hidden_dim].

        Returns:
            Tuple of b' [N, num_layers * hidden_dim] and the new hidden state.
        """
        _, h_n = self.gru(x.unsqueeze(0), hidden_state)
        b_prime = h_n.transpose(0, 1).reshape(x.shape[0], -1)
        return b_prime, h_n

    def init_hidden(self, num_envs: int, device: torch.device | str = "cpu") -> torch.Tensor:
        """Return a zero-initialized hidden state [num_layers, N, hidden_dim]."""
        return torch.zeros(self.num_layers, num_envs, self.hidden_dim, device=device)


class AttentionGate(nn.Module):
    """g_a: b' -> per-dimension attention alpha in (0, 1) over the l_e slots."""

    def __init__(self, input_dim: int, output_dim: int, hidden_dims: tuple[int, ...] | list[int] = (64, 64)) -> None:
        """Initialize the gate MLP (paper: {64, 64}).

        Args:
            input_dim: Dimension of b'.
            output_dim: Number of gated slots (extero latent total, 96).
            hidden_dims: Hidden dimensions.
        """
        super().__init__()
        self.net = MLP(input_dim, output_dim, list(hidden_dims), "lrelu")

    def forward(self, b_prime: torch.Tensor) -> torch.Tensor:
        """Return alpha [N, output_dim] in (0, 1)."""
        return torch.sigmoid(self.net(b_prime))


class BeliefMapper(nn.Module):
    """g_b: b' -> b_t base (120 = teacher's [l_e 96 | priv-slot 24] layout)."""

    def __init__(self, input_dim: int, output_dim: int, hidden_dims: tuple[int, ...] | list[int] = (64, 64)) -> None:
        """Initialize the mapper MLP (paper: {64, 64}).

        Args:
            input_dim: Dimension of b'.
            output_dim: Dimension of b_t (extero latent total + priv latent, 120).
            hidden_dims: Hidden dimensions.
        """
        super().__init__()
        self.net = MLP(input_dim, output_dim, list(hidden_dims), "lrelu")

    def forward(self, b_prime: torch.Tensor) -> torch.Tensor:
        """Return the base belief [N, output_dim]."""
        return self.net(b_prime)


class BeliefDecoder(nn.Module):
    """Training-only decoder: b_t -> [clean scan 208 | l_priv 24] for L_re.

    Hidden dims are not paper-pinned (the paper reconstructs the raw privileged
    state s_p; we reconstruct clean rings + l_priv instead -- deliberate
    deviation, F3) -- treat as a Phase 2 ablation knob.
    """

    def __init__(self, input_dim: int, output_dim: int, hidden_dims: tuple[int, ...] | list[int] = (128, 128)) -> None:
        """Initialize the decoder MLP.

        Args:
            input_dim: Dimension of b_t (120).
            output_dim: Reconstruction target dim (clean scan + l_priv, 232).
            hidden_dims: Hidden dimensions (ablation knob, not paper-pinned).
        """
        super().__init__()
        self.net = MLP(input_dim, output_dim, list(hidden_dims), "lrelu")

    def forward(self, b_t: torch.Tensor) -> torch.Tensor:
        """Return the reconstruction [N, output_dim]."""
        return self.net(b_t)


class StudentPolicy(nn.Module):
    """Student policy: belief stack + inherited teacher f_pi / g_e.

    Forward consumes raw streams (the student never sees ``priv``); the
    proprio normalizer is SEEDED from the teacher's statistics by
    :meth:`load_from_teacher` (kept as an updating module; freezing it is a
    Phase 2 decision), while the extero normalizer is the student's own (it
    sees noisy rings, teacher saw clean ones).
    """

    def __init__(
        self,
        proprio_dim: int = 90,
        extero_dim: int = 208,
        action_dim: int = 26,
        num_feet: int = 4,
        extero_encoder_dims: tuple[int, ...] | list[int] = (80, 60),
        extero_latent_per_foot: int = 24,
        trunk_dims: tuple[int, ...] | list[int] = (256, 160, 128),
    ) -> None:
        """Initialize the student policy with teacher-matching architecture.

        Args:
            proprio_dim: Proprio obs dimension (teacher: 90).
            extero_dim: Extero obs dimension (4 feet x points per foot).
            action_dim: Action dimension (teacher: 26).
            num_feet: Number of feet in the extero group.
            extero_encoder_dims: g_e hidden dims (must match teacher for transfer).
            extero_latent_per_foot: l_e dimension per foot (teacher: 24).
            trunk_dims: f_pi hidden dims (must match teacher for transfer).
        """
        super().__init__()
        self.proprio_dim = proprio_dim
        self.extero_dim = extero_dim
        self.action_dim = action_dim
        self.num_feet = num_feet
        if extero_dim % num_feet != 0:
            raise ValueError(f"extero dim {extero_dim} not divisible by num_feet {num_feet}.")
        self.points_per_foot = extero_dim // num_feet
        self.extero_latent_dim = num_feet * extero_latent_per_foot
        # teacher l_priv slot size (24); b_t's last slots reconstruct it
        self.priv_slot_dim = 24

        self.proprio_norm = EmpiricalNormalization(proprio_dim)
        self.extero_norm = EmpiricalNormalization(extero_dim)

        self.g_e = MLP(self.points_per_foot, extero_latent_per_foot, list(extero_encoder_dims), "lrelu")
        self.belief = BeliefEncoder(proprio_dim + self.extero_latent_dim)
        self.g_a = AttentionGate(100, self.extero_latent_dim)
        self.g_b = BeliefMapper(100, self.extero_latent_dim + self.priv_slot_dim)
        # f_pi input [o_p | b_t] == teacher latent [o_p | l_e | l_priv]
        self.f_pi = MLP(proprio_dim + self.extero_latent_dim + self.priv_slot_dim, action_dim, list(trunk_dims), "lrelu")
        self.decoder = BeliefDecoder(self.extero_latent_dim + self.priv_slot_dim, extero_dim + self.priv_slot_dim)

    def encode_extero(self, extero: torch.Tensor) -> torch.Tensor:
        """Normalize noisy rings and encode per foot -> l_e [N, extero_latent_dim]."""
        e = self.extero_norm(extero)
        n = e.shape[0]
        return self.g_e(e.view(n, self.num_feet, self.points_per_foot)).reshape(n, -1)

    def forward(
        self, proprio: torch.Tensor, extero: torch.Tensor, hidden_state: torch.Tensor
    ) -> tuple[torch.Tensor, torch.Tensor, dict[str, torch.Tensor]]:
        """One student step.

        Args:
            proprio: Raw proprio obs [N, proprio_dim].
            extero: Raw noisy extero obs [N, extero_dim].
            hidden_state: Belief GRU hidden state [2, N, 50].

        Returns:
            Tuple of actions [N, action_dim], the new hidden state, and a dict
            of internals (``o_p_n``, ``l_e``, ``b_prime``, ``alpha``, ``b_t``)
            for the distillation losses.
        """
        o_p_n = self.proprio_norm(proprio)
        l_e = self.encode_extero(extero)
        b_prime, hidden_state = self.belief(torch.cat((o_p_n, l_e), dim=-1), hidden_state)
        alpha = self.g_a(b_prime)
        b_t = self.g_b(b_prime)
        # FROZEN segmentation: b_t[:, :96] is the teacher l_e slot (gated),
        # b_t[:, 96:120] is the teacher l_priv slot (zero-pad side of g_b)
        b_t = torch.cat((b_t[..., : self.extero_latent_dim] + l_e * alpha, b_t[..., self.extero_latent_dim :]), dim=-1)
        actions = self.f_pi(torch.cat((o_p_n, b_t), dim=-1))
        return actions, hidden_state, {"o_p_n": o_p_n, "l_e": l_e, "b_prime": b_prime, "alpha": alpha, "b_t": b_t}

    def load_from_teacher(self, teacher: SplitEncoderModel) -> None:
        """Transfer f_pi / g_e weights and proprio normalization from the teacher.

        Asserts the f_pi input segment-order identity first: the teacher latent
        [proprio | l_e | l_priv] and the student input [proprio | b_t] must
        have identical segmentation, otherwise the transfer is a silent
        mis-wiring no shape check can catch. g_p, the critic, and the teacher's
        extero normalizer are deliberately NOT transferred.
        """
        # segment-order identity assertions
        if self.f_pi[0].in_features != teacher.mlp[0].in_features:
            raise ValueError(
                f"f_pi input dim {self.f_pi[0].in_features} != teacher latent dim "
                f"{teacher.mlp[0].in_features} -- student/teacher segmentation mismatch."
            )
        if self.proprio_dim != teacher.obs_dims["proprio"]:
            raise ValueError(
                f"proprio dim {self.proprio_dim} != teacher {teacher.obs_dims['proprio']}."
            )
        teacher_extero_latent = teacher.num_feet * teacher.extero_latent_per_foot
        if self.extero_latent_dim != teacher_extero_latent:
            raise ValueError(
                f"extero latent {self.extero_latent_dim} != teacher {teacher_extero_latent}."
            )
        if self.priv_slot_dim != teacher.priv_latent_dim:
            raise ValueError(
                f"priv slot {self.priv_slot_dim} != teacher priv latent {teacher.priv_latent_dim}."
            )
        self.g_e.load_state_dict(teacher.g_e.state_dict())
        self.f_pi.load_state_dict(teacher.mlp.state_dict())
        if teacher.obs_normalization:
            self.proprio_norm.load_state_dict(teacher.obs_normalizers["proprio"].state_dict())
