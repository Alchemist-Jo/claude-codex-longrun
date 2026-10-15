# AGENTS.md

evalkit runs evaluation suites over model checkpoints in shards and writes one `report.json` per run. `evalkit run configs/tiny.yaml` on the fixture in `tests/fixtures/tiny/` shows it working in under 10 seconds.

Codex loads the AGENTS.md files from the repository root down to its working directory when it starts. Claude Code loads this file at the start and a subdirectory's AGENTS.md when it first reads a file there. Before editing in a directory, read every AGENTS.md between the root and that directory.

## Map

| Path | Holds |
| --- | --- |
| `src/evalkit/` | The runner, the dataset adapters and the report writer. Its own rules are in `src/evalkit/AGENTS.md` |
| `tests/` | Unit tests; `tests/fixtures/tiny/` is a 4-shard suite for fast end-to-end tests |
| `docs/` | The report format and the configuration reference |
| `.agents/notes/` | Decision notes. Rules in `.agents/notes/README.md`. Search them with `rg <term> .agents/notes` |
| `.agents/work/` | Records of agent work cycles. History, not current facts |
| `.agents/bin/` | Scripts for detached jobs, waits and checks |
| `.agents/checks.json` | Every check, used by hooks, CI and agents |

## Rules for every change

- Change only what the task asks for. Every abstraction, option, configuration key and compatibility path needs a current consumer.
- A change in behaviour updates, in the same change, the README of the module and the interface comments at the call sites. When it alters a recorded decision, name the note under docs impact; notes are edited at close-out.
- Evidence is an external result: a test, a file, an exit status. A component's or an agent's own report of success is a claim.
- Catching an exception stops its propagation and undoes nothing. Claim a rollback or a safe retry only where the code guarantees it.
- Do not hide an unstable test with a longer timeout, a retry, a sleep, serial execution, a swallowed error or a weaker assertion.
- Code, comments and documents state current facts that a reader of this checkout can verify, without worker ids, review rounds or chat sessions.
- Do not read `.env` or credential files.

## Checks

~~~sh
python3 .agents/bin/run_checks.py --mode commit
python3 .agents/bin/run_checks.py --mode ci
~~~

## Where facts go

| Fact | Home |
| --- | --- |
| The report file format | `docs/report-format.md` |
| How a module is used and configured | The module's README |
| Why a decision was made and what was rejected | A note in `.agents/notes/` |
| What an agent did, when, with which evidence | `.agents/work/ledger.md` and the run directories |
