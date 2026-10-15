# AGENTS.md

<One paragraph: what this repository produces, who uses it, and the command that shows it working.>

Codex loads the AGENTS.md files from the repository root down to its working directory when it starts. Claude Code loads this file at the start and a subdirectory's AGENTS.md when it first reads a file there. Before editing in a directory, read every AGENTS.md between the root and that directory.

## Map

| Path | Holds |
| --- | --- |
| `<src/package/>` | <what the code does; its own AGENTS.md if it has rules of its own> |
| `<tests/>` | <test layout and fixtures> |
| `docs/` | Current documentation for users of the project |
| `.agents/notes/` | Decision notes: why the code is the way it is, alternatives that were rejected. Rules in `.agents/notes/README.md`. Search them with `rg <term> .agents/notes`, since plain `rg` skips hidden directories |
| `.agents/work/` | Records of agent work cycles: state, ledger, briefs, reviews, run directories. History, not current facts |
| `.agents/bin/` | Scripts for detached jobs, waits and checks |
| `.agents/checks.json` | Every check the project runs, used by hooks, CI and agents alike |

## Rules for every change

- Change only what the task asks for. Every abstraction, option, configuration key and compatibility path needs a current consumer.
- Edit the source of generated content and regenerate it. Never hand-edit generated output.
- A change in behaviour updates, in the same change, the README of the module and the interface comments at the call sites. When it alters a recorded decision, name the note under docs impact; notes are edited at close-out.
- Evidence is an external result: a test, a file, an exit status. A component's or an agent's own report of success is a claim.
- Catching an exception stops its propagation and undoes nothing. Logging is not recovery. Claim a rollback or a safe retry only where the code guarantees it.
- Do not hide an unstable test with a longer timeout, a retry, a sleep, serial execution, a swallowed error or a weaker assertion. Find the race or the shared state.
- Code, comments and documents state current facts that a reader of this checkout can verify. They do not mention worker ids, review rounds, chat sessions or plans that already happened; those belong in `.agents/work/` or in a note.
- Do not read `.env` or credential files.

## Checks

~~~sh
python3 .agents/bin/run_checks.py --mode commit   # fast checks of the repository layer
python3 .agents/bin/run_checks.py --mode test     # the test suite
python3 .agents/bin/run_checks.py --mode ci       # everything CI runs
~~~

A check that runs no test is not evidence. A rule that a check now enforces is deleted from this file.

## Where facts go

| Fact | Home |
| --- | --- |
| How to use a module, its configuration and its failures | The module's README |
| What a caller must know: conditions, return values, failures, ordering, ownership | The interface comment |
| A task with prerequisites and steps | `docs/`, as a tutorial |
| Why a decision was made and what was rejected | A note in `.agents/notes/` |
| What happened during an incident and what changed after it | `docs/postmortem/` |
| What an agent did, when, with which evidence | `.agents/work/ledger.md` and the run directories |

One fact has one home. Other places link to it.
