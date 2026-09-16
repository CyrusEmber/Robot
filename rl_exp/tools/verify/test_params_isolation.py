# -*- coding: utf-8 -*-
"""Params loaders must hand each caller its own document.

Why this is a gate and not a convention: a cfg construction runs a chain of
``__post_init__`` that each re-read the same yaml, so the loaders cache the *parsed*
document (``_params_document``, keyed by path + mtime + size) -- that cache is what makes
building a config cheap. What is frozen is the YAML file, not the Python object built from
it: returning the cached document itself would make every cfg in a process share one
mutable tree, and a single ``params[...] = ...`` anywhere would leak across versions and
tasks. The next load returning a clean document is the observable form of that contract.

Usage: python rl_exp\\tools\\verify\\test_params_isolation.py
"""
import pathlib
import sys

_REPO = pathlib.Path(__file__).absolute().parents[3]
sys.path.insert(0, str(_REPO))

from rl_exp.tasks import lizard_env_cfg, parkour_env_cfg, teacher_env_cfg  # noqa: E402

PROBE = "__isolation_probe__"


def _poison(document: dict) -> str | None:
    """Edit one nested mapping in place; returns the key it sat under, None if there is none."""
    for key, value in document.items():
        if isinstance(value, dict):
            value[PROBE] = "poisoned"
            return key
    return None


def _probe(loader, version, label: str) -> None:
    """One loader: two loads must not be the same object, and an edit must not survive."""
    first = loader(version)
    second = loader(version)
    assert first is not second, f"{label}: two loads handed out the same object"

    key = _poison(first)
    assert key is not None, f"{label}: no nested mapping to probe -- the fixture went stale"
    fresh = loader(version)
    assert PROBE not in fresh[key], (
        f"{label}: a caller's edit to its own document appeared in the next load -- the cache "
        f"is handing out the parsed document, so every cfg in this process shares one tree"
    )
    print(f"  ok {label}: each load is its own document")


def main() -> int:
    _probe(teacher_env_cfg._load_params, "v14", "teacher frozen v14")
    _probe(lizard_env_cfg._load_params, "v14", "family frozen v14")
    _probe(parkour_env_cfg._load_params, "v1", "parkour frozen v1")
    _probe(lizard_env_cfg._load_params, None, "family dev yaml")
    print("PARAMS_ISOLATION_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
