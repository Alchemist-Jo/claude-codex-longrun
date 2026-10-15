# Decision notes

Read when a ruling should outlast the cycle, when writing, merging or archiving a note, and when reviewing a close-out.

A note keeps what the code, the tests and the documents cannot: why a decision was made, which alternatives were really considered and why they lost, what it costs, and how it was verified. The ledger records that a ruling happened; a note records the reasoning a later reader needs to keep or change it.

## When to write one

Write a note for a decision that will guide later work: an ownership, a data or file format, an evaluation definition, a guarantee or a deliberate non-guarantee, a compatibility promise, a security or persistence rule, an experiment protocol, or a rejected alternative that someone will propose again. Size is no guide: a two-line patch can carry a lasting decision. Mechanical changes, renames and formatting get no note.

## Path and header

`.agents/notes/<lifecycle>/<class>/YYYY-MM-DD-topic.md`, dated when the decision was first proposed, with a lowercase topic joined by hyphens. The directories are the index; there is no central list.

| Lifecycle | Meaning |
| --- | --- |
| `proposed` | Not implemented yet |
| `implemented` | The current decision |
| `rejected` | Considered and declined |
| `archived` | Implemented, no longer guiding, kept for history |

| Class | For |
| --- | --- |
| `feature` | A capability added or removed |
| `bug-fix` | A fix whose reason is not obvious from the code |
| `simplification` | A removal or merge, with what was given up |
| `architecture` | The structure of the delivered code |
| `process` | How the project works: tooling, review, release |
| `testing` | What is tested and how |
| `experiment` | An experiment protocol, an evaluation definition, a metric, a seed or sampling rule |

The first lines are fixed:

~~~text
# Agent Note: <topic>

Status: implemented
Archived: 2026-11-02          only for archived notes
~~~

## Sections

| Status | Sections, as `## ` headings |
| --- | --- |
| proposed | Problem, Proposal, Alternatives considered, Acceptance, Risks |
| implemented | Problem, Decision, Alternatives considered, Consequences |
| rejected | Problem, Proposal, Alternatives considered, Rejection |

Templates: [proposed](../assets/templates/note-proposed.md) and [implemented](../assets/templates/note-implemented.md). Alternatives are only options that were actually considered: an advisor's answer, a rejected review suggestion, an option a brief tried. A note never invents an alternative to fill the section. A note written before this rule existed records the missing alternatives as unknown.

## Lifecycle

- **Implemented.** Rewrite the proposal in the present tense as the current fact. Proposal becomes Decision. Acceptance becomes the verification that exists and the gaps that remain. Remove plans that already happened. Move the file to `implemented/`.
- **Facts change.** Edit the note in the change that alters them: a path, a default, a mechanism. Do not append a history of edits.
- **Decision reversed.** Write a new note and link the two both ways. The old one is not quietly turned into its opposite.
- **New note on an old subject.** Search the active notes for the same decision first, with `rg <term> .agents/notes`; ripgrep skips hidden directories unless given the path, and `.rgignore` keeps the archive out. A note that fully replaces another may absorb it, keeping every unique reason, alternative, consequence and verification gap, and fixing every link to the old one. A partial replacement keeps both notes active, linked both ways; git history is not the only copy of a reason.
- **Removal of a capability.** The note that added it may absorb the removal only when no production code, configuration, schema, stored data, migration or supported test still promises it. Keep the original motive, the reason for removal, what was given up and the condition for bringing it back.
- **Rejected.** A proposal that will not happen moves to `rejected/` with a Rejection section. Keep a rejected note only when it prevents a plausible mistake from being repeated; otherwise delete it.
- **Archived.** An implemented note whose reasons no longer guide work, but which still has historical value, may be archived: move the file, add the `Archived:` line, fix the links. Ownership, security, persistence, wire formats, negative guarantees and easily repeated mistakes usually still guide work. Proposed notes are never archived.

Age, length, line count and the number of notes are never reasons to delete or archive.

## The frozen archive

Archived notes are never edited, moved, reformatted or deleted. Their facts may be stale by design, and a text search would rank them beside current results, so `.rgignore` excludes the directory. `repo_check.py --only archive` compares the archive with a base commit and accepts only added files: `HEAD` in the commit hook, the pull request base or the previous push in CI. Git already stores every byte, so no hash list is kept.

## Ledger to note

At close-out the main session reads the lineage's ledger lines and verdicts. A ruling line names the decision, the reason and what it costs if wrong; those three become Decision, part of Problem and part of Consequences. The advisor's answer and rejected review requests become Alternatives considered. A note may link to the advisor answer or the verdict in `.agents/work/` as evidence; it still states the reasoning itself, so it reads correctly if the work records are pruned.

## Checks

`repo_check.py --only notes` checks path, file name, header, status and sections. It cannot judge whether a decision is worth a note or whether an alternative was real; the reviewer does.
