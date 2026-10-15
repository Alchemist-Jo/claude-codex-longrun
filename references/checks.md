# Checks, hooks and CI

Read when setting up or changing the checks of a project, when a hook or CI fails, and when deciding what a passing check proves.

## The registry

`.agents/checks.json` lists every check once, in order:

~~~json
{
  "checks": [
    {"id": "repo", "command": ["python3", ".agents/bin/repo_check.py"], "modes": ["commit", "ci"]},
    {"id": "tests", "command": ["python3", "-m", "pytest", "-q"], "modes": ["test", "ci"], "timeout": 1800}
  ]
}
~~~

| Field | Meaning |
| --- | --- |
| `id` | Unique name, used by `--only` and in briefs |
| `command` | An argument array, run from the repository root without a shell |
| `modes` | `commit`, `test`, `ci`, or another name the project uses |
| `needs` | Earlier checks that must pass first; if one fails, this check is skipped and counts as failed |
| `timeout` | Seconds, default 600; on expiry the check's whole process group is terminated |

`python3 .agents/bin/run_checks.py --mode ci` runs the selected checks in order and prints each one's full output under a header, then a summary. Redirected to a file, the output is the evidence a reviewer reads. It exits 0 only when every selected check passed. `--only ID` runs one check and its needs; `--list` shows the selection without running it.

A check that selected no tests is not evidence. When a test command filters by name, the log must show how many tests ran. A new check needs a case that should fail and does: introduce the violation once, see the non-zero exit, remove it.

## Repository checks

`.agents/bin/repo_check.py` reads files and git only:

| Check | Error | Warning |
| --- | --- | --- |
| `links` | A local Markdown link to a missing file or outside the repository; a link starting with `/` is read from the root; work records and the archive are skipped | |
| `instructions` | An AGENTS.md chain over 32768 bytes | An instruction file over 200 lines; a CLAUDE.md beside an AGENTS.md without the line `@AGENTS.md`; a CLAUDE.md symlink |
| `notes` | A note with the wrong path, name, header, status or sections | |
| `archive` | An archived note modified, renamed or deleted relative to `--base`, default `HEAD` | |
| `residue` | A citation of a specific brief, review, run, advice or report under `.agents/work/`; a worker id next to round, brief, review, verdict or ruling | A common review phrase such as "review round 2" |

The residue check reads files outside `.agents/` and outside directories that start with a dot. It takes worker ids from `.agents/work/state.json`, so a variable named like a worker, such as `w1`, is only reported next to one of those words.

## Where each check runs

| Place | Command | Sees |
| --- | --- | --- |
| Pipeline, every round | `collect_round.py`, which runs `run_checks.py --mode ci` or the mode the brief names | The round commit, with changes outside the write set set aside |
| pre-commit and pre-merge-commit hooks | `run_checks.py --mode commit` | The working tree. The pre-commit framework sets unstaged changes to tracked files aside while hooks run; untracked files stay, and `repo_check.py` reads them too |
| pre-push hook | `run_checks.py --mode ci` | The working tree |
| CI | `run_checks.py --mode ci`, then `repo_check.py --only archive --base <base>` | The pushed commit; the base is the pull request base or the previous push |

Facts measured with git 2.x on 2026-10-15 that shape this table:

- A merge commit created by `git merge` runs `pre-merge-commit` and `commit-msg`, never `pre-commit`. A squash merge followed by `git commit` runs `pre-commit`. A fast-forward merge runs no hook. Install both hook types and merge workers with `git merge --no-ff`, or merges skip the checks.
- Commits in a linked worktree run the hooks of the main repository. The pipeline's round commits use `--no-verify` because they are snapshots for review; the pipeline runs the checks itself afterwards.
- `git stash` keeps one stack for all worktrees of a repository. Two pipelines that stash at the same time can pop each other's changes, which is why `collect_round.py` sets outside changes aside as a patch and a tar file in its own run directory.
- A subagent's working directory is reset between Bash calls, so a `cd` in one call does not carry into the next. The collection is therefore one script with absolute paths.

Hooks are cheap and decisive: they run the `commit` mode, which takes seconds. Full suites and platform matrices belong to the pipeline, pre-push and CI.

## CI

Add the steps of [github-checks.yml](../assets/project/github-checks.yml) to the project's workflow. It checks out the full history so the archive check can compare with the base. It checks and tests only. A workflow file shows that CI can run the checks; whether a failing check blocks a merge is a branch protection setting of the hosting platform, which the adoption report states separately. A passing CI run also does not prove what it did not run: product tests, type checks and builds are covered only when they are in the registry.

## Session-start hook

Claude Code runs a `SessionStart` hook at startup, on resume and after a compaction, and adds its output to the main session's context. With [claude-settings.json](../assets/project/claude-settings.json) merged into `.claude/settings.json`, the hook runs `work_state.py --bearings`: git status, worktrees, recent commits, the worker table, the liveness check and the last ledger lines. It exits 0 even when the state has errors, and prints nothing when the project has no state file.

In a test with Claude Code 2.1.284, the matcher `startup|resume|compact` fired for all three events, and the output reached the main session but not its subagents. The bearings in the context are a starting point; the main session still reconciles running jobs with their exit-status files before acting.

## What checks do not do

A check proves the property it tests on the content it saw. Link checks do not prove a document is correct, the notes check does not judge whether a decision is worth recording, and the residue check does not find every trace of a session. When a static check cannot interpret a dynamic case correctly, narrow what it claims or remove it rather than adding permanent exceptions.
