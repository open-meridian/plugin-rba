"""What this version declares beside its role, `data` (W8.1, W4.1; the
catalogue from contract v18), built from code and used twice: `__main__`
registers with it, and `meridian plugin upload` reads it from the built image
(pyproject.toml's `[tool.meridian] declaration`).

**The catalogue: four datasets** (the product owner, items 128, 130, 132,
140 and 143, 2026-11-19: Tier 1, the cash rate, F2's yields, F17's zero
curve and FX, the third parties' columns their own dataset; their keys
proposed, the product owner's to approve):

- **`rba_rates`**: the Cash Rate Target, the Interbank Overnight Cash Rate
  and the Cash Rate Total Return Index -- rates, daily, from table F1;
- **`rba_curves`**: F2's Australian Government bond yields (par yields) and
  F17's zero-coupon yields (zero rates), each on its curve's record --
  rates, daily;
- **`rba_fx`**: the exchange rates against the Australian dollar the RBA
  states as its own, each the price of the Australian dollar's cash
  instrument in the other currency -- prices, daily, from table F11.1;
- **`rba_restricted`**: the columns the tables name as a third party's --
  F1's BABs/NCDs (ASX) and OIS (FENICS), F11.1's A$1=USD (WM/Reuters) --
  rates and prices.

The first three are pushed as the RBA publishes them and any past day
pulled when the lake wants it.

**Served, not kept** (ruling 132, as plugin-fred's `fred_restricted` and
plugin-bank-of-england's curves). The RBA says third-party content in its
data may not be used without the third party's consent. So `rba_restricted`
is pulled only, never pushed, and none of its columns is kept in the
plugin's storage; the rows the lake receives are recorded as any are.
Whether a deployment keeps them is its licence: "served, not kept" is the
default the clause in its terms asks the deployment admin to set (ruling
1032 retired `licence_default`, so the plugin declares none).

Each: `vendor` the Reserve Bank of Australia, no aggregator; `cadence` a
day; its day Sydney's (the RBA's business day), ending at midnight; no
calendar (the platform holds none for the Australian dollar yet); no venue;
`history` 0, as each series states; its terms and pricing (contract 30,
ruling 1032) the RBA's, in plain words, and no licence declared -- a
deployment's licence, set on the Data sources page, is the one enforced; a
gap asked again (`gap_recovery` `backfill`, W10.14).

**Storage:** the RBA's tables, its own columns alone (raw.py), archivable,
ten years by default.
"""

from __future__ import annotations

from meridian import DatasetDeclaration
from meridian.declaration import RecordKind

from .raw import DEFAULT_WINDOW_DAYS, RESPONSES
from .series import CURVES, FX, RATES, RESTRICTED

KEYS = (RATES, CURVES, FX, RESTRICTED)
#: The dataset served when wanted and never kept here (ruling 132).
NOT_KEPT = (RESTRICTED,)
VENDOR = "Reserve Bank of Australia"
RATE = "meridian.v1.Rate"
PRICE = "meridian.v1.Price"
CADENCE = 86_400
DAY_TIME_ZONE = "Australia/Sydney"
DAY_END_MINUTE = 0

#: The RBA's terms, in plain words (contract 30, ruling 1032), from its
#: copyright and disclaimer notice (https://www.rba.gov.au/copyright/),
#: read on 2026-11-19.
RBA_TERMS = (
    "The Reserve Bank of Australia's website and statistical tables: free, no key or "
    "account. Its financial data, and the cash rate, may be used, reproduced and published "
    "for personal or commercial use, provided no endorsement by the RBA is stated or implied, "
    "the source is not misrepresented, customers are not charged for access without being "
    "told the RBA publishes the data free of charge, and the use is lawful; the RBA does not "
    'recommend its financial data as a benchmark. Attribution: "Source: Reserve Bank of '
    'Australia". The RBA may withdraw or change the data, its methods or its schedule '
    "without notice."
)
TERMS = {
    RATES: RBA_TERMS
    + " The cash rate is administered by the RBA under its Cash Rate Procedures Manual.",
    CURVES: RBA_TERMS,
    FX: RBA_TERMS,
    RESTRICTED: RBA_TERMS
    + (
        " Some data contain third-party content, which may not be used without the third "
        "party's consent: the tables name these columns' sources as ASX (the BABs/NCDs), "
        "FENICS (the OIS) and WM/Reuters (A$1=USD). Its licence default is served, not kept "
        "(ruling 132): the plugin pulls it only when wanted and keeps none of its columns; "
        "whether the lake keeps its rows is the deployment admin's licence to set."
    ),
}


def _dataset(key: str, data_types: list[str], modes: list[str]) -> DatasetDeclaration:
    return DatasetDeclaration(
        key=key,
        vendor=VENDOR,
        data_types=data_types,
        modes=modes,
        cadence=CADENCE,
        history=0,
        terms_and_pricing=TERMS[key],
        gap_recovery="backfill",
        day_time_zone=DAY_TIME_ZONE,
        day_end_minute=DAY_END_MINUTE,
    )


CATALOGUE = [
    _dataset(RATES, [RATE], ["push", "pull"]),
    _dataset(CURVES, [RATE], ["push", "pull"]),
    _dataset(FX, [PRICE], ["push", "pull"]),
    _dataset(RESTRICTED, [RATE, PRICE], ["pull"]),
]

RESPONSES_KIND = RecordKind(RESPONSES, "Raw responses", window_days=DEFAULT_WINDOW_DAYS)
