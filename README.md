# claude-codex-longrun

**English** | [简体中文](README.zh-CN.md)

[![v1.0](https://img.shields.io/badge/version-v1.0-315a66?style=flat-square)](SKILL.md) [![MIT](https://img.shields.io/badge/license-MIT-647467?style=flat-square)](LICENSE)

An agent skill for running a long project through several agents at once: a main Claude session that decides, Claude subagents that execute, Codex CLI that writes the code, and a read-only Codex advisor for questions of direction. The skill routes each piece of work to one of them and keeps the collaboration stable when jobs outlive the agents that started them, when context is compacted, when subagents hit permission prompts, and when two writers reach for the same file.

It needs no daemon, framework or database. State lives in a few files under `harness/`, jobs are ordinary processes started by `scripts/detach.sh` and observed by `scripts/wait.sh`, two short POSIX scripts, and a standard-library Python script checks the state.

## What the agent does

[SKILL.md](SKILL.md) is a guide for the main session:

1. **Route.** A table sends each piece of work to the main session, a read-only search agent, Codex at `high` or `xhigh` effort, a reviewer, a watcher, a pipeline runner, a reporter, the advisor, or the user. Codex launches, paid launches, kills, merges, pushes and deletions never leave the main session, and merges and pushes wait for the user's approval.
2. **Dispatch with a contract.** Codex gets a brief with a write set and acceptance commands. Subagents get a runbook with an output directory, forbidden actions and stop conditions. Every worker returns `DONE`, `DONE_WITH_CONCERNS`, `BLOCKED` or `NEEDS_CONTEXT`, and reports anomalies as Expected, Found, Why it matters.
3. **Keep one writer per file.** `scripts/harness_state.py --dispatch` refuses a worker whose write set overlaps a worker that holds those files. Overlapping work runs in sequence or as one combined brief.
4. **Detach jobs from waits.** `detach.sh` starts Codex jobs, advisor questions and paid runs in their own session with stdin closed, a pid file and an exit-status file. Waits use `wait.sh`, which only observes, so they can be lost and restarted. Completion is the exit-status file, never the end of a wait. A kill terminates the job's process group, and the exit-status file records it.
5. **Recover from files.** After a compaction or a new session, a bearings check reads git, the state file, the ledger and the run directories before anything else happens.
6. **Review before anything counts.** Codex never commits. After each round a pipeline subagent commits the write set as that round's commit, lists anything outside it, and writes the diff from the base and the diff for the round. A reviewer who did not write the code checks them against the brief. Review is capped at 5 rounds. From round 3 the main session rereads the failing criteria before choosing to rewrite the brief, raise the effort or start a fresh session, and after round 5 it records a ruling.
7. **Report checked numbers.** Reports come in a precise and a plain version with a checklist that ties every number to a source file the main session opened.

## Why these stability rules

Each rule answers a failure seen in real runs or documented upstream:

| Failure | Rule |
| --- | --- |
| A background command started by a subagent is killed when the subagent ends its turn ([claude-code#83627](https://github.com/anthropics/claude-code/issues/83627); not reproduced on 2.1.284 in an interactive session) | Jobs are detached; subagents wait in the foreground only |
| Background commands are stopped at a time limit ([#98273](https://github.com/anthropics/claude-code/issues/98273), [#100648](https://github.com/anthropics/claude-code/issues/100648)) | Long waits sit in the main session; a stopped wait means re-check |
| `codex exec` hangs with no output when a harness leaves stdin open | `detach.sh` closes stdin for every job |
| `codex mcp-server` was removed | The skill uses `codex exec` directly |
| A user configuration defaults Codex to maximum effort and full access | Sandbox and effort are set on every call |
| Parallel Codex runs conflict on one file | Write sets are checked before dispatch |
| Killing a wrapper leaves the job's children running | Kills target the job's process group |
| Subagents are blocked by permission prompts | Narrow allow rules for read-only commands; irreversible steps stay with the main session |

## Install and use

~~~sh
npx skills add Alchemist-Jo/claude-codex-longrun --skill claude-codex-longrun -g
~~~

Or clone it into the skills directory of Claude Code or Codex:

~~~sh
git clone https://github.com/Alchemist-Jo/claude-codex-longrun ~/.claude/skills/claude-codex-longrun
~~~

~~~text
Use $claude-codex-longrun to split this refactor between Codex and subagents.
Codex writes the code, a subagent reviews each change against its brief.
~~~

~~~text
Use $claude-codex-longrun to recover the project state after the compaction,
then tell me which workers are still running and what waits for me.
~~~

## Checks

~~~sh
python3 scripts/check_skill.py
python3 scripts/harness_state.py examples/harness/state.json --summary
for f in scripts/*.sh; do sh -n "$f"; done
python3 -m unittest discover -s tests -v
~~~

The [example](examples/README.md) is a harness directory caught mid-project, with one planned worker that overlaps a held file. The state check warns about it, and `--dispatch` on that worker fails.

## Sources and license

The routing and stability rules adapt ideas from [obra/superpowers](https://github.com/obra/superpowers), [openai/codex-plugin-cc](https://github.com/openai/codex-plugin-cc), [github/spec-kit](https://github.com/github/spec-kit), [automazeio/ccpm](https://github.com/automazeio/ccpm), [stellarlinkco/myclaude](https://github.com/stellarlinkco/myclaude), [humanlayer/humanlayer](https://github.com/humanlayer/humanlayer), [skills-directory/skill-codex](https://github.com/skills-directory/skill-codex) and two Anthropic engineering articles on multi-agent systems and long-running harnesses. No code was copied. See [method basis](references/basis.md), [third-party notices](THIRD_PARTY_NOTICES.md) and [LICENSE](LICENSE).
