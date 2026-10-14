# Routing detail

Read when a piece of work does not fit one row of the routing table, when work has to be split or combined, or when a route keeps failing.

## What a hand-off costs

Each hand-off transfers context in writing, adds a process that can fail, and adds a report the main session has to read. Multi-agent runs also spend several times the tokens of a single agent. Delegate when at least one of these holds:

- the work would pull many files or long logs into the main context, and only a conclusion is needed back
- the work writes code, which needs its own worktree and a reviewer who did not write it
- the work is a wait or a fixed sequence whose steps the main session would only watch
- an independent reading is the point, as in review or a directional question

Do it directly when the answer is one file read or one command away, when the edit is small and no worker holds the file, or when the output of the next command decides the route.

## Effort for Codex

| Effort | When |
| --- | --- |
| `medium` | A mechanical edit whose correctness the tests settle completely |
| `high` | The default for code |
| `xhigh` | A public interface, a file or data format, a protocol, an evaluation definition, ordering or concurrency, or a review round 3 escalation |
| maximum (`ultra` where the model offers it) | The read-only advisor only |

Set the effort on every call with `-c model_reasoning_effort="high"`. Do not rely on the user's configuration, which may default to the maximum.

## Splitting

A code brief should take Codex about 1 to 5 hours. Split larger work along write sets, so the parts can run in parallel or at least be reviewed apart:

1. List the files each part must change.
2. Parts whose write sets are disjoint and that do not depend on each other can run in parallel.
3. A part that depends on another's interface waits for that part's `ACCEPT`, and its brief names the accepted commit as its base.
4. Shared definitions, such as types, schemas or configuration read by several parts, belong to one part only. The others read them.

## Combining

When two planned briefs need the same file, merge them into one brief with the union of their write sets and acceptance items. Mark the originals `abandoned` in the state file with a ledger line that names the combined worker. One run on a combined brief costs less than resolving a merge conflict after two runs.

## Escalation ladder

| Signal | Next step |
| --- | --- |
| Codex run exits early or times out | Resume the session once with the failure and the log tail |
| Second failure on the same brief | Main session rereads the brief: missing context, an untestable criterion, a write set too small |
| Review round 3 on the same brief | Rewrite the criterion, raise the effort to `xhigh`, or start a fresh Codex session |
| Review round 5 still open | Main session rules: accept with a recorded limitation, park the item, or rescope |
| The same question of direction keeps reappearing in reviews | Take it to the advisor |

Do not escalate by switching the code writer to a Claude subagent. A failed Codex run is reported and its brief repaired.

## Routes that look right and are not

- A subagent that monitors another subagent. Subagents do not start or supervise agents. Waits belong to the main session or to one watcher.
- A reviewer that also fixes. A fix becomes the next Codex round, so the change keeps a single writer.
- Parallel Codex runs on one worktree. Each writer gets its own worktree, even when the write sets are disjoint.
- The advisor asked to choose between two implementations that a test could separate. Write the test instead.
