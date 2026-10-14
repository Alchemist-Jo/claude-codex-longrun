# w00 One line that names the observable change

Worker: w00
Base: main@0000000
Effort: high
Write set:
- path/to/file.py
- path/to/directory/

## Objective

One paragraph. State the behaviour that exists after this brief and does not exist before it, in terms a test or a command can show.

## Context

- Files to read before editing, with the reason for each.
- Rulings this brief depends on, by ledger date and worker, and advisor answers by file.
- Facts already established, with their evidence path, so they are not rediscovered.

## Changes

1. Each change, one per item, specific enough that a reviewer can say whether it happened.

## Out of scope

- Changes that look related but belong to another brief or to none.

## Acceptance

1. A testable statement, the command that checks it, and the expected result.
2. The full test suite passes: `<test command>` exits 0.

## Constraints

- Change only the files in the write set. If another file must change, stop and name it in the final message.
- Do not commit, amend, push, tag, rebase or create branches.
- Do not read `.env` or credential files.
- Do not start paid runs, GPU jobs or long-running services. Use the fixtures named in Context.
- Run the acceptance commands before finishing.

## Final message

1. Status: DONE, DONE_WITH_CONCERNS, BLOCKED or NEEDS_CONTEXT.
2. Files changed, each with one line on what changed.
3. Each acceptance item: met, not met or not checked, with the output line that shows it.
4. Commands run and their exit codes.
5. Anything the brief did not cover, and every file outside the write set that would need to change.
