# Dispatch

Read when starting Codex or Gemini on a brief, resuming a session, or dispatching a subagent.

Commands below run from the project's repository root, which holds the scripts in `.agents/bin/` as described in [adopt](adopt.md).

## Before any dispatch

1. Write the brief or fill in the runbook.
2. Add the worker to `.agents/work/state.json` with status `planned`, its route, brief, write set, resources, base commit and a new output directory under `.agents/work/runs/`. A read-only search, by a subagent or by Gemini in the main session's foreground, needs no entry: if its result is lost, it is run again.
3. Run `python3 .agents/bin/work_state.py --dispatch <id>`. Resolve every error before the worker starts.
4. For a Codex or Gemini brief, run `python3 .agents/bin/work_state.py --context <id>` and list its output under Standing rules in the brief. Codex loads the AGENTS.md files from the repository root down to its working directory once, at start, and Gemini loads the one in its working directory; neither loads those of the directories it is about to edit.
5. Set the status to `running` once the pid, or the subagent's start, is recorded.

## Writing the brief

Start from [the brief template](../assets/brief.md). The order matters: the write set, the standing rules and the constraints come before the changes, so they are read before the first edit.

- **Acceptance** names commands and expected results. For each behaviour change, ask for the narrowest test that would fail if the change regressed, and for each new or changed check, a case that the check rejects. The full checks are `python3 .agents/bin/run_checks.py --mode ci`. A filtered test command must show how many tests it selected.
- **Constraints** forbid hiding an unstable test behind a longer timeout, a retry, a sleep, serial execution, a swallowed error or a weaker assertion.
- **Docs impact** in the final message lists documents outside the write set that the change makes wrong, so the close-out can fix them.
- Documentation that describes the changed code, such as the module README and interface comments, belongs in the write set.

## Who does what for a writing worker

| Step | Owner |
| --- | --- |
| Prepare: run directory, worktree, `BRIEF.md` | Pipeline subagent, or the main session |
| Launch Codex or Gemini | Main session |
| Wait | Main session for long jobs, watcher for short ones, as in [waiting](waiting.md) |
| Collect: round commit, diffs, checks | Pipeline subagent |
| Review | Reviewer subagent |
| Ruling, next round, close-out, freeze, merge | Main session; the pipeline subagent may tag the freeze |

## Prepare

~~~sh
id=w12; n=1
base=3f2c1aa                  # the commit recorded in state.json, never recomputed
run="$PWD/.agents/work/runs/$id-r$n"   # absolute, so Codex and the wrapper agree on paths
wt="$(cd .. && pwd)/wt/$id"
mkdir "$run"                  # fails if it exists, which is a stop condition
git worktree add -b "worker/$id" "$wt" "$base"
cp ".agents/work/briefs/$id.md" "$wt/BRIEF.md"
ex="$(git rev-parse --path-format=absolute --git-common-dir)/info/exclude"
grep -qx 'BRIEF.md' "$ex" || echo 'BRIEF.md' >> "$ex"
~~~

## Launch

`.agents/bin/detach.sh` starts the command in its own session with stdin closed, writes the wrapper's pid to `pid`, captures `stdout.log` and `stderr.log`, and writes `exit-status` when the command exits.

~~~sh
.agents/bin/detach.sh "$run" -- codex exec -C "$wt" -s workspace-write \
  -c model_reasoning_effort="high" --json -o "$run/last-message.md" \
  "Read BRIEF.md in the working directory and carry it out exactly. Do not commit."
~~~

It prints the pid. Record the pid, `log` and `out` in the state file as paths relative to the repository root, then set `running`.

What each part prevents:

- Stdin closed: `codex exec` reads stdin even when a prompt is given. Left open by a harness, it waits with no output and no CPU.
- Own session: the job is outside the agent's process group, so it continues when the agent's turn ends or a background command is stopped. The pid is also the process group of everything Codex starts, which makes a later kill complete.
- `exit-status`: written only when Codex exits. Its presence is the only completion signal.
- `-s workspace-write` and the effort: the user's configuration may default to full access and maximum effort.
- `--json` and `-o`: the event stream goes to `stdout.log` and the final message to `last-message.md`, both readable after any interruption.
- `BRIEF.md` in `info/exclude`: the brief never enters a commit.

Use `-c model_reasoning_effort="xhigh"` for design-sensitive briefs.

## Session id

After round 1 starts, record the Codex session id in the worker's `session` field. It is the `thread_id` of the first `thread.started` event:

~~~sh
grep -o '"thread_id":"[^"]*"' "$run/stdout.log" | head -1 | cut -d'"' -f4
~~~

When a round starts a fresh session, the main session replaces `session` with the new id, so a later resume never returns to an abandoned conversation.

## Resume for the next round

~~~sh
id=w12; n=2; wt="$(cd .. && pwd)/wt/$id"; run="$PWD/.agents/work/runs/$id-r$n"
mkdir "$run"
~~~

Write the agreed changes to `$run/round.md`. It ends with: "For each change, verify the claim, then make the change or state the technical reason it is wrong. Do not agree without checking." Then launch in a separate command:

~~~sh
session=01a13bbd-7a71-7640-961c-682cf16eb66c     # the worker's session field in state.json
[ -n "$session" ] || { echo "no session id recorded" >&2; exit 1; }
test -s "$run/round.md" || { echo "round.md is missing or empty" >&2; exit 1; }
.agents/bin/detach.sh "$run" -- codex exec -C "$wt" -s workspace-write \
  -c model_reasoning_effort="high" --json -o "$run/last-message.md" \
  resume "$session" "$(cat "$run/round.md")"
~~~

Flags go between `exec` and `resume`. Avoid `resume --last` when more than one Codex session runs in the repository. Update `pid`, `log` and `out` in the state file to the new run directory and set `running`.

## Remote hosts

The scripts in `.agents/bin/` are part of the checkout, so a host with the project checked out at a recent commit already has them. Otherwise copy them once with `scp`. Run them from the host's checkout; do not pipe a script into `ssh host sh -s`, which failed in testing after the job had started. The job's files live in the same relative run directory of the host's checkout; the launch record and `collect/` stay in the local run directory.

~~~sh
ssh gpu-host 'cd /work/proj && mkdir .agents/work/runs/p07 && .agents/bin/detach.sh .agents/work/runs/p07 -- python train.py --config configs/base.yaml'
~~~

`ssh` returns as soon as the job is detached. When the connection drops, the job continues.

## The advisor

~~~sh
mkdir .agents/work/runs/a04          # the advisor's out; the answer goes to .agents/work/advice/
.agents/bin/detach.sh .agents/work/runs/a04 -- codex exec -C . -s read-only \
  -c model_reasoning_effort="ultra" -o .agents/work/advice/a04-answer.md \
  "$(cat .agents/work/advice/a04-question.md)"
~~~

Use the highest effort the configured model accepts. An answer at maximum effort can take longer than one foreground call allows, so it runs detached like any other job. The answer is saved verbatim beside the question.

## Gemini

`.agents/bin/gemini_run.py` runs agy, the Gemini CLI, headless. The command after `--` is agy with its model and effort, such as `agy --model <model> --effort high`, or a local wrapper that supplies them; [routing](routing.md) names the model for each route. Use absolute paths for `--run`, `--root` and `--prompt-file`.

### Preflight

Run it once per agy binary, and again whenever a launch reports a stale record:

~~~sh
run="$PWD/.agents/work/runs/preflight-$(date +%Y%m%d-%H%M)"; mkdir "$run"
python3 .agents/bin/gemini_run.py --preflight --run "$run" --root "$PWD" -- agy --model <fast model> --effort low
~~~

It runs six probes, each in its own directory under `$run`: an answer, a file read, a listed command, a denied command, a denied write and a web search. The two denial probes tell the model that the call will be denied and ask it to make the call anyway; a model that only reads the grants refuses on its own, and the hook is never tested. It writes `.agents/work/gemini-preflight.json` with the agy binary it tested and exits 0 only when every probe passed. agy updates itself, so the record also expires when the binary changes. The read and command probes compare the answer with the first line of `AGENTS.md` and with `HEAD`, so the working directory needs both.

### Read-only runs

A search that should finish within 10 minutes runs in the main session's foreground, with the Bash tool timeout above `--timeout`:

~~~sh
run="$PWD/.agents/work/runs/g04"; mkdir "$run"
python3 .agents/bin/gemini_run.py --run "$run" --root "$PWD" --timeout 540 \
  --prompt-file "$PWD/.agents/work/briefs/g04.md" -- agy --model <fast model> --effort low
~~~

Research, document review and upkeep checks get a state entry with route `gemini` and run detached:

~~~sh
.agents/bin/detach.sh "$run" -- python3 .agents/bin/gemini_run.py --run "$run" --root "$PWD" --web \
  --timeout 7200 --prompt-file "$PWD/.agents/work/briefs/g05.md" -- agy --model <strongest model> --effort high
~~~

Add `--read DIR` for each directory outside the working directory that the brief names; Gemini reads files there with its file tool, since shell commands stay inside the working directory. Add `--command 'CMD ARGS'` for each command beyond the default read-only list. The answer is in `$run/last-message.md`.

### Documentation maintenance

Prepare the worktree as for Codex. Then:

~~~sh
.agents/bin/detach.sh "$run" -- python3 .agents/bin/gemini_run.py --run "$run" --root "$wt" \
  --write docs/guide.md --write spec/ --timeout 3600 --prompt-file "$wt/BRIEF.md" \
  -- agy --model <strongest model> --effort high
~~~

The `--write` paths repeat the write set of the state entry, relative to the worktree. An acceptance command the brief asks Gemini to run is granted with `--command`, and it runs read-only. Collection, review and rounds follow the Codex steps: Gemini does not commit, and `collect_round.py` makes the round commit.

### Session id and resume

The launcher writes the conversation id to `$run/session`. Record it in the worker's `session` field. For the next round, write `round.md` as for Codex and launch in a separate command:

~~~sh
session=$(cat "$PWD/.agents/work/runs/w12-r1/session")
[ -n "$session" ] || { echo "no session id recorded" >&2; exit 1; }
.agents/bin/detach.sh "$run" -- python3 .agents/bin/gemini_run.py --run "$run" --root "$wt" \
  --write docs/guide.md --write spec/ --conversation "$session" --prompt-file "$run/round.md" \
  -- agy --model <strongest model> --effort high
~~~

Every round passes its grants again: the policy belongs to the run, not to the conversation.

### What the launcher does

1. It refuses to start, with exit status 2, when the run directory holds files of an earlier launch (`policy.json`, `result.json`, `hook-started`, `tools.jsonl` and the like), a path is invalid, the working directory's `.agents/hooks.json` lacks the policy hook, or the preflight record is missing, failed, or names another agy binary or an earlier modification time of it.
2. It writes `policy.json` and starts agy in the working directory with `--sandbox`, `--dangerously-skip-permissions`, `--print-timeout`, `--log-file`, `--disable-slash-commands` and `LONGRUN_GEMINI_POLICY` pointing at the policy. It passes no `--add-dir`: agy would load that directory's hooks and treat it as a workspace. The prompt opens with the grants, so the model can finish within them.
3. It keeps agy's JSON output in `result.json`, its stderr in `agy-stderr.log` and its log in `agy.log`, and writes the answer to `last-message.md` and the conversation id to `session`. The hook adds a line to `hook-started` before each model call and to `tools.jsonl` for each tool call; when it cannot write its audit line it denies the call and writes `hook-error`.
4. A SIGTERM, SIGINT or SIGHUP to the launcher stops agy's process group, so stopping the detached job stops agy too.
5. It judges the run and prints one line, `gemini_run: <verdict> <reason>`.

| Exit | Meaning |
| --- | --- |
| 0 | The hook ran, agy returned status `SUCCESS` with a non-empty answer, no tool call was denied and the run did not time out |
| 1 | The hook did not run or could not write its audit line, the launcher was stopped by a signal, agy failed or timed out, its output was not JSON or not `SUCCESS`, or the answer was empty |
| 2 | Refused before agy started |
| 3 | At least one tool call was denied; `tools.jsonl` names it, and `last-message.md` holds whatever answer exists |

agy itself exits 0 after a denial, a timeout and an empty answer alike. Only the launcher's exit status counts.

## Subagents

Dispatch with the Agent tool, one runbook per agent:

- the prompt is the runbook's absolute path and one line: "Follow this runbook exactly. Stop on any stop condition and report."
- use the strongest Claude model for review and reporting, and for any runbook with judgement in it
- run it in the background when the main session has other work, and wait for its notification rather than polling its transcript
- never give a subagent a runbook that asks it to start Codex, Gemini or another agent

A general-purpose subagent loads the root AGENTS.md at start and a subdirectory's AGENTS.md when it first reads a file there. The built-in Explore and Plan agents load neither. A subagent's report is a claim. The main session reads the files it points to before acting on anything that matters.

## Return contract

Every worker ends with:

1. status: `DONE`, `DONE_WITH_CONCERNS`, `BLOCKED` or `NEEDS_CONTEXT`
2. what changed or what was collected, as paths
3. each requested number with its source file
4. for anything unexpected: Expected, Found, Why it matters
5. what was not done, and why

Within 300 words unless the runbook says otherwise. Omitted or truncated output is marked as such.
