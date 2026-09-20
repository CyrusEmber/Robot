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

Which classes it is about is part of the claim: every configclass a *registered task* resolves to
-- resolved name by name through the identity map, because ``recipe_tasks`` builds them on demand
-- plus the wiring classes that carry the field. The exports are cross-checked against the map in
both directions, so a registered task whose class this gate stopped seeing is red rather than
quietly absent.
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
TASKS_MODULE = "rl_exp.tasks.recipe_tasks"
RECIPES_JSON = _REPO / "rl_exp" / "versions" / "recipes.json"


def _declared_entries() -> list[tuple[str, str]]:
    """``(module, class name)`` for every task the identity map registers, in map order.

    Read from ``versions/recipes.json`` rather than from the module under test, and not from the
    module's own export list: what that module exports is a *claim*, and a claim verified against
    the code that makes it is not verified. The map is the published copy -- ``check_recipe_map``
    binds it to the registry -- so comparing the two is a real cross-check, and one that survives
    the export list losing a name (the failure a gate reading only ``__all__`` cannot see).
    """
    document = json.loads(RECIPES_JSON.read_text(encoding="utf-8"))
    out: list[tuple[str, str]] = []
    for recipe_key in (document.get("tasks") or {}).values():
        entry = (document.get("recipes") or {}).get(recipe_key) or {}
        module, _, name = str(entry.get("env_cfg_entry") or "").partition(":")
        if module and name:
            out.append((module, name))
    return out


def _carries_target(obj) -> bool:
    """Is ``obj`` a configclass carrying ``params_version``? (Detected through the field surface,
    never through ``getattr(cls, ...)``: ``configclass`` erases those class attributes.)"""
    return inspect.isclass(obj) and (
        TARGET in getattr(obj, "__dataclass_fields__", {})
        or TARGET in getattr(obj, "__configclass_own_fields__", ())
    )


def _check_registry_exports(declared: list[tuple[str, str]], problems: list[str]) -> None:
    """This module's exports must be exactly the entries the identity map gives it.

    Both directions, because the two failures differ: an export with no entry is a name nothing can
    reach, and an entry with no export is a *registered task this gate would silently stop
    checking* -- the subject set shrinking, which is the one failure a gate cannot notice about
    itself. A name two tasks both claim is a third: the export list is a set, so the second one
    disappears without a trace.
    """
    declared_here = [name for module, name in declared if module == TASKS_MODULE]
    try:
        from rl_exp.tasks import recipe_tasks
    except Exception as exc:  # noqa: BLE001 - report, never mask a gate
        problems.append(f"{TASKS_MODULE} cannot be imported: {type(exc).__name__}: {exc}")
        return
    exported = set(getattr(recipe_tasks, "__all__", ()))
    missing = sorted(set(declared_here) - exported)
    if missing:
        problems.append(
            f"{TASKS_MODULE} does not export {missing} -- the identity map declares those tasks and"
            f" this gate would not be checking their classes"
        )
    extra = sorted(exported - set(declared_here))
    if extra:
        problems.append(f"{TASKS_MODULE} exports {extra}, which no registered task names")
    duplicates = sorted({name for name in declared_here if declared_here.count(name) > 1})
    if duplicates:
        problems.append(
            f"two registered tasks share a class name {duplicates} -- one of them has no class of"
            f" its own, and the export list can only carry one"
        )


def _cfg_classes(declared: list[tuple[str, str]], problems: list[str]) -> dict[str, type]:
    """Every configclass a registered task resolves to, plus the wiring classes, by name.

    Two sources, because the tree has two kinds of class and neither covers the other:

    * the **wiring and framework** classes, found by walking each module's namespace;
    * the **classes the identity map declares**, resolved one at a time through ``recipe_tasks``.

    The second is not optional. ``recipe_tasks`` builds one line's classes on demand (module
    ``__getattr__``, so that resolving a baseline task does not import the main line), so a
    namespace walk sees only the classes someone already asked for -- the subject set would shrink
    to the wiring classes, and this gate would keep passing while checking less. A declared entry
    that does not resolve is therefore a problem, never a skip, and a resolved class that carries
    no ``params_version`` is a problem too: filtering it out is exactly the silent shrinkage.

    Where a name is both (``LizardFlatEnvCfg`` is a wiring class and a registered task's class),
    the registry's wins: it is the one a run builds, and the one a field-surface claim is about.
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
            if _carries_target(obj) and obj.__module__.startswith("rl_exp.tasks") and obj.__qualname__ == name:
                found[name] = obj  # skip re-exports: __qualname__ == name
    try:
        from rl_exp.tasks import recipe_tasks
    except Exception as exc:  # noqa: BLE001 - report, never mask a gate
        problems.append(f"{TASKS_MODULE} cannot be imported, so no registered class can be resolved: {exc}")
    else:
        for name in sorted(set(n for module, n in declared if module == TASKS_MODULE)):
            try:
                obj = getattr(recipe_tasks, name)
            except AttributeError as exc:  # a declared entry that does not resolve is red
                problems.append(f"{TASKS_MODULE}:{name} is declared by the identity map but does not resolve: {exc}")
                continue
            if not _carries_target(obj):
                problems.append(f"{TASKS_MODULE}:{name}: a registered env cfg without {TARGET} as a field")
                continue
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
    declared = _declared_entries()
    _check_registry_exports(declared, problems)
    rows = {name: _probe(cls) for name, cls in _cfg_classes(declared, problems).items()}

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
