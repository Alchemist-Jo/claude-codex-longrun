# Watcher runbook: <worker id>

Role: wait for one job to end within this turn, then collect the listed numbers. Read-only.

## Inputs

- Run directory: `/abs/path/harness/runs/<worker>-r<round>/`, or on a remote host `/work/proj/harness/runs/<worker>/`
- Host: `local` or `<ssh host>`
- Expected exit status: 0

## Output

Create `/abs/path/harness/runs/<worker>-r<round>/collect/` in the local run directory, also for a remote job. Stop if it already exists. Write only there. Read remote files with `ssh <host> cat <path>`.

## Steps

1. Wait in the foreground with the Bash tool timeout set to 600000 ms, inside this turn:
   - local: `<skill>/scripts/wait.sh <run> 570`
   - remote: `ssh <host> /work/proj/harness/bin/wait.sh <remote run> 570`
2. Exit 3: repeat step 1 until 25 minutes have passed in total, then return `BLOCKED` with "still running". Never end the turn with a background command running.
3. Exit 4: return `BLOCKED` with the last 40 lines of `stderr.log` and `stdout.log`.
4. Exit 0: collect each checklist item into `collect/receipt.md`: the value, its file and line, and whether it matches the expectation. For a paid run, add the exit status and the wall time.

## Checklist

| Item | File | Expected |
| --- | --- | --- |
| <number or fact> | <path inside the run directory> | <value or range> |

## Forbidden

Starting, restarting, resuming or killing any process. Editing any file outside `collect/`. Reading `.env` or credential files. Writing `harness/state.json` or `harness/ledger.md`. Starting another agent.

## Stop conditions

An unexpected exit status or output, a missing input, a value outside its expected range, a permission prompt, a step outside this runbook. Write what you saw to `collect/receipt.md` and return.

## Return

Status, the receipt path, each checklist value with its source, and for anything unexpected: Expected, Found, Why it matters. At most 250 words.
