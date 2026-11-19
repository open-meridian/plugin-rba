"""The Reserve Bank of Australia's series this version carries, what each
one is, and the record it is recorded against: the plugin's series map.

The RBA publishes each statistical table as a CSV whose columns each state
their own `Series ID`, `Units` and `Source`. Each column carried is named
here by its Series ID, with the source this version expects: a column whose
table states another source is not recorded, and the Datasets page says so.

**Rates** (`rba_rates`, table F1). The Cash Rate Target (`FIRMMCRTD`) and
the Interbank Overnight Cash Rate (`FIRMMCRID`), each a `fixing`, the cash
rate with its day's volume ($m, `FIRMMCRIV`, recorded in Australian dollars)
and number of transactions (`FIRMMCRIN`); the Cash Rate Total Return Index
(`FIRMMCTRI`), an `index_level`, "Index 04-Jan-2011=100". Per cent,
actual/365 simple: the Australian money market's convention, which the RBA
states on none of these columns -- the plugin's statement.

**Curves** (`rba_curves`). Table F2's Australian Government bond yields,
"interpolated", at 2, 3, 5 and 10 years: constant maturities, so each a
`par_yield` (ruling 130) at its tenor on one `rate_curve` record,
semi-annual, actual/actual -- the bonds' coupon frequency, the plugin's
statement: the RBA states "Per cent per annum". Table F17's zero-coupon
yields at 0.25 to 10 years every quarter, each a `zero` at its tenor on one
`rate_curve` record, continuously compounded: the plugin's statement, read
from the RBA's own discount factors (F17's 9.75-year discount factor of 30
October 2026, 0.61, is exp(-5.07% x 9.75); annual compounding would give
0.617). The indexed bond's yield (a real yield, another curve's) and the
0-year zero-coupon yield (no tenor) are **not carried**; F17's forward rates
are not recorded (ruling 131).

**FX** (`rba_fx`, table F11.1): each currency's daily rate, "A$1=<code>":
units of the currency per Australian dollar, so each is a `Price` of the
Australian dollar's cash instrument in that currency, never inverted. The
Trade-weighted Index (an index, not a rate) and the SDR (the IMF's) are not
carried.

**Third parties' columns** (`rba_restricted`, ruling 132). F1's end-of-day
1, 3 and 6-month BABs/NCDs (source ASX), each a `fixing` at its tenor on
one `rate_curve` record, actual/365 simple; F1's 1, 3 and 6-month OIS
(source FENICS), each a `par_yield` at its tenor on one `rate_curve`
record, actual/365 simple; and F11.1's A$1=USD (source WM/Reuters), a
`Price` as the other rates are. The RBA's copyright notice says third-party
material in its data needs the third party's consent, so these are served,
not kept.

Each record is asked of the deployment by the RBA's own title for it as a
`symbol` at the source `rba`, a name **proposed** with this version for
the platform's seed; the platform seeds none yet, so until a deployment
holds a record its values wait, reported missing, never minted. The
Australian dollar is resolved by its ISO 4217 code, as plugin-ecb resolves
its currencies.
"""

from __future__ import annotations

from dataclasses import dataclass

from meridian.operations import RateConvention
from meridian.roles.data import rates

SOURCE = "rba"
INTEREST_RATE, INDEX, RATE_CURVE = "interest_rate", "index", "rate_curve"
#: The tables read, by the file each is published as.
F1, F2, F17, F11 = "F1", "F2", "F17", "F11.1"
TABLES = (F1, F2, F17, F11)
#: The datasets, as declared.py names them.
RATES, CURVES, FX, RESTRICTED = "rba_rates", "rba_curves", "rba_fx", "rba_restricted"
#: The RBA's own source for a column.
RBA = "RBA"

#: The Australian money market's convention; the Australian Government
#: bonds' (semi-annual coupons); a continuously compounded zero rate.
MONEY_MARKET_365 = RateConvention(day_count="act_365_fixed", compounding="simple")
BOND = rates.BOND_EQUIVALENT
CONTINUOUS = rates.CONTINUOUS
TRI_BASE = "2011-01-04=100"
#: The Australian dollar, the currency every exchange rate is the price of.
AUD = "AUD"


@dataclass(frozen=True)
class Record:
    """A referential record, by the code proposed for it at `rba`."""

    code: str
    instrument_type: str
    description: str

    @property
    def identifier(self) -> tuple[str, str, str]:
        return ("symbol", self.code, SOURCE)


CASH_RATE_TARGET = Record("Cash Rate Target", INTEREST_RATE, "RBA Cash Rate Target")
CASH_RATE = Record(
    "Interbank Overnight Cash Rate", INTEREST_RATE, "RBA Interbank Overnight Cash Rate"
)
CASH_RATE_TRI = Record("Cash Rate Total Return Index", INDEX, "RBA Cash Rate Total Return Index")
AGB = Record(
    "Australian Government bond yields",
    RATE_CURVE,
    "Australian Government bond yields, interpolated (RBA table F2)",
)
ZERO_COUPON = Record(
    "Zero-coupon interest rates",
    RATE_CURVE,
    "Australian zero-coupon interest rates, analytical series (RBA table F17)",
)
BABS = Record(
    "BABs/NCDs", RATE_CURVE, "Bank Accepted Bills/Negotiable Certificates of Deposit, end of day"
)
OIS = Record("OIS", RATE_CURVE, "Australian dollar overnight indexed swap rates")
RECORDS = (CASH_RATE_TARGET, CASH_RATE, CASH_RATE_TRI, AGB, ZERO_COUPON, BABS, OIS)


@dataclass(frozen=True)
class Column:
    """A column carried: its table, dataset, record, kind, tenor, the source
    its table is expected to state, and its convention."""

    table: str
    dataset: str
    record: Record
    kind: str
    tenor: str = ""
    source: str = RBA
    convention: RateConvention = MONEY_MARKET_365


#: The rate columns carried, by Series ID.
RATE_COLUMNS: dict[str, Column] = {
    "FIRMMCRTD": Column(F1, RATES, CASH_RATE_TARGET, "fixing"),
    "FIRMMCRID": Column(F1, RATES, CASH_RATE, "fixing"),
    "FIRMMCTRI": Column(F1, RATES, CASH_RATE_TRI, "index_level"),
    "FIRMMBAB30D": Column(F1, RESTRICTED, BABS, "fixing", "1M", "ASX"),
    "FIRMMBAB90D": Column(F1, RESTRICTED, BABS, "fixing", "3M", "ASX"),
    "FIRMMBAB180D": Column(F1, RESTRICTED, BABS, "fixing", "6M", "ASX"),
    "FIRMMOIS1D": Column(F1, RESTRICTED, OIS, "par_yield", "1M", "FENICS"),
    "FIRMMOIS3D": Column(F1, RESTRICTED, OIS, "par_yield", "3M", "FENICS"),
    "FIRMMOIS6D": Column(F1, RESTRICTED, OIS, "par_yield", "6M", "FENICS"),
    **{
        f"FCMYGBAG{y}D": Column(F2, CURVES, AGB, "par_yield", f"{y}Y", RBA, BOND)
        for y in (2, 3, 5, 10)
    },
    **{
        f"FZCY{q * 25}D": Column(
            F17,
            CURVES,
            ZERO_COUPON,
            "zero",
            f"{q // 4}Y" if q % 4 == 0 else f"{q * 3}M",
            RBA,
            CONTINUOUS,
        )
        for q in range(1, 41)
    },
}
#: The cash rate's volume ($m) and number of transactions, by Series ID.
VOLUME, COUNT = "FIRMMCRIV", "FIRMMCRIN"

#: The exchange rates carried: each Series ID's ISO 4217 code and the
#: source its table is expected to state.
FX_COLUMNS: dict[str, tuple[str, str]] = {
    "FXRUSD": ("USD", "WM/Reuters"),
    **{
        series: (code, RBA)
        for series, code in {
            "FXRCR": "CNY",
            "FXRJY": "JPY",
            "FXREUR": "EUR",
            "FXRSKW": "KRW",
            "FXRUKPS": "GBP",
            "FXRSD": "SGD",
            "FXRIRE": "INR",
            "FXRTB": "THB",
            "FXRNZD": "NZD",
            "FXRNTD": "TWD",
            "FXRMR": "MYR",
            "FXRIR": "IDR",
            "FXRVD": "VND",
            "FXRUAED": "AED",
            "FXRPNGK": "PGK",
            "FXRHKD": "HKD",
            "FXRCD": "CAD",
            "FXRSARD": "ZAR",
            "FXRSF": "CHF",
            "FXRPHP": "PHP",
        }.items()
    },
}

#: What the tables hold and are not carried, and why.
NOT_CARRIED = {
    "FIRMMCCRT": "the change in the Cash Rate Target: derived from the target",
    "FIRMMCRIH": "the highest interbank overnight rate of the day: not a fixing",
    "FIRMMCRIL": "the lowest interbank overnight rate of the day: not a fixing",
    "FIRMMTN1D": "Treasury Note yields: not in this version",
    "FCMYGBAGID": "the indexed bond's yield: a real yield, another curve's",
    "FZCY0D": "the 0-year zero-coupon yield: no tenor",
    "FXRTWI": "the Trade-weighted Index: an index, not an exchange rate",
    "FXRSDR": "the SDR: the IMF's",
}


def dataset_of_fx(series: str) -> str:
    """An exchange rate's dataset: the third party's apart."""
    return RESTRICTED if FX_COLUMNS[series][1] != RBA else FX
