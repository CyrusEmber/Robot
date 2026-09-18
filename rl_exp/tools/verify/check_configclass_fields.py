# -*- coding: utf-8 -*-
"""Configclass field-surface gate: is ``params_version`` a real dataclass field?

ARCH_PLAN Step 1.0. The answer decides the Step 2 remediation shape:

* **field** -- part of ``__init__`` / ``to_dict()`` / ``from_dict``; it can be
  promoted to an explicit build argument while keeping serialization compatible.
* **non-field** -- a channel outside the dataclass contract; it must be brought
  into the field surface first.

Why ``to_dict()`` answers the ``params/env.yaml`` question: IsaacLab's
``train.py`` dumps ``params/env.yaml`` through ``dump_yaml(..., env_cfg)``
(``train.py:273``), which calls ``class_to_dict`` (``utils/io/yaml.py:52-53``).
``configclass.to_dict`` *is* ``class_to_dict`` (``configclass.py:109``,
``:127-136``), so for a dump taken from an instance the two key sets are the same
by construction. Pass ``--env-yaml`` to compare against a real dump instead.

The configclass mechanics this gate observes (``configclass.py``): the decorator
snapshots the class body into ``__configclass_own_fields__`` (:95-97), then
back-fills annotations for un-annotated members (:99 -> ``_add_annotation_types``
:258) before wrapping with ``dataclass()`` (:115). ``_skippable_class_member``
(:524) only skips dunders, ``_CONFIGCLASS_METHODS``, already-annotated names,
callables and properties -- so a plain ``params_version = "v14"`` string becomes
a field. This gate pins the observed surface so that stops being a source-code
guess, and fails if the surface drifts.

No sim: constructs configs only, same footing as ``check_obs_layout.py``.
"""

import argparse
import importlib
import inspect
import json
import pathlib
import pkgutil
import sys

_REPO = pathlib.Path(__file__).resolve().parents[3]
sys.path.insert(0, str(_REPO))

import yaml  # noqa: E402

import rl_exp.tasks as _tasks_pkg  # noqa: E402

TARGET = "params_version"


def _cfg_classes() -> dict[str, type]:
    """Every configclass in ``rl_exp.tasks`` carrying ``params_version``, by name.

    Detected through ``__dataclass_fields__`` / ``__configclass_own_fields__``, never
    through ``getattr(cls, ...)``: ``_process_mutable_types`` turns every member into
    ``field(default_factory=...)`` (:475) and ``dataclass()`` drops those from the class
    namespace (:115), so most config values are unreadable as class attributes.
    """
    found: dict[str, type] = {}
    modules = sorted(m.name for m in pkgutil.iter_modules(_tasks_pkg.__path__))
    for mod_name in modules:
        try:
            module = importlib.import_module(f"rl_exp.tasks.{mod_name}")
        except Exception as exc:  # noqa: BLE001 - report, never mask a gate
            print(f"  SKIP module {mod_name}: {type(exc).__name__}: {exc}")
            continue
        for name, obj in vars(module).items():
            if (
                inspect.isclass(obj)
                and obj.__module__.startswith("rl_exp.tasks")
                and obj.__qualname__ == name  # skip re-exports
                and (
                    TARGET in getattr(obj, "__dataclass_fields__", {})
                    or TARGET in getattr(obj, "__configclass_own_fields__", ())
                )
            ):
                found[name] = obj
    return dict(sorted(found.items()))


def _probe(cls: type) -> dict:
    """Observe the field surface of one configclass (constructed, not built)."""
    inst = cls()
    fields = set(cls.__dataclass_fields__)
    inst_dict = set(inst.__dict__)
    dumped = inst.to_dict()
    return {
        "value": inst.params_version,
        "is_field": TARGET in fields,
        "in_own_fields": TARGET in set(getattr(cls, "__configclass_own_fields__", ())),
        "in_instance_dict": TARGET in inst_dict,
        "in_to_dict": TARGET in dumped,
        # False on this fork: default_factory fields are erased from the class namespace
        "class_attr_readable": hasattr(cls, TARGET),
        "field_count": len(fields),
        "own_field_count": len(getattr(cls, "__configclass_own_fields__", ())),
        "to_dict_count": len(dumped),
        # a declared field that never reaches __dict__ is a silent serialization loss
        "fields_not_serialized": sorted(f for f in fields if f not in inst_dict),
        "instance": inst,
        "dumped": dumped,
    }


def _check_shape(rows: dict[str, dict], problems: list[str]) -> None:
    """Branch-independent invariants: the target stays visible and serialized."""
    for name, p in rows.items():
        if not p["in_instance_dict"]:
            problems.append(f"{name}: params_version not readable on the instance at all")
        elif not p["in_to_dict"]:
            problems.append(
                f"{name}: params_version absent from to_dict() -> "
                f"params/env.yaml and log readers would silently lose it"
            )
        if p["fields_not_serialized"]:
            problems.append(
                f"{name}: dataclass fields missing from instance __dict__ "
                f"(never serialized): {p['fields_not_serialized']}"
            )

    kinds = {name: p["is_field"] for name, p in rows.items()}
    if len(set(kinds.values())) > 1:
        mixed = sorted(n for n, is_field in kinds.items() if is_field)
        problems.append(
            f"family is mixed field/non-field for params_version (field: {mixed}); "
            f"a per-class difference in decoration order would make loading depend on "
            f"which subclass was constructed"
        )

    if len({p["class_attr_readable"] for p in rows.values()}) > 1:
        readable = sorted(n for n, p in rows.items() if p["class_attr_readable"])
        problems.append(
            f"params_version is readable as a class attribute in only some versions "
            f"({readable}); class-level reads would work in a copy-paste and AttributeError "
            f"elsewhere -- no config read path may use getattr(cls, 'params_version')"
        )


def _check_branch(rows: dict[str, dict], problems: list[str]) -> None:
    """Branch-specific contract: field == constructible + round-trips through a dump."""
    is_field = all(p["is_field"] for p in rows.values())
    for name, p in rows.items():
        cls = type(p["instance"])
        if is_field:
            try:
                cls(params_version=p["value"])
            except Exception as exc:  # noqa: BLE001
                problems.append(f"{name}: params_version is a field but not accepted as a kwarg: {exc!r}")
                continue
            try:
                restored = cls()
                restored.from_dict(p["dumped"])
            except KeyError as exc:
                problems.append(
                    f"{name}: from_dict() rejects the params/env.yaml surface it just wrote "
                    f"({exc!r}); a logged run could no longer be replayed"
                )
            except Exception as exc:  # noqa: BLE001
                problems.append(f"{name}: from_dict() round trip failed: {type(exc).__name__}: {exc}")
            else:
                if restored.params_version != p["value"]:
                    problems.append(
                        f"{name}: from_dict() round trip changed params_version "
                        f"{p['value']!r} -> {restored.params_version!r}"
                    )
        else:
            try:
                cls(params_version=p["value"])
            except TypeError:
                pass  # expected for a non-field channel
            else:
                problems.append(
                    f"{name}: params_version is a non-field channel yet is accepted as a "
                    f"constructor kwarg -- the two surfaces disagree"
                )


def _check_play_inheritance(rows: dict[str, dict], problems: list[str]) -> None:
    """PLAY variants must not retarget the params line they belong to.

    The counterpart is the same recipe's train class -- by name, ``X_PLAY`` against ``X``. It used
    to be the MRO parent, because ``V14_PLAY`` extended ``V14``; the generated classes come off the
    shared wiring instead, whose own default is some other recipe, so an MRO answer would compare
    two unrelated things and redden every PLAY variant of the line. The MRO parent stays as the
    fallback for a class the declaration did not make (a framework or family class).
    """
    for name, p in rows.items():
        if not name.endswith("_PLAY"):
            continue
        train_name = name[: -len("_PLAY")]
        counterpart = rows.get(train_name)
        if counterpart is None:
            parent = next((c for c in type(p["instance"]).__mro__[1:] if c.__name__ in rows), None)
            if parent is None:
                continue
            train_name, counterpart = parent.__name__, rows[parent.__name__]
        if counterpart["value"] != p["value"]:
            problems.append(
                f"{name}: params_version {p['value']!r} != {train_name} "
                f"{counterpart['value']!r} (a PLAY variant must not retarget the line)"
            )


def _check_env_yaml(path: pathlib.Path, rows: dict[str, dict], problems: list[str]):
    """Compare against a real params/env.yaml dump, when one is available."""
    with open(path, encoding="utf-8") as f:
        dumped = yaml.full_load(f)
    known = {p["value"] for p in rows.values()}
    print(f"  env.yaml sample: {path}")
    print(f"  env.yaml has {TARGET}: {TARGET in dumped} (value {dumped.get(TARGET)!r})")
    if TARGET in dumped and dumped[TARGET] not in known:
        problems.append(
            f"env.yaml carries {TARGET}={dumped[TARGET]!r}, which no current configclass "
            f"declares; the dump cannot be attributed to a live version"
        )


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--env-yaml", type=pathlib.Path, help="a real params/env.yaml dump to compare against")
    ap.add_argument("--json", type=pathlib.Path, help="write the full observed field surface here")
    ap.add_argument("--self-test", action="store_true", help="also falsify the detector in-process")
    args = ap.parse_args()

    problems: list[str] = []
    rows = {name: _probe(cls) for name, cls in _cfg_classes().items()}

    print(f"  configclasses carrying {TARGET}: {len(rows)}")
    print("  name  value  field  own  instdict  to_dict  cls_attr  fields  own_fields  to_dict_keys")
    for name, p in rows.items():
        print(
            f"  {name}  {p['value']!r}  {int(p['is_field'])}  {int(p['in_own_fields'])}  "
            f"{int(p['in_instance_dict'])}  {int(p['in_to_dict'])}  {int(p['class_attr_readable'])}  "
            f"{p['field_count']}  {p['own_field_count']}  {p['to_dict_count']}"
        )

    field_rows = [n for n, p in rows.items() if p["is_field"]]
    if field_rows and len(field_rows) == len(rows):
        print(f"  VERDICT: {TARGET} IS a dataclass field in all {len(rows)} classes.")
        print("    mechanism: annotations back-filled (configclass.py:99), every member becomes")
        print("      field(default_factory=...) (:475), dataclass() wraps (:115) and erases the")
        print("      class attribute -> the value exists on instances only, and DOES reach")
        print("      to_dict()/from_dict and params/env.yaml (train.py:273 -> dict.py:57).")
        print("    => Step 2 may promote it to an explicit build argument; the field, its default")
        print("       and the log surface must be preserved (no getattr(cls, 'params_version') reads).")
    elif not field_rows:
        print(f"  VERDICT: {TARGET} is NOT a dataclass field: decoration-outside channel only;")
        print("           it still reaches to_dict() through _process_mutable_types (:486),")
        print("           so it must be brought into the field surface before Step 2 constrains it.")
    else:
        print(f"  VERDICT: mixed surface (field in {len(field_rows)}/{len(rows)} classes) - see drifts.")

    if args.env_yaml is not None:
        _check_env_yaml(args.env_yaml, rows, problems)
    _check_shape(rows, problems)
    _check_branch(rows, problems)
    _check_play_inheritance(rows, problems)

    if args.json is not None:
        surface = {
            name: {
                "value": p["value"],
                "is_field": p["is_field"],
                "in_own_fields": p["in_own_fields"],
                "in_instance_dict": p["in_instance_dict"],
                "in_to_dict": p["in_to_dict"],
                "class_attr_readable": p["class_attr_readable"],
                "fields": sorted(type(p["instance"]).__dataclass_fields__),
                "own_fields": sorted(getattr(type(p["instance"]), "__configclass_own_fields__", ())),
                "to_dict_keys": sorted(p["dumped"]),
            }
            for name, p in rows.items()
        }
        args.json.parent.mkdir(parents=True, exist_ok=True)
        with open(args.json, "w", encoding="utf-8") as f:
            json.dump(surface, f, indent=2, ensure_ascii=False, default=str)
        print(f"  surface written: {args.json}")

    if args.self_test:
        import test_configclass_fields_gate as falsifier

        if falsifier.main(rows) != 0:
            problems.append("field-surface falsifier stayed silent")

    for p in problems:
        print(f"  DRIFT: {p}")
    if problems:
        print(f"CONFIGCLASS_FIELDS_DRIFT ({len(problems)})")
        return 1
    print("CONFIGCLASS_FIELDS_OK")
    return 0


if __name__ == "__main__":
    # The in-process falsifier must import this instance, not execute a second copy.
    sys.modules.setdefault("check_configclass_fields", sys.modules[__name__])
    raise SystemExit(main())
