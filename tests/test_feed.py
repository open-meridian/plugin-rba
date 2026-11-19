"""The plugin's own conversion of the Reserve Bank of Australia's recorded
tables."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
from meridian.operations import as_decimal
from meridian.plugin.v1 import operations_pb2 as ops
from meridian.suites import Recorder

from rba.answers import NotRead, parse, without
from rba.portal import PATHS, SyntheticPortal

from conftest import AT, AUD, CURVES, FX, HELD, INSTANCE, RESTRICTED, feed, fx_want, resolving, want


def checked(tmp: Path, *left_out: str) -> Recorder:
    plugin = resolving(Recorder(INSTANCE), *left_out)
    asyncio.run(feed(tmp, plugin).check())
    return plugin


def rates_of(plugin: Recorder, subject: str, want_id: str | None = None) -> list[ops.Rate]:
    return [
        r
        for b in plugin.on("RecordRates")
        if want_id is None or b.want_id == want_id
        for r in b.rates
        if r.meta.subjects[0].entity_id == subject
    ]


def heard(tmp: Path, *asked: object, plugin: Recorder | None = None) -> Recorder:
    """The tables checked, then each want heard."""
    held = plugin or resolving(Recorder(INSTANCE))
    work = feed(tmp, held)
    asyncio.run(work.check())
    for one in asked:
        held.answer("ObservationsWanted", lambda _, w=one: w.message)  # type: ignore[misc]
        asyncio.run(held.hear(work))
    return held


def on(rates: list[ops.Rate], day: str, tenor: tuple[int, int] | None = None) -> ops.Rate:
    return next(
        r
        for r in rates
        if r.meta.business_date == day and (tenor is None or (r.tenor.count, r.tenor.unit) == tenor)
    )


def test_the_cash_rates_and_the_index(tmp_path: Path) -> None:
    plugin = checked(tmp_path)
    cash = on(rates_of(plugin, HELD["Interbank Overnight Cash Rate"]), "2026-11-18")
    assert cash.kind == ops.RATE_KIND_FIXING and str(as_decimal(cash.value.value)) == "4.85"
    assert cash.convention.day_count == ops.DAY_COUNT_ACT_365_FIXED
    assert cash.convention.compounding == ops.COMPOUNDING_SIMPLE
    assert str(as_decimal(cash.volume.amount)) == "1031000000" and cash.transaction_count == 9
    assert cash.meta.raw.key.endswith("-f1.json.gz") and not cash.meta.source_times
    target = on(rates_of(plugin, HELD["Cash Rate Target"]), "2026-11-18")
    assert str(as_decimal(target.value.value)) == "4.85"
    index = on(rates_of(plugin, HELD["Cash Rate Total Return Index"]), "2026-11-19")
    assert index.kind == ops.RATE_KIND_INDEX_LEVEL and index.value.index_base == "2011-01-04=100"
    assert str(as_decimal(index.value.value)) == "147.554507"


def test_the_curves_par_and_zero(tmp_path: Path) -> None:
    plugin = checked(tmp_path)
    agb = rates_of(plugin, HELD["Australian Government bond yields"])
    ten = on(agb, "2026-11-11", (10, ops.TENOR_UNIT_YEAR))
    assert ten.kind == ops.RATE_KIND_PAR_YIELD and str(as_decimal(ten.value.value)) == "5.044"
    assert ten.convention.periods_per_year == 2
    assert {r.meta.source.dataset for r in agb} == {CURVES}
    zero = rates_of(plugin, HELD["Zero-coupon interest rates"])
    three = on(zero, "2026-10-30", (3, ops.TENOR_UNIT_MONTH))
    assert three.kind == ops.RATE_KIND_ZERO and str(as_decimal(three.value.value)) == "4.79"
    assert three.convention.compounding == ops.COMPOUNDING_CONTINUOUS
    assert len({(r.tenor.count, r.tenor.unit) for r in zero}) == 40


def test_the_exchange_rates_the_dollars_price_never_inverted(tmp_path: Path) -> None:
    plugin = checked(tmp_path)
    prices = [p for b in plugin.on("RecordPrices") for p in b.prices]
    euro = next(p for p in prices if p.meta.row_key == "AUDEUR:2026-11-18")
    assert euro.meta.subjects[0].entity_id == AUD and euro.kind == ops.PRICE_KIND_CLOSE
    assert str(as_decimal(euro.price.amount)) == "0.6115" and euro.price.currency_code == "EUR"
    assert {p.meta.source.dataset for p in prices} == {FX}
    assert not any(p.price.currency_code == "USD" for p in prices)


def test_the_third_parties_columns_are_pulled_and_never_kept(tmp_path: Path) -> None:
    plugin = heard(
        tmp_path,
        fx_want("w-usd", "2026-11-18", RESTRICTED),
        want("w-bab", [HELD["BABs/NCDs"]], day="2026-11-18", dataset=RESTRICTED),
    )
    assert not rates_of(plugin, HELD["BABs/NCDs"], "")
    usd = [p for b in plugin.on("RecordPrices") if b.want_id == "w-usd" for p in b.prices]
    assert [str(as_decimal(p.price.amount)) for p in usd] == ["0.6739"]
    assert usd[0].meta.source.dataset == RESTRICTED and not usd[0].meta.HasField("raw")
    babs = rates_of(plugin, HELD["BABs/NCDs"], "w-bab")
    three = on(babs, "2026-11-18", (3, ops.TENOR_UNIT_MONTH))
    assert str(as_decimal(three.value.value)) == "5.07" and not three.meta.HasField("raw")
    work = feed(tmp_path)
    for key in work.raw.keys():  # noqa: SIM118 - RawStore.keys
        kept = work.raw.read(key)
        assert kept is not None
        assert "FIRMMBAB90D" not in kept["body"] and "FXRUSD" not in kept["body"]


def test_a_record_not_held_is_reported_missing_and_waits(tmp_path: Path) -> None:
    plugin = resolving(Recorder(INSTANCE), "Cash Rate Target")
    portal = SyntheticPortal(lambda: AT)
    work = feed(tmp_path, plugin, portal=portal)
    asyncio.run(work.check())
    asyncio.run(work.check())
    missed = {i.value for p in plugin.on("ReportMissingInstrument") for i in p.identifiers}
    assert missed == {"Cash Rate Target"} and not rates_of(plugin, HELD["Cash Rate Target"])
    # The third parties' records are resolved at a check, though pulled only.
    assert work.status.records["OIS"].instrument_id == HELD["OIS"]
    # F1 is asked whole again while its record waits; the rest answer 304.
    assert portal.asked.count(PATHS["F1"]) == 2


def test_wants_declined(tmp_path: Path) -> None:
    target = HELD["Cash Rate Target"]
    plugin = heard(
        tmp_path,
        want("w-1", [target], day="2026-10-01"),
        want("w-2", ["INS-ELSE"], day="2026-10-01"),
        want("w-3", [target], day="2026-10-04"),
        want("w-4", [target], day="2026-11-25"),
        fx_want("w-5", "2026-11-15"),
        want("w-6", [HELD["BABs/NCDs"]], day="2026-11-17"),
    )
    against = rates_of(plugin, target, "w-1")
    assert [r.meta.business_date for r in against] == ["2026-10-01"]
    reasons = [(d.want_id, ops.UnansweredReason.Name(d.reason)) for d in plugin.on("DeclineWant")]
    assert reasons == [
        ("w-2", "UNANSWERED_REASON_NOT_COVERED"),
        ("w-3", "UNANSWERED_REASON_SOURCE_SILENT"),
        ("w-4", "UNANSWERED_REASON_SOURCE_SILENT"),
        ("w-5", "UNANSWERED_REASON_SOURCE_SILENT"),
        ("w-6", "UNANSWERED_REASON_NOT_COVERED"),
    ]


def test_the_latest_wanted(tmp_path: Path) -> None:
    target = HELD["Cash Rate Target"]
    plugin = heard(tmp_path, want("w-l", [target]))
    assert [r.meta.business_date for r in rates_of(plugin, target, "w-l")] == ["2026-11-18"]


def test_nothing_recorded_twice_in_a_process(tmp_path: Path) -> None:
    plugin = resolving(Recorder(INSTANCE))
    work = feed(tmp_path, plugin)
    asyncio.run(work.check())
    before = (len(plugin.on("RecordRates")), len(plugin.on("RecordPrices")))
    asyncio.run(work.check())
    assert (len(plugin.on("RecordRates")), len(plugin.on("RecordPrices"))) == before


def test_a_column_naming_another_source_is_not_recorded(tmp_path: Path) -> None:
    class Moved(SyntheticPortal):
        async def get(self, path: str, since: str = "") -> object:  # type: ignore[override]
            got = await super().get(path, since)
            if path != PATHS["F11.1"] or got.status != 200:
                return got
            body = got.text.replace(
                "Source,WM/Reuters,RBA,RBA,RBA,RBA", "Source,WM/Reuters,RBA,RBA,RBA,LSEG"
            )
            return type(got)(path, 200, body.encode(), got.fetched_at, got.date, got.last_modified)

    plugin = resolving(Recorder(INSTANCE))
    work = feed(tmp_path, plugin, portal=Moved(lambda: AT))
    asyncio.run(work.check())
    prices = [p for b in plugin.on("RecordPrices") for p in b.prices]
    assert prices and not any(p.price.currency_code == "EUR" for p in prices)
    assert work.status.sources["F11.1"].other_source == {"FXREUR": "LSEG"}


def test_the_tables_read_as_written() -> None:
    held = SyntheticPortal(lambda: AT).recordings
    f1 = parse(held["F1"].body.decode(), "F1")
    assert f1.sources["FIRMMBAB90D"] == "ASX" and f1.sources["FIRMMOIS3D"] == "FENICS"
    assert f1.days[0].isoformat() == "2011-01-04" and not f1.unread
    kept = without(held["F1"].body.decode(), {"FIRMMCRTD"})
    assert "FIRMMBAB90D" not in kept and "FIRMMCRTD" in kept
    assert parse(kept, "F1").sources == {"FIRMMCRTD": "RBA"}
    with pytest.raises(NotRead):
        parse("<html>Not found</html>", "F1")
