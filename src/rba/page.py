"""The plugin's pages, under Manage alone: the data role's common pages
(spec/plugin-pages-follow-their-role), Connection and Datasets, in its
order, each also a read tool for agents on the deployment's MCP under the
role's names (`read_connection`, `read_datasets`). Each record is the
role's (`meridian.roles.data`), extended with the Reserve Bank of
Australia's fields; each template is the role's, with the RBA's nuance at
its blocks only, as plugin-ecb's are.

A data plugin shows its connectivity, its data subscriptions and how its
entitlements resolve, and no market data (the product owner, 2026-10-03):

- **Connection** (`/`): "Key" -- the mode (Live or Sample data), "No key
  needed", what the RBA serves; "Limits and use" -- the RBA states no
  figure, the requests made, the last check and error; "Stream": it does
  not stream. Then a tab of its own (`?tab=sources`), **Sources**, one line
  per table -- F1, F2, F17 and F11.1: its state, the latest day read, its
  calls, its last error, and in its detail where it reads and what of it is
  kept.
- **Datasets** (`/datasets`): "Served", "Wants" and "Subjects", each with
  the four datasets; then a tab of its own (`?tab=records`), **Records**:
  each record and exchange rate, with its convention and the deployment's
  instrument for it or why there is none, and each column read and not
  carried -- one line a row, searched and paged by the kit's om-pager to
  fit one screen.

Neither shows a rate or a price: those are the reading roles' to show.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import meridian
from meridian.roles import data

from . import records
from .declared import CATALOGUE
from .feed import Feed, SourceStatus, Status
from .portal import BASE, PATHS
from .series import (
    AGB,
    BABS,
    CASH_RATE_TRI,
    CURVES,
    FX,
    FX_COLUMNS,
    NOT_CARRIED,
    OIS,
    RATES,
    RESTRICTED,
    TABLES,
    ZERO_COUPON,
    dataset_of_fx,
)

TITLE = "Reserve Bank of Australia"
#: The kit these pages are built on: 0.12.0's "Facts" and "Next step".
KIT = "0.12.0"

pages = meridian.Pages(TITLE, templates=Path(__file__).parent / "templates", kit=KIT)

CONNECTION = "/"
DATASETS_PAGE = "/datasets"

MOST_QUERY = 100
CONNECTION_TABS = {"connection": "Connection", "sources": "Sources"}
TABS = {"served": "Served", "wants": "Wants", "records": "Records"}
#: The attribution the RBA's terms ask for.
ATTRIBUTION = "Source: Reserve Bank of Australia 2026"
SOURCE_NAMES = {
    "F1": "F1, money market (the cash rate; ASX's and FENICS's columns)",
    "F2": "F2, Australian Government bond yields",
    "F17": "F17, zero-coupon interest rates",
    "F11.1": "F11.1, exchange rates (WM/Reuters' A$1=USD among them)",
}
SHORT_NAMES = {
    "F1": "F1 money market",
    "F2": "F2 bond yields",
    "F17": "F17 zero-coupon",
    "F11.1": "F11.1 exchange rates",
}
DATASETS_OF = {
    "F1": f"{RATES}, {RESTRICTED}",
    "F2": CURVES,
    "F17": CURVES,
    "F11.1": f"{FX}, {RESTRICTED}",
}
#: What each table's kept answer holds, as Sources says it.
KEPT = {
    "F1": "Kept with the RBA's own columns alone: ASX's and FENICS's are served, not kept",
    "F2": "Kept whole",
    "F17": "Kept whole",
    "F11.1": "Kept with the RBA's own columns alone: WM/Reuters' A$1=USD is served, not kept",
}
CONVENTIONS = {
    "money": "actual/365, simple: the plugin's statement; the RBA states per cent",
    "index": "an index level, 04-Jan-2011 = 100, as the RBA states it",
    "bonds": (
        "par yields, semi-annual, actual/actual: the plugin's statement; the RBA states "
        "per cent per annum, interpolated"
    ),
    "zero": (
        "continuously compounded, actual/365: the plugin's statement, read from the RBA's own "
        "discount factors"
    ),
    "ois": "par yields, actual/365 simple: the plugin's statement",
    FX: "units of the currency per Australian dollar, as the RBA states it",
}

_held: dict[str, Any] = {}


def hold(feed: Feed) -> None:
    """The feed the pages read, once the plugin has registered."""
    _held["feed"] = feed


def _status() -> tuple[Status, Feed | None]:
    feed: Feed | None = _held.get("feed")
    return (feed.status if feed is not None else Status(), feed)


def _iso(moment: datetime | None) -> str:
    return moment.astimezone(UTC).isoformat(timespec="seconds") if moment else ""


def _day(day: date | None) -> str:
    return day.isoformat() if day else ""


def _source_state(held: SourceStatus, mode: str) -> str:
    if held.error and held.read_at is None:
        return "Not answering"
    if held.error:
        return "Answering"
    if held.read_at is None:
        return "Checking the RBA"
    return "Sample data" if mode == "synthetic" else "Answering"


def _state(status: Status) -> tuple[str, str, str]:
    """The head's status: its state, what it means, and its detail."""
    error = status.error
    if error and not status.read:
        return "error", "Not answering", error
    if error:
        return "warn", "Answering", error
    if not status.read:
        return "busy", "Checking the RBA", ""
    misses = [h.code for h in [*status.records.values(), status.aud] if h.miss]
    if misses:
        plural = "record" if len(misses) == 1 else "records"
        more = ", …" if len(misses) > 6 else ""
        return "warn", f"{len(misses)} {plural} not held", ", ".join(sorted(misses)[:6]) + more
    if status.mode == "synthetic":
        return "ok", "Sample data", ""
    return "ok", "Answering", ""


def _source(source: str, status: Status, instance: str) -> records.SourceRead:
    held = status.sources[source]
    return records.SourceRead(
        source=SOURCE_NAMES[source],
        dataset=", ".join(f"{instance}:{d}" for d in DATASETS_OF[source].split(", ")),
        kind=source,
        state=_source_state(held, status.mode),
        last_release=_day(held.latest_day),
        calls=held.fetches,
        last_error=held.error,
        reads=(
            "The answer recorded on 2026-11-19, committed with the plugin"
            if status.mode == "synthetic"
            else BASE + PATHS[source]
        ),
        history=KEPT[source],
    )


def connection_read(status: Status, feed: Feed | None) -> records.ConnectionRead:
    state, said, _ = _state(status)
    kept = feed.raw.keys() if feed is not None else []
    window = ""
    if feed is not None and feed.raw.granted:
        window = "in the storage the deployment grants, as its responses settings say"
    elif feed is not None:
        window = "in a directory of the plugin's own: this deployment grants no storage"
    instance = feed.plugin.identity.instance_id if feed is not None else "rba"
    answered = status.read or status.mode == "synthetic"
    return records.ConnectionRead(
        mode="Sample data" if status.mode == "synthetic" else "Live",
        credentials=[],
        entitled_at_vendor=(
            "The cash rate, the bond and zero-coupon yields and the exchange rates: no key"
            if answered
            else ""
        ),
        limit=(
            "The RBA states no figure; the plugin asks one request at a time, at most one every "
            "two seconds, and asks each table every hour whether it changed"
        ),
        calls=status.fetches,
        last_call_at=_iso(status.checked_at),
        last_error=status.error,
        sessions=None,
        state=state,
        said=said,
        source=(
            "The answers recorded on 2026-11-19, committed with the plugin"
            if status.mode == "synthetic"
            else f"{BASE}'s statistical tables"
        ),
        checked_at=_iso(status.checked_at),
        sources=[_source(source, status, instance) for source in TABLES],
        responses_kept=len(kept),
        kept_for=window,
    )


def _record_dataset(code: str) -> tuple[str, str, str]:
    """A record's dataset, what it is recorded as, and its convention."""
    if code == AGB.code:
        return CURVES, "par yields at 2, 3, 5 and 10 years", CONVENTIONS["bonds"]
    if code == ZERO_COUPON.code:
        return CURVES, "zero rates at 3 months to 10 years", CONVENTIONS["zero"]
    if code == CASH_RATE_TRI.code:
        return RATES, "index levels", CONVENTIONS["index"]
    if code == BABS.code:
        return RESTRICTED, "fixings at 1, 3 and 6 months (ASX)", CONVENTIONS["money"]
    if code == OIS.code:
        return RESTRICTED, "par yields at 1, 3 and 6 months (FENICS)", CONVENTIONS["ois"]
    return RATES, "fixings", CONVENTIONS["money"]


def datasets_read(status: Status, feed: Feed | None) -> records.DatasetsRead:
    instance = feed.plugin.identity.instance_id if feed is not None else "rba"
    answered = status.read or status.mode == "synthetic"
    served = data.served(
        CATALOGUE,
        instance,
        feed.wants if feed is not None else None,
        "Yes: no key needed" if answered else "Not asked yet",
    )
    rows = [
        records.RecordRead(
            code=h.code,
            name=h.name,
            dataset=_record_dataset(h.code)[0],
            recorded_as=_record_dataset(h.code)[1],
            convention=_record_dataset(h.code)[2],
            instrument_id=h.instrument_id,
            miss=h.miss,
            latest_day=_day(h.latest_day),
        )
        for h in status.records.values()
    ]
    aud = status.aud
    if aud.instrument_id or aud.miss:
        rows += [
            records.RecordRead(
                code=code,
                name=f"A$1={code} ({series}, source {source})",
                dataset=dataset_of_fx(series),
                recorded_as=f"the Australian dollar's price in {code}, a close",
                convention=CONVENTIONS[FX],
                instrument_id=aud.instrument_id,
                miss=aud.miss.replace("_", " "),
                latest_day=_day(status.fx_days.get(code)),
            )
            for series, (code, source) in sorted(FX_COLUMNS.items(), key=lambda s: s[1][0])
        ]
    rows += [
        records.RecordRead(
            code=held,
            name=why,
            dataset="",
            recorded_as="not carried",
            convention="",
            instrument_id="",
            miss="not carried",
        )
        for held, why in NOT_CARRIED.items()
        if status.records
    ]
    other = [
        f"{series}: {table} names its source {said}, not the one expected; not recorded"
        for table, held in status.sources.items()
        for series, said in sorted(held.other_source.items())
    ]
    return records.DatasetsRead(
        served=served,
        wants=list(data.want_rows(feed.wants)) if feed is not None else [],
        reads_instruments=True,
        attribution=ATTRIBUTION,
        records=rows,
        unread=other
        + [
            f"{line} ({n} reads)"
            for held in status.sources.values()
            for line, n in sorted(held.unread.items())
        ],
    )


def figures(status: Status, feed: Feed | None) -> list[meridian.Figure]:
    """The data role's figures, in its order (`meridian.roles.data`); the
    RBA's plugin reports none of its own."""
    state, said, why = _state(status)
    if status.mode == "synthetic" and state == "ok":
        connection: Any = "Sample data"
    elif said == "Not answering":
        connection = meridian.Figure("", said, state="error", why=why[:200])
    else:
        error = status.error
        connection = meridian.Figure(
            "", "Answering", state="warn" if error else None, why=error[:200]
        )
    last = feed.wants.counts.last_ns if feed is not None else 0
    return data.figures(
        connection=connection,
        entitled_at_vendor=f"{len(CATALOGUE)} of {len(CATALOGUE)} datasets",
        stream="Does not stream",
        last_recorded=(datetime.fromtimestamp(last / 10**9, UTC) if last else None),
    )


def _moment(value: str) -> str:
    """An ISO moment as a person reads it, to the minute in UTC."""
    if not value:
        return ""
    if len(value) == 10:
        return value
    return datetime.fromisoformat(value).astimezone(UTC).strftime("%Y-%m-%d %H:%M UTC")


def _weekday(value: str) -> str:
    return date.fromisoformat(value).strftime("%a %d %b %Y") if value else ""


def matching(query: str, *texts: str) -> bool:
    """Whether every word of a search is in one of `texts`, case aside."""
    words = query.lower().split()
    held = " ".join(texts).lower()
    return all(word in held for word in words)


pages.environment.filters["moment"] = _moment
pages.environment.filters["day"] = _weekday


@pages.page(
    CONNECTION,
    "Connection",
    levels="admin",
    answers=records.ConnectionRead,
    name="read_connection",
    description=(
        "How this plugin reaches the Reserve Bank of Australia's statistical tables, as "
        "every data plugin's Connection answers it: the mode (Live or Sample data), no key "
        "needed, what the RBA serves, its limits and the requests made, the last check and "
        "why it failed if it did; it does not stream. Then the RBA's own: each table -- F1, "
        "F2, F17 and F11.1 -- with its state, the latest day read, its calls and last error, "
        "and what of it is kept; and how many answers are kept. No rate."
    ),
)
async def connection(request: meridian.Request) -> meridian.Response:
    status, feed = _status()
    read = connection_read(status, feed)
    tab = request.query.get("tab", "connection")
    return pages.answer(
        "connection.html",
        read,
        detail=_state(status)[2],
        # Named apart from the SDK's own `tab` and `tabs` (0.32.3), which
        # would draw the data role's section row in their place.
        view=tab if tab in CONNECTION_TABS else "connection",
        views=CONNECTION_TABS,
        short=SHORT_NAMES,
    )


@pages.page(
    DATASETS_PAGE,
    "Datasets",
    levels="admin",
    answers=records.DatasetsRead,
    name="read_datasets",
    description=(
        "What this plugin serves the lake, as every data plugin's Datasets answers it: its "
        "four datasets as the catalogue declares them (the cash rates; the bond and "
        "zero-coupon yields; the exchange rates against the Australian dollar, prices; the "
        "third parties' columns, served, not kept), whether a deployment admin has licensed "
        "each, what it recorded and declined; the standing wants it keeps current and the "
        "wants it answered. Then the RBA's own: the attribution its terms ask for, and each "
        "record and exchange rate with its convention and the deployment's instrument for it "
        "or why there is none. No rate."
    ),
)
async def datasets(request: meridian.Request) -> meridian.Response:
    status, feed = _status()
    read = datasets_read(status, feed)
    # A browser draws one tab, its search narrowing the records drawn; a
    # tool answers every tab.
    query = request.query.get("q", "").strip()[:MOST_QUERY]
    tab = request.query.get("tab", "served")
    tab = "records" if query else tab if tab in TABS else "served"
    shown = [r for r in read.records if matching(query, r.code, r.name, r.dataset)]
    return pages.answer(
        "datasets.html",
        read,
        query=query,
        tab=tab,
        tabs=TABS,
        shown=shown,
        state=_state(status),
        checked_at=_iso(status.checked_at),
    )
