# Pipeline runbook: <worker id>, <prepare | collect | freeze>, round <n>

Role: run one fixed sequence of mechanical steps exactly as written. This runbook never starts Codex; the main session launches it.

## Inputs

- Repository: `/abs/repo`
- Worker: `<id>`, base `<commit from state.json>`, worktree `/abs/wt/<id>`
- Write set:
  - `<path>`
- Brief: `/abs/repo/harness/briefs/<id>.md`
- Run directory: `/abs/repo/harness/runs/<id>-r<n>`
- Previous round commit: `<from harness/runs/<id>-r<n-1>/round-commit, or the base in round 1>`
- Test command: `<command>`

Keep the sequence this dispatch names and delete the other two. Run `set -eu` first and check each command's exit status before the next.

## Prepare, round 1

1. `mkdir <run>`. Stop if it exists.
2. From `/abs/repo`: `git worktree add -b worker/<id> /abs/wt/<id> <base>`.
3. Copy the brief to `/abs/wt/<id>/BRIEF.md`, and add `BRIEF.md` to `info/exclude` of the common git directory if it is absent.
4. Return the worktree path and `git -C /abs/wt/<id> rev-parse HEAD`.

## Collect, after the main session reports that the job finished

Run `cd /abs/wt/<id>` as its own command first, then the git commands below without `-C`, so they match the project's permission rules.

1. `exit-status` exists in `<run>`. Stop if not.
2. `git rev-parse HEAD` equals the previous round commit. Stop if not: Codex committed.
3. Record what lies outside the write set, before anything else touches the worktree: `{ git diff --name-only -- . ':!<path>'; git ls-files -o --exclude-standard -- . ':!<path>'; } > <run>/outside.txt`, with one `':!<path>'` per write-set entry. Untracked files that Codex's own test runs created, and that the project does not ignore, appear here too; the reviewer judges them.
4. Stage the write set only, path by path, skipping a listed path that neither exists nor is tracked: `git add -A -- <path>`.
5. If `git diff --cached --quiet` reports nothing staged, the round only reverted files outside the write set: write the previous round commit to `<run>/round-commit` and skip to step 7. Otherwise commit with `git commit --no-verify -m "<id> round <n>"` and write `git rev-parse HEAD` to `<run>/round-commit`. Round commits are snapshots for review; the project's hooks run at the merge.
6. Diffs: `git diff <base> HEAD > <run>/diff.patch` and `git diff <previous round commit> HEAD > <run>/fix.patch`.
7. Tests: run the test command in the worktree, output to `<run>/tests.log`, exit status to `<run>/tests-exit-status`. A failing test is recorded, not a stop.
8. Return `DONE`, or `DONE_WITH_CONCERNS` when `outside.txt` is not empty or the tests failed.

## Freeze, after the main session's `ACCEPT` ruling

1. In `/abs/wt/<id>`: `git tag freeze/<id> <accepted round commit>`. Stop if the tag exists.
2. `git rev-parse freeze/<id>^{commit}` equals the accepted round commit.

## Forbidden

Starting Codex or any agent. Merging, pushing, deleting branches or tags, resolving conflicts, editing code, launching paid runs, killing processes. Staging anything outside the write set. Reading `.env` or credential files. Writing `harness/state.json` or `harness/ledger.md`.

## Stop conditions

A non-zero exit status not listed as expected, an existing run directory or tag, a HEAD that does not match, a permission prompt, a step this runbook does not cover. Stop at the first, write it to `<run>/pipeline-report.md`, and return.

## Return

Status, the steps completed, the paths and commits each produced, and for anything unexpected: Expected, Found, Why it matters. At most 200 words.
