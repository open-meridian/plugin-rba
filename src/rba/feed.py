"""The Reserve Bank of Australia's rates, curves and exchange rates into the
lake: each table's latest month recorded as the RBA publishes it, and any day
of any dataset recorded when the lake wants it (W10.4, W10.7), through the
SDK's rates helpers (`meridian.roles.data.rates`) and its `Wants`.

**Push: the RBA's own columns.** At start and every hour, each table is
asked with its `Last-Modified` as `If-Modified-Since`: a table not changed
is answered 304 and read no further. A table sent is kept (its own columns
alone, raw.py), and its days from a month before its latest are recorded,
in the lake's batches; the lake answers each value it holds unchanged. A
value the RBA revises is the same row key's next version. A table is asked
whole again while any of its records is not held, so its values are
recorded once the deployment holds the record.

**Pull: every dataset; the third parties' columns only so** (ruling 132,
declared.py). A want is read from the table holding it, asked whole; a
third party's column is read only so, and never kept.

**Rows** (series.py says each): the cash rates `fixing`s, the interbank
rate with its volume and number of transactions; the total return index an
`index_level`; F2's yields `par_yield`s and F17's `zero`s at their tenors on
their curves' records; the BABs/NCDs `fixing`s and the OIS `par_yield`s at
their tenors; each exchange rate a `close` `Price` of the Australian
dollar's cash instrument in the other currency. A value the RBA states
nothing for is no row, never a zero. Each is read from the RBA's text as a
`Decimal`, never a float. A column whose table names a source other than
the one series.py expects is not recorded, and the Datasets page says so.

**Published time.** The RBA states a publication date on each column, never
a time on a value: no row states one, rather than a wrong one.

**Subjects.** Each record by its code at `rba` (series.py), the Australian
dollar by its ISO 4217 code, resolved once per process; one the deployment
does not hold is reported missing, and its values wait. The plugin mints
nothing.

**Wants.** A want of one of the four datasets, for subjects the plugin
records -- a business date, a range of at most a year, or the latest -- is
read from the RBA and recorded against the want; a day the RBA states
nothing for, or one not come yet, is declined `source_silent`; any other
subject, or another kind of data, `not_covered`.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from typing import Any
from zoneinfo import ZoneInfo

import meridian
from meridian.operations import Money, ObservationMeta, Price, SubjectRef
from meridian.plugin.v1 import operations_pb2 as ops
from meridian.roles import data
from meridian.roles.data import rates

from .answers import NotRead, Table, parse, without
from .declared import DAY_TIME_ZONE, KEYS, PRICE, RATE
from .portal import PATHS, Fetched, Portal, PortalUnreachable, utc_now
from .raw import RawStore
from .series import (
    AUD,
    COUNT,
    FX,
    FX_COLUMNS,
    RATE_COLUMNS,
    RESTRICTED,
    SOURCE,
    TABLES,
    TRI_BASE,
    VOLUME,
    Column,
    Record,
    dataset_of_fx,
)

log = logging.getLogger("rba")

SYDNEY = ZoneInfo(DAY_TIME_ZONE)
#: The most days one want is answered for: a year.
MOST_DAYS = 366
#: How far before a table's latest day a check records: a month, so F17's
#: monthly additions are recorded whole.
PUSHED_DAYS = 31
#: Each dataset's tables.
TABLES_OF = {
    key: tuple(
        t
        for t in TABLES
        if any(c.table == t and c.dataset == key for c in RATE_COLUMNS.values())
        or (t == "F11.1" and any(dataset_of_fx(s) == key for s in FX_COLUMNS))
    )
    for key in KEYS
}


def _ns(moment: datetime) -> int:
    return int(moment.timestamp() * 1_000_000) * 1000


def day_bounds(day: date) -> tuple[int, int]:
    start = datetime.combine(day, time(0, 0), SYDNEY)
    return _ns(start), _ns(datetime.combine(day + timedelta(days=1), time(0, 0), SYDNEY))


@dataclass(frozen=True)
class Outcome:
    recorded: int = 0
    restated: int = 0
    unchanged: int = 0
    unresolved: tuple[str, ...] = ()


@dataclass
class Held:
    """A record or a currency as the plugin last saw it: the deployment's
    instrument, or why there is none, and the latest day recorded."""

    code: str
    name: str = ""
    instrument_id: str = ""
    miss: str = ""
    latest_day: date | None = None


@dataclass
class SourceStatus:
    """What the plugin last did with one table, for its pages."""

    source: str
    checked_at: datetime | None = None
    read_at: datetime | None = None
    error: str = ""
    first_day: date | None = None
    latest_day: date | None = None
    fetches: int = 0
    last_modified: str = ""
    unread: dict[str, int] = field(default_factory=dict)
    #: Columns whose table names another source than expected, with it.
    other_source: dict[str, str] = field(default_factory=dict)


@dataclass
class Status:
    """What the plugin last did, for its pages; lost on a restart."""

    mode: str = "live"
    started_at: datetime | None = None
    sources: dict[str, SourceStatus] = field(
        default_factory=lambda: {t: SourceStatus(t) for t in TABLES}
    )
    records: dict[str, Held] = field(default_factory=dict)
    aud: Held = field(default_factory=lambda: Held(AUD, "Australian dollar"))
    #: Each exchange rate's latest day recorded, by its currency's ISO code.
    fx_days: dict[str, date] = field(default_factory=dict)

    @property
    def checked_at(self) -> datetime | None:
        stamps = [s.checked_at for s in self.sources.values() if s.checked_at]
        return max(stamps) if stamps else None

    @property
    def error(self) -> str:
        return next((s.error for s in self.sources.values() if s.error), "")

    @property
    def fetches(self) -> int:
        return sum(s.fetches for s in self.sources.values())

    @property
    def read(self) -> bool:
        return any(s.read_at for s in self.sources.values())


class Feed(data.Role):
    """The plugin's data role class, its acts made on itself -- registered
    with `meridian.run`, or bound to the suite's recorder in its tests."""

    def __init__(
        self, portal: Portal, raw: RawStore, now: Callable[[], datetime] = utc_now
    ) -> None:
        self.portal = portal
        self.raw = raw
        self.now = now
        self.wants = data.Wants(self, KEYS, clock_ns=lambda: _ns(self.now()))
        self.rates = rates.Feed(
            self, SOURCE, wants=self.wants, day_zone=DAY_TIME_ZONE, clock_ns=lambda: _ns(self.now())
        )
        self.status = Status(mode=portal.mode, started_at=now())

    def today(self) -> date:
        return self.now().astimezone(SYDNEY).date()

    def use(self, portal: Portal) -> None:
        """Read from `portal` from now on: sample data turned on or off."""
        if portal.mode != self.portal.mode:
            self.portal = portal
            self.status.mode = portal.mode
            for held in self.status.sources.values():
                held.last_modified = ""

    # ── Reading ─────────────────────────────────────────────────────────

    async def read(self, table: str, since: str = "") -> tuple[Table | None, str, str]:
        """`table` read -- None where unchanged since `since` -- the key of
        its own columns in storage, and its Last-Modified.
        PortalUnreachable or NotRead otherwise."""
        held = self.status.sources[table]
        held.checked_at = self.now()
        try:
            fetched: Fetched = await self.portal.get(PATHS[table], since)
            held.fetches += 1
            if fetched.status == 304:
                held.error, held.read_at = "", self.now()
                return None, "", fetched.last_modified
            if fetched.status != 200:
                raise PortalUnreachable(f"{fetched.url[:120]} answered {fetched.status}")
            read = parse(fetched.text, table)
        except (PortalUnreachable, NotRead) as failed:
            held.error = str(failed)
            raise
        own = {s for s, said in read.sources.items() if said == "RBA" and not _third_party(s)}
        key = self.raw.keep(fetched, without(fetched.text, own))
        held.error, held.read_at = "", self.now()
        if read.days:
            held.first_day, held.latest_day = read.days[0], read.days[-1]
        for line in read.unread:
            held.unread[line] = held.unread.get(line, 0) + 1
        return read, key, fetched.last_modified

    # ── Resolving ───────────────────────────────────────────────────────

    async def record_of(self, record: Record) -> str:
        """A record's instrument, by its code at `rba`; empty, reported
        missing, where the deployment holds none."""
        held = self.status.records.setdefault(record.code, Held(record.code, record.description))
        if held.instrument_id:
            return held.instrument_id
        found = await self.rates.subject(
            record.identifier,
            description=record.description,
            instrument_type=record.instrument_type,
        )
        held.instrument_id, held.miss = found, "" if found else "not held: reported missing"
        return found

    async def aud(self) -> str:
        """The Australian dollar's cash instrument by ISO 4217, resolved now
        where not yet; empty, reported missing with why, where none
        resolves."""
        held = self.status.aud
        if held.instrument_id:
            return held.instrument_id
        identifier = ops.Identifier(scheme="iso4217", value=AUD)
        found = await self.resolve_identifier(
            identifiers=[identifier],
            as_of_ns=_ns(self.now()),
            stated_asset_class="cash",
            stated_currency=AUD,
            stated_description=f"{AUD} cash",
        )
        if found.found and found.instrument_id:
            held.instrument_id, held.miss = found.instrument_id, ""
            return str(found.instrument_id)
        if held.miss:
            return ""
        reason = found.miss_reason or ops.MISS_REASON_NOT_FOUND
        held.miss = ops.MissReason.Name(reason).removeprefix("MISS_REASON_").lower()
        await self.report_missing_instrument(
            source=SOURCE,
            asset_class="cash",
            identifiers=[identifier],
            reason=reason,
            as_of_ns=_ns(self.now()),
            observed_at_ns=_ns(self.now()),
        )
        return ""

    # ── Recording ───────────────────────────────────────────────────────

    def _note(self, held: Held, day: date) -> None:
        if held.latest_day is None or day > held.latest_day:
            held.latest_day = day

    def _stated_by(self, read: Table, series: str, expected: str) -> bool:
        """Whether the table names `series`' source as series.py expects;
        noted for the Datasets page where it does not."""
        said = read.sources.get(series, "")
        if said == expected:
            return True
        self.status.sources[read.name].other_source[series] = said or "none"
        return False

    async def _rate_rows(
        self, read: Table, key: str, dataset: str, days: set[date] | None
    ) -> list[Any]:
        rows: list[Any] = []
        for seen in read.observations:
            column: Column | None = RATE_COLUMNS.get(seen.series)
            if column is None or column.dataset != dataset or column.table != read.name:
                continue
            if days is not None and seen.day not in days:
                continue
            if not self._stated_by(read, seen.series, column.source):
                continue
            subject = await self.record_of(column.record)
            if not subject:
                continue
            extra: dict[str, Any] = {}
            said = seen.text
            if seen.series == "FIRMMCRID":
                stated = read.on(seen.day)
                if VOLUME in stated:
                    extra["volume"] = Money(stated[VOLUME].value * Decimal(1_000_000), AUD)
                if COUNT in stated and stated[COUNT].text.isdigit():
                    extra["transaction_count"] = int(stated[COUNT].text)
                said += "|" + "|".join(
                    stated[s].text if s in stated else "" for s in (VOLUME, COUNT)
                )
            value = (
                rates.index_level(seen.text, TRI_BASE)
                if column.kind == "index_level"
                else rates.percent(seen.text)
            )
            raw_key = (
                self.raw.noted(f"{seen.series}:{seen.day}={said}", seen.day, key)[0].key
                if dataset != RESTRICTED
                else ""
            )
            rows.append(
                self.rates.rate(
                    subject,
                    dataset,
                    column.kind,
                    value,
                    business_date=seen.day,
                    convention=column.convention,
                    tenor=column.tenor or None,
                    series=column.record.code,
                    raw_key=raw_key,
                    **extra,
                )
            )
            self._note(self.status.records[column.record.code], seen.day)
        return rows

    async def _prices(self, read: Table, dataset: str, days: set[date] | None) -> list[Any]:
        prices: list[Any] = []
        if read.name != "F11.1":
            return prices
        wanted = [s for s in FX_COLUMNS if dataset_of_fx(s) == dataset]
        if not wanted:
            return prices
        subject = await self.aud()
        if not subject:
            return prices
        source = self.wants.dataset(dataset)
        for seen in read.observations:
            if seen.series not in wanted or (days is not None and seen.day not in days):
                continue
            code, expected = FX_COLUMNS[seen.series]
            if not self._stated_by(read, seen.series, expected):
                continue
            start, end = day_bounds(seen.day)
            prices.append(
                Price(
                    meta=ObservationMeta(
                        row_key=f"{AUD}{code}:{seen.day.isoformat()}",
                        subjects=[SubjectRef(entity_id=subject)],
                        source=ops.Source(dataset=source),
                        valid_from_ns=start,
                        valid_until_ns=end,
                        business_date=seen.day.isoformat(),
                    ),
                    kind="close",
                    price=Money(seen.value, code),
                    basis="per_unit",
                )
            )
            held = self.status.fx_days.get(code)
            self.status.fx_days[code] = max(held, seen.day) if held else seen.day
            self._note(self.status.aud, seen.day)
        return prices

    async def record(
        self,
        read: Table,
        key: str,
        dataset: str,
        *,
        want_id: str = "",
        days: Iterable[date] | None = None,
        subjects: set[str] | None = None,
        latest: bool = False,
    ) -> tuple[Outcome, set[str]]:
        """Record `dataset`'s values in `read` -- on `days` and for
        `subjects` where given, each subject's latest day alone where
        `latest` -- against `want_id` where given. What the lake answered,
        and the subjects a row was sent for."""
        wanted = set(days) if days is not None else None
        rate_rows = await self._rate_rows(read, key, dataset, wanted)
        prices = await self._prices(read, dataset, wanted)
        if subjects is not None:
            rate_rows = [r for r in rate_rows if r.meta.subjects[0].entity_id in subjects]
            prices = [p for p in prices if p.meta.subjects[0].entity_id in subjects]
        if latest:
            rate_rows, prices = _latest(rate_rows), _latest(prices)
        unresolved = [h.code for h in self.status.records.values() if h.miss]
        if prices or (dataset == FX and self.status.aud.miss):
            unresolved += [AUD] if self.status.aud.miss else []
        self.raw.save_firsts()
        counts = self.wants.sent_to(dataset)
        before = (counts.recorded, counts.restated, counts.unchanged)
        if rate_rows:
            await self.rates.record(dataset, rate_rows, want_id)
        if prices:
            await self.wants.record("prices", prices, dataset, want_id)
        sent = {r.meta.subjects[0].entity_id for r in [*rate_rows, *prices]}
        outcome = Outcome(
            counts.recorded - before[0],
            counts.restated - before[1],
            counts.unchanged - before[2],
            tuple(unresolved),
        )
        return outcome, sent

    async def check(self) -> dict[str, Outcome]:
        """Ask each table whether it changed; record the latest month of
        each one sent, for its pushed datasets."""
        done: dict[str, Outcome] = {}
        for table in TABLES:
            held = self.status.sources[table]
            try:
                read, key, modified = await self.read(table, held.last_modified)
            except (PortalUnreachable, NotRead) as failed:
                log.warning("%s was not read: %s", table, failed)
                continue
            if read is None:
                continue
            latest = read.days[-1] if read.days else self.today()
            recent = {d for d in read.days if d >= latest - timedelta(days=PUSHED_DAYS)}
            unresolved: tuple[str, ...] = ()
            for dataset in KEYS:
                if dataset == RESTRICTED or table not in TABLES_OF[dataset]:
                    continue
                outcome, _ = await self.record(read, key, dataset, days=recent)
                done[f"{table}:{dataset}"] = outcome
                unresolved += outcome.unresolved
            # Asked whole again while a record waits, so its values are
            # recorded once the deployment holds it.
            held.last_modified = "" if unresolved else modified
            log.info(
                "%s read to %s%s", table, latest, f"; not held: {unresolved}" * bool(unresolved)
            )
        await self.resolve_pulled()
        return done

    async def resolve_pulled(self) -> None:
        """The records of the third parties' columns, read only when wanted,
        resolved so a want can name them, as the rest are by recording."""
        for column in RATE_COLUMNS.values():
            if column.dataset == RESTRICTED:
                await self.record_of(column.record)

    # ── Wants ───────────────────────────────────────────────────────────

    async def on_observations_wanted(
        self, heard: meridian.Heard[ops.ObservationsWantedEvent]
    ) -> None:
        await self.wants.hear(heard, self.answer)

    async def on_want_withdrawn(self, heard: meridian.Heard[ops.WantWithdrawnEvent]) -> None:
        self.wants.withdraw(heard.message.want_id)
        log.info("standing want %s withdrawn", heard.message.want_id)

    def _days(self, want: ops.ObservationsWantedEvent) -> list[date] | None:
        """The days a want asks; None where it asks only the latest."""
        if want.business_date:
            return [date.fromisoformat(want.business_date)]
        if want.valid_from_ns or want.valid_until_ns:
            # Whole seconds, so the last nanosecond before a midnight is
            # that day's, never rounded into the next.
            start = datetime.fromtimestamp(want.valid_from_ns // 10**9, SYDNEY).date()
            until = want.valid_until_ns - 1 if want.valid_until_ns else _ns(self.now())
            end = datetime.fromtimestamp(until // 10**9, SYDNEY).date()
            span = [start + timedelta(days=n) for n in range((end - start).days + 1)]
            return span[-MOST_DAYS:]
        return None

    async def _held(self, dataset: str) -> set[str]:
        """The subjects `dataset` records, resolved now where not yet."""
        held: set[str] = set()
        for column in RATE_COLUMNS.values():
            if column.dataset == dataset:
                held.add(await self.record_of(column.record))
        if any(dataset_of_fx(s) == dataset for s in FX_COLUMNS):
            held.add(await self.aud())
        return held - {""}

    async def answer(
        self,
        want: ops.ObservationsWantedEvent,
        key: str,
        subjects: list[str],
        kinds: tuple[int, ...],
    ) -> dict[str, str]:
        """One want answered from the RBA: its values recorded against it,
        and each subject declined, with why."""
        if key not in KEYS or want.data_type not in ("", RATE, PRICE):
            return {s: "not_covered" for s in subjects}
        held = await self._held(key)
        declined = {s: "not_covered" for s in subjects if s not in held}
        asked = [s for s in subjects if s in held]
        if not asked:
            return declined
        if want.standing:
            self.wants.stand(want, asked, kinds)
        days = self._days(want)
        if days is not None:
            days = [d for d in days if d <= self.today()]
        sent: set[str] = set()
        if days is None or days:
            for table in TABLES_OF[key]:
                try:
                    read, raw_key, _ = await self.read(table)
                except (PortalUnreachable, NotRead) as failed:
                    log.warning("want %s: %s was not read: %s", want.want_id, table, failed)
                    continue
                if read is None:
                    continue
                last = read.days[-1] if read.days else self.today()
                wanted = (
                    set(days)
                    if days is not None
                    else {d for d in read.days if d >= last - timedelta(days=PUSHED_DAYS)}
                )
                _, got = await self.record(
                    read,
                    raw_key,
                    key,
                    want_id=want.want_id,
                    days=wanted,
                    subjects=set(asked),
                    latest=days is None,
                )
                sent |= got
        for subject in asked:
            if subject not in sent:
                declined[subject] = "source_silent"
        return declined


def _latest(rows: list[Any]) -> list[Any]:
    """Each subject's rows of its latest day alone."""
    last: dict[str, str] = {}
    for row in rows:
        subject = row.meta.subjects[0].entity_id
        last[subject] = max(last.get(subject, ""), row.meta.business_date)
    return [r for r in rows if r.meta.business_date == last[r.meta.subjects[0].entity_id]]


def _third_party(series: str) -> bool:
    """Whether series.py names `series` a third party's column."""
    column = RATE_COLUMNS.get(series)
    if column is not None:
        return column.dataset == RESTRICTED
    return series in FX_COLUMNS and dataset_of_fx(series) == RESTRICTED
