# -*- coding: utf-8 -*-
"""Params loaders must hand each caller its own document.

Why this is a gate and not a convention: a cfg construction runs a chain of
``__post_init__`` that each re-read the same yaml, so the loader caches the *parsed*
document (``document``, keyed by path + mtime + size) -- that cache is what makes
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

from rl_exp.tasks import recipe_params  # noqa: E402

PROBE = "__isolation_probe__"


def _poison(document: dict) -> str | None:
    """Edit one nested mapping in place; returns the key it sat under, None if there is none."""
    for key, value in document.items():
        if isinstance(value, dict):
            value[PROBE] = "poisoned"
            return key
    return None


def _probe(line: str, version: str | None, label: str) -> None:
    """One line load: two reads must not be the same object, and an edit must not survive."""
    first = recipe_params.load(line, version)
    second = recipe_params.load(line, version)
    assert first is not second, f"{label}: two loads handed out the same object"

    key = _poison(first)
    assert key is not None, f"{label}: no nested mapping to probe -- the fixture went stale"
    fresh = recipe_params.load(line, version)
    assert PROBE not in fresh[key], (
        f"{label}: a caller's edit to its own document appeared in the next load -- the cache "
        f"is handing out the parsed document, so every cfg in this process shares one tree"
    )
    print(f"  ok {label}: each load is its own document")


def main() -> int:
    # ``recipe_params`` is the one loader left (``lizard2_env_cfg`` reaches its parameters through
    # it), and these are the two shapes a caller can ask for: a frozen version, and the line's own
    # live dev yaml -- the file whose edits the mtime-keyed cache has to notice.
    _probe("lizard2/main", "v3", "lizard2 frozen v3")
    _probe("lizard2/main", None, "lizard2 dev yaml")
    print("PARAMS_ISOLATION_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
