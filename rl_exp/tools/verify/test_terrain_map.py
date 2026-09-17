# -*- coding: utf-8 -*-
"""Offline gate for the one column-split rule and the split record (ARCH_PLAN 3.3b/3.3c).

Two things a curriculum may rely on, and one it may not:

* the split rule reproduces ``TerrainGenerator``'s curriculum split -- checked here against
  **hand-computed** column assignments, not against the rule itself;
* the record's sanity refusals all fire: an unknown sub-terrain, a dropped or duplicated cell,
  an index out of range, a random-mode record claiming columns, a curriculum record without
  them, a recorded pairing anomaly, and a captured cell that disagrees with the declared split;
* pairing is by cfg identity, so an ``_add_sub_terrain`` with nothing pending -- or with a cfg
  the generator never handed to the mesh builder -- is refused rather than matched to the
  nearest entry.

The negative direction is built in: every refusal is exercised on a record that is otherwise
valid, so a green run cannot come from a check that never fires.
"""

import pathlib
import sys

_REPO = pathlib.Path(__file__).resolve().parents[3]
# imported as a module, not as `rl_exp.tasks.terrain_map`: the package __init__ registers the
# gym tasks and would make this stdlib-only gate pay a framework import to test arithmetic
sys.path.insert(0, str(_REPO / "rl_exp" / "tasks"))

import terrain_map  # noqa: E402


class _Sub:
    def __init__(self, proportion: float):
        self.proportion = proportion


class _Cfg:
    """Just enough of a generator cfg for the record builder (no isaaclab import here)."""

    def __init__(self, proportions: dict[str, float], num_rows: int, num_cols: int, curriculum: bool = True):
        self.sub_terrains = {name: _Sub(share) for name, share in proportions.items()}
        self.num_rows, self.num_cols, self.curriculum = num_rows, num_cols, curriculum


def _cfg() -> _Cfg:
    # cumulative boundaries 0.25 / 0.5 / 1.0, so columns 0,1,2,2 -- and 2 rows x 4 cols
    return _Cfg({"flat": 0.25, "stairs|0": 0.25, "stairs|1": 0.5}, num_rows=2, num_cols=4)


def _record() -> dict:
    cfg = _cfg()
    record = terrain_map.new_record(cfg, id(cfg))
    for col, index in enumerate(record["columns"]):
        for row in range(cfg.num_rows):
            record["cells"].append({
                "row": row, "col": col, "sub_terrain": record["sub_terrains"][index],
                "difficulty": 0.5, "params": "sha256:x",
            })
    return record


def test_split_rule_matches_hand_computed_columns() -> None:
    """Equal thirds over 9 columns, and a boundary case where the epsilon decides."""
    assert terrain_map.column_split([1.0, 1.0, 1.0], 9) == (0, 0, 0, 1, 1, 1, 2, 2, 2), \
        "equal shares must split into equal column runs"
    # [3, 1] over 8 columns: boundaries 0.75 / 1.0. Column 6 sits at 0.75 + 0.001 > 0.75, so it
    # belongs to the second sub-terrain -- without the epsilon it would land in the first.
    assert terrain_map.column_split([3.0, 1.0], 8) == (0, 0, 0, 0, 0, 0, 1, 1), \
        "the boundary epsilon must push a boundary column to the higher sub-terrain"


def test_pairing_is_by_cfg_identity() -> None:
    """A cell pairs only with a pending get for the very same cfg; otherwise it is refused."""
    index, reason = terrain_map.pair([], 7)
    assert index is None and "no preceding" in reason, f"an add with nothing pending: {reason}"
    pending = [(1, 0.1, "sha256:a"), (2, 0.2, "sha256:b")]
    assert terrain_map.pair(pending, 2) == (1, ""), "the matching entry must be the one consumed"
    index, reason = terrain_map.pair(pending, 3)
    assert index is None and "identity does not match" in reason, f"a foreign cfg must be refused: {reason}"


def test_a_sound_record_passes() -> None:
    """The baseline: everything below is one violation away from this."""
    record = _record()
    assert record["columns"] == [0, 1, 2, 2], f"declared split: {record['columns']}"
    assert terrain_map.check(record) == [], f"a valid record must carry no problem: {terrain_map.check(record)}"
    assert terrain_map.column_of(record, 3) == 2, "column_of reads the declared mapping"


def test_each_sanity_violation_is_caught() -> None:
    """One injected violation per refusal, each on an otherwise valid record."""
    cases: dict[str, callable] = {
        "unknown sub-terrain": lambda r: r["cells"][0].update(sub_terrain="nowhere|9"),
        "duplicate cell": lambda r: r["cells"].append(dict(r["cells"][0])),
        "missing cell": lambda r: r["cells"].pop(),
        "column out of range": lambda r: r["cells"][0].update(col=99),
        "row out of range": lambda r: r["cells"][0].update(row=99),
        "pairing anomaly": lambda r: r["anomalies"].append("cell (0, 0): no preceding _get_terrain_mesh"),
        "curriculum without columns": lambda r: r.update(columns=None),
    }
    for label, mutate in cases.items():
        record = _record()
        mutate(record)
        assert terrain_map.check(record), f"{label} must be reported as a problem"
    # the random mode is the mirror image: a column mapping there is a claim it cannot make
    record = _record()
    record["mode"] = terrain_map.MODE_RANDOM
    assert any("per cell" in problem for problem in terrain_map.check(record)), \
        "random mode must not declare a column mapping"


def test_a_disagreeing_cell_is_caught() -> None:
    """The load-bearing check: a captured cell that the declared split does not predict."""
    record = _record()
    assert terrain_map.check(record) == [], "the control record must be sound first"
    record["cells"][0]["sub_terrain"] = record["sub_terrains"][2]  # column 0 generated a foreign type
    problems = terrain_map.check(record)
    assert any("declared split says" in problem for problem in problems), \
        f"a generator/declaration disagreement must be reported: {problems}"
    # and a corrupted declaration is caught the same way round
    record = _record()
    record["columns"] = [0, 0, 0, 0]
    assert any("declared split says" in problem for problem in terrain_map.check(record)), \
        "a corrupted declared split must not survive"


def test_column_of_refuses_a_missing_mapping() -> None:
    """No mapping, or a column outside it, is an error -- never a default answer."""
    random_record = _record()
    random_record["columns"] = None
    for record, column in ((random_record, 0), (_record(), 9)):
        try:
            terrain_map.column_of(record, column)
        except terrain_map.SplitRecordError:
            continue
        raise AssertionError(f"column {column} must raise, not answer")


def _main() -> None:
    tests = [fn for name, fn in sorted(globals().items()) if name.startswith("test_") and callable(fn)]
    for fn in tests:
        fn()
        print(f"[OK] {fn.__name__}")
    assert "torch" not in sys.modules, "this gate must stay framework-free"
    print(f"test_terrain_map: {len(tests)} passed")


if __name__ == "__main__":
    _main()
