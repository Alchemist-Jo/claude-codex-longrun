# Launch record: p07

Written by the main session in the run directory before the launch. The watcher writes the receipt to `collect/receipt.md` after the run.

| Field | Value |
| --- | --- |
| Command | `ssh gpu-host 'cd /work/evalkit && harness/bin/detach.sh harness/runs/p07 -- python train.py --config configs/base.yaml'` |
| Starts from | tag `freeze/w11` at `9b04d2e` |
| Host | `gpu-host` |
| Expected duration | 6 hours |
| Expected cost | about 24 GPU hours |
| Kill condition | a NaN loss in stdout.log, or no new log line for 20 minutes |
| Launched at | 2026-10-14 09:12 |
| Pid | 48211 |

## Numbers to collect

| Number | File | Expected |
| --- | --- | --- |
| final validation accuracy | eval/final.json, key `val_acc` | between 0.70 and 0.80 |
| steps completed | stdout.log, last `step=` line | 12000 |
