# -*- coding: utf-8 -*-
"""Negative control for check_configclass_fields.py (the gate's own falsifier).

A gate that has never been seen to fail is not a gate. This injects each drift the
gate claims to catch -- target missing from to_dict(), a declared field never
reaching the instance __dict__, the class attribute becoming readable again, a
mixed field/non-field family, the instance attribute vanishing, the field /
non-field branch contract disagreeing, and a PLAY variant retargeting the recipe it
belongs to -- and asserts every one of them produces a problem. Row dicts are
shallow-copied and mutated; no config is rebuilt.
"""

import sys

sys.path.insert(0, ".")
sys.path.insert(0, "rl_exp/tools/verify")
import check_configclass_fields as g

rows: dict[str, dict] = {}
TARGET = "LizardRoughTeacherEnvCfg_V14"
PLAY_TARGET = "LizardRoughTeacherEnvCfg_V14_PLAY"


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
    ])
    print("CONFIGCLASS_FIELDS_GATE_FALSIFIABLE" if ok else "CONFIGCLASS_FIELDS_GATE_SILENT")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
