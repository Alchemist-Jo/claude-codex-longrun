# Pipeline runbook: <worker id>, <prepare | collect | freeze>, round <n>

Role: run one fixed sequence of mechanical steps exactly as written. This runbook never starts Codex or Gemini; the main session launches them.

## Inputs

- Repository: `/abs/repo`
- Worker: `<id>`, base `<commit from state.json>`, worktree `/abs/wt/<id>`
- Write set:
  - `<path>`
- Brief: `/abs/repo/.agents/work/briefs/<id>.md`
- Run directory: `/abs/repo/.agents/work/runs/<id>-r<n>`
- Previous round commit: `<from .agents/work/runs/<id>-r<n-1>/round-commit, or the base in round 1>`
- Check mode: `<ci, or the mode the brief names>`

Keep the sequence this dispatch names and delete the other two. Your working directory is reset between commands, so every command uses absolute paths. Check each command's exit status before the next.

## Prepare, round 1

1. `mkdir <run>`. Stop if it exists.
2. `git -C /abs/repo worktree add -b worker/<id> /abs/wt/<id> <base>`.
3. Copy the brief to `/abs/wt/<id>/BRIEF.md`, and add `BRIEF.md` to `info/exclude` of the common git directory if it is absent.
4. Return the worktree path and `git -C /abs/wt/<id> rev-parse HEAD`.

## Collect, after the main session reports that the job finished

1. `mkdir <run>/collection`. Stop if it exists.
2. Start the collection detached:
   `/abs/repo/.agents/bin/detach.sh <run>/collection -- python3 /abs/repo/.agents/bin/collect_round.py --run <run> --worktree /abs/wt/<id> --base <base> --parent <previous round commit> --label "<id> round <n>" --mode <mode> -- <path> [<path> ...]`
3. Wait in the foreground with the Bash tool timeout set to 600000 ms: `/abs/repo/.agents/bin/wait.sh <run>/collection 570`. On exit 3, repeat until 25 minutes have passed in total, then return `BLOCKED` with "collection still running". On exit 4, return `BLOCKED` with the last 40 lines of `<run>/collection/stderr.log`.
4. Read `<run>/collection/exit-status` and `<run>/collect-report.md`:
   - 0: the checks passed and nothing lies outside the write set. Return `DONE`.
   - 1: return `DONE_WITH_CONCERNS`, naming the paths in `outside.txt` and the failing checks from the summary line of `tests.log`.
   - 2 or anything else: the collection stopped. Return `BLOCKED` with the report's reason.
5. If `tests.log` shows a test command that selected no tests, return `DONE_WITH_CONCERNS` and say so.

## Freeze, after the main session's `ACCEPT` ruling and the close-out

1. `git -C /abs/repo tag freeze/<id> <accepted commit>`. Stop if the tag exists.
2. `git -C /abs/repo rev-parse freeze/<id>^{commit}` equals the accepted commit.

## Forbidden

Starting Codex, Gemini or any agent. Merging, pushing, deleting branches or tags, resolving conflicts, editing code, launching paid runs, killing processes. Running git commands that change the worktree by hand instead of through `collect_round.py`. Using `git stash`, whose stack all worktrees share. Reading `.env` or credential files. Writing `.agents/work/state.json`, `.agents/work/ledger.md` or a note.

## Stop conditions

A non-zero exit status not listed as expected, an existing run directory or tag, a collection that stopped, a permission prompt, a step this runbook does not cover. Stop at the first, write it to `<run>/pipeline-report.md`, and return.

## Return

Status, the steps completed, the paths and commits each produced, the check summary line from `tests.log`, and for anything unexpected: Expected, Found, Why it matters. At most 200 words.
