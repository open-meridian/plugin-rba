# Changelog

## 0.1.0

On open-meridian 0.36.0, contract 30, on core aae501d's harness. The
product owner's items 128, 130, 132, 140 and 143 (2026-11-19): Tier 1, the
cash rate, F2's yields as par yields, F17's zero curve and FX, the third
parties' columns their own dataset, served, not kept. The dataset keys, the
records' codes and the source `rba` are proposed here, the product owner's
to approve.

- **`rba_rates`** (push and pull): the Cash Rate Target and the Interbank
  Overnight Cash Rate (`fixing`, the latter with volume and transaction
  count); the Cash Rate Total Return Index (`index_level`).
- **`rba_curves`** (push and pull): F2's yields at 2, 3, 5 and 10 years
  (`par_yield`, semi-annual, the plugin's statement); F17's zero-coupon
  yields at 3 months to 10 years (`zero`, continuously compounded, read
  from the RBA's own discount factors).
- **`rba_fx`** (push and pull): F11.1's rates the RBA states as its own,
  each the `close` price of the Australian dollar's cash instrument in the
  other currency, never inverted.
- **`rba_restricted`** (pull only, served, not kept): F1's BABs/NCDs (ASX)
  and OIS (FENICS), F11.1's A$1=USD (WM/Reuters), as each table's `Source`
  line names them; a column whose table names another source than expected
  is not recorded, and the Datasets page says so.
- **Each table asked whether it changed** (`If-Modified-Since`); a table
  sent is kept with the RBA's own columns alone.
- **No record minted;** no published time. No forwards (ruling 131).
- **Pages:** the data role's Connection (with Sources) and Datasets (with
  Records).
- **Sample data:** the four tables recorded on 2026-11-19, the RBA's own
  columns as received; the third parties' columns (BABs/NCDs, OIS, A$1=USD,
  the SDR) synthetic, invented by a seeded generator in the same shape.

SDK 0.37.0: waits for a lost sidecar; its storage is read once registered,
on an instance run as shards or with a standby pod the shard's own folder.

SDK 0.37.1: a raw record kept from two threads at once waits instead of being dropped.
