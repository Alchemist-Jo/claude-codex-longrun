# Review

Read when dispatching a reviewer, reading a verdict, or ruling on one.

## What the reviewer receives

The [reviewer runbook](../assets/runbooks/reviewer.md), filled in with:

- the brief, the worktree, the recorded base and the round commit
- the run directory: `diff.patch` from the base, `fix.patch` for this round, `outside.txt` with `outside.patch` and `outside-new.lst`, `last-message.md`, `exit-status`, `tests.log` and `tests-exit-status`, and for a Gemini round `tools.jsonl`
- the previous verdict, from round 2 on
- the must-check points: places where a wrong change would still pass the tests, named by the main session

Must-check points are specific to the change. Two examples from one project: whether the inference archive is written only at round boundaries, and whether branches selected by name are classified as the fixed protocol. Each point names what to look for and where.

## Procedure

Read the requirements before the change. Judging a diff against a memory of the brief is how a violation passes review.

1. Read the brief, its acceptance items, its out-of-scope list, the standing rules it names and the must-check points.
2. Read `outside.txt`. Every entry is a change outside the write set and becomes a requested change: revert that file.
3. Read `diff.patch`, which runs from the recorded base, never from `HEAD~1`, and the code around it at the round commit. The writer's final message is a claim to check.
4. Read `tests.log`. It describes the round commit with the outside changes set aside. A filtered test command that selected no tests leaves its acceptance item not met.
5. For each acceptance item: met, not met, or not verifiable, with the log line or the file and line that shows it. Where the brief added or changed a check, confirm that a case the check must reject exists and fails in the log.
6. For each must-check point: the answer and its location.
7. The repository lens:
   - behaviour that changed has its module README and interface comments changed in the same diff, as in [documentation](documentation.md)
   - no session residue entered code, comments or documents, as in [prose](prose.md); the `repo` check in `tests.log` reports the mechanical cases
   - documents outside the write set that the change makes wrong are listed for the close-out
   - rulings in this review that will guide later work are named as note candidates
8. Compare the diff with the out-of-scope list.
9. From round 2 on, check `fix.patch` against the open items, confirm that items met earlier still hold in `diff.patch`, and read the writer's reasons for any change it declined.

The reviewer runs nothing that writes, so it does not rerun the checks. It reads the log the pipeline produced.

## What a finding contains

Each requested change names the defect, the file and location, the impact on the brief's criteria, and the evidence. A short verdict with one substantiated blocker is worth more than a list of preferences. Problems a passing check already enforces are left out. Findings outside the brief never enter the change list; they go under Outside the brief for the ledger.

## Verdict format

~~~text
REQUEST_CHANGES

Acceptance
1. met: `pytest tests/test_runner.py -k resume` passes, 2 selected, .agents/work/runs/w12-r1/tests.log line 18
2. not met: no test named `identical` exists; tests.log line 25 shows "0 selected"

Must-check
1. end marker: yes, src/evalkit/runner.py:96 reruns a shard whose last line is not `#end`

Repository
1. docs: src/evalkit/README.md still says resume restarts from shard 0, line 41
2. residue: none found
3. close-out: docs/usage.md describes --resume, outside the write set
4. note candidate: completeness is defined by the end marker

Changes requested
1. tests/test_runner.py: add the test for acceptance item 2. Interrupt after shard 2, resume, and compare with an uninterrupted run byte for byte. Evidence: tests.log line 25.
2. src/evalkit/README.md line 41: describe resumption from the first incomplete shard.

Outside the brief
1. src/evalkit/io.py reads result files without a size limit. Not part of this brief.
~~~

The first line is `ACCEPT`, `REQUEST_CHANGES`, or `BLOCKED` when the review could not be done, followed by the reason. The main session treats any other first line, or a missing verdict file, as `BLOCKED` and dispatches the reviewer again with the same runbook.

## Ruling

The main session reads the verdict and the cited locations, then:

- agrees with the requested changes it accepts, rejects the rest with a reason, and writes one ledger line
- on agreement with an `ACCEPT`, sets the worker to `accepted` and starts the [close-out](closeout.md)
- puts findings outside the brief into the ledger as candidates for later briefs

A must-check point or a reviewer rule that proved its worth, because a later round's diff actually fixed what it found, may be added to the runbook template. A comment that was only acknowledged, resolved or answered with "fixed" is not that evidence.

## Rounds

| Round | Before launching it |
| --- | --- |
| 2 | Resume the same Codex session or Gemini conversation with only the agreed changes in `round.md`, which asks the writer to verify each one and to make it or give the technical reason against it |
| 3 | Reread the failing criteria first. Rewrite an untestable criterion, raise the effort, or start a fresh session with the brief and the open items. Choose one |
| 4 | As round 3 |
| 5 | The last round. `round.md` lists every open item |
| After 5 | No further round. The main session decides: accept with a recorded limitation, park the item in the ledger, or rescope into a new brief |

A re-review does not reopen settled items without a new reason.

## Gemini answers

A Gemini document review, upkeep check or research report is a list of candidates. Each item cites `path:line` or a URL with the quoted text, as [the Gemini brief](../assets/gemini-brief.md) requires. Before an item enters the ledger, a brief, a note or a document, the main session or a reviewer subagent opens the location and confirms that the quote is there and supports the item. An item that fails is dropped, and the count of dropped items is reported with the answer. An item without a source is checked from scratch or dropped.

In a Gemini documentation round, the reviewer also reads `tools.jsonl`. A denied call shows where the writer tried to go beyond its brief, and a run that exited 3 needs the main session's ruling before its round is reviewed.
