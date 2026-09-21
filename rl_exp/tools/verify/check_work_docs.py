# Copyright (c) 2022-2026, The Isaac Lab Project Developers (https://github.com/isaac-sim/IsaacLab/blob/main/CONTRIBUTORS.md).
# All rights reserved.
#
# SPDX-License-Identifier: BSD-3-Clause

# -*- coding: utf-8 -*-
"""Work-ledger tool: list the items in flight, locate one, check their shape.

An item is one file under ``work/active/`` and, once closed, one file under
``work/closed/<year>/``. The file *is* the identity record: closing moves it, it does not
rewrite it. The point of the directory is that the default read cost grows with the work in
flight, not with everything ever done -- so the tool lists what is in flight and says how
much of it was migrated, and everything else is found by search.

Three modes, one implementation of the item format:

* ``--list [KEY]`` -- one line per active item (id / status / scope / title), after a line naming
  the scope it covers; ``KEY`` narrows the view. The list is for *choosing* an item, so the action
  and the close condition stay in the file and are fetched with ``--locate`` -- a shortened second
  copy here would be one more thing to keep in step.
* ``--locate KEY`` -- the files whose id, title or body matches KEY, with line numbers.
* ``--check`` (default) -- the shape gates below, each printing what it saw.

What each measurement is for -- three different things, not one budget:

| 对象 | 用途 |
|---|---|
| ``--list`` 实际输出 | **默认发现成本**（未选事项前付的那一笔；闸门直接量这几行） |
| 单个事项文件的字节数 | **选中后的阅读成本**（按需读，不设上限） |
| ``work/active/`` 总量 | **积压与膨胀警报**，不是 token 预算（没人读这个和） |

An item is front matter plus a free body::

    ---
    id: <matches the file name>
    title: <one line>
    scope: <path(s) that exist -- a range, never a word from a list>
    status: <open/in_progress/blocked/done/cancelled/superseded>
    landing: <path[#anchor], ...>          # where the rule lives, or will live
    next: <the action to take>             # active items only
    close_when: <who checks what, observes what, and what each outcome means>
    depends_on: <an active item id, or a live mechanism path>
    evidence: <acceptance/records/<stem>[#anchor]>
    outcome: <what happened>               # closed items only
    superseded_by: <item id or mechanism path>   # when status is superseded
    ---

The body states the current situation only: no superseded states, no copy of a number or a
digest whose owner is elsewhere, no restatement of a rule that lives in a mechanism.

Closing an item is a move, not a rewrite: the file goes to ``closed/<year>/``, keeps its id,
drops ``next`` and gains ``outcome``; unfinished work becomes its own active item. Evidence
goes to ``acceptance/records/<date>-<object>-<topic>.md``, which carries five sections in
order -- 适用范围 / 验收条件 / 结果 / 证据引用 / 未覆盖边界 -- so a reader can see where the
record's authority stops.

The ledger is a document set, not a database: there is no id registry, and the tool does
not pretend to own one. Uniqueness is only ever checked over the files that exist right
now, and a cancelled item stays in the closed tree as the record of the decision.

Known ceilings, deliberate:

* Only ``sha256:`` digests are rejected in an item body, not "all block values". A ratio
  pattern fires on legitimate prose (the same ceiling ``check_version_docs.py`` hit), and a
  gate that cries wolf gets ignored rather than obeyed; the rest is review.
* The scope word list is not a vocabulary the tool owns. An item names where it lives, and
  that path has to exist -- a list would be edited the moment it fires.
* The budget reports the biggest contributors and stops there. It never cancels, closes or
  archives anything: whether a cancellation is justified is not decidable here, and a tool
  that trades work away to get under a byte count is worse than an honest overrun.
"""

from __future__ import annotations

import argparse
import pathlib
import re
import sys
import tempfile

_REPO = pathlib.Path(__file__).resolve().parents[3]
_ACTIVE = _REPO / "work" / "active"
_CLOSED = _REPO / "work" / "closed"
_RECORDS = _REPO / "acceptance" / "records"

#: Sections every acceptance record carries, in this order. The record is evidence, so the
#: points it does NOT cover are part of it: a reader has to see where its authority stops.
_RECORD_SECTIONS = ("适用范围", "验收条件", "结果", "证据引用", "未覆盖边界")
_RECORD_NAME = re.compile(r"\d{4}-\d{2}-\d{2}-[a-z0-9-]+\.md")

#: The only statuses an item may carry.
_STATUS = ("open", "in_progress", "blocked", "done", "cancelled", "superseded")
#: Fields every item has, active or closed.
_COMMON = ("id", "title", "scope", "status", "landing")
#: Fields an active item adds; a closed item must not keep "next" around.
_ACTIVE_ONLY = ("next", "close_when")
#: Fields a closed item adds.
_CLOSED_ONLY = ("outcome",)
#: Bytes of the ``--list`` output. **This is the default discovery cost** -- what someone pays
#: before deciding which item to open -- so it is measured directly, over the exact lines
#: ``--list`` prints, rather than proxied by any one field's length. Measured 2026-09-21: 1434
#: bytes for 8 items (179 per line) once the list stopped carrying ``next``; before that it was
#: 4638. 4096 leaves room for the ~25 items the two sessions are heading for and still expires
#: around 4 KB, where the remedy is to narrow the view -- never to cancel an item.
LIST_BYTES = 4096
#: Total bytes of ``work/active/``. **Not a read budget and not a token budget**: nobody reads
#: the sum, items are read on demand. It is a backlog alarm, and its value is set as roughly
#: 2.5x the measured working steady state (8 items = 20643 bytes, ~2.6 KB per item) so it stays
#: quiet during ordinary work and speaks up around twenty open items -- at that point the
#: backlog itself is the problem, not the bytes. Raise it by hand with a reason written here,
#: never from inside a run.
BUDGET_BYTES = 48000
#: Total bytes of ``work/active/``. A growth alarm, **not** the default read cost (items are
#: read on demand): it fires before the ledger turns into another file nobody can afford to
#: read. Raised 24000 -> 48000 on 2026-09-21 because two sessions share it and ~25 items at the
#: measured ~2 KB each is ordinary work, not bloat. Raise it by hand with a reason, never from
#: inside a run.
BUDGET_BYTES = 48000

_SHA = re.compile(r"\bsha256:[0-9a-fA-F]{8,}")


class Item:
    """One ledger item: its path, its fields and its body."""

    def __init__(self, path: pathlib.Path, fields: dict[str, str], body: str) -> None:
        self.path = path
        self.fields = fields
        self.body = body

    @property
    def id(self) -> str:
        return self.fields.get("id", "")

    @property
    def closed(self) -> bool:
        return self.path.parent != _ACTIVE


def _parse(path: pathlib.Path) -> tuple[Item | None, list[str]]:
    """Read one item; the second value is the list of problems found while reading it."""
    problems: list[str] = []
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return None, [f"{_rel(path)}: no front matter (the file must start with '---')"]
    end = next((i for i, line in enumerate(lines[1:], 1) if line.strip() == "---"), None)
    if end is None:
        return None, [f"{_rel(path)}: front matter is never closed by a second '---'"]
    fields: dict[str, str] = {}
    for offset, line in enumerate(lines[1:end], 2):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if ":" not in line:
            problems.append(f"{_rel(path)}:{offset}: front matter line has no 'key:'")
            continue
        key, _, value = line.partition(":")
        key = key.strip()
        if key in fields:
            problems.append(f"{_rel(path)}:{offset}: '{key}' appears twice")
        fields[key] = value.strip()
    return Item(path, fields, "\n".join(lines[end + 1 :])), problems


def _rel(path: pathlib.Path) -> str:
    """Path as it is written in a message: relative to the repo root when it is inside."""
    try:
        return path.relative_to(_REPO).as_posix()
    except ValueError:
        return path.as_posix()


def _refs(value: str) -> list[str]:
    """A comma-separated field as a list, empty entries dropped."""
    return [part.strip() for part in value.split(",") if part.strip()]


def _items() -> tuple[list[Item], list[str]]:
    """Every item on disk, plus the problems found while reading them all."""
    items: list[Item] = []
    problems: list[str] = []
    for path in sorted(_ACTIVE.glob("*.md")) + sorted(_CLOSED.rglob("*.md")):
        if not path.is_file():
            continue
        item, found = _parse(path)
        problems.extend(found)
        if item is not None:
            items.append(item)
    return items, problems


def _tally(items: list[Item], problems: list[str]) -> int:
    """Shape gates, each one printing what it saw."""
    active = [i for i in items if not i.closed]
    closed = [i for i in items if i.closed]

    for item in items:
        for field in _COMMON:
            if not item.fields.get(field):
                problems.append(f"{_rel(item.path)}: '{field}' is missing or empty")
        status = item.fields.get("status", "")
        if status and status not in _STATUS:
            problems.append(
                f"{_rel(item.path)}: status '{status}' is not one of {'/'.join(_STATUS)}"
            )
        if item.path.stem != item.id:
            problems.append(
                f"{_rel(item.path)}: id '{item.id}' does not match the file name "
                f"('{item.path.stem}.md' is the identity record)"
            )
        wanted = _ACTIVE_ONLY if not item.closed else _CLOSED_ONLY
        for field in wanted:
            if not item.fields.get(field):
                problems.append(f"{_rel(item.path)}: '{field}' is missing or empty")
        # ``next`` is deliberately not length-capped: the list does not print it, and trimming it
        # would trade the field's executability for a shorter line nobody reads. The default cost
        # is the list itself -- see LIST_BYTES below.
        if item.closed and item.fields.get("next"):
            problems.append(
                f"{_rel(item.path)}: a closed item keeps 'next' ({item.fields['next']!r}) -- "
                "unfinished work has to become an active item"
            )

    seen: dict[str, str] = {}
    for item in items:
        if item.id in seen:
            problems.append(
                f"{_rel(item.path)}: id '{item.id}' is already used by {seen[item.id]} "
                "(uniqueness is only claimed over the files present)"
            )
        seen[item.id] = _rel(item.path)

    ids_active = {i.id for i in active}
    ids_closed = {i.id for i in closed}
    for item in items:
        for side in ("scope", "landing", "depends_on"):
            for ref in _refs(item.fields.get(side, "")):
                target = ref.split("#", 1)[0].strip()
                if not target:
                    problems.append(f"{_rel(item.path)}: '{side}' has an empty entry")
                    continue
                if side == "depends_on" and target in ids_active:
                    continue
                if (_REPO / target).exists():
                    continue
                extra = ""
                if side == "depends_on" and target in ids_closed:
                    extra = " (it is a closed item: depend on a live mechanism instead)"
                problems.append(f"{_rel(item.path)}: '{side}' -> {target} does not exist{extra}")
        if item.fields.get("status") == "superseded":
            target = item.fields.get("superseded_by", "").split("#", 1)[0].strip()
            if not target or not ((_REPO / target).exists() or target in seen):
                problems.append(
                    f"{_rel(item.path)}: status is 'superseded' but 'superseded_by' "
                    f"({item.fields.get('superseded_by', '')!r}) resolves to nothing"
                )
        for ref in _refs(item.fields.get("evidence", "")):
            stem = ref.split("#", 1)[0].strip()
            if not stem:
                problems.append(f"{_rel(item.path)}: 'evidence' has an empty entry")
                continue
            candidates = [_REPO / stem, _REPO / f"{stem}.md"]
            if not any(c.exists() for c in candidates):
                problems.append(f"{_rel(item.path)}: 'evidence' -> {stem} does not exist")
        for match in _SHA.finditer(item.body):
            problems.append(
                f"{_rel(item.path)}: body carries a digest ({match.group(0)[:24]}…) -- "
                "point at the record that holds it instead of copying it"
            )

    records = sorted(_RECORDS.glob("*.md")) if _RECORDS.is_dir() else []
    for record in records:
        if not _RECORD_NAME.fullmatch(record.name):
            problems.append(
                f"{_rel(record)}: a record is named <date>-<object>-<topic>.md, lower case"
            )
        headings = [
            line.split("## ", 1)[1].strip()
            for line in record.read_text(encoding="utf-8").splitlines()
            if line.startswith("## ")
        ]
        present: list[str] = []
        for heading in headings:
            section = next((s for s in _RECORD_SECTIONS if heading.startswith(s)), None)
            if section is not None and section not in present:
                present.append(section)
        if present != list(_RECORD_SECTIONS):
            problems.append(
                f"{_rel(record)}: sections must be {' / '.join(_RECORD_SECTIONS)} in that order "
                f"(found {present or 'none'}) -- the record has to say where its authority stops"
            )

    list_bytes = len("\n".join(_list_lines(items)).encode("utf-8"))
    if list_bytes > LIST_BYTES:
        problems.append(
            f"`--list` prints {list_bytes} bytes, over the {LIST_BYTES}-byte default-discovery "
            "budget: narrow the view (`--list <关键词>`) or close what is finished. This is a "
            "discovery-cost alarm: not a reason to cancel, close or archive anything, and not a "
            "reason to shorten `next`."
        )

    total = sum(i.path.stat().st_size for i in active)
    if total > BUDGET_BYTES:
        ranked = sorted(active, key=lambda i: -i.path.stat().st_size)[:3]
        shape = ", ".join(f"{i.id} {i.path.stat().st_size}" for i in ranked)
        problems.append(
            f"work/active/ is {total} bytes, over the {BUDGET_BYTES} budget "
            f"(biggest contributors: {shape}). Deduplicate, narrow an item or raise the "
            "budget by hand -- this tool will not cancel, close or archive anything."
        )
    print(
        f"  items: {len(active)} active / {len(closed)} closed "
        f"| active bytes {total}/{BUDGET_BYTES} | records {len(records)}"
    )
    return 1 if problems else 0


def _list_lines(items: list[Item], needle: str | None = None) -> list[str]:
    """The exact lines ``--list`` prints. The cap is measured on these, not on any one field.

    The list exists to let a reader *choose* an item, so it carries id, status, scope and title.
    The action and the close condition stay in the file and are fetched with ``--locate``: a
    second, shortened copy of them here would be one more thing to keep in step.
    """
    active = sorted((i for i in items if not i.closed), key=lambda i: i.id)
    if needle:
        low = needle.lower()
        active = [
            i
            for i in active
            if low in (i.id + i.fields.get("title", "") + i.fields.get("scope", "")).lower()
        ]
    head = f"范围：已迁移 {len(active)} 项"
    head += f"（过滤 {needle!r}）" if needle else ""
    head += "（work/active/；原文档里的挂账尚未迁移的不在此列）"
    lines = [head] + [
        f"  {i.id}  [{i.fields.get('status', '')}]  {i.fields.get('scope', '')}"
        f"  {i.fields.get('title', '')}"
        for i in active
    ]
    if not needle:
        lines.append("  （next 与关闭条件不进列表：用 `--locate <关键词>` 取）")
    return lines


def _list(needle: str | None = None) -> int:
    """Print the items in flight, saying out loud how much of the ledger that covers."""
    items, problems = _items()
    for line in _list_lines(items, needle):
        print(line)
    for problem in problems:
        print(f"  DRIFT: {problem}")
    return 1 if problems else 0


def _locate(key: str) -> int:
    """Print the item files whose id, title or body carries KEY, with line numbers."""
    items, problems = _items()
    needle = key.lower()
    hits = 0
    for item in items:
        lines = item.path.read_text(encoding="utf-8").splitlines()
        where = [f"{_rel(item.path)}:{n}" for n, line in enumerate(lines, 1) if needle in line.lower()]
        if needle not in item.id.lower() and not where:
            continue
        hits += 1
        state = "closed" if item.closed else item.fields.get("status", "")
        print(f"{_rel(item.path)}  [{state}]  {item.fields.get('title', '')}")
        for spot in where[:5]:
            print(f"    {spot}")
    if not hits:
        print(f"no item matches {key!r} ({len(items)} item file(s) searched)")
        return 1
    for problem in problems:
        print(f"  DRIFT: {problem}")
    return 1 if problems else 0


_GOOD = """\
---
id: {id}
title: {title}
scope: notes
status: {status}
landing: notes/rule.md#anchor
next: do the next thing
close_when: the observation reads as X
---

Body text.
"""


def self_test() -> int:
    """Falsifiers: each gate must fire on the fixture that trips it, and only there."""
    problems: list[str] = []
    with tempfile.TemporaryDirectory() as tmp:
        global _REPO, _ACTIVE, _CLOSED, _RECORDS, BUDGET_BYTES, LIST_BYTES
        saved = (_REPO, _ACTIVE, _CLOSED, _RECORDS, BUDGET_BYTES, LIST_BYTES)
        root = pathlib.Path(tmp)
        (root / "work" / "active").mkdir(parents=True)
        (root / "work" / "closed" / "2026").mkdir(parents=True)
        (root / "notes").mkdir()
        (root / "notes" / "rule.md").write_text("anchor\n", encoding="utf-8")
        (root / "acceptance" / "records").mkdir(parents=True)
        good_record = "".join(f"## {s}\n\nbody\n\n" for s in _RECORD_SECTIONS)
        (root / "acceptance" / "records" / "2026-09-20-good.md").write_text(good_record, encoding="utf-8")
        (root / "acceptance" / "records" / "2026-09-20-partial.md").write_text(
            "## 适用范围\n\nonly this one\n", encoding="utf-8"
        )
        (root / "acceptance" / "records" / "Bad_Name.md").write_text(good_record, encoding="utf-8")

        def item(name: str, text: str, closed: bool = False) -> None:
            folder = root / "work" / ("closed/2026" if closed else "active")
            (folder / f"{name}.md").write_text(text, encoding="utf-8")

        good = _GOOD.format(id="good", title="ok", status="open")
        item("good", good)
        item(
            "no-close-when",
            _GOOD.format(id="no-close-when", title="x", status="open").replace(
                "close_when: the observation reads as X\n", ""
            ),
        )
        item("bad-status", _GOOD.format(id="bad-status", title="x", status="done-ish"))
        item("name-mismatch", _GOOD.format(id="different", title="x", status="open"))
        item(
            "bad-landing",
            _GOOD.format(id="bad-landing", title="x", status="open").replace(
                "notes/rule.md#anchor", "notes/not-there.md"
            ),
        )
        item(
            "dep-on-closed",
            _GOOD.format(id="dep-on-closed", title="x", status="open").replace(
                "next:", "depends_on: gone\nnext:"
            ),
        )
        item(
            "bad-evidence",
            _GOOD.format(id="bad-evidence", title="x", status="open").replace(
                "next:", "evidence: acceptance/records/2026-09-20-absent\nnext:"
            ),
        )
        item(
            "digest",
            _GOOD.format(id="digest", title="x", status="open")
            + "\narchived as sha256:0123456789abcdef and then some\n",
        )
        item(
            "closed-item",
            "---\nid: closed-item\ntitle: done\nscope: rl_exp/tools/verify\n"
            "status: done\nlanding: notes/rule.md\noutcome: shipped\n"
            "next: keep going\n---\n",
            closed=True,
        )
        item(
            "gone",
            "---\nid: gone\ntitle: retired\nscope: rl_exp/tools/verify\n"
            "status: cancelled\nlanding: notes/rule.md\noutcome: superseded by nothing\n---\n",
            closed=True,
        )
        item("dup-a", _GOOD.format(id="dup-a", title="x", status="open"))
        item("dup-b", _GOOD.format(id="dup-a", title="x", status="open"))
        item(
            "bad-scope",
            _GOOD.format(id="bad-scope", title="x", status="open").replace(
                "scope: notes", "scope: some/invented/word"
            ),
        )
        item("broken", "---\nid: broken\ntitle: unterminated\n")

        _REPO, _ACTIVE, _CLOSED = root, root / "work" / "active", root / "work" / "closed"
        _RECORDS = root / "acceptance" / "records"
        items, detected = _items()
        _tally(items, detected)
        for expected in (
            "'close_when' is missing or empty",
            "status 'done-ish' is not one of",
            "does not match the file name",
            "notes/not-there.md does not exist",
            "closed item: depend on a live mechanism",
            "acceptance/records/2026-09-20-absent does not exist",
            "body carries a digest",
            "a closed item keeps 'next'",
            "front matter is never closed",
            "already used",
            "some/invented/word does not exist",
            "2026-09-20-partial.md: sections must be",
            "Bad_Name.md: a record is named",
        ):
            if not any(expected in p for p in detected):
                problems.append(f"falsifier did not fire: {expected!r}")
        # The clean fixture must not be blamed by any gate.
        blamed = [p for p in detected if "good.md" in p]
        if blamed:
            problems.append(f"a clean item was blamed: {blamed}")
        if not detected:
            problems.append("nothing was flagged at all: the fixture tree is not being read")

        saved_budget = BUDGET_BYTES
        BUDGET_BYTES = 10
        budget_problems: list[str] = []
        _tally(_items()[0], budget_problems)
        BUDGET_BYTES = saved_budget
        if not any("over the" in p for p in budget_problems):
            problems.append("falsifier did not fire: the active-set budget")
        if not any("will not cancel" in p for p in budget_problems):
            problems.append("the budget message does not say the tool decides nothing")

        saved_list = LIST_BYTES
        LIST_BYTES = 10
        list_problems: list[str] = []
        _tally(_items()[0], list_problems)
        LIST_BYTES = saved_list
        if not any("default-discovery budget" in p for p in list_problems):
            problems.append("falsifier did not fire: the --list discovery budget")
        if not any("not a reason to cancel" in p for p in list_problems):
            problems.append("the --list budget message does not refuse to justify a cancellation")
        _REPO, _ACTIVE, _CLOSED, _RECORDS, BUDGET_BYTES, LIST_BYTES = saved

    for problem in problems:
        print(f"  FALSIFIER: {problem}")
    print(
        "WORK_DOCS_SELF_TEST_OK (14 item + 3 record fixtures)"
        if not problems
        else f"WORK_DOCS_SELF_TEST_DRIFT ({len(problems)})"
    )
    return 1 if problems else 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument(
        "--list",
        nargs="?",
        const="",
        metavar="KEY",
        help="print the items in flight, optionally filtered by KEY",
    )
    parser.add_argument("--locate", metavar="KEY", help="print the item files matching KEY")
    parser.add_argument("--self-test", action="store_true", help="run the falsifiers")
    args = parser.parse_args(argv)
    if args.self_test:
        return self_test()
    if args.list is not None:
        return _list(args.list or None)
    if args.locate:
        return _locate(args.locate)
    items, problems = _items()
    code = _tally(items, problems)
    for problem in problems:
        print(f"  DRIFT: {problem}")
    print(
        f"WORK_DOCS_OK ({len(items)} item file(s))"
        if code == 0
        else f"WORK_DOCS_DRIFT ({len(problems)})"
    )
    return code


if __name__ == "__main__":
    sys.exit(main())
