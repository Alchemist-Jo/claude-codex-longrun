# Decision notes

A note keeps the reasons that the code, the tests and the documents cannot carry: the decision, the alternatives that were really considered, the cost, and how the decision was verified. One decision has one note. A mechanical change gets no note.

## Where and how

Path: `.agents/notes/<lifecycle>/<class>/YYYY-MM-DD-topic.md`, dated the day the decision was first proposed. The directories are the index; there is no separate list.

- Lifecycle: `proposed`, `implemented`, `rejected`, `archived`.
- Class: `feature`, `bug-fix`, `simplification`, `architecture`, `process`, `testing`, `experiment`.

The first three lines are fixed:

~~~text
# Agent Note: <topic>

Status: <proposed | implemented | rejected>
~~~

Sections, as `## ` headings:

| Lifecycle | Sections |
| --- | --- |
| proposed | Problem, Proposal, Alternatives considered, Acceptance, Risks |
| implemented | Problem, Decision, Alternatives considered, Consequences |
| rejected | Problem, Proposal, Alternatives considered, Rejection |
| archived | As implemented, with `Archived: YYYY-MM-DD` on line 4 |

## Lifecycle

- When a proposal is implemented, rewrite it in the present tense: Proposal becomes Decision, and Acceptance becomes the verification that exists or the gap that remains. Move it to `implemented/`.
- When the facts change, edit the note. When the decision is reversed, write a new note and link the two both ways.
- Before writing a note, search the active notes for the same decision with `rg <term> .agents/notes`; plain `rg` skips hidden directories, and `.rgignore` keeps the archive out. A note that fully replaces another may absorb it, keeping every reason, alternative and verification gap of the old one and fixing the links to it. A partial replacement keeps both notes, linked.
- A proposal that will not happen moves to `rejected/` with a Rejection section. Keep a rejected note only when it stops a plausible mistake from being repeated.
- Archive an implemented note only when its reasons no longer guide future work and it still has historical value. Archiving moves the file, adds the `Archived:` line and fixes the links. Archived notes are never edited afterwards, and searches skip them through `.rgignore`.
- Age, length and count are never reasons to delete or archive.

`python3 .agents/bin/repo_check.py --only notes --only archive` checks the paths, headers, sections and the frozen archive.
