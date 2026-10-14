# Review

Read when dispatching a reviewer, reading a verdict, or ruling on one.

## What the reviewer receives

The [reviewer runbook](../assets/runbooks/reviewer.md), filled in with:

- the brief, the worktree, the recorded base and the round commit
- the run directory: `diff.patch` from the base, `fix.patch` for this round, `outside.txt`, `last-message.md`, `exit-status` and `tests.log`
- the previous verdict, from round 2 on
- the must-check points: places where a wrong change would still pass the tests, named by the main session

Must-check points are specific to the change. Two examples from one project: whether the inference archive is written only at round boundaries, and whether branches selected by name are classified as the fixed protocol. Each point names what to look for and where.

## Procedure

1. Read `outside.txt`. Every entry is a change outside the write set and becomes a requested change: revert that file.
2. Read `diff.patch`, which runs from the recorded base, never from `HEAD~1`, and the code around it at the round commit. The writer's final message is a claim to check.
3. For each acceptance item: met, not met, or not verifiable, with the test-log line or the file and line that shows it.
4. For each must-check point: the answer and its location.
5. Compare the diff with the out-of-scope list.
6. From round 2 on, check `fix.patch` against the open items, and confirm that items met earlier still hold in `diff.patch`.

The reviewer runs nothing that writes, so it does not rerun the tests. It reads the log the pipeline produced.

## Verdict format

~~~text
REQUEST_CHANGES

Acceptance
1. met: `pytest tests/test_runner.py -k resume` passes, harness/runs/w12-r1/tests.log line 18
2. not met: no test named `identical` exists; tests.log line 25 shows "no tests ran"

Must-check
1. end marker: yes, src/evalkit/runner.py:96 reruns a shard whose last line is not `#end`

Changes requested
1. In tests/test_runner.py, add the test for acceptance item 2: interrupt after shard 2, resume, compare with an uninterrupted run byte for byte.

Outside the brief
1. src/evalkit/io.py reads result files without a size limit. Not part of this brief.
~~~

The first line is `ACCEPT`, `REQUEST_CHANGES`, or `BLOCKED` when the review could not be done, followed by the reason. Each requested change names a file, a location and the criterion it serves. Nothing outside the brief enters the change list.

## Ruling

The main session reads the verdict and the cited locations, then:

- agrees with the requested changes it accepts, rejects the rest with a reason, and writes one ledger line
- on agreement with an `ACCEPT`, sets the worker to `accepted` and has the freeze tag created
- puts findings outside the brief into the ledger as candidates for later briefs

## Rounds

| Round | Before launching it |
| --- | --- |
| 2 | Resume the same Codex session with only the agreed changes in `round.md` |
| 3 | Reread the failing criteria first. Rewrite an untestable criterion, raise the effort to `xhigh`, or start a fresh Codex session with the brief and the open items. Choose one |
| 4 | As round 3 |
| 5 | The last round. `round.md` lists every open item |
| After 5 | No further round. The main session decides: accept with a recorded limitation, park the item in the ledger, or rescope into a new brief |

A re-review does not reopen settled items without a new reason.
