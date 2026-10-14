# State, bearings and freezes

Read when setting up a project, at the start of every session, after every context compaction, and when freezing accepted work.

## Layout

~~~text
harness/
  state.json        every worker: route, status, write set, worktree, session, pid, log, output
  ledger.md         rulings, launches, kills, merges, changes of direction
  briefs/           one brief or filled runbook per worker
  reviews/          one verdict per review round
  advice/           advisor questions and verbatim answers
  reports/          facts sheets, reports and number checklists
  bin/              detach.sh, on remote hosts
  runs/<worker>-r<round>/
                    pid, exit-status, stdout.log, stderr.log, last-message.md, round.md,
                    tests.log, round-commit, diff.patch, fix.patch, outside.txt,
                    launch-record.md, collect/
~~~

The main session alone writes `state.json` and `ledger.md`. Subagents write only inside the directory or file their runbook names. Commit `harness/` with the project. Large logs can be listed in `.gitignore` once their numbers are in a receipt.

## state.json

Start from [assets/state.json](../assets/state.json). One entry per worker:

| Field | Meaning |
| --- | --- |
| `id` | Short and stable, such as `w12`. A worker that continues another uses `w12.1` and sets `parent` |
| `route` | `codex`, `subagent`, `advisor` or `paid-run` |
| `status` | See the transitions below |
| `brief` | Path to the brief or runbook, relative to the repository root |
| `writes` | Files the worker may change. A directory ends with `/`. Empty for read-only workers |
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

A worker holds its write set while `running`, `review`, `changes` or `accepted`. A `stopped` worker keeps its entry and does not hold files, so an overlap with it is a warning. Workers in one lineage, connected by `parent`, may share files.

## Checking the file

~~~sh
python3 "$H/scripts/harness_state.py" harness/state.json --summary --alive
python3 "$H/scripts/harness_state.py" harness/state.json --dispatch w13
~~~

`$H` is this skill's directory. The script reports overlapping write sets, running processes without a pid or log, shared outputs and missing briefs. With `--alive` it reads each local running job's `exit-status`: present means collect and update the status, missing with the pid gone is an error. Remote jobs are listed for checking on their host.

## Ledger

One line per event, appended, never edited:

~~~text
2026-10-14 w12 Ruling: request change 1, reject change 2; 2 edits cli.py outside the write set; one more round if wrong. Evidence: harness/reviews/w12-r1.md
2026-10-14 p07 Launch: tag freeze/w11, host gpu-host, pid 48211, expected 6 h. Record: harness/runs/p07/launch-record.md
2026-10-15 w12 Merge: waiting for the user's approval; tag freeze/w12 at 3f9e0b2.
~~~

A ruling names the decision, the reason and what it costs if wrong. After a compaction, the ledger and `git log` are the record of why things are as they are.

## Bearings

Run before any other action at the start of a session and after every compaction:

1. `pwd`, `git status --short`, `git worktree list`, `git log --oneline -10`.
2. `python3 "$H/scripts/harness_state.py" harness/state.json --summary --alive`.
3. The last 20 lines of `harness/ledger.md`.
4. For each remote job marked running, the single check in [waiting](waiting.md): `wait.sh <run> 0` on its host.
5. Reconcile: dispatch collection for finished jobs, report jobs that died, and update the state file.

Only then choose the next route. A summary held in memory from before the compaction is not evidence.

## Round commits

Codex never commits. After each round, the pipeline subagent commits the round's write-set changes on the worker branch, so every round has a commit and the reviewer can diff any two of them:

~~~sh
set -eu
base=3f2c1aa; wt=/abs/wt/w12; run=/abs/repo/harness/runs/w12-r2   # base from state.json
parent=$(cat /abs/repo/harness/runs/w12-r1/round-commit)   # round 1 uses the recorded base
test "$(git -C "$wt" rev-parse HEAD)" = "$(git -C "$wt" rev-parse "$parent")"   # Codex made no commit
keep=(':!src/evalkit/runner.py' ':!tests/test_runner.py')                         # the write set, excluded
{ git -C "$wt" diff --name-only -- . "${keep[@]}"; git -C "$wt" ls-files -o --exclude-standard -- . "${keep[@]}"; } > "$run/outside.txt"
for p in src/evalkit/runner.py tests/test_runner.py; do                          # the write set
  if [ -e "$wt/$p" ] || git -C "$wt" ls-files --error-unmatch -- "$p" >/dev/null 2>&1; then
    git -C "$wt" add -A -- "$p"                                                   # skips a listed file never created
  fi
done
if git -C "$wt" diff --cached --quiet; then
  echo "$parent" > "$run/round-commit"                                        # the round only reverted outside files
else
  git -C "$wt" commit --no-verify -m "w12 round 2"                            # a snapshot; hooks run at the merge
  git -C "$wt" rev-parse HEAD > "$run/round-commit"
fi
git -C "$wt" diff "$base" HEAD > "$run/diff.patch"      # the whole change
git -C "$wt" diff "$parent" HEAD > "$run/fix.patch"     # this round only
~~~

The pipeline's own test run happens after the commit, so files it creates do not enter `outside.txt`.

`outside.txt` lists changes outside the write set, which stay unstaged. Untracked files from Codex's own test runs appear there unless the project ignores them; the reviewer judges each entry. A non-empty file goes to the reviewer and makes the pipeline report `DONE_WITH_CONCERNS`. The worker branch is local, and the merge decides whether its round commits are squashed.

## Freeze

After `ACCEPT` and the main session's ruling, the freeze is a tag on the accepted round commit:

~~~sh
git -C "$wt" tag freeze/w12 "$(cat harness/runs/w12-r2/round-commit)"
git -C "$wt" rev-parse freeze/w12^{commit}
~~~

The tag fixes the code that was reviewed. The run directories are written once and stay as the evidence. The merge itself and any push are the main session's, after the user's approval.
