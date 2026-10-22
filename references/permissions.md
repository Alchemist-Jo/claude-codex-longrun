# Permissions

Read when a subagent is blocked by a permission prompt, when setting up a project to reduce prompts, or when deciding what a Gemini run may do.

## What blocks and what to do

Subagents meet the permission system more often than the main session, and every block costs a round trip through the user. A blocked subagent stops on the first prompt and reports it. The main session then does one of three things:

- runs the step itself, when the step belongs to the main session anyway: paid launches, kills, merges, pushes, deletions
- asks the user, when the step is new
- adds a narrow rule, when the same read-only step will recur

## Settings example

Add the worktree root as a working directory with `/add-dir ../wt` or the `--add-dir` flag, so that read-only commands there, such as `cat`, `tail`, `ls` and the read-only forms of `git`, run without a prompt. Then allow the exact forms the runbooks use. In `.claude/settings.json` of the project, with the real paths:

~~~json
{
  "permissions": {
    "allow": [
      "Bash(.agents/bin/wait.sh *)",
      "Bash(python3 .agents/bin/work_state.py *)",
      "Bash(python3 .agents/bin/run_checks.py *)",
      "Bash(python3 .agents/bin/repo_check.py *)",
      "Bash(/abs/repo/.agents/bin/detach.sh /abs/repo/.agents/work/runs/*/collection -- python3 /abs/repo/.agents/bin/collect_round.py *)",
      "Bash(/abs/repo/.agents/bin/wait.sh *)",
      "Bash(ssh gpu-host /work/proj/.agents/bin/wait.sh *)",
      "Bash(ssh gpu-host cat *)",
      "Bash(ssh gpu-host tail *)",
      "Bash(ssh gpu-host nvidia-smi *)",
      "Bash(git worktree add *)",
      "Bash(git tag freeze/*)",
      "Edit(.agents/work/runs/**)",
      "Edit(.agents/work/reviews/**)",
      "Edit(.agents/work/reports/**)"
    ],
    "ask": [
      "Bash(ssh gpu-host kill *)",
      "Bash(ssh gpu-host pkill *)",
      "Bash(git push *)",
      "Bash(git merge *)"
    ],
    "deny": [
      "Read(.env)",
      "Read(.env.*)"
    ]
  }
}
~~~

`wait.sh`, `work_state.py` and `repo_check.py` only read, and `run_checks.py` and `collect_round.py` run the checks the project already declared, so allowing them costs little. Subagents use absolute paths, because their working directory is reset between commands; write the rules with the real repository path in place of `/abs/repo`. The `git` rules cover the worktree preparation and the freeze tag. The `Edit` rules cover the output files subagents write by redirection. A step that still prompts on the first run shows the exact form to add.

Rules are evaluated deny first, then ask, then allow, so an ask rule prompts even when a broader allow rule also matches. A trailing ` *` matches the bare command too. Compound commands are split at `&&`, `||`, `;` and `|`, and each part must match on its own. Allow rules in a project's `.claude/settings.json` apply only after the workspace trust dialog has been accepted.

A broad rule such as `Bash(ssh gpu-host *)` removes the most prompts, and it also lets any agent launch or kill on that host without a prompt. Use it when the operator accepts that. Otherwise keep the narrow forms above and leave launches with the main session.

## What rules do not do

Permission rules match the command as an agent usually writes it. A command routed through `sh -c`, a different path or a quoted remote string is not matched the same way. The rules keep accidents rare among cooperating agents. The runbook's forbidden actions remain the rule the agents follow.

Launches through `detach.sh` and `gemini_run.py` are not in the allow list. They are the main session's, they are infrequent, and `detach.sh` runs whatever follows `--`, so a prompt for each launch costs little and keeps the user aware of what starts. The sandbox flag in a Codex command decides what Codex may write; the policy below decides what Gemini may do.

## Gemini tool policy

agy cannot show a permission prompt in a headless run. It denies the call, still reports status `SUCCESS` and exits 0, and a hook decision of `allow` does not lift that denial. `gemini_run.py` therefore runs agy with `--dangerously-skip-permissions` and moves every decision into the PreToolUse hook in `.agents/hooks.json`, which reads the run's `policy.json`:

| Tool | Allowed when |
| --- | --- |
| `read_file` | the path lies inside the working directory or a `--read` directory |
| `write_file`, `edit_file` | the path is a `--write` file or lies inside a `--write` directory |
| `run_command` | one listed program with quoted arguments, without pipes, redirections, variables, substitutions, braces or unquoted globs; no option that runs a program, writes a file, follows links or searches hidden or ignored files; every argument that names an existing path lies inside the read roots |
| `search_web` | the run has `--web` |
| `manage_task` | the action is `list` or `status` |
| any other tool, including `ask_question` and the subagent tools | never |

A path named `.env` or `.env.*`, or a link to one, is denied as a file tool path and as a command argument; file contents and search patterns are not checked. The listed commands are `ls`, `cat`, `head`, `tail`, `wc`, `pwd`, `rg`, `grep` without recursion, `find` without `-exec`, `-delete` or `-L`, and the `git` subcommands `status`, `diff`, `log`, `show`, `ls-files`, `grep`, `rev-parse` and `blame` without `--open-files-in-pager`, `--ext-diff`, `--output` or `--no-index`, plus each `--command`. `rg` searches recursively and skips hidden and ignored files, which keeps `.env` files out of recursive searches. agy's `--sandbox` makes every command read-only, so a granted build command cannot write either, and it limits command reads to the working directory, system files and the temporary directory. Files in a `--read` directory are therefore read with the file tool. Writes go through the file tools and the write set.

Grant per task what the brief needs and no more. A denied call ends the run with exit status 3. The main session reads `tools.jsonl`, then either grants the missing access in a new run or rules that the answer stands without it.

The hook prints nothing when `LONGRUN_GEMINI_POLICY` is unset, so interactive agy sessions in the project keep agy's own permission flow. A hook that crashes or times out blocks the call. The launcher creates `tools.jsonl` before agy starts; a hook that cannot append to it denies the call and writes `hook-error`, and the run fails. A `hooks.json` that agy cannot parse is skipped with only a log warning, so the launcher requires the `hook-started` file, to which the hook's PreInvocation handler adds a line before each model call. SessionStart cannot serve: it does not fire when a run resumes a conversation.
