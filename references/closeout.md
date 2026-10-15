# Close-out

Read after the main session has agreed with an `ACCEPT` and before the freeze.

A cycle produces rulings, advisor answers and review findings that live in `.agents/work/`. Close-out decides which of them must outlast the cycle and puts them where the next reader will look: a decision note or a document. It also makes the changes to shared documents that the worker could not make, because they were outside its write set.

## What goes into the close-out

The main session reads the worker's final messages, the verdicts and the ledger lines of the worker's lineage, and lists:

| Item | Becomes | Example |
| --- | --- | --- |
| A ruling whose reason will guide later work: an ownership, a format, a guarantee, an alternative that will be proposed again | A new note, or an edit of the note on the same decision | "Shard resumption stays generic in the runner" |
| A ruling that reverses an earlier decision | A new note linked both ways to the old one | |
| Docs impact the worker reported, in files outside its write set | An edit of that document | The root README's usage section |
| A finding outside the brief that the main session wants kept | A ledger line as a candidate, or a proposed note | |

Mechanical rulings, such as which round to resume, stay in the ledger. When the list is empty, skip to the freeze.

## Steps

1. Add a worker in the same lineage, such as `w12.1` with `parent` set to `w12`. It uses w12's worktree, its `base` is `worker/w12@<accepted commit>`, and its write set is the notes and documents on the list. Its route is `codex` when Codex writes the documents and `main` when the main session makes every edit itself. Run `--dispatch` for it. A conflict means another close-out holds the same document; wait until that one is merged.
2. When another close-out of a shared document was merged after this worker's base, the main session first merges the default branch into the worker branch, so the edit starts from the merged text, and records that merge commit as the close-out's base.
3. Write the changes in the worktree, with a new run directory such as `.agents/work/runs/w12.1-r1/`:
   - Notes are the main session's. A reporter subagent may draft one from a facts sheet into its own output, using [the note templates](../assets/templates/note-implemented.md); the main session edits it and places it. Follow [notes](notes.md).
   - Document edits that follow from the code go to the same Codex session as one more round, with the items in `round.md`.
   - When the main session made every edit itself, it writes `0` to the run directory's `exit-status` once it is done, so the collection treats the round like any other.
4. The pipeline collects the close-out round like any other round, with the accepted commit as `--parent`: round commit, diffs, checks in `ci` mode with outside changes set aside.
5. The reviewer reads `fix.patch` for the close-out with the [documentation](documentation.md) and [prose](prose.md) rules: each fact in its home, no session residue, notes with real alternatives.
6. On `ACCEPT`, the freeze tags the close-out's round commit, and the ledger records it.

Two close-outs that edit the same shared document run one after the other, each starting from the merged result of the previous one. Two finished edits of the same section conflict at the merge, or one silently replaces the other when a tool rewrites whole blocks.

## What does not belong

- A summary of the cycle in a document. The ledger and the run directories hold the history.
- A note for a mechanical change, a rename or a formatting change.
- Plans for later work in an implemented note. They go into a proposed note or the ledger.
