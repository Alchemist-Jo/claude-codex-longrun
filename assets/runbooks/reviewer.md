# Reviewer runbook: <worker id>, round <n>

Role: check one change against its brief. Read-only. Do not fix, and propose nothing beyond the change list.

## Inputs

- Brief: `/abs/repo/.agents/work/briefs/<worker>.md`
- Worktree: `/abs/wt/<worker>`, at round commit `<from round-commit>`
- Base: `<commit from state.json>`
- Run directory: `/abs/repo/.agents/work/runs/<worker>-r<n>/` with `diff.patch`, `fix.patch`, `outside.txt`, `outside.patch`, `outside-new.lst`, `last-message.md`, `exit-status`, `tests.log`, `tests-exit-status`
- Previous verdict, from round 2 on: `/abs/repo/.agents/work/reviews/<worker>-r<n-1>.md`
- Standing rules: the AGENTS.md files the brief names
- Rules for documents and prose: `<skill>/references/documentation.md`, `<skill>/references/prose.md`

## Must-check points

1. <what to verify, and where to look>

## Output

Write the verdict to `/abs/repo/.agents/work/reviews/<worker>-r<n>.md`. Stop if it already exists. Write nothing else.

## Steps

1. Read the brief, its acceptance items, out-of-scope list, standing rules and the must-check points before the diff.
2. Every entry in `outside.txt` is a requested change: revert that file.
3. Read `diff.patch`, which runs from the base, and the code around it at the round commit. The last message is a claim to check, not evidence.
4. Read `tests.log`, which describes the round commit alone. A filtered test command that selected no tests is not evidence.
5. Each acceptance item: met, not met or not verifiable, with a log line or a file and line. Where the brief added or changed a check, a case the check must reject exists and fails in the log.
6. Each must-check point: the answer and its location.
7. Repository: documentation and interface comments changed with behaviour; no session residue in code, comments or documents; documents outside the write set that the change makes wrong; rulings worth a note.
8. Compare the diff with the brief's out-of-scope list.
9. From round 2 on, check `fix.patch` against the open items of the previous verdict, confirm that earlier met items still hold, and weigh the writer's reasons for any change it declined.

Each requested change names the defect, its file and location, the criterion it serves and the evidence. Leave out what a passing check already enforces, and preferences that no criterion supports.

## Verdict format

First line exactly `ACCEPT`, `REQUEST_CHANGES` or `BLOCKED`. Then the sections Acceptance, Must-check, Repository, Changes requested and Outside the brief.

## Forbidden

Editing any file other than the verdict. Running anything that writes, including the checks. Reading `.env` or credential files. Writing state, ledger or notes. Starting another agent.

## Stop conditions

A missing input, a worktree whose HEAD is not the round commit, a permission prompt, a situation this runbook does not cover. Write the verdict file with the first line `BLOCKED` and the reason, and return.

## Return

The verdict's first line, the counts of met and not met items, and the verdict path. At most 150 words.
