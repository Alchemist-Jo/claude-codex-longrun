# Adopt the layout in a project

Read when a project has no `.agents/` directory yet, when bringing an existing project under this skill, or when updating the scripts in `.agents/bin/` to a newer version of the skill.

`$H` below is this skill's directory, for example `H=~/.claude/skills/longrun`. Adoption changes the project's instructions, hooks and CI, so the main session plans it and the user approves it before it is committed. A large merge of existing rules can go to Codex as a brief whose write set is the files listed in step 3.

## 1. Read what exists

Nothing is overwritten. Before writing anything, record in the adoption brief:

- `git status --short`, the default branch and whether the working tree is clean
- every `AGENTS.md`, `CLAUDE.md`, `CLAUDE.local.md` and `.cursor/rules` file, and what each says
- `.claude/settings.json` and its hooks and permissions, and `.agents/hooks.json` or other Gemini CLI files in `.agents/`
- git hooks: `git config core.hooksPath`, `.pre-commit-config.yaml`, `lefthook.yml`, `.husky/`
- CI: `.github/workflows/`, `.gitlab-ci.yml`, and which checks are required on the default branch
- the real commands for install, test and lint, from the README, `Makefile`, `pyproject.toml` or `package.json`, and whether each passes now
- existing decision records, such as `docs/adr/`, and documentation layout

## 2. Create the directories and copy the scripts

~~~sh
mkdir -p .agents/bin .agents/notes .agents/work/briefs .agents/work/reviews .agents/work/advice .agents/work/reports .agents/work/runs
cp "$H"/scripts/detach.sh "$H"/scripts/wait.sh "$H"/scripts/work_state.py "$H"/scripts/run_checks.py "$H"/scripts/repo_check.py "$H"/scripts/collect_round.py "$H"/scripts/gemini_run.py "$H"/scripts/gemini_hook.py .agents/bin/
test -e .agents/hooks.json || cp "$H/assets/project/gemini-hooks.json" .agents/hooks.json
cp "$H/assets/project/notes-README.md" .agents/notes/README.md
cp "$H/assets/state.json" .agents/work/state.json
printf '# Ledger\n\nWritten by the main session only. One line per event.\n' > .agents/work/ledger.md
grep -qx '.agents/notes/archived/' .rgignore 2>/dev/null || cat "$H/assets/project/rgignore" >> .rgignore
~~~

Set the project name in `state.json` and remove the sample worker. When `.agents/hooks.json` already existed, add the named hook `longrun-gemini-policy` from [gemini-hooks.json](../assets/project/gemini-hooks.json) to it instead. The hooks file is committed with the scripts, because Gemini loads it from the checkout it runs in, including each worktree. The scripts are copies so that CI, git hooks and remote hosts can run them from the checkout. To update them later, copy again and review the diff.

Large logs under `.agents/work/runs/` can be ignored once their numbers are in a receipt, for example with `.agents/work/runs/*/stdout.log` in `.gitignore`.

## 3. Write the standing rules

Start from [the root template](../assets/project/AGENTS.md).

- **No AGENTS.md yet:** fill in the template: one paragraph on the project, the map with the real directories, the checks, and the rules that apply to this project. Keep it near 100 lines and under 200.
- **An AGENTS.md exists:** keep its content and its author's wording. Add the rows of the map and the rules it lacks. Move long procedures into `docs/` and link them.
- **A CLAUDE.md exists:** Claude Code reads AGENTS.md only where no CLAUDE.md exists in the directory or above, unless the setting `claude-md-and-agents-md` is on. Move shared rules into AGENTS.md and make `@AGENTS.md` the first line of CLAUDE.md, keeping only Claude-specific lines below it. Never replace it with a symlink: Claude Code's Edit and Write refuse to write through one, and Windows checks it out as a text file.
- **Area rules:** write a subdirectory AGENTS.md only for rules that hold in that directory and nowhere else. It adds to the root file and never repeats it.

Every rule should be one that an agent would otherwise get wrong. A rule that a check now enforces is removed from the file.

## 4. List the checks

Copy [checks.json](../assets/project/checks.json) to `.agents/checks.json` and replace the `tests` command with the project's real one. Add lint, type or build checks the project already runs, each with the modes it belongs to:

| Mode | Runs | Used by |
| --- | --- | --- |
| `commit` | fast checks of the repository layer and anything under a few seconds | pre-commit and pre-merge-commit hooks |
| `test` | the test suite | the pipeline, when a brief asks only for tests |
| `ci` | everything that checks the code and the documents | the pipeline by default, the pre-push hook, CI |

Run `python3 .agents/bin/run_checks.py --mode ci` once. Failures that existed before adoption are recorded in the adoption report and in the ledger, not fixed during adoption.

## 5. Hooks, CI and the session-start hook

Reuse what the project has. Add only what is missing.

- **pre-commit framework in use:** add the two local hooks from [pre-commit-config.yaml](../assets/project/pre-commit-config.yaml) and make sure `default_install_hook_types` includes `pre-merge-commit`. A merge commit runs `pre-merge-commit` and never `pre-commit`. Run `pre-commit install`.
- **Another hook manager or none:** call `python3 .agents/bin/run_checks.py --mode commit` from the pre-commit and pre-merge-commit hooks, and `--mode ci` from pre-push.
- **CI:** add the two final steps of [github-checks.yml](../assets/project/github-checks.yml) to the existing workflow, or copy it as `.github/workflows/checks.yml` with the project's install steps. No deploy or publish step is added. A workflow file does not make a check required; that is a setting of the hosting platform, reported to the user.
- **Session start:** merge [claude-settings.json](../assets/project/claude-settings.json) into `.claude/settings.json`. It runs the bearings check at startup, resume and after a compaction, and its output enters the main session's context. Subagents do not receive it.

## 6. Existing decision records

Leave `docs/adr/` or similar records where they are and link them from `.agents/notes/README.md`. New decisions go to `.agents/notes/`. Do not convert old records into notes: their alternatives would have to be reconstructed, and a note never invents an alternative.

## 7. Verify and report

~~~sh
python3 .agents/bin/repo_check.py
python3 .agents/bin/work_state.py --summary
python3 .agents/bin/run_checks.py --mode commit
~~~

When the project will use Gemini, run the preflight from [dispatch](dispatch.md) once the hooks file is committed. It writes `.agents/work/gemini-preflight.json`; every Gemini launch requires a passing record for the installed agy.

The adoption report lists every file created or changed, every rule moved and where it went, the checks with their current results, the hooks installed, and what was not verified, such as whether CI runs on the hosting platform and whether its checks are required.
