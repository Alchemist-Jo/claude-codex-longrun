# Waiting, paid runs and kills

Read when a Codex job or a paid run has started, when a wait was cut off, before a paid launch, and before a kill.

## Why waits fail

Reported platform behaviours that end waits which look healthy:

- A background Bash command started by a subagent is killed when that subagent ends its turn, and the completion notification it was promised never arrives ([anthropics/claude-code#83627](https://github.com/anthropics/claude-code/issues/83627), closed as not planned). In a test on Claude Code 2.1.284 in an interactive session, this did not reproduce: the subagent's background command and its detached job both kept running and finished after the subagent returned.
- Claude Code stops background commands at a time limit and reports that the command "was stopped after reaching its background time limit" ([#98273](https://github.com/anthropics/claude-code/issues/98273)). Release 2.1.288 scoped the limit to unattended sessions such as `-p`, the Agent SDK, CI and cloud, as quoted in [#100648](https://github.com/anthropics/claude-code/issues/100648), which reports Remote Control sessions still receiving it.
- An SSH connection that holds a remote wait can drop.

Which of these causes a given cut-off depends on the version and the kind of session. The design below survives all of them, so the cause does not have to be known first.

## The pattern

1. **The job is detached.** It was started with `scripts/detach.sh`, as in [dispatch](dispatch.md): own session, stdin closed, pid file, exit-status file. Losing any agent or any wait leaves it running.
2. **The wait is an observer.** It blocks until the pid disappears. It can be killed and restarted without effect on the job.
3. **Completion is a file.** The job finished when `exit-status` exists. The end of a wait means only that the wait ended.
4. **Collection reads files.** Numbers come from logs and outputs in the run directory, so a new collector repeats the work exactly.

## Where the wait lives

| Expected duration | Holder | How |
| --- | --- | --- |
| Under about 25 minutes | Watcher subagent | Foreground waits of at most 10 minutes each, inside one turn, then collection |
| Longer, or unknown | Main session | One background command that returns when the job exits. On its notification, dispatch the watcher for collection only |

A watcher never ends its turn while a background child is running, and never starts the job it watches.

## Wait commands

`scripts/wait.sh RUN_DIR [MAX_SECONDS]` observes a job started by `detach.sh` and never touches it. It prints one line and exits 0 when the job finished, with the job's exit status in the line, 3 when the job is still running after `MAX_SECONDS`, and 4 when the pid is gone without an exit-status file.

| Holder | Local | Remote |
| --- | --- | --- |
| Watcher, one foreground call | `"$H/scripts/wait.sh" harness/runs/w12-r1 570` | `ssh gpu-host /work/proj/harness/bin/wait.sh /work/proj/harness/runs/p07 570` |
| Main session, one background command | `"$H/scripts/wait.sh" harness/runs/w12-r1` | `ssh gpu-host /work/proj/harness/bin/wait.sh /work/proj/harness/runs/p07` |
| Single check, as in the bearings | `"$H/scripts/wait.sh" harness/runs/w12-r1 0` | `ssh gpu-host /work/proj/harness/bin/wait.sh /work/proj/harness/runs/p07 0` |

When the SSH connection drops, the job continues. Reissue the same command.

## After a wait ends

1. Exit 0: the job finished. Collect by the runbook's checklist.
2. Exit 3, or a wait that was itself cut off: the job may still run. Reissue the wait. Report nothing about the result.
3. Exit 4: the job died without finishing. Report `BLOCKED` with the last 40 lines of `stderr.log` and `stdout.log`.

`python3 "$H/scripts/harness_state.py" harness/state.json --alive`, with `H` set to this skill's directory, applies the same three cases to every local job marked running.

## Paid runs

Before the launch, the main session fills in [the launch record](../assets/launch-record.md) in the run directory: the command, the frozen tag the run starts from, the host, the expected duration and cost, the numbers to collect with their files, and the kill condition. It launches the run itself with `detach.sh`, writes the pid and the start time into the record, and adds a ledger line.

After the run, the watcher writes the receipt to `collect/receipt.md` in the local run directory, reading remote files with `ssh gpu-host cat`: exit status, wall time, every collected number with its file and line, and anything that did not match the expectation.

## Kills

Only the main session kills. The pid file holds the wrapper's pid, which is also the process group of the job. Before the kill, list the group and compare the command lines with the launch record. On a remote host, run each command through `ssh gpu-host 'cd /work/proj && ...'`.

~~~sh
pid=$(cat harness/runs/p07/pid)
ps -o pid,etime,args -p "$(pgrep -d, -g "$pid")"
~~~

Terminate the job under the wrapper first, give the wrapper up to 30 seconds to record the exit status, then terminate what remains of the group. A job's own children are not children of the wrapper, and a job that saves state on SIGTERM can take a while to exit:

~~~sh
run=harness/runs/p07; pid=$(cat "$run/pid")
pkill -TERM -P "$pid"
i=0; while [ ! -f "$run/exit-status" ] && [ $i -lt 30 ]; do sleep 1; i=$((i + 1)); done
kill -TERM -- "-$pid" 2>/dev/null
sleep 30; pgrep -g "$pid" && kill -KILL -- "-$pid"
~~~

The wrapper records exit status 143 unless the job ignored SIGTERM for 30 seconds, in which case `exit-status` stays missing and the ledger entry is the record. The group id is the recorded pid, so nothing outside the job is touched. Never kill by process name. Record the kill in the ledger with the reason, the time and the pid, then set the worker to `stopped`.
