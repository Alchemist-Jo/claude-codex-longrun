# Ledger

Written by the main session only. One line per event.

2026-10-12 a03 Ruling: adopt the advisor's split; shard resumption stays generic in the runner, dataset-specific recovery stays in adapters; reversing it later means moving two adapters. Evidence: .agents/work/advice/a03-answer.md. Note: .agents/notes/proposed/architecture/2026-10-12-generic-shard-resumption.md
2026-10-13 w12 Dispatch: effort high, base main@3f2c1aa, write set runner.py and test_runner.py.
2026-10-13 w13 Dispatch: effort xhigh because it changes the report file format, base main@3f2c1aa.
2026-10-14 p07 Launch: tag freeze/w11, host gpu-host, pid 48211, expected 6 h, about 24 GPU hours. Record: .agents/work/runs/p07/launch-record.md
2026-10-14 w12 Ruling: request change 1, reject change 2; change 2 edits cli.py, which is outside the write set and belongs to w14; one more round if wrong. Evidence: .agents/work/reviews/w12-r1.md
2026-10-14 w12 Round 2: resume session 01a13bbd with change 1 only. Record: .agents/work/runs/w12-r2/round.md
2026-10-14 w14 Hold: shares src/evalkit/runner.py with w12; starts after w12 merges, from the merged commit, or is combined with w12 if w12 needs cli.py.
