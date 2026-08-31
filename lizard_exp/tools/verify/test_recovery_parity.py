# -*- coding: utf-8 -*-
"""Parity test: vectorized recovery_times vs a naive per-env reference.

Pure torch (no Isaac runtime needed). The vectorized implementation
(unfold-based first-sustained-window scan) must match the straightforward
loop on random series and on edge cases. The cleanup commit that vectorized
it claimed a parity pass but never committed the test -- this is that missing
artifact.

Usage: python lizard_exp\\tools\\verify\\test_recovery_parity.py
"""
import pathlib
import sys

import torch

_REPO = pathlib.Path(__file__).absolute().parents[3]
sys.path.insert(0, str(_REPO / "ablation_harness"))
from components.recovery import recovery_times  # noqa: E402


def reference(lin_error, push_step, threshold, sustain, step_dt, valid_mask):
    """Straightforward (slow) transcription of the protocol semantics."""
    num_steps, num_envs = lin_error.shape
    times, spikes = [], []
    for n in range(num_envs):
        post = lin_error[push_step:, n]
        spike = float(post.max()) if post.numel() > 0 else 0.0
        ok = [bool(valid_mask[j, n]) and float(lin_error[j, n]) < threshold
              for j in range(push_step, num_steps)]
        t = float("nan")
        for i in range(len(ok) - sustain + 1):
            if all(ok[i:i + sustain]):
                t = i * step_dt
                break
        times.append(t)
        spikes.append(spike)
    recovered = [t for t in times if t == t]
    if recovered:
        ts = torch.tensor(recovered)
        mean_t, median_t = ts.mean().item(), ts.median().item()
        p90_t = torch.quantile(ts, 0.9).item()
    else:
        mean_t = median_t = p90_t = float("nan")
    return {
        "recovery_time_mean_s": mean_t,
        "recovery_time_median_s": median_t,
        "recovery_time_p90_s": p90_t,
        "never_recovered_frac": 1.0 - len(recovered) / num_envs,
        "spike_mean_mps": torch.tensor(spikes).mean().item(),
    }


def check(lin_error, push_step, threshold, sustain, step_dt, valid_mask, label):
    got = recovery_times(lin_error, push_step, threshold, sustain, step_dt, valid_mask)
    exp = reference(lin_error, push_step, threshold, sustain, step_dt, valid_mask)
    for key in exp:
        g, e = got[key], exp[key]
        if g != g and e != e:  # both NaN
            continue
        assert abs(g - e) < 1e-5, f"{label}: {key} got {g} expected {e}"
    print(f"  ok {label}")


def main():
    step_dt, threshold, sustain = 0.02, 0.25, 25

    # random series with a kick spike and random death times, 4 seeds
    for seed in range(4):
        gen = torch.Generator().manual_seed(seed)
        steps, envs, push = 400, 32, 100
        lin = torch.rand(steps, envs, generator=gen) * 0.6
        lin[push:] += 0.4
        first_done = torch.full((envs,), steps, dtype=torch.long)
        dead = torch.rand(envs, generator=gen) < 0.3
        if bool(dead.any()):
            first_done[dead] = torch.randint(push - 50, steps, (int(dead.sum()),), generator=gen)
        valid = torch.arange(steps).unsqueeze(1) <= first_done.unsqueeze(0)
        check(lin, push, threshold, sustain, step_dt, valid, f"random seed{seed}")

    steps, envs = 200, 8
    ones = torch.ones(steps, envs, dtype=torch.bool)
    # all below -> recovery 0
    check(torch.full((steps, envs), 0.1), 50, threshold, sustain, step_dt, ones, "all-below")
    # none below -> never recovered, aggregates NaN
    check(torch.full((steps, envs), 1.0), 50, threshold, sustain, step_dt, ones, "none-below")
    # env dies inside the first sustain window -> never recovered
    valid2 = ones.clone()
    valid2[60:] = False
    check(torch.full((steps, envs), 0.1), 50, threshold, sustain, step_dt, valid2, "done-midwindow")
    # tail shorter than the sustain window -> no windows at all
    check(torch.full((steps, envs), 0.1), steps - 10, threshold, sustain, step_dt, ones, "short-tail")
    # single env, recovery exactly at the last possible window
    lin = torch.full((steps, 1), 1.0)
    lin[120:146] = 0.1
    lin[146:] = 0.1  # stays below: first full window starts at 120
    check(lin, 100, threshold, sustain, step_dt, torch.ones(steps, 1, dtype=torch.bool), "single-env")

    print("ALL_RECOVERY_PARITY_TESTS_PASSED")


if __name__ == "__main__":
    main()
