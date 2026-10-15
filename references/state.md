# State, bearings, round commits and freezes

Read at the start of every session, after every context compaction, when collecting a round, and when freezing accepted work.

## Work records

~~~text
.agents/work/
  state.json        every worker: route, status, write set, resources, worktree, session, pid, log, output
  ledger.md         rulings, launches, kills, merges, changes of direction
  briefs/           one brief or filled runbook per worker
  reviews/          one verdict per review round
  advice/           advisor questions and verbatim answers
  reports/          facts sheets, reports and number checklists
  runs/<worker>-r<round>/
                    pid, exit-status, stdout.log, stderr.log, last-message.md, round.md,
                    round-commit, diff.patch, fix.patch, outside.txt, outside.patch,
                    outside-new.lst, outside-new.tar, tests.log, tests-exit-status,
                    collect-report.md, collection/, launch-record.md, collect/
~~~

The main session alone writes `state.json`, `ledger.md` and the notes. Subagents write only inside the directory or file their runbook names. Commit `.agents/work/` with the project. Large logs can be listed in `.gitignore` once their numbers are in a receipt.

## state.json

Start from [assets/state.json](../assets/state.json). One entry per worker:

| Field | Meaning |
| --- | --- |
| `id` | Short and stable, such as `w12`. A worker that continues another, such as a close-out, uses `w12.1` and sets `parent` |
| `route` | `codex`, `subagent`, `advisor`, `paid-run`, or `main` for work the main session does itself in a worktree, such as a close-out edit |
| `status` | See the transitions below |
| `brief` | Path to the brief or runbook, relative to the repository root |
| `writes` | Files the worker may change. A directory ends with `/`. Empty for read-only workers |
| `resources` | Named things only one worker may use at a time, such as `gpu-host/port:6379` or `gpu-host/gpus`. Compared as exact strings |
| `base` | `branch@commit` the worker started from, recorded once and never recomputed |
| `worktree` | Required for a Codex worker that writes |
| `session` | The Codex session id to resume, replaced when a round starts a fresh session |
| `round` | The current round number |
| `host` | `local` or the SSH host name |
| `pid` | The wrapper's pid from the current run directory |
| `log` | The main log of the current run |
| `out` | The current run's own directory, or for a reviewer its verdict file. Never shared |
| `parent` | The worker this one continues |

On every new round, the main session updates `round`, `pid`, `log` and `out` to the new run directory. A state file that still points at the previous round would make a finished earlier round look like the current result.

## Status transitions

| From | Event | To |
| --- | --- | --- |
| `planned` | launched, pid recorded | `running` |
| `running` | `exit-status` exists and collection returned | `review` |
| `review` | ruling: requested changes agreed | `changes` |
| `changes` | next round launched | `running` |
| `review` | ruling: `ACCEPT` | `accepted` |
| `accepted` | merged by the main session after approval | `merged` |
| `running` | killed, or died without `exit-status` | `stopped` |
| any open status | replaced by a combined brief, or dropped | `abandoned` |
| `running`, read-only worker | returned | `done` |

A worker holds its write set and resources while `running`, `review`, `changes` or `accepted`. A `stopped` worker keeps its entry and does not hold them, so an overlap with it is a warning. Workers in one lineage, connected by `parent`, may share files.

## Checking the file

~~~sh
python3 .agents/bin/work_state.py --summary --alive
python3 .agents/bin/work_state.py --dispatch w13
python3 .agents/bin/work_state.py --context w13
~~~

The script reports overlapping write sets and resources, running processes without a pid or log, shared outputs and missing briefs. With `--alive` it reads each local running job's `exit-status`: present means collect and update the status, missing with the pid gone is an error. Remote jobs are listed for checking on their host. `--context` prints the AGENTS.md files below the root that apply to the worker's write set.

## Ledger

One line per event, appended, never edited:

~~~text
2026-10-14 w12 Ruling: request change 1, reject change 2; 2 edits cli.py outside the write set; one more round if wrong. Evidence: .agents/work/reviews/w12-r1.md
2026-10-14 p07 Launch: tag freeze/w11, host gpu-host, pid 48211, port 6379, expected 6 h. Record: .agents/work/runs/p07/launch-record.md
2026-10-15 w12 Merge: waiting for the user's approval; tag freeze/w12 at 3f9e0b2.
~~~

A ruling names the decision, the reason and what it costs if wrong. At close-out, rulings that will guide later work become notes, as in [notes](notes.md). After a compaction, the ledger and `git log` are the record of why things are as they are.

## Bearings

Run before any other action at the start of a session and after every compaction:

~~~sh
python3 .agents/bin/work_state.py --bearings
~~~

It prints `git status --short`, `git worktree list`, the last five commits, the worker table with the liveness check, and the last ledger lines. With the session-start hook from [checks](checks.md), Claude Code runs it at startup, on resume and after a compaction, and the output is already in context. Then:

1. For each remote job marked running, the single check in [waiting](waiting.md): `wait.sh <run> 0` on its host.
2. Reconcile: dispatch collection for finished jobs, report jobs that died, and update the state file.
3. Read the AGENTS.md of the directories the next step touches, and the notes on the same subject.

Only then choose the next route. A summary held in memory from before the compaction is not evidence.

## Round commits

Codex never commits. After each round, the pipeline subagent runs `.agents/bin/collect_round.py`, which commits the round's write-set changes on the worker branch, so every round has a commit and the reviewer can diff any two of them, and then runs the checks on that commit alone. A subagent's working directory is reset between commands, so the script takes absolute paths and never relies on a `cd`. The checks may outlast one foreground call, so the collection runs detached:

~~~sh
run=/abs/repo/.agents/work/runs/w12-r2; mkdir "$run/collection"
.agents/bin/detach.sh "$run/collection" -- python3 /abs/repo/.agents/bin/collect_round.py \
  --run "$run" --worktree /abs/wt/w12 --base 3f2c1aa \
  --parent "$(cat /abs/repo/.agents/work/runs/w12-r1/round-commit)" \
  --label "w12 round 2" --mode ci -- src/evalkit/runner.py tests/test_runner.py
.agents/bin/wait.sh "$run/collection" 570
~~~

Round 1 passes the recorded base as `--parent`. The script:

1. stops unless `exit-status` exists and HEAD equals the parent, which shows that Codex made no commit
2. resets the index, so a change Codex staged outside the write set cannot enter the commit, and lists every change outside the write set in `outside.txt`
3. stages the write set path by path, skipping a listed file that was never created, and commits it with `--no-verify`; a round that only reverted outside files keeps the parent; it writes `round-commit`, `diff.patch` from the base and `fix.patch` for the round
4. saves whatever is left, which lies outside the write set, as `outside.patch` and `outside-new.tar`, and removes it, so the worktree equals the round commit plus ignored files
5. runs `.agents/bin/run_checks.py --mode ci` in the worktree into `tests.log` and `tests-exit-status`
6. restores the saved changes, also when it is terminated during the checks

Its exit status is 0 when the checks passed and nothing lies outside the write set, 1 when the round needs the reviewer's attention, and 2 when it stopped; `collect-report.md` says which. Without step 4, a change outside the write set can make the checks pass for code the round commit does not contain. `git stash` is not used, because all worktrees of a repository share one stash stack. Files the checks themselves create appear in the next round's `outside.txt` unless the project ignores them.

`outside.txt` lists changes outside the write set, which stay unstaged in the worktree. A non-empty file goes to the reviewer and makes the pipeline report `DONE_WITH_CONCERNS`. The worker branch is local, and the merge decides whether its round commits are squashed.

## Freeze

After `ACCEPT`, the main session's ruling and the close-out, the freeze is a tag on the accepted commit:

~~~sh
git -C "$wt" tag freeze/w12 "$(cat .agents/work/runs/w12.1-r1/round-commit)"
git -C "$wt" rev-parse freeze/w12^{commit}
~~~

The tag fixes the code that was reviewed. The run directories are written once and stay as the evidence. The merge itself and any push are the main session's, after the user's approval. Merge with `git merge --no-ff worker/<id>`: a merge commit runs the `pre-merge-commit` hook, so the checks run at the merge when hooks are installed as in [checks](checks.md), while a fast-forward merge runs no hook at all.
