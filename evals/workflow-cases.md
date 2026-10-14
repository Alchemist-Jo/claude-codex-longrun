# Observable workflow cases

These cases guide review of the skill in use. They are not a scoring rubric, and no case is recorded as executed without its state file, ledger lines and run directories.

- Routing a mixed request: a question answered from one file stays in the main session; a search across the code base goes to a read-only search agent; a code change goes to Codex with an explicit effort; nothing irreversible leaves the main session.
- Two changes that touch one file: `harness_state.py --dispatch` fails for the second, and the main session sequences them or writes one combined brief. No conflict is resolved by hand.
- A Codex job of two hours: the job is detached with a pid file and an exit-status file; the main session holds the wait; the watcher is dispatched only for collection; a wait stopped at a time limit leads to a re-check, not a report.
- A watcher session that ends early: a new watcher with the same runbook starts from the files and produces the same receipt.
- A subagent blocked by a permission prompt: it stops on the first prompt; the main session runs the step, asks the user, or adds a narrow read-only rule.
- A review that keeps failing: round 2 resumes the same session; from round 3 the main session rereads the failing criteria before choosing the next step; after round 5 a ruling is recorded.
- Recovery after a compaction: the bearings check runs before any action; running workers are reconciled with their exit-status files; nothing is reported from memory.
- A paid run: a launch record exists before the launch; the kill, if any, targets the recorded process group after comparing its command lines; the receipt's numbers each name a file and line.
- A report: every number in both versions appears in the checklist, and the main session opened each source before sending.

The example harness directory is exercised by the unit tests and the state check. Those checks do not establish that a real project ran under the skill.
