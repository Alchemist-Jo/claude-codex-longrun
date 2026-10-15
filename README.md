# claude-codex-longrun

**English** | [简体中文](README.zh-CN.md)

[![v2.0](https://img.shields.io/badge/version-v2.0-315a66?style=flat-square)](SKILL.md) [![MIT](https://img.shields.io/badge/license-MIT-647467?style=flat-square)](LICENSE)

An agent skill for running a long project through several agents at once: a main Claude session that decides, Claude subagents that execute, Codex CLI that writes the code, and a read-only Codex advisor for questions of direction. It has two layers that share one set of files.

- **The run layer** routes each piece of work and keeps the collaboration stable when jobs outlive the agents that started them, when context is compacted, when subagents hit permission prompts, and when two writers reach for the same file.
- **The repository layer** keeps what outlasts a session in known places: short AGENTS.md files that Codex and Claude Code both load, decision notes with a lifecycle, documentation that changes with the code, and one list of checks used by the pipeline, git hooks, CI and a session-start hook.

It needs no daemon, framework or database. State and records live under `.agents/` in the project, jobs are ordinary processes started by `detach.sh` and observed by `wait.sh`, and four standard-library Python scripts check the state, collect each round, run the project's checks and check the repository.

## Project layout

~~~text
AGENTS.md                 standing rules and a map, about 100 lines
<area>/AGENTS.md          only where an area has rules of its own
docs/                     current documentation
.agents/
  checks.json             every check, one list
  bin/                    detach.sh, wait.sh, work_state.py, collect_round.py,
                          run_checks.py, repo_check.py
  notes/                  decision notes: proposed, implemented, rejected, archived
  work/                   state.json, ledger.md, briefs, reviews, advice, reports, runs
~~~

The places differ by lifetime. AGENTS.md holds what every task needs, `docs/` and `.agents/notes/` hold what stays true across cycles, and `.agents/work/` holds what happened in one cycle. Work records reach notes and documents only at close-out, and code and documents never cite them.

## What the agent does

[SKILL.md](SKILL.md) is a guide for the main session:

1. **Adopt.** Bring a project into the layout without overwriting its rules, hooks or CI: merge AGENTS.md, keep CLAUDE.md as an import of it, list the real checks, add the hooks and CI steps that are missing.
2. **Route.** A table sends each piece of work to the main session, a read-only search agent, Codex at `high` or `xhigh` effort, a reviewer, a watcher, a pipeline runner, a reporter, the advisor, or the user. Launches, kills, merges, pushes and deletions never leave the main session, and merges and pushes wait for the user's approval.
3. **Dispatch with a contract.** Codex gets a brief with a write set, the nested AGENTS.md files it would not load on its own, acceptance commands and a docs-impact field. Subagents get runbooks with an output directory, forbidden actions and stop conditions.
4. **Keep one writer per file and one holder per resource.** `work_state.py --dispatch` refuses a worker whose write set, port or GPU host overlaps one that is held.
5. **Detach jobs from waits.** `detach.sh` starts jobs in their own session with stdin closed, a pid file and an exit-status file. Completion is the exit-status file, never the end of a wait.
6. **Review the commit, not the worktree.** Codex never commits. After each round a pipeline subagent runs `collect_round.py`, which commits the write set, sets everything else aside, runs the checks on that commit alone, and restores the rest. A reviewer who did not write the code checks the diffs against the brief, and also checks documentation, session residue and note candidates. Review is capped at 5 rounds.
7. **Close out.** Rulings that will guide later work become decision notes, and shared documents are updated by one writer at a time, before the freeze tag.
8. **Recover from files.** A session-start hook prints the bearings after startup, resume and compaction: git status, workers, liveness, ledger tail.
9. **Report checked numbers.** Reports come in a precise and a plain version with a checklist tying every number to a source file.

## Why these rules

Each rule answers a failure seen in real runs, documented upstream, or measured while building the skill:

| Failure | Rule |
| --- | --- |
| A background command started by a subagent is killed when the subagent ends its turn ([claude-code#83627](https://github.com/anthropics/claude-code/issues/83627); not reproduced on 2.1.284 in an interactive session) | Jobs are detached; subagents wait in the foreground only |
| Background commands are stopped at a time limit ([#98273](https://github.com/anthropics/claude-code/issues/98273), [#100648](https://github.com/anthropics/claude-code/issues/100648)) | Long waits sit in the main session; a stopped wait means re-check |
| `codex exec` hangs with no output when a harness leaves stdin open | `detach.sh` closes stdin for every job |
| A user configuration defaults Codex to maximum effort and full access | Sandbox and effort are set on every call |
| Parallel Codex runs conflict on one file; two runs on one host collide on a port | Write sets and resources are checked before dispatch |
| Killing a wrapper leaves the job's children running | Kills target the job's process group |
| Codex builds its instruction chain from the root to its working directory, so it skips the AGENTS.md of the package it edits (measured) | Briefs list those files, from `work_state.py --context` |
| Claude Code skips AGENTS.md wherever a CLAUDE.md exists ([docs](https://code.claude.com/docs/en/memory)) | AGENTS.md is the only source; CLAUDE.md imports it |
| A test run in the worktree passed because of a change outside the write set that the round commit did not contain (measured) | Checks run on the round commit with outside changes set aside |
| All worktrees share one `git stash` stack (measured); a subagent's working directory is reset between commands | The collection is one script with absolute paths that sets changes aside as files in its own run directory |
| A merge commit runs `pre-merge-commit`, never `pre-commit`, and a fast-forward runs no hook (measured) | Hooks install both types; workers merge with `--no-ff` |
| Two parallel changes that update one long-lived document overwrite each other ([OpenSpec](https://github.com/Fission-AI/OpenSpec)) | Close-outs that edit a shared document run one at a time |
| Multi-round edits leave "fixed in round 2" and review references in code and docs | `repo_check.py` reports work-record citations; the reviewer applies the residue rules |
| Subagents are blocked by permission prompts | Narrow allow rules for the scripts and read-only commands; irreversible steps stay with the main session |

## Install and use

~~~sh
npx skills add Alchemist-Jo/claude-codex-longrun --skill claude-codex-longrun -g
~~~

Or clone it into the skills directory of Claude Code or Codex:

~~~sh
git clone https://github.com/Alchemist-Jo/claude-codex-longrun ~/.claude/skills/claude-codex-longrun
~~~

~~~text
Use $claude-codex-longrun to adopt this repository: keep my existing rules and
CI, add the .agents layout, and tell me which checks fail today.
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
python3 scripts/work_state.py examples/project/.agents/work/state.json --summary
python3 scripts/repo_check.py examples/project
for f in scripts/*.sh; do sh -n "$f"; done
python3 -m unittest discover -s tests -v
~~~

The [example](examples/README.md) is a project caught mid-cycle, with one planned worker that overlaps a held file, nested rules for one package, and two proposed notes.

## Sources and license

The run layer adapts ideas from [obra/superpowers](https://github.com/obra/superpowers), [openai/codex-plugin-cc](https://github.com/openai/codex-plugin-cc), [github/spec-kit](https://github.com/github/spec-kit), [automazeio/ccpm](https://github.com/automazeio/ccpm), [stellarlinkco/myclaude](https://github.com/stellarlinkco/myclaude), [humanlayer/humanlayer](https://github.com/humanlayer/humanlayer), [skills-directory/skill-codex](https://github.com/skills-directory/skill-codex) and two Anthropic engineering articles. The repository layer adapts rules from [deepseek-ai/deepseek-harness](https://github.com/deepseek-ai/deepseek-harness), through the portable selection in [WncFht/agent-maintenance](https://github.com/WncFht/agent-maintenance), both MIT. No code was copied; rules were restated in English. See [method basis](references/basis.md), [third-party notices](THIRD_PARTY_NOTICES.md) and [LICENSE](LICENSE).
