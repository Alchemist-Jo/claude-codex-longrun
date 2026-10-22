# Observable workflow cases

These cases guide review of the skill in use. They are not a scoring rubric, and no case is recorded as executed without its state file, ledger lines and run directories.

## Run layer

- Routing a mixed request: a question answered from one file stays in the main session; a search across the code base goes to a read-only search agent; a code change goes to Codex with an explicit effort; nothing irreversible leaves the main session.
- Two changes that touch one file: `work_state.py --dispatch` fails for the second, and the main session sequences them or writes one combined brief. No conflict is resolved by hand.
- Two paid runs that need one port: the second is refused at dispatch until the first ends or uses another port, which its configuration also sets.
- A Codex job of two hours: the job is detached with a pid file and an exit-status file; the main session holds the wait; the watcher is dispatched only for collection; a wait stopped at a time limit leads to a re-check, not a report.
- A watcher session that ends early: a new watcher with the same runbook starts from the files and produces the same receipt.
- A subagent blocked by a permission prompt: it stops on the first prompt; the main session runs the step, asks the user, or adds a narrow rule.
- A round that changed a file outside its write set: the file is in `outside.txt`, the checks in `tests.log` ran without it, and the reviewer requests the revert.
- A review that keeps failing: round 2 resumes the same session and Codex answers each requested change; from round 3 the main session rereads the failing criteria before choosing the next step; after round 5 a ruling is recorded.
- Recovery after a compaction: the session-start hook prints the bearings, or the main session runs them; running workers are reconciled with their exit-status files; nothing is reported from memory.
- A paid run: a launch record exists before the launch; the kill, if any, targets the recorded process group after comparing its command lines and ends with an empty group; the receipt's numbers each name a file and line.
- A report: every number in both versions appears in the checklist, and the main session opened each source before sending.
- A Gemini run whose tool call is denied: `gemini_run.py` exits 3, `tools.jsonl` names the call, and the main session widens the grants or changes the brief before relaunching; the run is not reported as done.
- A Gemini launch after the CLI updated itself: `gemini_run.py` and `work_state.py --dispatch` refuse with a stale preflight record; the main session runs the preflight before any launch.
- A Gemini research answer: every claim carries a file line or a URL with a quote; the main session opens a sample of the sources before using the answer, and drops claims whose quote is missing.
- A Gemini documentation round: Gemini edits in its own worktree and does not commit; `collect_round.py` makes the round commit; an edit outside the write set is in `outside.txt`; round 2 resumes the same conversation with the grants passed again.

## Repository layer

- Adopting a project with a CLAUDE.md and a pre-commit setup: shared rules move to AGENTS.md, CLAUDE.md starts with `@AGENTS.md`, the existing hooks gain the two local hooks and `pre-merge-commit`, and the adoption report lists checks that failed before adoption.
- A brief for a package with its own AGENTS.md: `--context` lists the file, the brief names it under Standing rules, and the reviewer checks the change against it.
- A behaviour change: the module README and interface comments change in the same round; documents outside the write set are listed as docs impact and changed at close-out.
- A ruling that will be proposed again later: it becomes a note at close-out with the advisor's options as alternatives, and the ledger line stays as the record of when it was made.
- Two close-outs that both edit the root README: the second is refused at dispatch until the first is merged.
- A comment saying "fixed in w12 round 2": `repo_check.py` reports it, and the comment is replaced by the condition it stood for.
- An archived note edited in a pull request: the archive check in CI fails against the pull request base.

The example project is exercised by the unit tests, the state check and the repository check. Those checks do not establish that a real project ran under the skill.
