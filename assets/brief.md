# w00 One line that names the observable change

Worker: w00
Base: main@0000000
Effort: high
Write set:
- path/to/file.py
- path/to/README.md
- path/to/directory/

## Constraints

- Change only the files in the write set. If another file must change, stop and name it in the final message.
- Do not commit, amend, push, tag, rebase or create branches.
- Do not read `.env` or credential files.
- Do not start paid runs, GPU jobs or long-running services. Use the fixtures named in Context.
- Do not hide an unstable test with a longer timeout, a retry, a sleep, serial execution, a swallowed error or a weaker assertion.
- Code, comments and documents state current facts. Do not mention this brief, its worker id, rounds or reviews in them.
- Run the acceptance commands before finishing.

## Standing rules

Read these before editing; they are not loaded automatically from the worktree root:

- `path/to/AGENTS.md` (the output of `work_state.py --context w00`)

## Objective

One paragraph. State the behaviour that exists after this brief and does not exist before it, in terms a test or a command can show.

## Context

- Files to read before editing, with the reason for each.
- Notes and rulings this brief depends on: note paths, ledger dates and workers, advisor answers by file.
- Facts already established, with their evidence path, so they are not rediscovered.

## Changes

1. Each change, one per item, specific enough that a reviewer can say whether it happened.
2. The module README and interface comments that describe the changed behaviour.

## Out of scope

- Changes that look related but belong to another brief or to none.

## Acceptance

1. A testable statement, the narrowest command that would fail if it regressed, and the expected result, including how many tests it selects.
2. For a new or changed check: a case the check rejects, and the rejection in the output.
3. Every check passes: `python3 .agents/bin/run_checks.py --mode ci` exits 0.

## Final message

1. Status: DONE, DONE_WITH_CONCERNS, BLOCKED or NEEDS_CONTEXT.
2. Files changed, each with one line on what changed.
3. Each acceptance item: met, not met or not checked, with the output line that shows it.
4. Commands run and their exit codes.
5. Docs impact: documents outside the write set that this change makes wrong, with the section.
6. Anything the brief did not cover, and every file outside the write set that would need to change.
