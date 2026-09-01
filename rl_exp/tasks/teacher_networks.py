# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

"""Teacher network modules for Lizard-Rough-v3 (paper-aligned three-encoder teacher).

Implements the Miki et al. 2022 teacher architecture as an rsl_rl ``MLPModel``
subclass, so it plugs into ``OnPolicyRunner`` via the ``class_name`` point path
(``resolve_callable``, rsl_rl 5.4.2 utils.py:97 / ppo.py:416-418) with zero
rsl_rl modifications::

    foot rings x4 --g_e {80,60} shared--> l_e (24/foot, concat 96) --\\
    privileged 83  --g_p {64,32}--------> l_priv (24)                +--> f_pi {256,160,128} --> action 26
    proprio 90 ----------------------------------------------------/

Observation groups (env-side contract, names checked at construction):

* ``proprio``: ``[N, 90]`` noisy proprioception
* ``extero``: ``[N, 4 * points_per_foot]`` height rings, feet in env term
  order (lf, rf, rl, rr -- asserted by check_obs_layout.py)
* ``priv``: ``[N, 83]`` privileged state

Each stream carries its own ``EmpiricalNormalization`` (paper: per-stream
running mean/std). The f_pi input segment order is FROZEN to
``[proprio | l_e | l_priv]``: the student's ``b_t`` (student_networks.py)
must reproduce exactly this segmentation for zero-change weight transfer --
same dims in a different order is a silent mismatch no shape check catches.
"""

from __future__ import annotations

import copy

import torch
import torch.nn as nn
from tensordict import TensorDict

from rsl_rl.models import MLPModel
from rsl_rl.modules import EmpiricalNormalization
from rsl_rl.modules.mlp import MLP
from rsl_rl.utils import resolve_callable

# obs group names are the model<->env contract; order here is the frozen f_pi
# input segmentation (proprio | extero latent | priv latent)
OBS_GROUP_CONTRACT: tuple[str, str, str] = ("proprio", "extero", "priv")


class SplitEncoderModel(MLPModel):
    """Teacher actor/critic with split per-foot extero / privileged encoders.

    The actor uses a Gaussian distribution (``distribution_cfg``); the critic is
    constructed without one (deterministic value head, ``output_dim=1``). Both
    share the same encoder architecture ("critic 同构" -- separate weights).

    Constructor kwargs mirror ``RslRlMLPModelCfg`` fields plus the encoder
    architecture knobs, so a configclass subclass can drive everything through
    ``construct_algorithm``'s ``**cfg["actor"]`` call.
    """

    is_recurrent: bool = False

    def __init__(
        self,
        obs: TensorDict,
        obs_groups: dict[str, list[str]],
        obs_set: str,
        output_dim: int,
        hidden_dims: tuple[int, ...] | list[int] = (256, 160, 128),
        activation: str = "lrelu",
        obs_normalization: bool = False,
        distribution_cfg: dict | None = None,
        extero_encoder_dims: tuple[int, ...] | list[int] = (80, 60),
        extero_latent_per_foot: int = 24,
        priv_encoder_dims: tuple[int, ...] | list[int] = (64, 32),
        priv_latent_dim: int = 24,
        num_feet: int = 4,
    ) -> None:
        """Initialize the split-encoder teacher model.

        Args:
            obs: Observation TensorDict from the environment (all groups).
            obs_groups: Mapping from observation sets to lists of group names.
            obs_set: Observation set to use ("actor" or "critic").
            output_dim: Action dimension (actor) or 1 (critic).
            hidden_dims: f_pi trunk hidden dimensions.
            activation: Activation name (paper uses LeakyReLU, to normalize each stream separately.
            distribution_cfg: Output distribution config (actor only).
            extero_encoder_dims: g_e hidden dimensions (shared across feet).
            extero_latent_per_foot: l_e dimension per foot.
            priv_encoder_dims: g_p hidden dimensions.
            priv_latent_dim: l_priv dimension.
            num_feet: Number of feet in the extero group.
        """
        # bypass MLPModel.__init__ (single normalizer + plain MLP); rebuild here
        nn.Module.__init__(self)

        active = list(obs_groups[obs_set])
        if set(active) != set(OBS_GROUP_CONTRACT):
            raise ValueError(
                f"{type(self).__name__} requires obs groups {list(OBS_GROUP_CONTRACT)} "
                f"in obs_groups[{obs_set!r}], got {active}."
            )
        for name in OBS_GROUP_CONTRACT:
            if len(obs[name].shape) != 2:
                raise ValueError(
                    f"obs group '{name}' must be 1D per env, got shape {obs[name].shape}."
                )
        self.obs_groups = active
        self.obs_set = obs_set
        self.obs_dims = {name: int(obs[name].shape[-1]) for name in OBS_GROUP_CONTRACT}
        self.obs_dim = sum(self.obs_dims.values())
        self.output_dim = output_dim

        # per-stream running mean/std (paper: three separate normalizers)
        self.obs_normalization = obs_normalization
        self.obs_normalizers = nn.ModuleDict(
            {
                name: EmpiricalNormalization(self.obs_dims[name]) if obs_normalization else nn.Identity()
                for name in OBS_GROUP_CONTRACT
            }
        )

        # g_e: shared per-foot extero encoder; input dim follows the env pattern
        # (52 points/foot today, 40-point fallback re-sizes without code change)
        self.num_feet = num_feet
        if self.obs_dims["extero"] % num_feet != 0:
            raise ValueError(
                f"extero dim {self.obs_dims['extero']} not divisible by num_feet {num_feet}."
            )
        self.points_per_foot = self.obs_dims["extero"] // num_feet
        self.extero_latent_per_foot = extero_latent_per_foot
        self.g_e = MLP(self.points_per_foot, extero_latent_per_foot, list(extero_encoder_dims), activation)

        # g_p: privileged encoder
        self.priv_latent_dim = priv_latent_dim
        self.g_p = MLP(self.obs_dims["priv"], priv_latent_dim, list(priv_encoder_dims), activation)

        # f_pi trunk over [proprio | l_e | l_priv] -- named "mlp" for MLPModel
        # base-class forward()/export compatibility
        self.latent_dim = self.obs_dims["proprio"] + num_feet * extero_latent_per_foot + priv_latent_dim
        if distribution_cfg is not None:
            cfg = dict(distribution_cfg)
            dist_class = resolve_callable(cfg.pop("class_name"))
            self.distribution = dist_class(output_dim, **cfg)
            trunk_out = self.distribution.input_dim
        else:
            self.distribution = None
            trunk_out = output_dim
        self.mlp = MLP(self.latent_dim, trunk_out, list(hidden_dims), activation)
        if self.distribution is not None:
            self.distribution.init_mlp_weights(self.mlp)

    def get_latent(
        self,
        obs: TensorDict,
        masks: torch.Tensor | None = None,
        hidden_state=None,
    ) -> torch.Tensor:
        """Build the f_pi latent: per-stream normalize, encode, frozen concat."""
        o_p = self.obs_normalizers["proprio"](obs["proprio"])
        extero = self.obs_normalizers["extero"](obs["extero"])
        n = extero.shape[0]
        l_e = self.g_e(extero.view(n, self.num_feet, self.points_per_foot)).reshape(n, -1)
        l_p = self.g_p(self.obs_normalizers["priv"](obs["priv"]))
        # FROZEN segment order [proprio | l_e | l_priv] -- student b_t must match
        return torch.cat((o_p, l_e, l_p), dim=-1)

    def update_normalization(self, obs: TensorDict) -> None:
        """Update the per-stream normalization statistics from a batch."""
        if self.obs_normalization:
            for name in OBS_GROUP_CONTRACT:
                self.obs_normalizers[name].update(obs[name])

    def as_jit(self) -> nn.Module:
        """Return a JIT-exportable copy taking the flat [proprio|extero|priv] obs."""
        return _TorchSplitEncoderModel(self)

    def as_onnx(self, verbose: bool) -> nn.Module:
        """Return an ONNX-exportable copy taking the flat [proprio|extero|priv] obs."""
        return _OnnxSplitEncoderModel(self, verbose)


class _TorchSplitEncoderModel(nn.Module):
    """Exportable SplitEncoderModel (JIT): flat raw-obs input, deterministic output."""

    def __init__(self, model: SplitEncoderModel) -> None:
        super().__init__()
        self.obs_normalizers = copy.deepcopy(model.obs_normalizers)
        self.g_e = copy.deepcopy(model.g_e)
        self.g_p = copy.deepcopy(model.g_p)
        self.mlp = copy.deepcopy(model.mlp)
        self.num_feet = model.num_feet
        self.points_per_foot = model.points_per_foot
        self.dims = dict(model.obs_dims)
        if model.distribution is not None:
            self.deterministic_output = model.distribution.as_deterministic_output_module()
        else:
            self.deterministic_output = nn.Identity()

    def _latent(self, x: torch.Tensor) -> torch.Tensor:
        d = self.dims
        o_p = self.obs_normalizers["proprio"](x[..., : d["proprio"]])
        extero = self.obs_normalizers["extero"](x[..., d["proprio"] : d["proprio"] + d["extero"]])
        priv = self.obs_normalizers["priv"](x[..., d["proprio"] + d["extero"] :])
        n = extero.shape[0]
        l_e = self.g_e(extero.view(n, self.num_feet, self.points_per_foot)).reshape(n, -1)
        l_p = self.g_p(priv)
        return torch.cat((o_p, l_e, l_p), dim=-1)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """Run deterministic inference on pre-concatenated raw observations."""
        return self.deterministic_output(self.mlp(self._latent(x)))

    @torch.jit.export
    def reset(self) -> None:
        """Reset recurrent export state (no-op)."""
        pass


class _OnnxSplitEncoderModel(_TorchSplitEncoderModel):
    """ONNX variant of the export wrapper with dummy inputs and IO names."""

    def __init__(self, model: SplitEncoderModel, verbose: bool) -> None:
        super().__init__(model)
        self.verbose = verbose
        self.input_size = sum(model.obs_dims.values())

    def get_dummy_inputs(self) -> tuple[torch.Tensor]:
        """Return representative dummy inputs for ONNX tracing."""
        return (torch.zeros(1, self.input_size),)

    @property
    def input_names(self) -> list[str]:
        """Return ONNX input tensor names."""
        return ["obs"]

    @property
    def output_names(self) -> list[str]:
        """Return ONNX output tensor names."""
        return ["actions"]
