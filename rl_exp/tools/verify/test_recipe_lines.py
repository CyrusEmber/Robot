# -*- coding: utf-8 -*-
"""Negative control for recipe_lines.discover: every refusal must actually fire.

The gate's value is not "it finds the yaml" -- it is "an unrecognised tree is an error
instead of a silent skip", so each convention violation is tampered for explicitly and
must raise. A discovery entry whose leniency modes were never demonstrated is how the
three previous copies drifted apart in the first place.
"""

import json
import pathlib
import sys
import tempfile

sys.path.insert(0, ".")
sys.path.insert(0, "rl_exp/tools/verify")
from recipe_lines import RecipeLineError, discover  # noqa: E402

PROBLEMS: list[str] = []


def check(name: str, ok: bool, detail: str = "") -> None:
    print(f"  {'ok  ' if ok else 'FAIL'} {name}{'' if ok else f': {detail}'}")
    if not ok:
        PROBLEMS.append(f"{name}: {detail}")


def _make_tree(root: pathlib.Path, lines: dict[str, list[str]]) -> pathlib.Path:
    """Build ``versions/<key>/<key_leaf>_params.yaml`` plus one yaml per version dir."""
    for key, versions in lines.items():
        line_root = root.joinpath(*key.split("/"))
        line_root.mkdir(parents=True, exist_ok=True)
        (line_root / f"{line_root.name}_params.yaml").write_text("x: 1\n", encoding="utf-8")
        for version in versions:
            version_dir = line_root / version
            version_dir.mkdir(exist_ok=True)
            (version_dir / f"{line_root.name}_params.yaml").write_text("x: 1\n", encoding="utf-8")
    return root


def _refuses(name: str, root: pathlib.Path, keyword: str) -> None:
    try:
        discover(root)
    except RecipeLineError as err:
        check(name, keyword in str(err), f"raised without {keyword!r}: {err}")
        return
    check(name, False, "no error raised")


def main() -> int:
    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = pathlib.Path(tmp)

        # --- happy path: main line + side line, numeric version order -------------
        # Keys are family-relative paths, so the main line is "lizard/main": since the
        # layout move it lives in its own directory like any other line.
        root = _make_tree(tmp_path / "ok", {"lizard/main": ["v10", "v2"], "lizard/parkour": ["v1"]})
        lines = discover(root)
        check("ok/line-keys", sorted(lines) == ["lizard/main", "lizard/parkour"], f"{sorted(lines)}")
        check(
            "ok/version-order-numeric",
            list(lines["lizard/main"].versions) == ["v2", "v10"],
            f"{list(lines['lizard/main'].versions)}",
        )
        check("ok/side-line-own-yaml", lines["lizard/parkour"].dev_yaml.name == "parkour_params.yaml")
        check("ok/main-line-own-yaml", lines["lizard/main"].dev_yaml.name == "main_params.yaml")
        check(
            "ok/lock-is-per-line",
            lines["lizard/main"].lock_path.name == "cfg_lock.json"
            and lines["lizard/main"].lock_path.parent != lines["lizard/parkour"].lock_path.parent,
            "two lines resolved to the same lock file",
        )

        # --- a non-version subdirectory is not a line ----------------------------
        (tmp_path / "ok" / "lizard" / "docs").mkdir()
        check("ok/plain-subdir-not-a-line", sorted(discover(root)) == ["lizard/main", "lizard/parkour"])

        # --- refusals ------------------------------------------------------------
        _refuses("refuse/absent-versions-dir", tmp_path / "nope", "does not exist")

        zero = _make_tree(tmp_path / "zero", {"lizard/main": ["v1"]})
        (zero / "lizard" / "main" / "main_params.yaml").unlink()
        _refuses("refuse/no-params-at-line-root", zero, "no *")

        two = _make_tree(tmp_path / "two", {"lizard/main": ["v1"]})
        (two / "lizard" / "main" / "other_params.yaml").write_text("x: 1\n", encoding="utf-8")
        _refuses("refuse/two-params-at-line-root", two, "exactly one")

        two_versions = _make_tree(tmp_path / "twover", {"lizard/main": ["v1"]})
        (two_versions / "lizard" / "main" / "v1" / "main_params.yaml").unlink()
        _refuses("refuse/no-frozen-yaml", two_versions, "no *")

        renamed = _make_tree(tmp_path / "renamed", {"lizard/main": ["v1"]})
        (renamed / "lizard" / "main" / "main_params.yaml").rename(
            renamed / "lizard" / "main" / "main_v1_params.yaml"
        )
        _refuses("refuse/basename-names-its-line", renamed, "convention")

        # --- the move's own leftovers: the family directory is not a line ---------
        # Both shapes below are what a half-finished layout move leaves behind, and both
        # used to be a silent skip -- discovery simply never looked at them.
        stray = _make_tree(tmp_path / "stray", {"lizard/main": ["v1"]})
        (stray / "lizard" / "lizard_params.yaml").write_text("x: 1\n", encoding="utf-8")
        _refuses("refuse/stray-params-at-family-root", stray, "outside any line")

        loose_version = _make_tree(tmp_path / "loose", {"lizard/main": ["v1"]})
        (loose_version / "lizard" / "v9").mkdir()
        _refuses("refuse/version-dir-outside-a-line", loose_version, "outside any line")

    # --- the real tree: discovery and the lifecycle index must agree -------------
    # Not a hardcoded list of today's lines: what has to hold is that the filesystem and
    # the declared index name the SAME lines (the other direction -- every declared line
    # exists -- is the registry gate's job). A hardcoded list would need editing every
    # time a line is added, and would then assert nothing about agreement.
    real = discover()
    registry = json.loads(
        (pathlib.Path("rl_exp") / "versions" / "lines.json").read_text(encoding="utf-8")
    )["lines"]
    check("real/lines-match-registry", sorted(real) == sorted(registry), f"discovered {sorted(real)} vs declared {sorted(registry)}")
    check("real/main-line-has-versions", bool(real["lizard/main"].versions), "the main line discovered no versions")
    check(
        "real/version-handles-are-vN",
        all(name.startswith("v") and name[1:].isdigit() for line in real.values() for name in line.versions),
        "a discovered version handle is not v<N>",
    )
    check(
        "real/frozen-yamls-exist",
        all(path.is_file() for line in real.values() for path in line.versions.values()),
        "a discovered frozen yaml is missing on disk",
    )

    if PROBLEMS:
        print(f"RECIPE_LINES_GATE_FAILED ({len(PROBLEMS)})")
        return 1
    print("RECIPE_LINES_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
