# Prose, comments and session residue

Read when reviewing text that agents wrote or edited: documents, comments, docstrings, prompts, error messages, notes. The same rules go into briefs that ask for such text.

## Scope first

Know the task and its scope before touching text. A review or an audit reports; only an implementation task rewrites. Without a named scope, establish the files first instead of sweeping the repository. Third-party code and archived notes are out of scope. Generated files, snapshots and fixtures are derived: change their source and regenerate.

Strings that a model or a user sees, such as prompts, error messages and CLI output, are behaviour. Changing them is a code change with the tests and snapshots that cover them, never a wording pass.

## List the propositions before editing

Before shortening or rewriting a passage, list what it asserts:

- subject and action
- conditions, timing and order
- obligations: must, may, must not
- negative guarantees and exceptions
- ownership, side effects, failures and their consequences

Each valid proposition survives the edit. Fewer words is not an improvement in itself. Supplying a missing condition or restoring a deleted one counts as much as removing noise.

Decide each item as keep, add, trim, restore, restructure or defer. Where two versions both keep every fact and differ only in a real trade-off, report it rather than inventing a worse alternative.

## What goes where in code

- **Public interfaces:** the difference between return values, errors, side effects, ownership, cancellation and persistence.
- **Internal comments:** structure that is not local, invariants, races, unexpected failures. Not a line-by-line paraphrase of the code.
- **Tests:** only what is not obvious: an indirect observation, a platform difference, why a fixture or entry point was chosen. Not a restatement of the assertion.
- **Call sites** keep the full local contract; long derivations and history link to their home.

A fixed regression is described as a present-tense condition, "without the end-marker check, a truncated shard is counted as complete", not as a story of the fix.

## Session residue

Agents leave traces of how a text was produced. The test for each reference: can a reader who has only this checkout, and no chat, no pull request discussion and no unmerged draft, resolve it and verify the fact? If not, restate the fact the reference stood for, then remove the reference. A sentence that only narrates the process, with no fact in it, is deleted.

Look for:

- worker ids, round numbers, brief and review names, ledger entries, session ids
- design numbers and phase labels from documents that are not in the repository
- the perspective of a pull request or a previous commit: "now", "no longer", "this change", "used to"
- a running history of old and new behaviour in a current document
- who agreed to what in review, and arguments addressed to a reviewer
- line-by-line translations of code
- plans and guesses left over after the work was done
- slips of the authoring language: a sentence half in another language, a term from the chat that the repository never defines

Keep:

- an issue or ticket reference with a resolvable target, and the reason a warning is suppressed
- a real compatibility contract between an old and a new format
- standard sections of notes and postmortems, incident timelines, the alternatives of a decision, limits with evidence

`repo_check.py --only residue` finds references to specific work records and worker ids next to round, brief, review, verdict or ruling, and flags common review phrases as warnings. A probe is only a starting point: words such as "decision", "reviewer", "previously" and "no longer" find candidates, and an empty result does not mean the text is clean. Read the densest comments, READMEs and notes in scope.

## Calibration

| Text | Judgement |
| --- | --- |
| A comment "loop over the list and remove the item" above code that says exactly that | Delete it |
| "Stop accepting work, wait for in-flight calls, then close the client" | Keep the order and the completion condition; never compress it to "cancel on close" |
| "Decided in review not to retry" | State the reason that holds now: "retrying after an unknown result can submit twice"; a longer reason goes into a note |
| "Per decision 7, finished in the next PR" | Find a committed source; without one, keep the exact current fact and move the unfinished work to a tracked item |
| "No write happened; that does not mean there were no side effects before the failure" | Keep it: it is a failure guarantee, not noise |
| "Compatible with format v2; unknown fields are ignored" | Keep it: a real compatibility contract |
| "This version finally fixes the bug" | Replace with the current condition and behaviour; evidence goes to a postmortem |
| "May reject" shortened to "returns" | Reject the edit: it changes the obligation and the failure |
| Redundant text in a generated file | Change the template or source and regenerate |
| A user-facing prompt reworded for style | A behaviour change: check the scenarios and snapshots, or defer it |

## Terms

Use the standard term of the field. Name the subject, the action, the condition and the result directly. Avoid metaphors and invented labels for things the field already names. Keep terms stable across the repository; a reviewer treats a new name for an existing thing as a defect.

After the edit, rerun the probes, check the links, and read the whole diff. Report what was kept and what was deferred.
