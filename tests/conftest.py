"""Shared stand-ins: the Reserve Bank of Australia's recorded tables, a
fixed clock, the deployment holding some of the RBA's records and every
currency, and the lake's wants as the sidecar delivers them."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from meridian.plugin.v1 import operations_pb2 as ops
from meridian.receive import Heard
from meridian.suites import Recorder

from rba.feed import Feed
from rba.portal import SyntheticPortal
from rba.raw import RawStore

#: After the recording: 22:00 UTC on Thursday 19 November 2026, 09:00 on
#: the 20th in Sydney.
AT = datetime(2026, 11, 19, 22, 0, tzinfo=UTC)
INSTANCE = "rba"
RATES = f"{INSTANCE}:rba_rates"
CURVES = f"{INSTANCE}:rba_curves"
FX = f"{INSTANCE}:rba_fx"
RESTRICTED = f"{INSTANCE}:rba_restricted"
AUD = "LCL-AUD"
#: The records the tests' deployment holds, by their code at `rba`.
HELD = {
    "Cash Rate Target": "INS-CRT",
    "Interbank Overnight Cash Rate": "INS-CASH",
    "Cash Rate Total Return Index": "INS-TRI",
    "Australian Government bond yields": "INS-AGB",
    "Zero-coupon interest rates": "INS-ZERO",
    "BABs/NCDs": "INS-BABS",
    "OIS": "INS-OIS",
}


def resolving(plugin: Recorder, *left_out: str, ambiguous: str = "") -> Recorder:
    """`plugin` resolving `HELD`'s records but `left_out`, and each ISO code to
    `LCL-<code>` (`ambiguous` to two records)."""

    def resolved(params: ops.ResolveIdentifierParams) -> ops.ResolveIdentifierResult:
        named = params.identifiers[0]
        if named.scheme == "iso4217":
            if named.value == ambiguous:
                return ops.ResolveIdentifierResult(
                    found=False, miss_reason=ops.MISS_REASON_AMBIGUOUS
                )
            return ops.ResolveIdentifierResult(found=True, instrument_id=f"LCL-{named.value}")
        found = HELD.get(named.value, "") if named.source == "rba" else ""
        if not found or named.value in left_out:
            return ops.ResolveIdentifierResult(found=False, miss_reason=ops.MISS_REASON_NOT_FOUND)
        return ops.ResolveIdentifierResult(found=True, instrument_id=found)

    plugin.answer("ResolveIdentifier", resolved)
    return plugin


def feed(
    tmp: Path, plugin: Recorder | None = None, *, portal: Any = None, at: datetime = AT
) -> Feed:
    held = plugin if plugin is not None else resolving(Recorder(INSTANCE))
    return held.bind(Feed(portal or SyntheticPortal(lambda: at), RawStore(tmp), now=lambda: at))


def want(
    want_id: str,
    subjects: list[str],
    *,
    day: str = "",
    standing: bool = False,
    dataset: str = RATES,
    data_type: str = "meridian.v1.Rate",
    kinds: tuple[Any, ...] = (),
) -> Heard:  # type: ignore[type-arg]
    return Heard(
        row="ObservationsWanted",
        message=ops.ObservationsWantedEvent(
            want_id=want_id,
            dataset=dataset,
            data_type=data_type,
            subjects=[ops.SubjectRef(entity_id=s) for s in subjects],
            kinds=list(kinds),
            business_date=day,
            standing=standing,
        ),
    )


def fx_want(want_id: str, day: str, dataset: str = FX, subject: str = AUD) -> Heard:  # type: ignore[type-arg]
    return want(
        want_id,
        [subject],
        day=day,
        dataset=dataset,
        data_type="meridian.v1.Price",
        kinds=(ops.PRICE_KIND_CLOSE,),
    )
