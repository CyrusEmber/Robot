# -*- coding: utf-8 -*-
"""Negative control for check_configclass_fields.py (the gate's own falsifier).

A gate that has never been seen to fail is not a gate. This injects each drift the
gate claims to catch -- target missing from to_dict(), a declared field never
reaching the instance __dict__, the class attribute becoming readable again, a
mixed field/non-field family, the instance attribute vanishing, the field /
non-field branch contract disagreeing, a PLAY variant retargeting the recipe it
belongs to, and each way a framework-dropped `velocity_limit` can stop being
recognisably inert -- and asserts every one of them produces a problem. Row dicts
are shallow-copied and mutated; no config is rebuilt.
"""

import sys
import types

sys.path.insert(0, ".")
sys.path.insert(0, "rl_exp/tools/verify")
import check_configclass_fields as g

from isaaclab.actuators import ImplicitActuatorCfg

rows: dict[str, dict] = {}
# The subject pair is NAMED, not derived from `rows`: a mutation has to land on a class the gate
# really probes (see the absent check below), and a name picked out of `rows` could never be
# absent from it -- the check would be a tautology. The pair is the active line's train/PLAY pair,
# so re-pointing it is the deliberate act a retired line requires (2026-10: the lizard/main pair
# this used to name went with the line).
TARGET = "Lizard2FlatV3EnvCfg"
PLAY_TARGET = "Lizard2FlatV3EnvCfg_PLAY"


def _synthetic(*, stub: tuple[str, ...] = (), **groups) -> dict:
    """A row carrying the caller's actuator groups, so a mutation cannot touch a real cfg.

    The other cases mutate a row *dict*; this claim reads the constructed cfg, and mutating a real
    one would leave the drift in place for every later case and for the gate's own run. The groups
    are real ``ImplicitActuatorCfg`` objects unless named in ``stub``, which is how the one case that
    is about the actuator *kind* isolates itself: a stub fires that branch and nothing else.
    """
    actuators = {}
    for group, (value, simulated) in groups.items():
        if group in stub:
            actuators[group] = types.SimpleNamespace(velocity_limit=value, velocity_limit_sim=simulated)
        else:
            actuators[group] = ImplicitActuatorCfg(joint_names_expr=[".*"], stiffness=1.0, damping=1.0,
                                                   velocity_limit=value, velocity_limit_sim=simulated)
    robot = types.SimpleNamespace(actuators=actuators)
    return {"instance": types.SimpleNamespace(scene=types.SimpleNamespace(robot=robot))}


def _snapshot() -> dict[str, dict]:
    return {name: dict(row) for name, row in rows.items()}


def _fires(mutate, checker, tag: str) -> bool:
    probe = _snapshot()
    mutate(probe)
    problems: list[str] = []
    checker(probe, problems)
    print(f"  {tag}: {'FIRES' if problems else 'SILENT'}")
    return bool(problems)


def main(probed_rows: dict[str, dict] | None = None) -> int:
    global rows
    rows = probed_rows if probed_rows is not None else {
        name: g._probe(cls) for name, cls in g._cfg_classes(g._declared_entries(), []).items()
    }
    # The subject set is part of what this control asserts. If the gate stops seeing the class the
    # mutations are applied to, every case below would still "fire" on a dict it then KeyErrors out
    # of -- a bare KeyError is not a verdict, and a control that crashes is indistinguishable from
    # a control that passed. Say which target went missing instead.
    absent = [name for name in (TARGET, PLAY_TARGET) if name not in rows]
    if absent:
        print(f"  the gate no longer probes {absent} -- it is a registered task's class, so the")
        print("  subject set shrank; the cases below would test a mutation no assertion covers")
        print("CONFIGCLASS_FIELDS_GATE_SILENT")
        return 1
    ok = all([
        _fires(lambda r: r[TARGET].update(in_to_dict=False), g._check_shape, "to_dict loss      "),
        _fires(lambda r: r[TARGET].update(in_instance_dict=False), g._check_shape, "instance loss    "),
        _fires(lambda r: r[TARGET].update(fields_not_serialized=["x"]), g._check_shape, "field loss       "),
        _fires(lambda r: r[TARGET].update(class_attr_readable=True), g._check_shape, "cls attr mismatch"),
        _fires(lambda r: r[TARGET].update(is_field=False), g._check_shape, "mixed surface    "),
        _fires(lambda r: r[TARGET].update(is_field=False), g._check_branch, "branch mismatch  "),
        # the PLAY variant is paired with its train class by name: the rule that used to be read off
        # the MRO. Moving it without a falsifier is exactly how a rule stops being one.
        _fires(lambda r: r[PLAY_TARGET].update(value="v99"), g._check_play_inheritance, "play retarget    "),
        # The inert velocity declaration: four ways out of the pinned state, one case each, so a
        # case cannot pass on a branch that belongs to a different one.
        _fires(lambda r: r.update(synthetic=_synthetic(tail=(4.0, None))),
               g._check_inert_velocity_limits, "unreviewed group "),
        _fires(lambda r: r.update(synthetic=_synthetic(legs=(8.0, None))),
               g._check_inert_velocity_limits, "value moved      "),
        _fires(lambda r: r.update(synthetic=_synthetic(legs=(10.0, 8.0))),
               g._check_inert_velocity_limits, "sim cap enabled  "),
        _fires(lambda r: r.update(synthetic=_synthetic(legs=(10.0, None), stub=("legs",))),
               g._check_inert_velocity_limits, "actuator honours "),
    ])
    print("CONFIGCLASS_FIELDS_GATE_FALSIFIABLE" if ok else "CONFIGCLASS_FIELDS_GATE_SILENT")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
