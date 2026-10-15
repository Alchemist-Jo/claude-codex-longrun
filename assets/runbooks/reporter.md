# Reporter runbook: <topic>

Role: write two versions of one report from a facts sheet, and list every number used.

## Inputs

- Facts sheet: `/abs/path/.agents/work/reports/<date>-<topic>/facts.md`
- Reader of the plain version: <who>
- Language: <language>
- Limits: precise <n> words or characters, plain <n>

## Output

`precise.md`, `plain.md` and `checklist.md` in the facts sheet's directory. Stop if any exists.

## Rules

- Use only facts from the sheet. Add no number, cause, comparison or recommendation.
- Write "cause not established" where the sheet says so.
- Keep every number exactly as the sheet gives it, with its unit.
- Use neutral status labels: completed, confirmed, below baseline, not yet established.
- `checklist.md` has one row per number in either version: the number, the version and sentence it appears in, and its facts-sheet row.

## Forbidden

Opening sources outside the facts sheet to add facts. Editing any other file. Writing state or ledger. Starting another agent.

## Stop conditions

A fact the report needs that the sheet lacks, two sheet rows that contradict each other, a limit that cannot be met without dropping a fact the sheet marks as required. Write the problem into `checklist.md` and return.

## Return

The three paths, the word counts, and any fact that was left out with the reason. At most 120 words.
