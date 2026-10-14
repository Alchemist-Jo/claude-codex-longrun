---
name: claude-codex-longrun
description: Routes the work of a long software or research project across the main session, Claude subagents and Codex CLI, and keeps that collaboration stable over days of background jobs, context compactions and permission prompts. Gives a routing table for what the main session does itself, what goes to a read-only search agent, to Codex at high or xhigh effort, to a reviewer, a watcher, a pipeline runner, a reporter or a read-only design advisor, and what only the user decides. Covers briefs and runbooks with stop conditions, one writer per file, worktree isolation, jobs detached from the waits that watch them, state kept in files, round commits and review with a round cap, paid runs, kills, freezes and reports with checked numbers. Use when the user wants to split work between Claude and Codex, dispatch Codex or subagents, run several agents in parallel without conflicts, wait on a long Codex job or paid run, recover a multi-agent project after a cut-off or compaction, review delegated code, or reduce permission round trips. Not for a small edit made directly in the session, reviewing an existing pull request on its own (code-review), or a project progress report document (research-report). 触发词：多代理协作、harness、路由、派 Codex、子代理、并行冲突、盯进程、长任务等待、被切断、恢复现场、只读评审、付费运行、设计顾问、权限放行、汇报核对。
license: MIT
metadata:
  version: "1.0.0"
---

# Claude Codex Long Run

Use this skill when one main session runs a project through other agents: Claude subagents for execution, Codex CLI for code and a read-only Codex advisor for direction. The skill decides where each piece of work goes and keeps the arrangement working when jobs outlive the agents that started them, when context is compacted, when the permission system blocks a subagent, and when two writers reach for the same file. Everything it relies on is a plain file in the repository, a standard command, or one of the small scripts in `scripts/`. It needs no daemon, framework or database.

## Goal

The main session keeps the project correct and moving with the fewest hand-offs that still give isolation and independent checking. At every point:

- each piece of work sits on one route of the table below, and every worker except a read-only search agent has a brief or runbook naming its objective, inputs, write set, output, stop conditions and check
- no file is in the write set of two workers at once
- every long job runs detached from the agent that waits on it, so a lost wait loses nothing
- the state of every worker can be rebuilt from `harness/state.json`, the ledger, git and the run directories, without any agent's memory
- delegated code counts as done only after a review against its brief, by an agent that did not write it
- the main session itself executes Codex launches, paid launches, process kills, merges, pushes and deletions, and runs a merge or push only after the user's explicit approval
- every number reported to the user traces to a file the main session opened

## Routing

Take the first row that fits. A route is worth its hand-off only when it keeps file dumps out of the main context, isolates a writer, or adds an independent check.

| Work | Route | Settings |
| --- | --- | --- |
| A paid launch, a kill, a merge, a push, a deletion, anything outward-facing or touching credentials | Main session only; merges and pushes after user approval | |
| A preference, a budget, or a scope the material cannot settle | The user | |
| A fact in a known file, a command whose output decides the next step, a small edit to a file no worker holds | Main session, directly | |
| Finding code, files or facts across many locations | Read-only search subagent | returns the conclusion and paths; no state entry |
| A question of direction: how a flow should be fixed, where general and special cases divide, how a candidate pool is chosen, how a boundary is drawn | Advisor: Codex read-only at maximum effort | `-s read-only` |
| A code change larger than about 5 hours | Split by write set, then route each part | |
| Two code changes whose write sets overlap | One combined brief and one Codex run | union of the write sets |
| A change to a public interface, a file or data format, a protocol, an evaluation definition, or ordering and concurrency logic | Codex in its own worktree | effort `xhigh` |
| Any other code change | Codex in its own worktree | effort `high` |
| Preparing a worktree, collecting a finished round, tagging a freeze | Pipeline subagent | runbook |
| Waiting on a job that may run longer than about 25 minutes | Main session, one background wait | see Stability |
| Collecting results after a job ends, or a short wait | Watcher subagent | checklist, read-only |
| Review of delegated code against its brief | Reviewer subagent, read-only | diffs from the recorded base |
| Drafting a report from established facts | Reporter subagent | facts sheet, word limits |

Subagents run on the strongest available Claude model unless the runbook is purely mechanical. Subagents never start Codex or another agent. Each returns to the main session, which alone picks the next route. [Routing detail](references/routing.md) covers splitting, combining, effort escalation and when not to delegate.

## Dispatch

Before a worker starts, its brief or runbook exists and its entry is in `harness/state.json` with status `planned`.

- **Codex** gets a brief from [assets/brief.md](assets/brief.md): objective, context, write set, out of scope, acceptance commands with expected results, constraints and the final-message format. The brief always says not to commit. The pipeline subagent prepares the worktree; the main session launches Codex with `scripts/detach.sh`. Commands, overrides and resume are in [dispatch](references/dispatch.md).
- **Subagents** get a runbook copied from [assets/runbooks](assets/runbooks/): role, inputs as absolute paths, one new output directory or file, allowed commands, forbidden actions, stop conditions, checklist and return format with a word limit.

Check before each dispatch that the new worker's write set is free, with `H` set to this skill's directory:

~~~sh
python3 "$H/scripts/harness_state.py" harness/state.json --dispatch w12
~~~

Workers return one status: `DONE`, `DONE_WITH_CONCERNS`, `BLOCKED` or `NEEDS_CONTEXT`. Anything unexpected is reported as Expected, Found and Why it matters. The report stays within 300 words unless the runbook sets another limit, and it points to files instead of pasting them.

These stop conditions appear in every brief and runbook:

- a command exits with an unexpected status or prints an unexpected result
- a named input is missing, or the output directory already exists
- a number disagrees with the expectation the runbook states
- a permission prompt or a permission denial
- the next step would write outside the write set or output, or touch a process, branch, tag or remote the runbook does not name
- the situation is not covered

To stop is to take no further action, write what was observed into the output, and return. The worker does not patch, retry with different flags or route around a block.

## Stability

These rules answer failures that recur in long multi-agent runs. [Waiting](references/waiting.md) and [state](references/state.md) hold the commands.

1. **Detach the job from the wait.** Start every Codex job, advisor question and paid run with `scripts/detach.sh`: its own session, stdin closed, logs, a pid file and an exit-status file in a new run directory. Background commands can be stopped at a time limit, SSH connections drop, and subagent sessions end. A detached job survives all three, and its wait can be restarted at any time.
2. **Hold long waits where they last.** Every wait is `scripts/wait.sh`, which only observes. The main session holds any wait that may pass about 25 minutes, as one background command that returns when the job exits. A watcher subagent waits only in the foreground, in calls of at most 10 minutes inside one turn, and never ends its turn while a background child runs. A wait that ended means re-check the job. Only the exit-status file means the job finished.
3. **Keep state in files.** `harness/state.json` lists every worker with its route, status, write set, worktree, session, round, pid, log and output. `harness/ledger.md` records every ruling. Only the main session writes either, and it updates the worker's pid, log and output at every new round. At the start of a session and after every compaction, run the bearings check in [state](references/state.md) before acting.
4. **One writer per file.** Parallel writers need disjoint write sets. An overlap means sequence, or one combined brief. A conflict is never resolved by hand outside a brief.
5. **Override Codex defaults on every call.** Set the sandbox, the effort and the output paths explicitly. A user configuration may default to the highest effort and full access, which a code worker must not inherit. Use `codex exec` rather than an MCP bridge: the `codex mcp-server` command has been removed.
6. **Bound every loop.** A review cycle has at most 5 rounds. A failed Codex run is resumed once with its failure; a second failure returns to the main session. A worker blocked by a permission prompt stops on the first prompt.
7. **Verify from artifacts.** Done means an exit-status file, a round commit, a test log, diffs from the recorded base and a review verdict, never a worker's own summary.

## Rounds and Review

Codex never commits. After each round the pipeline subagent checks that HEAD has not moved, records changes outside the write set in `outside.txt`, commits the write set on the worker branch as that round's commit, and writes `diff.patch` from the base and `fix.patch` for the round. A round that only reverted files outside the write set keeps the previous commit. The pipeline then runs the tests. Every round therefore has a commit, and any two rounds can be compared.

The reviewer reads the diffs and the code at the round commit, checks every acceptance item and every must-check point the main session named, and treats the writer's summary as a claim. The first line of its verdict is `ACCEPT`, `REQUEST_CHANGES` or `BLOCKED`, followed by a numbered list of concrete changes tied to the brief. Every entry in `outside.txt` becomes a request to revert that file. Findings outside the brief go to the ledger as candidates, not into the fix list.

The main session rules on each verdict. Round 2 resumes the same Codex session with the agreed changes only. From round 3, the main session first rereads the failing criteria, since a criterion that keeps failing may not be testable as written, and then rewrites the brief, raises the effort to `xhigh`, or starts a fresh session. After round 5 the main session decides and records the ruling. [Review](references/review.md) has the verdict format.

## Paid Runs, Kills and Freezes

Before a paid launch the main session writes a launch record from [assets/launch-record.md](assets/launch-record.md) in the run directory: command, frozen tag, host, expected duration and cost, numbers to collect, and the condition for killing the run. It launches the run itself with `detach.sh` and records the pid. The watcher writes the receipt to `collect/receipt.md`.

Before a kill the main session lists the job's process group and compares it with the launch record. It terminates the job under the wrapper, gives the wrapper time to record exit status 143, then terminates the rest of the group, and records the kill in the ledger. A freeze is a tag on the accepted round commit. See [waiting](references/waiting.md) and [state](references/state.md).

## Direction and Reports

The advisor answers only questions of direction. A subagent drafts the question from [the question runbook](assets/runbooks/question.md), the main session edits it, launches Codex read-only at maximum effort with `detach.sh` and keeps the answer verbatim under `harness/advice/`. The ruling goes into the ledger before any brief depends on it. Bugs, implementation detail and anything a test can settle never go to the advisor. See [advisor](references/advisor.md).

For a report, the main session writes a facts sheet: each number, path, commit and status with its source file. The reporter returns a precise version, a plain version and a number checklist within the word limits it was given. A cause the evidence does not establish is reported as not established. The main session opens each source in the checklist before sending. See [reporting](references/reporting.md).

## Permissions

The permission system blocks subagents more often than the main session. Each block costs a round trip through the user. Narrow allow rules for read-only commands on a known host remove most of them, while launches, kills, merges and pushes stay with the main session behind a prompt. Permission rules match the usual form of a command and are not a security boundary. They keep accidents rare among cooperating agents. [Permissions](references/permissions.md) gives a settings example.

## Invariants

| Invariant | Threshold | Checked by |
| --- | --- | --- |
| Write sets | no file in two holding workers | `harness_state.py --dispatch` before each start |
| Detached jobs | every running job has a pid, a log and, once finished, an exit-status file | `harness_state.py --alive` |
| Codex commits | none: HEAD equals the previous round commit when the round ends | pipeline collection step |
| Changed files | inside the write set | `outside.txt`, read by the reviewer |
| Acceptance | every item met, each with an output line or file location | review verdict |
| Review rounds | 5 at most, then a recorded ruling | ledger |
| Irreversible actions | executed by the main session, merges and pushes after approval | ledger |
| Subagent writes | inside the worker's new output, or its worktree for the pipeline runner | runbook and `git status` |
| Freeze | the tag resolves to the accepted round commit | `git rev-parse freeze/<id>^{commit}` |
| Reported numbers | each traced to an opened source | number checklist |

## When Something Fails

| Symptom | Response |
| --- | --- |
| A watcher session ends before the job | Check `exit-status` and the pid. If the job still runs, hold the wait in the main session and dispatch a watcher only for collection. |
| A background wait reports a time limit | Re-check the job. It did not finish unless its exit-status file exists. |
| `--alive` reports a pid gone without `exit-status` | The job died. Read the log tails, set the worker to `stopped`, and decide whether to relaunch. |
| `codex exec` produces no output and no CPU | It was started without stdin closed. Kill it after confirming its pid and command line, and relaunch with `detach.sh`. |
| A subagent hits a permission prompt | It stops and reports. The main session runs the step itself, asks the user, or adds a narrow read-only rule. |
| A worker changed a file outside its write set | The reviewer requests the revert. The other worker's change on that file stands. |
| A Codex run exits without finishing | Resume the session once with the failure. On a second failure, the main session rereads the brief. |
| Context was compacted or the session restarted | Run the bearings check before any other action. |
| A worker reports success but the test log fails | The test log stands. The change goes back with the failing output. |
| Reviewer and writer disagree | The main session rules and records why. |

These moves are never allowed:

- a worker fixing, retrying or working around an anomaly it found
- Codex committing, pushing or tagging, or any worker editing outside its write set
- a merge without an `ACCEPT` for the exact commit being merged, or without the user's approval
- a Codex launch, a paid launch, a kill or a push by a subagent
- a subagent reading `.env` or credential files, or writing the state file or the ledger
- reporting a result before its exit-status file and collection exist

## Final Checklist

- Every worker in `harness/state.json` has a brief, an output and a current status, and `harness_state.py --alive` reports no error.
- Every merged change has a review verdict, a ledger entry and a freeze tag on the accepted round commit.
- Every paid run has a launch record and a receipt, and every kill has a ledger entry.
- Every number in the report was checked against its source file.
- Every action waiting on the user is named, with what will happen on approval.

## Delivery

Each cycle leaves in the repository the briefs, runbooks, verdicts, advisor answers, the ledger and the state file under `harness/`, one run directory per round with its logs, exit status, round commit, diffs and test output, a tag per freeze, and the report with its number checklist. The message to the user lists which workers changed state, which numbers were checked, which actions wait for approval, and every check that was not run.

[Method basis](references/basis.md) records the sources, the open-source projects compared and the tests behind the stability rules. [The example](examples/README.md) shows a harness directory mid-project.
