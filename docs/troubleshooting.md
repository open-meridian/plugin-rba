# Troubleshooting

| What you see | What it means | What to do |
|---|---|---|
| **Not answering** | No check has reached the RBA's website | Check the deployment's outbound access to www.rba.gov.au; the plugin tries again within the hour |
| **Answering**, with a warning | An earlier check worked; the last did not | Nothing, usually: the next check runs within the hour |
| **N records not held** | Your deployment holds no record for a cash rate or a curve: the platform does not seed them yet | Nothing the plugin can do: it never makes a record. Their values are recorded once your deployment holds them |
| A currency not resolved | Its ISO 4217 code found no cash instrument, or two | Complete or merge the instrument at the Instruments page |
| A column "names its source ..., not the one expected" | The RBA changed a column's source | Its values are not recorded until the plugin is updated: report it |
| A day declined, *source silent* | A weekend, a holiday, a day not published yet | Wait for the RBA's next publication |
| A subject declined, *not covered* | Not one of this plugin's records or currencies | Check the Records tab |
| Datasets: **Not licensed yet** | No deployment admin has licensed the dataset | Ask a deployment admin to license it on Data sources |
