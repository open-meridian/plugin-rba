# Setup

## Launching it

The RBA's data need no key and no account. Launch the plugin and approve its
one role, `data`. It reads the tables at once, and every hour after; the
third parties' columns only when the lake asks for a day.

Its settings: the **Raw responses window** and **past the window** (the
SDK's), and on a deployment installed for development, **Sample data**: the
RBA's tables recorded on 19 November 2026, committed with the plugin.

## Its datasets

On the deployment's **Data sources** page (deployment admins), for each of
`<instance>:rba_rates`, `<instance>:rba_curves`, `<instance>:rba_fx` and
`<instance>:rba_restricted`:

1. **License it.** Each dataset describes the RBA's terms in words and
   declares no licence ([terms](terms.md)). `rba_restricted` carries the
   clause "served, not kept": its columns are ASX's, FENICS's and
   WM/Reuters' content, whose use needs their consent, so the plugin reads
   them only when wanted and keeps none of them; set its licence not to
   keep them unless your terms with those parties allow it. Until a licence
   is set, the lake keeps the rows and reads every use right restrictively.
2. **Entitle** each plugin that reads it.
3. **Priority**, where another dataset states the same values.

## The records

Each rate is about a record named by the RBA's title at `rba`:
`rba:Cash Rate Target`, `rba:Interbank Overnight Cash Rate`,
`rba:Cash Rate Total Return Index`, `rba:Australian Government bond yields`,
`rba:Zero-coupon interest rates`, `rba:BABs/NCDs`, `rba:OIS`. The platform
does not seed them yet, and the plugin never makes one: the Datasets page's
Records tab shows each as not held, and its values wait until your
deployment holds it. The Australian dollar is found by its ISO 4217 code.
