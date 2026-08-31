# -*- coding: utf-8 -*-
"""Read final curriculum stage values from the training tfevents log."""

import glob
import pathlib

from tensorboard.backend.event_processing.event_accumulator import EventAccumulator

run_dir = sorted(glob.glob(r"E:\IsaacLab\logs\rsl_rl\lizard_flat\*"))[-1]
acc = EventAccumulator(run_dir)
acc.Reload()

tags = [t for t in acc.Tags().get("scalars", []) if "Curriculum" in t]
print("RUN %s" % run_dir)
for tag in sorted(tags):
    events = acc.Scalars(tag)
    last = events[-1]
    print("CURR %s last_step=%d value=%s" % (tag, last.step, last.value))

all_tags = acc.Tags().get("scalars", [])
for tag in sorted(all_tags):
    if tag.startswith("Episode_Reward") or "Metrics" in tag or "train" in tag.lower():
        events = acc.Scalars(tag)
        last = events[-1]
        print("TAG %s last_step=%d value=%.4f" % (tag, last.step, last.value))
print("=== DONE ===")
