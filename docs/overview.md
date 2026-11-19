# Overview

The Reserve Bank of Australia publishes the rates this plugin puts into your
deployment's lake:

- **The cash rate** (`<instance>:rba_rates`): the Cash Rate Target, the
  Interbank Overnight Cash Rate with its volume and number of transactions,
  and the Cash Rate Total Return Index (04-Jan-2011 = 100).
- **Curves** (`<instance>:rba_curves`): the Australian Government bond
  yields, interpolated, at 2, 3, 5 and 10 years; the zero-coupon yields at 3
  months to 10 years.
- **Exchange rates** (`<instance>:rba_fx`): each currency's daily rate
  against the Australian dollar, the price of one dollar in that currency.
- **Third parties' columns** (`<instance>:rba_restricted`): the bank bill
  (BABs/NCDs) and OIS rates and the A$1=USD rate, which the RBA's tables
  name as ASX's, FENICS's and WM/Reuters'.

It reads the RBA's public statistical tables: no key, no account. It asks
each table every hour whether it changed. The third parties' columns are
read only when your lake asks for a day (served, not kept: [terms](terms.md));
any past day of any dataset is read when the lake asks for it.

## What it records

- **Each value as the RBA writes it,** made an exact decimal from its text.
  A day the RBA states nothing for is no value, never a zero.
- **Conventions.** The RBA states per cent; the plugin states the cash
  rates actual/365 simple, the bond yields par yields with semi-annual
  compounding, and the zero-coupon yields continuously compounded, as the
  RBA's own discount factors show.
- **Against your deployment's records.** Each rate's record is asked of
  your deployment by the RBA's title for it at `rba`; the plugin never
  makes a record: one your deployment does not hold is reported missing,
  and its values wait. The Australian dollar is found by its ISO 4217 code.
- **No published time:** the RBA states none on a value.
- **Not carried:** the indexed bond's real yield, forward rates, the
  Trade-weighted Index, the SDR, the Treasury Note yields.

## What it never does

It records no trade and shows no value on its pages. It holds no account and
uses no key. Its exchange rates are never inverted, and it keeps none of a
third party's columns.
