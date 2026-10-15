# Permissions

Read when a subagent is blocked by a permission prompt, or when setting up a project to reduce prompts.

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

Launches through `detach.sh` are not in the allow list. They are the main session's, they are infrequent, and `detach.sh` runs whatever follows `--`, so a prompt for each launch costs little and keeps the user aware of what starts. The sandbox flag in a Codex command decides what Codex may write.
