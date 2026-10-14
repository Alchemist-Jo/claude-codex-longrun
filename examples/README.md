# Example: a harness directory mid-project

A fictional evaluation tool, evalkit, part-way through a cycle. The files show the shapes the skill uses. The project, its numbers and the advisor's answer are illustrative.

| File | Shows |
| --- | --- |
| [state.json](harness/state.json) | Six workers on four routes: an advisor question that is done, a Codex worker in review changes, its reviewer, a running Codex worker, a planned worker that overlaps, a paid run |
| [ledger.md](harness/ledger.md) | Rulings with reason and cost if wrong, a launch, a hold caused by an overlap |
| [w12 brief](harness/briefs/w12.md) | A complete code brief with write set, out of scope and acceptance commands |
| [r12-1 runbook](harness/briefs/r12-1.md) | A reviewer runbook with two must-check points |
| [w12 round 1 verdict](harness/reviews/w12-r1.md) | `REQUEST_CHANGES` with a change the main session then rejected because it falls outside the write set |
| [a03 question](harness/advice/a03-question.md) and [answer](harness/advice/a03-answer.md) | A directional question and its verbatim answer |
| [p07 launch record](harness/runs/p07/launch-record.md) | A paid run with its kill condition and the numbers to collect |

Run the state check from the repository root:

~~~sh
python3 scripts/harness_state.py examples/harness/state.json --summary
~~~

It passes with one warning: w14 is planned with `src/evalkit/runner.py` in its write set while w12 holds that file. Dispatching w14 now fails:

~~~sh
python3 scripts/harness_state.py examples/harness/state.json --dispatch w14
~~~

The ledger records the decision this check supports: w14 waits for w12 to merge, or the two are combined into one brief.
