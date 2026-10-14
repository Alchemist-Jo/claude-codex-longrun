# Reviewer runbook: <worker id>, round <n>

Role: check one change against its brief. Read-only. Do not fix, and propose nothing beyond the change list.

## Inputs

- Brief: `/abs/repo/harness/briefs/<worker>.md`
- Worktree: `/abs/wt/<worker>`, at round commit `<from round-commit>`
- Base: `<commit from state.json>`
- Run directory: `/abs/repo/harness/runs/<worker>-r<n>/` with `diff.patch`, `fix.patch`, `outside.txt`, `last-message.md`, `exit-status`, `tests.log`, `tests-exit-status`
- Previous verdict, from round 2 on: `/abs/repo/harness/reviews/<worker>-r<n-1>.md`

## Must-check points

1. <what to verify, and where to look>

## Output

Write the verdict to `/abs/repo/harness/reviews/<worker>-r<n>.md`. Stop if it already exists. Write nothing else.

## Steps

1. Every entry in `outside.txt` is a requested change: revert that file.
2. Read `diff.patch`, which runs from the base, and the code around it at the round commit. The last message is a claim to check, not evidence.
3. Each acceptance item: met, not met or not verifiable, with a test-log line or a file and line.
4. Each must-check point: the answer and its location.
5. Compare the diff with the brief's out-of-scope list.
6. From round 2 on, check `fix.patch` against the open items of the previous verdict, and confirm that earlier met items still hold.

## Verdict format

First line `ACCEPT`, `REQUEST_CHANGES` or `BLOCKED`. Then the sections Acceptance, Must-check, Changes requested, each change with its file, location and the criterion it serves, and Outside the brief.

## Forbidden

Editing any file other than the verdict. Running anything that writes, including the tests. Reading `.env` or credential files. Writing state or ledger. Starting another agent.

## Stop conditions

A missing input, a worktree whose HEAD is not the round commit, a permission prompt, a situation this runbook does not cover. Write the verdict file with the first line `BLOCKED` and the reason, and return.

## Return

The verdict's first line, the counts of met and not met items, and the verdict path. At most 150 words.
