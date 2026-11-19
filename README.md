# meridian-rba

The Reserve Bank of Australia's public rates for
[Open Meridian](https://open-meridian.com): an Open Meridian plugin that puts
the cash rate, the Australian Government bond yields, the zero-coupon curve
and the RBA's daily exchange rates into a deployment's lake. It reads the
RBA's statistical tables F1, F2, F17 and F11.1, and holds the `data` role, a
data plugin. This is release 0.1.0, a draft for the product owner. How to
set it up and use it is in [docs/](docs/README.md).

It is built on the SDK it pins, `open-meridian==0.36.0` (contract 30).

## What it records

- **`<instance>:rba_rates`** (pushed as published, and pulled): the Cash
  Rate Target and the Interbank Overnight Cash Rate, each a `fixing`, the
  cash rate with its volume and number of transactions; the Cash Rate Total
  Return Index, an index level, 04-Jan-2011 = 100. Actual/365 simple, the
  plugin's statement: the RBA states per cent.
- **`<instance>:rba_curves`** (pushed and pulled): F2's Australian
  Government bond yields, interpolated, at 2, 3, 5 and 10 years, each a
  `par_yield` (semi-annual, the plugin's statement); F17's zero-coupon
  yields at 3 months to 10 years every quarter, each a `zero`, continuously
  compounded -- the plugin's statement, read from the RBA's own discount
  factors.
- **`<instance>:rba_fx`** (pushed and pulled): each currency's daily rate
  the RBA states as its own, "A$1=<code>", the price of the Australian
  dollar's cash instrument in that currency, never inverted.
- **`<instance>:rba_restricted`** (pulled only, served, not kept): the
  columns the tables name as a third party's -- F1's BABs/NCDs (ASX) and OIS
  (FENICS), F11.1's A$1=USD (WM/Reuters).
- **Records:** each is asked of the deployment by the RBA's title for it at
  `rba` (`rba:Cash Rate Target`); the platform seeds none yet, so each is
  reported missing, never minted, and its rates wait. The Australian dollar
  resolves by its ISO 4217 code.
- **Not presented:** the indexed bond's real yield, the 0-year zero-coupon
  yield, F17's forward rates (ruling 131), the Trade-weighted Index, the
  SDR, the Treasury Note yields, the cash rate's daily high and low. No
  published time is recorded: the RBA states none on a value.

## Served, not kept

The RBA says third-party content in its data may not be used without the
third party's consent. Each table names each column's source, so the
columns it names as ASX's, FENICS's and WM/Reuters' are their own dataset,
read only when the lake wants a day; the plugin keeps the RBA's own columns
of each table and none of theirs. The dataset's terms carry the clause for
the deployment admin, whose licence says whether the lake keeps their rows.

## Deploying it

On a deployment, with the `meridian` CLI connected (`meridian connect`):

    meridian plugin upload       # from this directory
    meridian plugin launch rba   # a deployment admin approves its one role, data

No key and no account. A deployment admin then licenses its four datasets
and entitles the plugins that read them on the Data sources page
([docs/setup.md](docs/setup.md)).

## Checking it

    make ci-local                  # lint, tests, plugin check, image, e2e: the pre-push gate
    make preview SHOTS=<dir>       # each page in a browser with the kit, at 375, 582 and 1280 px

`tests/test_suite.py` runs the SDK's data suite on the plugin's own
conversion, and it passes; a case about what the RBA never states here is
not presented, with why.

## The terms, summarised

Not legal advice; read the RBA's own words
([copyright and disclaimer](https://www.rba.gov.au/copyright/)) before
relying on them. Its financial data and the cash rate may be used for
personal or commercial use, without implying the RBA's endorsement, without
misrepresenting the source, and without charging for access without saying
the RBA publishes them free; the RBA does not recommend its financial data
as a benchmark; attribution "Source: Reserve Bank of Australia"; third-party
content needs the third party's consent. Each dataset says so in words, and
declares no licence: the deployment admin's licence is the one enforced.
This project is not affiliated with or endorsed by the Reserve Bank of
Australia.

## Licence

Apache-2.0 (LICENSE, NOTICE). The RBA's tables under `src/rba/responses/`
are as received on 2026-11-19.
