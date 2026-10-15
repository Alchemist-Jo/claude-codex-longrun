# Example: a project mid-cycle

A fictional evaluation tool, evalkit, part-way through a cycle. The files show the shapes the skill uses. The project, its numbers and the advisor's answer are illustrative, and the source code is left out. `.agents/bin/` is also left out; adoption copies the scripts there.

## Repository layer

| File | Shows |
| --- | --- |
| [AGENTS.md](project/AGENTS.md) | A root AGENTS.md: one paragraph, a map, the rules for every change, the checks, where facts go |
| [src/evalkit/AGENTS.md](project/src/evalkit/AGENTS.md) | Rules that hold only in one package; Codex started at the worktree root does not load them, so briefs name them |
| [.agents/checks.json](project/.agents/checks.json) | The check registry used by the pipeline, hooks and CI |
| [notes README](project/.agents/notes/README.md) | The note rules every agent in the project reads |
| [resumption note](project/.agents/notes/proposed/architecture/2026-10-12-generic-shard-resumption.md) | A proposed architecture note whose alternatives come from an advisor answer; w12's close-out will move it to `implemented/` |
| [bootstrap note](project/.agents/notes/proposed/experiment/2026-10-14-bootstrap-resamples.md) | A proposed experiment note with a measurable acceptance |
| [.rgignore](project/.rgignore) | Keeps the frozen archive out of searches |

## Run layer

| File | Shows |
| --- | --- |
| [state.json](project/.agents/work/state.json) | Six workers on four routes: an advisor question that is done, a Codex worker in review changes, its reviewer, a running Codex worker, a planned worker that overlaps, a paid run holding a GPU host and a port |
| [ledger.md](project/.agents/work/ledger.md) | Rulings with reason and cost if wrong, a launch, a hold caused by an overlap |
| [w12 brief](project/.agents/work/briefs/w12.md) | A complete code brief: constraints first, the standing rules from `--context`, acceptance with selected-test counts and a rejected case, docs impact |
| [r12-1 runbook](project/.agents/work/briefs/r12-1.md) | A reviewer runbook with two must-check points |
| [w12 round 1 verdict](project/.agents/work/reviews/w12-r1.md) | `REQUEST_CHANGES` with a change the main session then rejected because it falls outside the write set |
| [a03 question](project/.agents/work/advice/a03-question.md) and [answer](project/.agents/work/advice/a03-answer.md) | A directional question and its verbatim answer |
| [p07 launch record](project/.agents/work/runs/p07/launch-record.md) | A paid run with its ports and devices, kill condition and the numbers to collect |

## Checks on the example

From the skill's repository root:

~~~sh
python3 scripts/work_state.py examples/project/.agents/work/state.json --summary
python3 scripts/work_state.py examples/project/.agents/work/state.json --context w12
python3 scripts/repo_check.py examples/project
~~~

The state check passes with one warning: w14 is planned with `src/evalkit/runner.py` in its write set while w12 holds that file. Dispatching w14 now fails:

~~~sh
python3 scripts/work_state.py examples/project/.agents/work/state.json --dispatch w14
~~~

The ledger records the decision this check supports: w14 waits for w12 to merge, or the two are combined into one brief. `--context w12` prints `src/evalkit/AGENTS.md`, the file the w12 brief lists under Standing rules. The repository check passes with no error.
