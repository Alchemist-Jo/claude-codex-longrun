# Launch record: <run id>

Written by the main session in the run directory before the launch. The watcher writes the receipt to `collect/receipt.md` after the run.

| Field | Value |
| --- | --- |
| Command | `detach.sh <run dir> -- <exact command line>` |
| Starts from | tag `freeze/<worker>` at `<commit>` |
| Host | `<host>` |
| Ports and devices | `<host>/port:<n>`, `<host>/gpus`, also listed under `resources` in the state file |
| Expected duration | <hours> |
| Expected cost | <amount and unit> |
| Kill condition | <observable condition, such as a NaN loss in the log or no log line for 20 minutes> |
| Launched at | <time, filled in at launch> |
| Pid | <wrapper pid, filled in at launch> |

## Numbers to collect

| Number | File | Expected |
| --- | --- | --- |
| <metric> | <path> | <value or range> |
