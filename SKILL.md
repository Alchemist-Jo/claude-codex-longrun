---
name: claude-codex-longrun
description: Runs a long software or research project through the main Claude session, Claude subagents and Codex CLI, and keeps the repository in a state the next session can trust. Gives a routing table, briefs and runbooks with stop conditions, one writer per file and per resource, detached jobs, state in files, round commits checked as committed, capped review, close-out, paid runs, kills and checked reports; plus a .agents/ layout, short layered AGENTS.md, decision notes, docs synced with code, session-residue cleanup and one check list shared by hooks and CI. Use to split work between Claude and Codex, run agents in parallel, wait on long jobs, recover after compaction, review delegated code, or set up and maintain a repository for agent work. Not for a small direct edit or reviewing a pull request alone. 触发词：多代理协作、派 Codex、子代理、并行冲突、长任务等待、恢复现场、只读评审、付费运行、项目目录、AGENTS.md、决策记录、文档同步、会话残留、hooks、CI、接入项目。
license: MIT
metadata:
  version: "2.0.0"
---

# Claude Codex Long Run

Use this skill when one main Claude session runs a project through other agents: Claude subagents for execution, Codex CLI for code and a read-only Codex advisor for direction. It has two layers. The run layer decides where each piece of work goes and keeps it working when jobs outlive the agents that started them, when context is compacted, when permission prompts block a subagent, and when two writers reach for one file. The repository layer keeps what outlasts a session in known places: standing rules every agent loads, decision notes, current documentation and the checks that hold them in shape. Everything is a plain file in the repository, a standard command or a small script in `.agents/bin/`. No daemon, framework or database is needed.

## Goal

The main session keeps the project correct and moving with the fewest hand-offs that still give isolation and independent checking, and leaves a repository that a new session or a new agent can work in from its files alone. At every point:

- each piece of work sits on one route of the table below, and every worker except a read-only search agent has a brief or runbook naming its objective, inputs, write set, output, stop conditions and check
- no file and no named resource, such as a port or a GPU host, is held by two workers at once
- every long job runs detached from the agent that waits on it, so a lost wait loses nothing
- the state of every worker can be rebuilt from `.agents/work/`, git and the run directories, without any agent's memory
- delegated code counts as done only after its round commit passed the checks as committed and a reviewer who did not write it accepted it against its brief
- the main session itself executes Codex launches, paid launches, process kills, merges, pushes and deletions, and runs a merge or push only after the user's explicit approval
- standing rules live in short AGENTS.md files, each fact has one home, and code and documents state current facts without citing work records
- every number reported to the user traces to a file the main session opened

## Project Layout

~~~text
AGENTS.md                 standing rules and a map of the repository, about 100 lines
<area>/AGENTS.md          only where an area has rules of its own
docs/                     current documentation for users
.agents/
  checks.json             every check, run by the pipeline, git hooks, CI and agents
  bin/                    detach.sh, wait.sh, work_state.py, run_checks.py, repo_check.py,
                          collect_round.py
  notes/                  decision notes: proposed/ implemented/ rejected/ archived/
  work/                   records of work cycles: state.json, ledger.md, briefs/,
                          reviews/, advice/, reports/, runs/
~~~

The three places differ by lifetime. AGENTS.md holds what every task needs. `docs/` and `.agents/notes/` hold what stays true across cycles: current facts and the reasons behind them. `.agents/work/` holds what happened in a cycle and may cite worker ids, rounds and reviews. Content moves from work records into notes and documents only at close-out, by the main session's decision. Code and documents never cite a work record. Notes may cite one as evidence.

Codex builds its instruction chain once per run from the repository root down to its working directory, so a worker started at the worktree root does not load `src/pkg/AGENTS.md`. The brief names those files. Claude Code reads AGENTS.md natively when no CLAUDE.md exists in the directory or above it, and loads a subdirectory's file when it first reads a file there. Keep AGENTS.md as the only instruction source: no CLAUDE.md beside it and no symlink, or a CLAUDE.md whose first line is `@AGENTS.md`.

To set the layout up in a project, or to bring an existing project in without overwriting its rules, hooks or CI, follow [adopt](references/adopt.md). Commands below run from the repository root.

## Routing

Take the first row that fits. A route is worth its hand-off only when it keeps file dumps out of the main context, isolates a writer, or adds an independent check.

| Work | Route | Settings |
| --- | --- | --- |
| A paid launch, a kill, a merge, a push, a deletion, anything outward-facing or touching credentials | Main session only; merges and pushes after user approval | |
| A preference, a budget, or a scope the material cannot settle | The user | |
| A fact in a known file, a command whose output decides the next step, a small edit to a file no worker holds | Main session, directly | |
| A decision note, the ledger, the state file | Main session; a reporter subagent may draft a note from a facts sheet | |
| Finding code, files or facts across many locations, or auditing documents against the code | Read-only search subagent | returns the conclusion and paths; no state entry |
| A question of direction: how a flow should be fixed, where general and special cases divide, how a candidate pool is chosen, how a boundary is drawn | Advisor: Codex read-only at maximum effort | `-s read-only` |
| A code change larger than about 5 hours | Split by write set, then route each part | |
| Two code changes whose write sets overlap | One combined brief and one Codex run | union of the write sets |
| A change to a public interface, a file or data format, a protocol, an evaluation definition, or ordering and concurrency logic | Codex in its own worktree | effort `xhigh` |
| Any other code change, including documentation that changes with code | Codex in its own worktree | effort `high` |
| Preparing a worktree, collecting a finished round, tagging a freeze | Pipeline subagent | runbook |
| Waiting on a job that may run longer than about 25 minutes | Main session, one background wait | see Stability |
| Collecting results after a job ends, or a short wait | Watcher subagent | checklist, read-only |
| Review of delegated work against its brief | Reviewer subagent, read-only | diffs from the recorded base |
| Drafting a report from established facts | Reporter subagent | facts sheet, word limits |

Subagents run on the strongest available Claude model unless the runbook is purely mechanical. The built-in Explore and Plan agents load no AGENTS.md, so search runbooks name the rules that matter. Subagents never start Codex or another agent. Each returns to the main session, which alone picks the next route. [Routing detail](references/routing.md) covers splitting, combining, effort escalation and when not to delegate.

## Dispatch

Before a worker starts, its brief or runbook exists and its entry is in `.agents/work/state.json` with status `planned`.

- **Codex** gets a brief from [assets/brief.md](assets/brief.md): objective, standing rules, context, write set, out of scope, acceptance with commands and expected results, constraints and the final-message format. Critical constraints come before the changes. The brief always says not to commit. The pipeline subagent prepares the worktree; the main session launches Codex with `.agents/bin/detach.sh`. Commands, overrides and resume are in [dispatch](references/dispatch.md).
- **Subagents** get a runbook copied from [assets/runbooks](assets/runbooks/): role, inputs as absolute paths, one new output directory or file, allowed commands, forbidden actions, stop conditions, checklist and return format with a word limit.

Check before each dispatch that the worker's write set and resources are free, and list the nested AGENTS.md files its brief must name:

~~~sh
python3 .agents/bin/work_state.py --dispatch w12
python3 .agents/bin/work_state.py --context w12
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

1. **Detach the job from the wait.** Start every Codex job, advisor question and paid run with `.agents/bin/detach.sh`: its own session, stdin closed, logs, a pid file and an exit-status file in a new run directory. Background commands can be stopped at a time limit, SSH connections drop, and subagent sessions end. A detached job survives all three, and its wait can be restarted at any time.
2. **Hold long waits where they last.** Every wait is `.agents/bin/wait.sh`, which only observes. The main session holds any wait that may pass about 25 minutes, as one background command that returns when the job exits. A watcher subagent waits only in the foreground, in calls of at most 10 minutes inside one turn, and never ends its turn while a background child runs. A wait that ended means re-check the job. Only the exit-status file means the job finished.
3. **Keep state in files.** `.agents/work/state.json` lists every worker with its route, status, write set, resources, worktree, session, round, pid, log and output. `.agents/work/ledger.md` records every ruling. Only the main session writes either, and it updates the worker's pid, log and output at every new round. At the start of a session and after every compaction, run `work_state.py --bearings` and reconcile before acting. A SessionStart hook can run it automatically, as in [checks](references/checks.md).
4. **One writer per file, one holder per resource.** Parallel writers need disjoint write sets. Paid runs that need the same port or GPU host declare it under `resources`. An overlap means sequence, or one combined brief. A conflict is never resolved by hand outside a brief.
5. **Override Codex defaults on every call.** Set the sandbox, the effort and the output paths explicitly. A user configuration may default to the highest effort and full access, which a code worker must not inherit. Use `codex exec` rather than an MCP bridge: the `codex mcp-server` command has been removed.
6. **Bound every loop.** A review cycle has at most 5 rounds. A failed Codex run is resumed once with its failure; a second failure returns to the main session. A worker blocked by a permission prompt stops on the first prompt.
7. **Verify from artifacts.** Done means an exit-status file, a round commit, a check log of that commit, diffs from the recorded base and a review verdict, never a worker's own summary. A test run that selected no tests is not evidence.

## Rounds and Review

Codex never commits. After each round the pipeline subagent runs `.agents/bin/collect_round.py` detached, with absolute paths, because a subagent's working directory is reset between commands. The script checks that HEAD has not moved, unstages anything Codex staged, records changes outside the write set in `outside.txt`, commits the write set on the worker branch as that round's commit, and writes `diff.patch` from the base and `fix.patch` for the round. It then sets the remaining changes aside in the run directory, runs `run_checks.py` so the log describes the round commit and nothing else, and restores them. A round that only reverted files outside the write set keeps the previous commit.

The reviewer reads the brief, its acceptance items and the must-check points before the diff, then the diffs and the code at the round commit. It treats the writer's summary as a claim. Each finding names the defect, the location, the impact and the evidence; one substantiated blocker is worth more than a list of preferences, and anything a passing check already enforces is left out. The reviewer also checks that documentation and interface comments changed with behaviour, that no session residue entered code or documents, and which rulings deserve a note. The first line of its verdict is `ACCEPT`, `REQUEST_CHANGES` or `BLOCKED`; the main session treats any other first line as `BLOCKED`. Every entry in `outside.txt` becomes a request to revert that file. Findings outside the brief go to the ledger as candidates.

The main session rules on each verdict. Round 2 resumes the same Codex session with the agreed changes, and Codex verifies each one and either makes it or answers with a technical reason. From round 3, the main session first rereads the failing criteria, since a criterion that keeps failing may not be testable as written, and then rewrites the brief, raises the effort to `xhigh`, or starts a fresh session. After round 5 the main session decides and records the ruling. [Review](references/review.md) has the verdict format.

## Close-out

An accepted change is not yet ready to merge. Before the freeze, the main session decides what the cycle leaves behind:

1. **Notes.** Each ruling whose reasons will guide later work becomes a new note or an edit of an existing one, following [notes](references/notes.md). Advisor answers and rejected review suggestions supply the alternatives.
2. **Shared documents.** Changes the worker listed under docs impact, in files outside its write set such as the root README or a guide in `docs/`, are made now.
3. **One writer.** The close-out is a follow-up worker in the same lineage, such as `w12.1`, in the same worktree, whose write set is those notes and documents. `--dispatch` therefore keeps two close-outs from editing one shared document at once, and a second close-out starts from the merged result of the first.
4. **Checks and review.** The pipeline collects the close-out round like any other, the checks run in `ci` mode including `repo_check.py`, and the reviewer reads the close-out diff with the documentation and prose lenses.

The freeze then tags the accepted close-out commit. [Close-out](references/closeout.md) has the steps.

## Paid Runs, Kills and Freezes

Before a paid launch the main session writes a launch record from [assets/launch-record.md](assets/launch-record.md) in the run directory: command, frozen tag, host, ports and devices, expected duration and cost, numbers to collect, and the condition for killing the run. It records the run's resources in the state file, launches it itself with `detach.sh` and records the pid. The watcher writes the receipt to `collect/receipt.md`.

Before a kill the main session lists the job's process group and compares it with the launch record. It terminates the job under the wrapper, gives the wrapper time to record exit status 143, then terminates the rest of the group, waits for it to empty, and records the kill in the ledger. A freeze is a tag on the accepted round commit. See [waiting](references/waiting.md) and [state](references/state.md).

## Direction and Reports

The advisor answers only questions of direction. A subagent drafts the question from [the question runbook](assets/runbooks/question.md), the main session edits it, launches Codex read-only at maximum effort with `detach.sh` and keeps the answer verbatim under `.agents/work/advice/`. The ruling goes into the ledger before any brief depends on it. Bugs, implementation detail and anything a test can settle never go to the advisor. See [advisor](references/advisor.md).

For a report, the main session writes a facts sheet: each number, path, commit and status with its source file. The reporter returns a precise version, a plain version and a number checklist within the word limits it was given. A cause the evidence does not establish is reported as not established. The main session opens each source in the checklist before sending. See [reporting](references/reporting.md).

## Writing and Records

Agent-written text drifts in two directions: it keeps the history of how it was made, and it loses conditions when shortened. Three references hold the rules every writer and reviewer applies:

- [Documentation](references/documentation.md): which carrier holds which fact, one home per fact, and claims checked by running them as written.
- [Prose](references/prose.md): list the propositions before editing, keep every condition, order, obligation and failure, and remove session residue, judged by whether a reader with only this checkout can verify each reference.
- [Notes](references/notes.md): lifecycle, sections, supersession, and an archive that only grows.

`repo_check.py` enforces what a script can: local links, the size of each AGENTS.md chain, note structure, the frozen archive and references to work records. The rest is the reviewer's judgement.

## Checks and Hooks

`.agents/checks.json` lists every check once. The pipeline, the git hooks, CI and agents all call `.agents/bin/run_checks.py --mode <commit|test|ci>`, so a check means the same in each place. A merge commit runs the `pre-merge-commit` hook and never `pre-commit`, and a fast-forward runs none, so hooks install both and workers are merged with `git merge --no-ff`. Round commits use `--no-verify` because they are snapshots for review; the checks still run on them in the pipeline. [Checks](references/checks.md) covers the registry, the hooks, CI and the session-start hook.

## Permissions

The permission system blocks subagents more often than the main session. Each block costs a round trip through the user. Narrow allow rules for the scripts in `.agents/bin/` and for read-only commands on a known host remove most of them, while launches, kills, merges and pushes stay with the main session behind a prompt. Permission rules match the usual form of a command and are not a security boundary. They keep accidents rare among cooperating agents. [Permissions](references/permissions.md) gives a settings example.

## Invariants

| Invariant | Threshold | Checked by |
| --- | --- | --- |
| Write sets and resources | no file and no resource held by two workers | `work_state.py --dispatch` before each start |
| Detached jobs | every running job has a pid, a log and, once finished, an exit-status file | `work_state.py --alive` |
| Codex commits | none: HEAD equals the previous round commit when the round ends | pipeline collection step |
| Changed files | inside the write set | `outside.txt`, read by the reviewer |
| Check evidence | the log describes the round commit with outside changes set aside, and at least one test ran | `tests.log`, read by the reviewer |
| Acceptance | every item met, each with an output line or file location | review verdict |
| Review rounds | 5 at most, then a recorded ruling | ledger |
| Irreversible actions | executed by the main session, merges and pushes after approval | ledger |
| Subagent writes | inside the worker's new output, or its worktree for the pipeline runner | runbook and `git status` |
| Instruction files | each AGENTS.md chain within 32768 bytes; no CLAUDE.md that hides AGENTS.md | `repo_check.py` |
| Work records | not cited from code or documents | `repo_check.py` |
| Notes | path, header and sections of their lifecycle; archived notes only added | `repo_check.py`, with `--base` in CI |
| Freeze | the tag resolves to the accepted close-out or round commit | `git rev-parse freeze/<id>^{commit}` |
| Reported numbers | each traced to an opened source | number checklist |

## When Something Fails

| Symptom | Response |
| --- | --- |
| A watcher session ends before the job | Check `exit-status` and the pid. If the job still runs, hold the wait in the main session and dispatch a watcher only for collection. |
| A background wait reports a time limit | Re-check the job. It did not finish unless its exit-status file exists. |
| `--alive` reports a pid gone without `exit-status` | The job died. Read the log tails, set the worker to `stopped`, and decide whether to relaunch. |
| `codex exec` produces no output and no CPU | It was started without stdin closed. Kill it after confirming its pid and command line, and relaunch with `detach.sh`. |
| A subagent hits a permission prompt | It stops and reports. The main session runs the step itself, asks the user, or adds a narrow rule. |
| A worker changed a file outside its write set | The reviewer requests the revert. The other worker's change on that file stands. |
| The checks fail on the round commit but passed in the worker's own run | The worker relied on a change outside its write set. The round goes back with the failing log, or the main session widens the write set in a rewritten brief. |
| A Codex run exits without finishing | Resume the session once with the failure. On a second failure, the main session rereads the brief. |
| Codex ignored a rule of a subdirectory | The brief did not name that AGENTS.md. Add the output of `--context` to the brief. |
| `repo_check.py` reports a work record cited from code or a document | State the fact itself, or move the reason into a note. |
| Context was compacted or the session restarted | Run the bearings check before any other action. |
| A worker reports success but the check log fails | The check log stands. The change goes back with the failing output. |
| Reviewer and writer disagree | The main session rules and records why. |

These moves are never allowed:

- a worker fixing, retrying or working around an anomaly it found
- Codex committing, pushing or tagging, or any worker editing outside its write set
- a merge without an `ACCEPT` for the exact commit being merged, or without the user's approval
- a Codex launch, a paid launch, a kill or a push by a subagent
- a subagent reading `.env` or credential files, or writing the state file, the ledger or a note
- reporting a result before its exit-status file and collection exist
- editing, moving or deleting an archived note

## Final Checklist

- Every worker in `.agents/work/state.json` has a brief, an output and a current status, and `work_state.py --alive` reports no error.
- Every merged change has a review verdict, a close-out, a ledger entry and a freeze tag on the accepted commit.
- Every ruling that guides later work is in a note, and every behaviour change is in the documentation it affects.
- `run_checks.py --mode ci` passes on the frozen commit.
- Every paid run has a launch record and a receipt, and every kill has a ledger entry.
- Every number in the report was checked against its source file.
- Every action waiting on the user is named, with what will happen on approval.

## Delivery

Each cycle leaves in the repository the briefs, runbooks, verdicts, advisor answers, the ledger and the state file under `.agents/work/`, one run directory per round with its logs, exit status, round commit, diffs and check log, the notes and documents changed at close-out, a tag per freeze, and the report with its number checklist. The message to the user lists which workers changed state, which numbers were checked, which actions wait for approval, and every check that was not run.

[Method basis](references/basis.md) records the sources, the open-source projects compared and the tests behind the rules. [The example](examples/README.md) shows a project mid-cycle.
