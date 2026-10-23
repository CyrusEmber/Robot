# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

# -*- coding: utf-8 -*-
"""Access to the declared observation protocols (``ARCH_PLAN`` Step 3.1a).

One reader for the declaration in ``versions/obs_protocols.json``, so the network's reshape
contract, the smoke specs and the static gates stop carrying their own copy of the group and
foot order. Four hand-kept copies of "the feet are lf, rf, rl, rr" is four chances to fix
three of them.

Stdlib only and no isaaclab import: a caller that must not pay a 2.5 s framework import (or
must keep working while the task tree is mid-edit) can still ask what the layout is.

The declaration is the *identity* of a protocol, not its construction: this module never
builds a config and never derives a layout from one. ``check_obs_protocol`` compares the
declared layout against the constructed cfg, which is what keeps the two from drifting apart.
"""

from __future__ import annotations

import functools
import importlib.util
import hashlib
import re
import json
import pathlib
import xml.etree.ElementTree as ET

_file_binding_spec = importlib.util.spec_from_file_location(
    "file_binding", pathlib.Path(__file__).resolve().parents[1] / "tools" / "runrecord" / "binding.py")
file_binding = importlib.util.module_from_spec(_file_binding_spec)
_file_binding_spec.loader.exec_module(file_binding)

DECLARATION = pathlib.Path(__file__).resolve().parents[2] / "rl_exp" / "versions" / "obs_protocols.json"
ANCHORS = pathlib.Path(__file__).resolve().parents[2] / "rl_exp" / "versions" / "obs_protocol_anchors.json"
_FOOT_SUFFIX = "_foot_ring"


class ProtocolError(ValueError):
    """The declaration cannot answer the question -- never a silent default."""


@functools.lru_cache(maxsize=1)
def declaration() -> dict:
    """The parsed declaration.

    Raises:
        ProtocolError: the file is missing or unreadable. An absent declaration is not an
            empty one: every caller here answers a question about identity, and answering it
            with nothing would let a wrong layout pass.
    """
    try:
        return json.loads(DECLARATION.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as err:
        raise ProtocolError(f"cannot read {DECLARATION}: {err}") from err


RUNTIME_ORDERS = pathlib.Path(__file__).resolve().parents[2] / "rl_exp" / "versions" / "joint_order_runtime.json"
"""The measured articulation order, keyed by ASSET, so it sits with the other registries at
``versions/`` rather than inside one family's directory: the fact belongs to the body a recipe
loads, and the second family to land (lizard2) had to write its order into a file named after the
first one (moved 2026-09-22)."""


def _document_for_route(line: str, version: str | None) -> tuple[dict, pathlib.Path] | None:
    """The recipe's parameters document for a line/version route, or ``None``.

    Addressed by the route's own line and version, not by guessing a filename from a task id: a
    rename must not silently resolve to no document. Shared by the runtime reader
    (:func:`usd_path`) and the offline gate, so "which asset does this task load" has one answer --
    the two asking it differently is how a coverage check ends up measuring a set the runtime never
    loads.
    """
    if not isinstance(line, str) or not line:
        return None
    line_dir = DECLARATION.parent / line
    basename = f"{line_dir.name}_params.yaml"
    candidates = [line_dir / basename] if not isinstance(version, str) else [
        line_dir / version / basename, line_dir / basename]
    path = next((candidate for candidate in candidates if candidate.is_file()), None)
    if path is None:
        return None
    try:
        import yaml

        return yaml.safe_load(path.read_text(encoding="utf-8")), path
    except Exception:  # a document that cannot be parsed is a missing document here
        return None


def _params_document(task_id: str) -> tuple[dict, pathlib.Path] | None:
    """The recipe's parameters document and its path, or ``None`` when it cannot be found."""
    route = task_route(task_id)
    return _document_for_route(route.get("line"), route.get("version"))


def usd_path_for_route(line: str, version: str | None) -> str | None:
    """The asset a line/version's recipe loads, or ``None`` when the document does not say."""
    found = _document_for_route(line, version)
    if found is None:
        return None
    asset = ((found[0].get("robot") or {}) if isinstance(found[0], dict) else {}).get("usd_path")
    return asset if isinstance(asset, str) and asset else None


def usd_path(task_id: str) -> str | None:
    """The asset a task's recipe loads, or ``None`` when the document does not say."""
    route = task_route(task_id)
    return usd_path_for_route(route.get("line"), route.get("version"))


def family_of(task_id: str) -> str | None:
    """The family a task belongs to, read off its route line (``lizard2/main`` -> ``lizard2``).

    Sits next to :func:`usd_path` because both answer "what does this task load": a family's mesh
    tree is a per-family fact (``versions/<family>/assets.json``), and a caller that resolves one of
    the two by guessing from a task id can end up measuring assets no run loaded.
    """
    line = task_route(task_id).get("line")
    if not isinstance(line, str) or not line:
        return None
    return line.split("/")[0]


def runtime_joint_order_for_asset(asset: str) -> list[str] | None:
    """The measured articulation order of an asset, or ``None`` when unpinned.

    Keyed by the asset because that is what the order belongs to: every recipe loading the same
    USD resolves the same sequence, whatever line or version it belongs to.
    """
    if not asset or not RUNTIME_ORDERS.is_file():
        return None
    try:
        entry = (json.loads(RUNTIME_ORDERS.read_text(encoding="utf-8")).get("assets") or {}).get(asset)
    except (OSError, json.JSONDecodeError):
        return None
    order = (entry or {}).get("joint_order")
    return list(order) if isinstance(order, list) and order else None


def runtime_joint_order(task_id: str) -> list[str] | None:
    """The measured articulation order of this task's asset, or ``None`` when unpinned.

    Kept apart from the recipe's ``joint_order`` on purpose: that one is the URDF tree order the
    deployment side reads, while this one is what the observation and the action actually index.
    A permutation here misaligns every checkpoint trained before it, so it is measured once and
    compared from then on, never inferred from the version or the asset's name.
    """
    asset = usd_path(task_id)
    return runtime_joint_order_for_asset(asset) if asset else None


def joint_order_digest(task_id: str) -> str | None:
    """A digest of the pinned runtime order, for run records: which order a policy trained under."""
    order = runtime_joint_order(task_id)
    if order is None:
        return None
    return hashlib.sha256("\n".join(order).encode("utf-8")).hexdigest()


def task_route(task_id: str) -> dict:
    """The declaration's route for one task: ``protocol``, ``version``, ``line``.

    Empty for an undeclared task: callers that need a hard failure ask
    :func:`protocol_for`, while a reader reporting on many tasks wants the absence as a value.
    """
    route = (declaration().get("tasks") or {}).get(task_id)
    return dict(route) if isinstance(route, dict) else {}


def declared(task_id: str) -> bool:
    """Whether the declaration carries this task at all.

    Asked separately from :func:`protocol_for` because "not declared" and "declared but the
    recipe has no live config any more" are different situations: the first is a typo or a gap
    and should raise, the second is a retirement -- a legal lifecycle move whose golden and
    frozen yaml stay -- and a gate should report it as a line of text, not die importing.
    """
    route = (declaration().get("tasks") or {}).get(task_id)
    return isinstance(route, dict) and "protocol" in route


def protocol_for(task_id: str) -> str:
    """The protocol identity a task declares.

    Raises:
        ProtocolError: the task is not declared. Identity is read, never guessed from the task
            id or the entry point path.
    """
    route = (declaration().get("tasks") or {}).get(task_id)
    if not isinstance(route, dict) or "protocol" not in route:
        raise ProtocolError(f"{task_id}: no protocol declared for this task")
    return route["protocol"]


def groups_for(task_id: str) -> dict:
    """The declared layout of a task's protocol: group name -> terms, order included.

    Raises:
        ProtocolError: the task is undeclared, or names a protocol the declaration omits.
    """
    key = protocol_for(task_id)
    entry = (declaration().get("protocols") or {}).get(key)
    if not isinstance(entry, dict) or not isinstance(entry.get("groups"), dict):
        raise ProtocolError(f"{task_id}: protocol {key} has no groups in the declaration")
    return entry["groups"]


def terms_for(task_id: str, group: str) -> list[str]:
    """The declared term order of one group.

    Raises:
        ProtocolError: the task declares no such group, or the group is dropped there (a
            dropped group has no terms to hand out).
    """
    groups = groups_for(task_id)
    if group not in groups:
        raise ProtocolError(f"{task_id}: protocol declares no group {group!r}; has {sorted(groups)}")
    entry = groups[group]
    if entry.get("dropped"):
        raise ProtocolError(f"{task_id}: group {group!r} is dropped for this task")
    return list(entry.get("terms") or [])


def live_terms_for(task_id: str, group: str) -> list[str]:
    """The terms a group actually carries: the declared order minus the dropped ones.

    A dropped term is still part of the declaration -- it says the cfg had a term there and
    took it away -- while the manager sees only the live ones. Both questions are asked, so
    both answers are available from one place.

    Raises:
        ProtocolError: as :func:`terms_for`.
    """
    groups = groups_for(task_id)
    terms = terms_for(task_id, group)
    dropped = set(groups[group].get("dropped_terms") or [])
    return [term for term in terms if term not in dropped]


def anchors() -> dict:
    """The approved facts about each protocol: digest, widths, label, purpose.

    Read from the same file the gate reads and never writes: approving a digest or a width is
    a separate, deliberate act, and a module that could refresh them would approve anything it
    happened to load.

    Raises:
        ProtocolError: the file is missing or unreadable.
    """
    try:
        return json.loads(ANCHORS.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as err:
        raise ProtocolError(f"cannot read {ANCHORS}: {err}") from err


def recorded_dims(task_id: str) -> dict[str, int] | None:
    """The approved per-group widths FOR THIS TASK, or ``None`` when unapproved.

    Keyed by the asset first, because a protocol identity is the layout (groups, term order,
    clip/scale/noise) and says nothing about how wide a joint vector is, so two assets with
    different joint counts legitimately share one protocol while building different widths
    (lizard 26 joints / policy 90, lizard2 30 joints / policy 102 -- measured 2026-09-22). Keyed
    per protocol, the second one would be compared against the first one's number forever. This
    is the same reasoning as :func:`runtime_joint_order_for_asset`: the fact belongs to the asset
    a recipe loads.

    The asset is not always enough: two versions of one family load one asset under one layout
    while their ACTION interfaces differ, so they build different widths (lizard2 v1 commands the
    blades / policy 102, v2 does not / 98 -- measured 2026-09-28). A task layer, where a protocol
    carries one, is the narrower claim and is preferred; every task that does not need it keeps
    reading the asset's number.

    ``None`` and ``{}`` mean different things -- unmeasured versus measured-and-empty -- so the
    caller can tell "nobody has looked" from "there is nothing there".
    """
    key = protocol_for(task_id)
    entry = (anchors().get("protocols") or {}).get(key)
    if not isinstance(entry, dict):
        return None
    by_task = (entry.get("dims_by_task") or {}).get(task_id)
    if isinstance(by_task, dict) and by_task:
        return dict(by_task)
    by_asset = entry.get("dims")
    asset = usd_path(task_id)
    dims = (by_asset or {}).get(asset) if isinstance(by_asset, dict) and asset else None
    return dict(dims) if isinstance(dims, dict) and dims else None


# ---------------------------------------------------------------------------------------------
# The body a recipe loads: its usd, its urdf, and the meshes that urdf references.
#
# One implementation for the three callers that need it -- the asset lock builder, the joint-layout
# probe and the contact-ownership probe -- because two of them used to derive the family from the
# spawn path's parent directory and re-invent the urdf lookup, which is how a new body ends up
# paired with the old family's URDF. The recipe's declared ``usd_path`` is the entry, always.
# ---------------------------------------------------------------------------------------------


def urdf_refs(urdf: pathlib.Path) -> list[pathlib.Path]:
    """Where a URDF's mesh references resolve, relative to the URDF's own directory.

    Parsed as XML rather than matched with a pattern: a regex expecting ``<mesh filename="…"`` reads
    a URDF written with single quotes, or with the attributes in another order, as a body with NO
    meshes -- and "no meshes" is the answer every caller treats as clean, so a mesh could change with
    nothing noticing. Tags are matched by local name, so a namespace cannot hide them either.

    Raises:
        ProtocolError: the file exists but is not readable XML. Refused rather than answered with an
            empty list: an unparsed URDF is not a body without meshes.
    """
    if not urdf.is_file():
        return []
    try:
        root = ET.fromstring(urdf.read_text(encoding="utf-8"))
    except (OSError, ET.ParseError) as err:
        raise ProtocolError(f"{urdf}: not readable URDF XML ({err})") from err
    refs: list[pathlib.Path] = []
    for element in root.iter():
        if element.tag.rpartition("}")[2] != "mesh":
            continue
        name = element.get("filename")
        if name:
            refs.append(urdf.parent / name)
    return refs


def _rl_exp() -> pathlib.Path:
    """The ``rl_exp`` base that declared asset paths are relative to (``assets/...``, ``versions/...``)."""
    return DECLARATION.parents[1]


def _key(path: pathlib.Path, base: pathlib.Path, what: str) -> str:
    """The path as a repo-relative key, refusing anything that resolves outside ``rl_exp``."""
    resolved = path.resolve()
    if resolved != base and base not in resolved.parents:
        raise ProtocolError(f"{what} {path} resolves outside {base}")
    return str(resolved.relative_to(base)).replace("\\", "/")


def resolve_urdf(usd: pathlib.Path, family: str, base: pathlib.Path | None = None) -> pathlib.Path:
    """The URDF of the body a usd belongs to.

    Two shapes, one rule. A body in its own directory carries ``<stem>.urdf`` beside its usda. The
    legacy layout is ``assets/<family>/<family>.usda`` with ``versions/<family>/<family>.urdf``, and
    that fallback applies to THAT usd path only: anywhere else a usda with no urdf beside it is
    refused, because pairing a new body with the family's old URDF is precisely the mismatch a lock
    would then pin as the body the version loads.

    Raises:
        ProtocolError: no urdf can be resolved for this usd.
    """
    base = base or _rl_exp()
    beside = usd.parent / f"{usd.stem}.urdf"
    if beside.is_file():
        return beside
    if usd.resolve() == (base / "assets" / family / f"{family}.usda").resolve():
        legacy = base / "versions" / family / f"{family}.urdf"
        if legacy.is_file():
            return legacy
        raise ProtocolError(f"{family}: the declared legacy usd {usd.name} has no "
                            f"versions/{family}/{family}.urdf either")
    raise ProtocolError(f"{family}: {usd} is not the declared legacy usd and has no <stem>.urdf "
                        "beside it -- a body in its own directory must ship its own URDF")


def resolve_body(usd_rel: str, family: str, base: pathlib.Path | None = None) -> dict:
    """The files a declared body is made of: its usd, its urdf, and the meshes the urdf references.

    Args:
        usd_rel: the recipe's ``usd_path``, relative to ``rl_exp``.
        family: the family the recipe belongs to (the legacy-shape fallback is keyed by it).
        base: ``rl_exp`` to resolve against; defaults to the real tree.

    Returns:
        ``{"usd": Path, "urdf": Path, "refs": [Path], "keys": [str]}`` -- the paths resolved, and the
        same set spelled as repo-relative keys (the spelling the asset locks use).

    Raises:
        ProtocolError: the usd is missing, resolves outside ``rl_exp``, has no urdf, or a mesh
            reference lands outside it.
    """
    base = base or _rl_exp()
    usd = base / usd_rel
    if not usd.is_file():
        raise ProtocolError(f"{usd_rel} is not on disk (under {base})")
    urdf = resolve_urdf(usd, family, base)
    keys = [_key(usd, base, "usd"), _key(urdf, base, "urdf")]
    refs: list[pathlib.Path] = []
    for ref in urdf_refs(urdf):
        keys.append(_key(ref, base, "mesh reference"))
        refs.append(ref.resolve())
    return {"usd": usd.resolve(), "urdf": urdf.resolve(), "refs": refs, "keys": sorted(set(keys))}


def body_for_task(task_id: str, base: pathlib.Path | None = None) -> dict:
    """The body a task's recipe loads: the route names the line, the line's recipe names the usd.

    One path from a task id to files, shared by the tools that used to derive a family from the spawn
    path's parent directory. Same return shape as :func:`resolve_body`.

    Raises:
        ProtocolError: the task is undeclared, its recipe declares no ``usd_path``, or the body
            cannot be resolved.
    """
    route = task_route(task_id)
    line = route.get("line")
    if not isinstance(line, str) or not line:
        raise ProtocolError(f"{task_id}: no line declared, so no body to resolve")
    usd_rel = usd_path_for_route(line, route.get("version"))
    if not usd_rel:
        raise ProtocolError(f"{task_id}: its recipe declares no usd_path")
    return resolve_body(usd_rel, line.split("/")[0], base)


def _joint_names_module():
    """Load the shared stdlib table without importing the task registry."""
    spec = importlib.util.spec_from_file_location("diagnostic_joint_names", pathlib.Path(__file__).with_name("joint_names.py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_diagnostic_target(path, cfg, task, *, naming_override=None, usd_override=None,
                           urdf_override=None) -> dict:
    """Bind an instantiated diagnostic cfg to a declared USD/URDF pair.

    Manifest paths are absolute or relative to ``rl_exp``. ``config`` contains existing
    dotted cfg fields, never classes or callables; action joint lists and ``joint_order``
    must be explicit. No recipe, registry, protocol or lock is written.
    """
    names = _joint_names_module()
    base = _rl_exp().resolve()
    family = family_of(task)
    if not family:
        raise ProtocolError(f"{task}: no declared family")

    def real(value):
        if not isinstance(value, (str, pathlib.Path)) or not str(value):
            raise ProtocolError(f"{task}: missing file path {value!r}")
        candidate = pathlib.Path(value)
        if not candidate.is_absolute() and candidate.parts and candidate.parts[0] == "rl_exp":
            return (base.parent / candidate).resolve()
        return (candidate if candidate.is_absolute() else base / candidate).resolve()

    actual = real(cfg.scene.robot.spawn.usd_path)
    original = body_for_task(task)
    document = None
    if path is not None:
        source = pathlib.Path(path).resolve()
        try:
            document = json.loads(source.read_text(encoding="utf-8"))
        except (OSError, ValueError) as err:
            raise ProtocolError(f"{source}: cannot read diagnostic manifest: {err}") from err
        if not isinstance(document, dict):
            raise ProtocolError(f"{source}: manifest must be an object")
        binding = dict(document.get("target_binding", document))
        if binding.get("task") != task:
            raise ProtocolError(f"{source}: task {binding.get('task')!r} != {task!r}")
        if real(binding.get("source")) != source:
            raise ProtocolError(f"{source}: target_binding.source must name this manifest")
        naming = names.naming_from_binding(binding)
        target = real(binding.get("target"))
        key = _key(target, base, "diagnostic USD")
        if key.split("/")[0] not in ("assets", "out"):
            raise ProtocolError(f"{source}: diagnostic USD must be isolated under assets/ or out/")
        body = resolve_body(key, family, base)
        if real(binding.get("urdf")) != body["urdf"]:
            raise ProtocolError(f"{source}: USD/URDF pair differs from resolved {body['urdf']}")
        if body["urdf"].parent != body["usd"].parent:
            raise ProtocolError(f"{source}: diagnostic URDF must be colocated with USD")
        for ref in body["refs"]:
            if not ref.is_file():
                raise ProtocolError(f"{source}: missing mesh file {ref}")
        for field, digest in document.get("sha256", {}).items():
            if field not in ("target", "urdf") or not isinstance(digest, str):
                raise ProtocolError(f"{source}: invalid sha256 field {field!r}")
            if file_binding.sha256_file(real(binding[field])) != digest:
                raise ProtocolError(f"{source}: {field} sha256 mismatch")
    else:
        if actual != original["usd"]:
            raise ProtocolError(f"{task}: cfg USD {actual} differs from declared {original['usd']}")
        body = original
        params = _params_document(task)
        if params is None:
            raise ProtocolError(f"{task}: no parameters document for target binding source")
        naming = names.naming_for(params[0].get("robot", {}).get("naming", "shared"))
        binding = names.binding_for_target(str(body["usd"]), str(params[1]), naming)
        binding.update(task=task, urdf=str(body["urdf"]))
    if naming_override is not None and names.naming_id(naming) != naming_override:
        raise ProtocolError(f"{task}: --naming {naming_override} disagrees with target {names.naming_id(naming)}")
    for override, field in ((usd_override, "usd"), (urdf_override, "urdf")):
        if override is not None and real(override) != body[field]:
            raise ProtocolError(f"{task}: raw {field} override differs from declared pair; use --target_config")

    tree = ET.parse(body["urdf"]).getroot()
    joints = [joint.get("name") for joint in tree.findall("joint") if joint.get("type") != "fixed"]
    names.validate_joint_names(joints, naming, target=str(body["urdf"]),
                               expected=binding.get("joint_names") if document is not None else None)
    if document is not None and "joint_names" not in binding:
        raise ProtocolError(f"{path}: target_binding needs exact joint_names")
    links = [link.get("name") for link in tree.findall("link")]
    if len(set(links)) != len(links):
        raise ProtocolError(f"{body['urdf']}: duplicate links")
    by_child = {}
    for joint in tree.findall("joint"):
        child = joint.find("child").get("link")
        if child in by_child:
            raise ProtocolError(f"{body['urdf']}: duplicate parent joints for {child}")
        by_child[child] = joint
    for leg in names.LEGS:
        end = names.end_link(leg, naming)
        parent_joint = names.joint_name(leg, names.roots_of(naming, leg)[-1])
        if end not in links or end not in by_child or by_child[end].get("name") != parent_joint:
            raise ProtocolError(f"{body['urdf']}: {end} must be child of {parent_joint}")
        cursor, chain = end, []
        while cursor in by_child:
            if cursor in chain:
                raise ProtocolError(f"{body['urdf']}: cycle at {cursor}")
            chain.append(cursor)
            cursor = by_child[cursor].find("parent").get("link")
        for root in names.roots_of(naming, leg):
            joint = names.joint_name(leg, root)
            if joint not in joints and names.naming_id(naming) == "shared" and root == "hip":
                continue  # legacy lizard has no root swing joint
            if joint not in joints or names.link_name(leg, root) not in chain:
                raise ProtocolError(f"{body['urdf']}: missing/disconnected role {leg}/{root}")
    if document is None:
        binding = names.binding_for_target(str(body["usd"]), binding["source"], naming, joint_names=joints)
        binding.update(task=task, urdf=str(body["urdf"]))
    declared_urdf_joints = binding.get("joint_names")
    binding.update(target=str(body["usd"]), urdf=str(body["urdf"]),
                   joint_names=list(declared_urdf_joints) if declared_urdf_joints is not None else joints)

    if document is not None:
        import copy

        payload = document.get("config", {})
        if not isinstance(payload, dict):
            raise ProtocolError(f"{path}: config must be an object of dotted cfg fields")
        order = document.get("joint_order")
        if order != joints:
            raise ProtocolError(f"{path}: joint_order must explicitly list exact URDF joint names in URDF order")
        runtime_order = document.get("runtime_joint_order")
        if runtime_order is not None and (not isinstance(runtime_order, list)
                or len(runtime_order) != len(joints) or set(runtime_order) != set(joints)):
            raise ProtocolError(f"{path}: runtime_joint_order must list exact URDF joint names")
        draft = copy.deepcopy(cfg)
        old_joints = [j.get("name") for j in ET.parse(original["urdf"]).getroot().findall("joint")
                      if j.get("type") != "fixed"]
        old_links = [link.get("name") for link in ET.parse(original["urdf"]).getroot().findall("link")]
        mapping = {}
        for leg in names.LEGS:
            for role, new_root in binding["roles"][leg].items():
                old_root = role
                mapping[names.joint_name(leg, old_root)] = names.joint_name(leg, new_root)
                mapping[names.link_name(leg, old_root)] = names.link_name(leg, new_root)

        def remap(value, pool):
            if isinstance(value, str):
                if value in mapping:
                    return mapping[value]
                matched = [name for name in pool if re.fullmatch(value, name)]
                if any(name in mapping for name in matched):
                    return [mapping.get(name, name) for name in matched]
                return value
            if isinstance(value, (list, tuple)):
                out = []
                for item in value:
                    changed = remap(item, pool)
                    out.extend(changed if isinstance(changed, list) else [changed])
                return out
            if isinstance(value, dict):
                out = {}
                for key, item in value.items():
                    keys = remap(key, pool)
                    for changed in keys if isinstance(keys, list) else [keys]:
                        if changed in out:
                            raise ProtocolError(f"{path}: remapping duplicates {changed}")
                        out[changed] = item
                return out
            return value

        seen = set()

        def visit(value):
            if id(value) in seen:
                return
            seen.add(id(value))
            fields = value if isinstance(value, dict) else vars(value) if hasattr(value, "__dict__") else {}
            for field, item in list(fields.items()):
                if field.startswith("_") or callable(item):
                    continue
                if field in ("joint_pos", "joint_vel", "joint_names", "joint_names_expr", "scale",
                             "stiffness", "damping", "effort_limit", "velocity_limit", "armature",
                             "body_names"):
                    changed = remap(item, old_links if field == "body_names" else old_joints)
                    if isinstance(value, dict):
                        value[field] = changed
                    else:
                        setattr(value, field, changed)
                elif field == "prim_path" and isinstance(item, str):
                    prefix, separator, leaf = item.rpartition("/")
                    if leaf in mapping:
                        setattr(value, field, prefix + separator + mapping[leaf])
                    elif any(re.fullmatch(leaf, name) and name in mapping for name in old_links):
                        selected = remap(leaf, old_links)
                        setattr(value, field, prefix + separator + "(" + "|".join(map(re.escape, selected)) + ")")
                elif isinstance(item, (list, tuple)):
                    for child in item:
                        visit(child)
                elif isinstance(item, dict) or hasattr(item, "__dict__"):
                    visit(item)

        for section in ("scene", "actions", "observations", "rewards", "terminations", "events"):
            visit(getattr(draft, section, None))
        for dotted, value in payload.items():
            parts = dotted.split(".")
            if len(parts) < 2 or parts[0] not in ("scene", "actions", "observations", "rewards", "terminations", "events") or any(p.startswith("_") for p in parts):
                raise ProtocolError(f"{path}: unsupported config field {dotted}")
            obj = draft
            for part in parts[:-1]:
                obj = obj[part] if isinstance(obj, dict) else getattr(obj, part)
            field = parts[-1]
            prior = obj[field] if isinstance(obj, dict) else getattr(obj, field)
            if callable(prior) or field in ("func", "class_type", "usd_path"):
                raise ProtocolError(f"{path}: config cannot replace {dotted}")
            if isinstance(obj, dict):
                obj[field] = value
            else:
                setattr(obj, field, value)
        def validate_fields(value):
            fields = value if isinstance(value, dict) else vars(value) if hasattr(value, "__dict__") else {}
            for field, item in fields.items():
                if field.startswith("_") or callable(item):
                    continue
                if field in ("joint_pos", "joint_vel", "joint_names", "joint_names_expr", "body_names"):
                    patterns = list(item) if isinstance(item, (dict, list, tuple)) else [item] if isinstance(item, str) else []
                    pool = links if field == "body_names" else joints
                    for pattern in patterns:
                        if not isinstance(pattern, str) or not any(re.fullmatch(pattern, name) for name in pool):
                            raise ProtocolError(f"{path}: {field} selection {pattern!r} matches no target name; provide config")
                elif isinstance(item, dict) or hasattr(item, "__dict__"):
                    validate_fields(item)
        for section in ("scene", "actions", "observations", "rewards", "terminations", "events"):
            validate_fields(getattr(draft, section, None))
        for term_name, term in vars(draft.actions).items():
            if term is None or not hasattr(term, "joint_names"):
                continue
            dotted = f"actions.{term_name}.joint_names"
            if dotted not in payload or not isinstance(term.joint_names, list) or not term.joint_names:
                raise ProtocolError(f"{path}: explicit nonempty {dotted} required (cancel whole terms with null)")
            names.validate_joint_names(term.joint_names, naming, target=dotted)
            if not set(term.joint_names) <= set(joints):
                raise ProtocolError(f"{path}: {dotted} names absent joints")
        draft.scene.robot.spawn.usd_path = str(body["usd"])
        cfg.__dict__.update(draft.__dict__)
        binding["joint_order"] = list(order)
        binding["runtime_joint_order"] = document.get("runtime_joint_order")
    print(f"DIAGNOSTIC_TARGET task={task} target={binding['target']} urdf={binding['urdf']} source={binding['source']} naming={names.naming_id(naming)}")
    return binding


def validate_diagnostic_runtime(binding, cfg, robot, sensor, manager) -> None:
    """Validate exact live joints, four feet and ordered action channels before measuring."""
    names = _joint_names_module()
    naming = names.naming_from_binding(binding)
    names.validate_joint_names(list(robot.joint_names), naming, target=binding["target"],
                               expected=binding["joint_names"])
    expected = set(names.contact_body_names(naming))
    for label, bodies in (("robot", list(robot.body_names)), ("sensor", list(sensor.body_names))):
        allowed_links = {names.link_name(leg, root) for leg in names.LEGS
                         for root in names.roots_of(naming, leg)}
        end_roots = {names.roots_of(naming, leg)[-1] for leg in names.LEGS}
        foreign = [body for body in bodies if (body.split("_", 1)[0] in names.LEGS
                   and body not in allowed_links) or (any(body.endswith("_" + root) for root in end_roots)
                   and body not in expected)]
        if foreign:
            raise ProtocolError(f"{binding['target']}: {label} foreign/cross-limb bodies {foreign}")
        feet = [name for name in bodies if names.is_contact_body_bound(name, naming)]
        if len(set(bodies)) != len(bodies) or len(feet) != 4 or set(feet) != expected:
            raise ProtocolError(f"{binding['target']}: {label} feet {feet} != {sorted(expected)}")
    if not set(sensor.body_names) <= set(robot.body_names):
        raise ProtocolError(f"{binding['target']}: sensor contains foreign bodies")
    carried = []
    for term_name in manager.active_terms:
        term = manager.get_term(term_name)
        term_cfg = getattr(cfg.actions, term_name)
        declared = term_cfg.joint_names
        patterns = [declared] if isinstance(declared, str) else declared
        if all(pattern in robot.joint_names for pattern in patterns) and getattr(term_cfg, "preserve_order", False):
            expected_channels = list(patterns)
        else:
            expected_channels = [name for name in robot.joint_names if any(re.fullmatch(p, name) for p in patterns)]
        actual = list(term._joint_names)
        if not patterns or not actual or actual != expected_channels:
            raise ProtocolError(f"{binding['target']}: {term_name} channels {actual} != nonempty cfg {expected_channels}")
        carried.extend(actual)
    names.validate_joint_names(carried, naming, target=binding["target"] + " action channels")
    if len(carried) != manager.total_action_dim or not set(carried) <= set(robot.joint_names):
        raise ProtocolError(f"{binding['target']}: action dimension/joint mismatch")
    order = binding.get("runtime_joint_order")
    if order is not None and list(robot.joint_names) != order:
        raise ProtocolError(f"{binding['target']}: runtime joint order differs from manifest")


def diagnostic_target_self_check() -> None:
    """Offline loader regression: paired renamed trees, cfg remap and rejection paths."""
    import copy
    import tempfile
    from types import SimpleNamespace as NS
    from unittest.mock import patch

    names = _joint_names_module()
    with tempfile.TemporaryDirectory(prefix="diagnostic_target_") as folder:
        base = pathlib.Path(folder)

        def body(naming_id):
            naming = names.naming_for(naming_id)
            directory = base / "assets" / naming_id
            directory.mkdir(parents=True)
            usd = directory / f"{naming_id}.usda"
            usd.write_text("#usda 1.0\n", encoding="utf-8")
            tree = ET.Element("robot", name=naming_id)
            ET.SubElement(tree, "link", name="base_link")
            joints = []
            for leg in names.LEGS:
                parent = "base_link"
                for root in names.roots_of(naming, leg):
                    child = names.link_name(leg, root)
                    ET.SubElement(tree, "link", name=child)
                    joint_name = names.joint_name(leg, root)
                    joints.append(joint_name)
                    joint = ET.SubElement(tree, "joint", name=joint_name, type="revolute")
                    ET.SubElement(joint, "parent", link=parent)
                    ET.SubElement(joint, "child", link=child)
                    parent = child
            urdf = usd.with_suffix(".urdf")
            ET.ElementTree(tree).write(urdf, encoding="unicode")
            return usd, urdf, joints

        original_usd, original_urdf, old_joints = body("shared")
        cfg = NS(scene=NS(robot=NS(spawn=NS(usd_path=str(original_usd)),
                 init_state=NS(joint_pos={".*_haa_joint": 0.2}),
                 actuators={"legs": NS(joint_names_expr=[".*_hfe_joint"])}),
                 foot_sensor=NS(prim_path="{ENV_REGEX_NS}/Robot/lf_foot")),
                 actions=NS(legs=NS(joint_names=old_joints, scale=0.5, preserve_order=True)))
        original = {"usd": original_usd, "urdf": original_urdf}
        params_path = base / "fixture_params.yaml"
        with patch.dict(globals(), _rl_exp=lambda: base, family_of=lambda task: "lizard2",
                        body_for_task=lambda task: original,
                        _params_document=lambda task: ({"robot": {"usd_path": str(original_usd)}}, params_path)):
            bound = load_diagnostic_target(None, copy.deepcopy(cfg), "fixture")
            assert bound["joint_names"] == old_joints
            assert bound["source"] == str(params_path)
            count = 0
            for naming_id in ("shared", "split", "palm"):
                usd, urdf, joints = (original_usd, original_urdf, old_joints) if naming_id == "shared" else body(naming_id)
                manifest = base / f"{naming_id}.json"
                binding = names.binding_for_target(str(usd), str(manifest), names.naming_for(naming_id), joint_names=joints)
                binding.update(task="fixture", urdf=str(urdf))
                document = {"target_binding": binding, "joint_order": joints,
                            "runtime_joint_order": joints,
                            "config": {"actions.legs.joint_names": joints}}
                if naming_id == "palm":
                    document["config"]["scene.foot_sensor.prim_path"] = "{ENV_REGEX_NS}/Robot/lf_wrist"
                manifest.write_text(json.dumps(document), encoding="utf-8")
                target_cfg = copy.deepcopy(cfg)
                loaded = load_diagnostic_target(manifest, target_cfg, "fixture")
                assert target_cfg.scene.robot.spawn.usd_path == str(usd)
                assert target_cfg.scene.foot_sensor.prim_path.endswith(names.end_link("lf", names.naming_for(naming_id)))
                assert cfg.scene.robot.spawn.usd_path == str(original_usd)
                robot = NS(joint_names=joints, body_names=["base_link", *names.contact_body_names(names.naming_for(naming_id))])
                sensor = NS(body_names=list(reversed(robot.body_names)))
                manager = NS(active_terms=["legs"], total_action_dim=len(joints), get_term=lambda _: NS(_joint_names=joints))
                validate_diagnostic_runtime(loaded, target_cfg, robot, sensor, manager)
                mutations = [lambda d: d["target_binding"].update(task="wrong"),
                             lambda d: d["target_binding"].update(source=str(base / "wrong.json")),
                             lambda d: d["target_binding"].update(urdf=str(original_urdf) if naming_id != "shared" else str(base / "wrong.urdf")),
                             lambda d: d["target_binding"].update(joint_names=joints[:-1]),
                             lambda d: d["config"].clear(),
                             lambda d: d["config"].update({"actions.legs.joint_names": []}),
                             lambda d: d.update(joint_order=joints[:-1]),
                             lambda d: d.update(joint_order=list(reversed(joints)))]
                for mutate in mutations:
                    bad = copy.deepcopy(document)
                    mutate(bad)
                    manifest.write_text(json.dumps(bad), encoding="utf-8")
                    try:
                        load_diagnostic_target(manifest, copy.deepcopy(cfg), "fixture")
                    except (ValueError, KeyError):
                        count += 1
                    else:
                        raise AssertionError("malformed manifest accepted")
                manifest.write_text(json.dumps(document), encoding="utf-8")
                urdf_text = urdf.read_text(encoding="utf-8")
                for defect in ("duplicate_parent", "duplicate_link"):
                    broken_tree = ET.fromstring(urdf_text)
                    if defect == "duplicate_parent":
                        duplicate = copy.deepcopy(broken_tree.find("joint"))
                        duplicate.set("name", "duplicate_parent_fixed")
                        duplicate.set("type", "fixed")
                    else:
                        duplicate = copy.deepcopy(broken_tree.find("link"))
                    broken_tree.insert(0, duplicate)
                    ET.ElementTree(broken_tree).write(urdf, encoding="unicode")
                    try:
                        load_diagnostic_target(manifest, copy.deepcopy(cfg), "fixture")
                    except ValueError:
                        count += 1
                    else:
                        raise AssertionError(f"{defect} accepted")
                    finally:
                        urdf.write_text(urdf_text, encoding="utf-8")
                for bad in ([], joints + [joints[0]], joints + ["lf_foreign_joint"]):
                    bad_cfg = copy.deepcopy(target_cfg)
                    bad_cfg.actions.legs.joint_names = bad
                    bad_manager = NS(active_terms=["legs"], total_action_dim=len(bad),
                                     get_term=lambda _, carried=bad: NS(_joint_names=carried))
                    try:
                        validate_diagnostic_runtime(loaded, bad_cfg, robot, sensor, bad_manager)
                    except ValueError:
                        count += 1
                    else:
                        raise AssertionError("empty/duplicate/foreign action selection accepted")
                sensor.body_names.remove(names.end_link("lf", names.naming_for(naming_id)))
                try:
                    validate_diagnostic_runtime(loaded, target_cfg, robot, sensor, manager)
                except ValueError:
                    count += 1
                else:
                    raise AssertionError("incomplete sensor accepted")
            for options in ({"usd_override": str(base / "wrong.usda")}, {"naming_override": "split"}):
                try:
                    load_diagnostic_target(None, copy.deepcopy(cfg), "fixture", **options)
                except ValueError:
                    count += 1
                else:
                    raise AssertionError("unbound override accepted")
            assert count == 44, count
    print("DIAGNOSTIC_TARGET_SELF_CHECK_OK: shared/split/palm cfg and runtime; 44 negatives")


def dims_for(task_id: str) -> dict[str, int]:
    """The approved per-group widths a smoke assertion may compare against.

    Raises:
        ProtocolError: this task's asset has no approved widths. Asserting against an invented
            width is worse than not asserting: it fails the tree for being right.
    """
    dims = recorded_dims(task_id)
    if dims is None:
        raise ProtocolError(
            f"{task_id}: no approved dims for this protocol on {usd_path(task_id)!r}; a real run "
            "has to measure them first"
        )
    return dims


def feet_for(task_id: str, group: str = "extero") -> tuple[str, ...]:
    """The foot order a task's ring group encodes, derived from its term names.

    Derived rather than declared twice: the extero group's terms *are* the feet in order, so a
    second list would be a second place to keep in step. Every term must carry the ring suffix,
    and the group must hold one term per foot.

    Raises:
        ProtocolError: a term does not match the ring naming, so the order cannot be read.
    """
    terms = terms_for(task_id, group)
    feet: list[str] = []
    for term in terms:
        if not term.endswith(_FOOT_SUFFIX):
            raise ProtocolError(f"{task_id}: group {group!r} term {term!r} is not a ring term; foot order cannot be read")
        feet.append(term[: -len(_FOOT_SUFFIX)])
    if len(set(feet)) != len(feet):
        raise ProtocolError(f"{task_id}: group {group!r} repeats a foot: {feet}")
    return tuple(feet)
