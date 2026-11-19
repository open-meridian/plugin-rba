"""The data suite (meridian.suites), each case the Reserve Bank of
Australia's series present mapped to the plugin's own conversion of the
RBA's recorded tables, the whole suite passing.

Presented: the exchange rates' price cases (each a close of the Australian
dollar's cash instrument in the other currency, exact, a correction the
same row's next version, the dollar resolving to two records, a want
recorded against and a subject declined); `a-same-day-revision` (the Cash
Rate Target revised), `an-index-level` (the Cash Rate Total Return Index),
`a-curve-for-a-date` and `a-tenor-not-published` (F2's yields of 3 and 6
January 2014: the 10-year alone, then all four); the wants and licences
cases.

Not presented, each with why: every case about a kind of data the RBA never
publishes here (bars, trades, quotes, venues, crypto, outcomes, chains,
filings, holdings, dividends, ratings, pools, derived series); the calendar
cases (no calendar declared); `a-rate-fixing` (it asks for percentiles,
which the RBA does not state), `two-conventions-one-tenor` (no bill),
`a-curve-point-from-another-source`; `a-daily-close` and
`reports-its-feed-delay` (the RBA states no published time);
`records-a-datasets-liveness`.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from meridian.plugin.v1 import operations_pb2 as ops
from meridian.suites import ANSWERED_BY_SDK, Recorder, run, suite

from rba.portal import PATHS, Fetched, SyntheticPortal

from conftest import AT, CURVES, FX, HELD, INSTANCE, RATES, feed, fx_want, resolving, want

NEVER = {
    "bars": "the RBA states one rate a day: no open, high, low or volume",
    "a crypto asset's price": "the RBA rates currencies: no token",
    "prices on a venue": "the RBA's rates are its own, no venue's",
    "a security's price": "the RBA rates currencies: no security another source named",
    "trades": "the RBA states one rate a day: no trades",
    "quotes": "the RBA states one rate a day: no quotes",
    "settlement dates": "records each value as published; never computes a settlement date",
    "outcomes": "the RBA publishes no event contract, so no outcome",
    "disputed outcomes": "the RBA publishes no event contract, so no outcome disputed",
    "streams": "it asks the RBA hourly; it streams nothing",
    "option chains": "the RBA publishes no option chain",
    "filings": "the RBA publishes rates: no company's filings",
    "holdings": "the RBA publishes rates: no holdings report",
    "corporate actions": "the RBA publishes rates: no declared dividend",
    "ratings": "the RBA publishes rates: no rating",
    "derived series": "the RBA's values are recorded as published: no series derived from them",
    "factors": "the RBA publishes rates: no pool, so no pool's factor",
    "calendars": (
        "its datasets declare no calendar: the platform holds none for the Australian dollar yet"
    ),
    "publication times": "the RBA states no published time for a value",
}
NOT_PRESENTED = {
    **{c.name: NEVER[c.about] for c in suite("data").cases if c.about in NEVER},
    "a-rate-fixing": "the RBA states no percentiles for the cash rate",
    "two-conventions-one-tenor": "the RBA publishes no bill here: one convention a point",
    "a-curve-point-from-another-source": "the RBA publishes no curve point another source does",
    "queries-the-lake-within-bounds": "it records no trades",
    "a-daily-close": "the RBA states no published time for a rate",
}


class Changed(SyntheticPortal):
    """The RBA, read twice: as recorded, then with the Cash Rate Target of
    18 November revised and the euro's rate of 18 November corrected."""

    def __init__(self) -> None:
        super().__init__(lambda: AT)
        self.reads: dict[str, int] = {}

    async def get(self, path: str, since: str = "") -> Fetched:
        got = await super().get(path, "")
        table = "F1" if path == PATHS["F1"] else "F11.1" if path == PATHS["F11.1"] else ""
        self.reads[table] = self.reads.get(table, 0) + 1
        if not table or self.reads[table] == 1:
            return got
        old = (
            "18-Nov-2026,4.85,,4.85"
            if table == "F1"
            else "18-Nov-2026,0.6720,62.60,4.4798,106.96,0.6115"
        )
        new = (
            "18-Nov-2026,4.60,,4.85"
            if table == "F1"
            else "18-Nov-2026,0.6720,62.60,4.4798,106.96,0.6199"
        )
        assert old in got.text
        body = got.text.replace(old, new).encode()
        return Fetched(path, 200, body, got.fetched_at, got.date, got.last_modified + " later")


async def _hear(recorder: Recorder, work: Any, message: Any) -> None:
    recorder.answer("ObservationsWanted", lambda _: message)
    await recorder.hear(work)


def _span(day: datetime, days: int) -> tuple[int, int]:
    return int(day.timestamp()) * 10**9, int((day + timedelta(days=days)).timestamp()) * 10**9


def producers(tmp: Path) -> dict[str, Callable[[Recorder], Awaitable[None]]]:
    async def read(recorder: Recorder) -> None:
        resolving(recorder)
        work = feed(tmp, recorder)
        await work.check()

    async def changed(recorder: Recorder) -> None:
        resolving(recorder)
        work = feed(tmp, recorder, portal=Changed())
        await work.check()
        await work.check()

    async def two_records(recorder: Recorder) -> None:
        resolving(recorder, ambiguous="AUD")
        await feed(tmp, recorder).check()

    async def curve(recorder: Recorder) -> None:
        resolving(recorder)
        work = feed(tmp, recorder)
        start, until = _span(datetime(2014, 1, 3, tzinfo=ZoneInfo("Australia/Sydney")), 4)
        asked = want("w-c", [HELD["Australian Government bond yields"]], dataset=CURVES)
        asked.message.valid_from_ns, asked.message.valid_until_ns = start, until
        await _hear(recorder, work, asked.message)

    async def gap(recorder: Recorder) -> None:
        resolving(recorder)
        work = feed(tmp, recorder)
        agb = HELD["Australian Government bond yields"]
        await _hear(recorder, work, want("w-g", [agb], day="2014-01-03", dataset=CURVES).message)
        sent = [r for b in recorder.on("RecordRates") for r in b.rates]
        assert {(r.tenor.count, r.tenor.unit) for r in sent} == {(10, ops.TENOR_UNIT_YEAR)}

    def wanted(message: Any) -> Callable[[Recorder], Awaitable[None]]:
        async def produce(recorder: Recorder) -> None:
            resolving(recorder)
            work = feed(tmp, recorder)
            await _hear(recorder, work, message)

        return produce

    async def licences(recorder: Recorder) -> None:
        recorder.answer(
            "ListDatasets",
            lambda _: ops.ListDatasetsResult(licences=[ops.DatasetLicence(dataset=FX)]),
        )
        work = feed(tmp, recorder)
        await work.wants.read_licences()
        assert work.wants.licensed == {FX}

    async def withdrawn(recorder: Recorder) -> None:
        resolving(recorder)
        work = feed(tmp, recorder)
        recorder.answer(
            "WantWithdrawn", lambda _: ops.WantWithdrawnEvent(want_id="w-s", dataset=RATES)
        )
        await recorder.hear(work)

    return {
        "the-forming-day-restated": changed,
        "an-exact-price": read,
        "an-fx-rate": read,
        "an-asset-that-does-not-resolve": two_records,
        "a-want-recorded-against": wanted(fx_want("w-1", "2026-10-01").message),
        "a-subject-declined": wanted(fx_want("w-2", "2026-10-01", subject="LCL-CAD").message),
        "a-standing-want-withdrawn": withdrawn,
        "reads-its-datasets-licences": licences,
        "a-same-day-revision": changed,
        "an-index-level": read,
        "a-curve-for-a-date": curve,
        "a-tenor-not-published": gap,
    }


def test_the_data_suite_passes(tmp_path: Path) -> None:
    report = run("data", producers(tmp_path), not_presented=NOT_PRESENTED, instance_id=INSTANCE)
    assert report.passed, report.failures
    assert sorted(report.not_presented) == sorted(NOT_PRESENTED)
    assert len(report.passed_cases) == 12 + len(ANSWERED_BY_SDK)
