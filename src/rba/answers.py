"""The Reserve Bank of Australia's statistical tables, read as the RBA wrote
them.

Each table is a CSV (UTF-8, with a byte-order mark): its title on the first
line (`F1 INTEREST RATES AND YIELDS – MONEY MARKET`), then lines each naming
what they hold in the first cell -- `Title`, `Description`, `Frequency`,
`Type`, `Units`, `Source`, `Publication date`, `Series ID` -- a cell a
column; then one line a day, its date as `18-Nov-2026`, each column's value
as the RBA writes it, empty where it states none: no value, never a zero.

A value is kept as the text the RBA wrote, and read as a `Decimal` from it,
never a float; a value that does not read is kept as not read, and never
recorded.
"""

from __future__ import annotations

import csv
import io
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal, InvalidOperation

MISSING = {"", "NA", "N/A", "n/a", "-"}


class NotRead(Exception):  # noqa: N818 - what the answer was not
    """An answer that is not what was asked for."""


@dataclass(frozen=True)
class Observation:
    """One value as the RBA stated it: its column's Series ID, day and text."""

    series: str
    day: date
    text: str

    @property
    def value(self) -> Decimal:
        return Decimal(self.text)


@dataclass
class Table:
    """A table read: each column's Series ID with its `Units` and `Source`,
    its values in order, and the values that did not read."""

    name: str
    units: dict[str, str] = field(default_factory=dict)
    sources: dict[str, str] = field(default_factory=dict)
    observations: list[Observation] = field(default_factory=list)
    unread: list[str] = field(default_factory=list)

    @property
    def days(self) -> list[date]:
        return sorted({o.day for o in self.observations})

    def on(self, day: date) -> dict[str, Observation]:
        return {o.series: o for o in self.observations if o.day == day}


def _number(text: str) -> bool:
    try:
        return Decimal(text).is_finite()
    except InvalidOperation:
        return False


def parse(text: str, name: str) -> Table:
    """A statistical table's CSV, read; NotRead where it is not one."""
    read = Table(name)
    rows = list(csv.reader(io.StringIO(text.lstrip("﻿"))))
    named = {r[0].strip(): r for r in rows if r and r[0] and not r[0][:1].isdigit()}
    if not rows or not rows[0] or not rows[0][0].startswith(name) or "Series ID" not in named:
        raise NotRead(f"the answer is not the RBA's table {name}: {text[:80]!r}")
    ids = [c.strip() for c in named["Series ID"][1:]]
    for key, into in (("Units", read.units), ("Source", read.sources)):
        for series, said in zip(ids, named.get(key, [key])[1:], strict=False):
            into[series] = said.strip()
    for row in rows:
        if not row or not row[0][:1].isdigit():
            continue
        try:
            day = datetime.strptime(row[0].strip(), "%d-%b-%Y").date()
        except ValueError:
            read.unread.append(f"{name}: a day {row[0][:20]!r}")
            continue
        for series, stated in zip(ids, row[1:], strict=False):
            said = stated.strip()
            if not series or said in MISSING:
                continue
            if not _number(said):
                read.unread.append(f"{series} {day}: {said[:40]!r}")
                continue
            read.observations.append(Observation(series, day, said))
    read.observations.sort(key=lambda o: (o.series, o.day))
    return read


def without(text: str, kept: set[str]) -> str:
    """The table with only the columns whose Series ID is in `kept`, and
    the first: for keeping the RBA's own columns and none of a third
    party's."""
    rows = list(csv.reader(io.StringIO(text.lstrip("﻿"))))
    ids = next((r for r in rows if r and r[0].strip() == "Series ID"), [])
    keep = [0] + [i for i, s in enumerate(ids) if i and s.strip() in kept]
    out = io.StringIO()
    writer = csv.writer(out, lineterminator="\n")
    for row in rows:
        writer.writerow([row[i] for i in keep if i < len(row)] if len(row) > 1 else row)
    return out.getvalue()
