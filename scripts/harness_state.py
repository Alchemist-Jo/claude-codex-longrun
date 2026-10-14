"""Check the harness state file and print the bearings for a new session.

The state file (default harness/state.json) lists every worker the main
session has dispatched: Codex runs, subagents, advisor questions and paid
runs. Only the main session writes it. This script reports, without changing
anything:

- workers whose write sets overlap while both hold them
- running processes without a log or a pid
- two workers that share an output directory
- briefs that do not exist
- with --alive, local running processes that finished, which need
  collection, and those that died without an exit-status file

With --dispatch ID the named worker is treated as holding its write set, so
the check answers whether it can start now. With --summary the script prints
the worker table first. Errors exit with status 1.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import sys

STATUSES = ("planned", "running", "review", "changes", "accepted", "merged", "done", "stopped", "abandoned")
HOLDING = {"running", "review", "changes", "accepted"}
CLOSED = {"merged", "done", "abandoned"}
ROUTES = ("codex", "subagent", "advisor", "paid-run")
PROCESS_ROUTES = {"codex", "advisor", "paid-run"}
REQUIRED = ("id", "route", "status", "brief", "out")
BASE = re.compile(r"^[^@\s]+@[0-9a-f]{7,40}$")


def writes(worker: dict) -> list[str]:
    value = worker.get("writes") or []
    return value if isinstance(value, list) else [value]


def overlaps(a: str, b: str) -> bool:
    if a == b:
        return True
    if a.endswith("/") and b.startswith(a):
        return True
    return b.endswith("/") and a.startswith(b)


def describe(a: str, b: str) -> str:
    if a == b:
        return a
    inner, outer = (b, a) if a.endswith("/") and b.startswith(a) else (a, b)
    return f"{inner} (inside {outer})"


def lineage(worker_id: str, workers: dict[str, dict]) -> set[str]:
    seen = {worker_id}
    parent = workers.get(worker_id, {}).get("parent")
    while parent and parent in workers and parent not in seen:
        seen.add(parent)
        parent = workers[parent].get("parent")
    return seen


def pid_alive(pid: int) -> bool:
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    return True


def load(path: Path) -> tuple[dict[str, dict], list[str]]:
    data = json.loads(path.read_text(encoding="utf-8"))
    problems: list[str] = []
    workers: dict[str, dict] = {}
    for index, worker in enumerate(data.get("workers", [])):
        worker_id = worker.get("id") or f"#{index}"
        if worker_id in workers:
            problems.append(f"ERROR {worker_id}: duplicate id")
            continue
        workers[worker_id] = worker
    return workers, problems


def check_worker(worker_id: str, worker: dict, workers: dict[str, dict], root: Path) -> list[str]:
    problems = []
    for key in REQUIRED:
        if not worker.get(key):
            problems.append(f"ERROR {worker_id}: missing {key}")
    status, route = worker.get("status"), worker.get("route")
    if status and status not in STATUSES:
        problems.append(f"ERROR {worker_id}: status {status!r} is not one of {', '.join(STATUSES)}")
    if route and route not in ROUTES:
        problems.append(f"ERROR {worker_id}: route {route!r} is not one of {', '.join(ROUTES)}")
    if worker.get("base") and not BASE.match(worker["base"]):
        problems.append(f"ERROR {worker_id}: base must look like main@1a2b3c4")
    for path in writes(worker):
        if path.startswith("/") or ".." in Path(path).parts or re.search(r"[*?\[]", path):
            problems.append(f"ERROR {worker_id}: write path {path!r} must be relative, without globs; mark directories with a trailing /")
    if writes(worker) and not worker.get("worktree") and route == "codex":
        problems.append(f"ERROR {worker_id}: a Codex worker that writes needs its own worktree")
    if route == "advisor" and writes(worker):
        problems.append(f"ERROR {worker_id}: the advisor route is read-only and cannot hold a write set")
    if status == "running" and route in PROCESS_ROUTES:
        if not worker.get("log"):
            problems.append(f"ERROR {worker_id}: running process without a log path")
        if not isinstance(worker.get("pid"), int):
            problems.append(f"ERROR {worker_id}: running process without an integer pid")
    parent = worker.get("parent")
    if parent and parent not in workers:
        problems.append(f"ERROR {worker_id}: parent {parent} is not in the state file")
    brief = worker.get("brief")
    if brief and not (root / brief).exists():
        problems.append(f"ERROR {worker_id}: brief {brief} does not exist")
    return problems


def check_shared(workers: dict[str, dict], dispatch: str | None) -> list[str]:
    problems = []
    outs: dict[str, str] = {}
    for worker_id, worker in workers.items():
        out = worker.get("out")
        if out:
            key = out.rstrip("/")
            if key in outs:
                problems.append(f"ERROR {worker_id} and {outs[key]} share output directory {out}; every run gets a new one")
            outs.setdefault(key, worker_id)
    live = [w for w, worker in workers.items() if worker.get("status") not in CLOSED and writes(worker)]
    for i, a in enumerate(live):
        for b in live[i + 1:]:
            if b in lineage(a, workers) or a in lineage(b, workers):
                continue
            shared = sorted({describe(p, q) for p in writes(workers[a]) for q in writes(workers[b]) if overlaps(p, q)})
            if not shared:
                continue
            holding = [w for w in (a, b) if workers[w].get("status") in HOLDING or w == dispatch]
            level = "ERROR" if len(holding) == 2 else "WARN"
            problems.append(f"{level} {a} and {b} both write {', '.join(shared)}; run them in sequence or give the files to one combined brief")
    return problems


def check_alive(workers: dict[str, dict], root: Path) -> list[str]:
    problems = []
    for worker_id, worker in workers.items():
        if worker.get("status") != "running" or not isinstance(worker.get("pid"), int):
            continue
        host = worker.get("host", "local")
        if host != "local":
            problems.append(f"NOTE {worker_id}: pid {worker['pid']} is on {host}; check its exit-status there")
            continue
        exit_file = root / worker.get("out", "") / "exit-status"
        if exit_file.is_file():
            status = exit_file.read_text(encoding="utf-8").strip()
            problems.append(f"NOTE {worker_id}: finished with exit status {status}; collect, then update its status")
        elif not pid_alive(worker["pid"]):
            problems.append(f"ERROR {worker_id}: pid {worker['pid']} is gone and {exit_file.relative_to(root)} does not exist; the job died without finishing")
    return problems


def summary(workers: dict[str, dict]) -> str:
    rows = ["| Worker | Route | Status | Writes | Worktree | Out |", "| --- | --- | --- | --- | --- | --- |"]
    for worker_id, worker in workers.items():
        rows.append("| {} | {} | {} | {} | {} | {} |".format(
            worker_id, worker.get("route", ""), worker.get("status", ""),
            ", ".join(f"`{p}`" for p in writes(worker)) or "none",
            worker.get("worktree", ""), worker.get("out", "")))
    return "\n".join(rows) + "\n"


def run(state: Path, dispatch: str | None = None, alive: bool = False) -> tuple[dict[str, dict], list[str]]:
    workers, problems = load(state)
    root = state.resolve().parent.parent
    if dispatch:
        if dispatch not in workers:
            problems.append(f"ERROR --dispatch {dispatch}: no such worker")
            dispatch = None
        elif workers[dispatch].get("status") != "planned":
            problems.append(f"ERROR --dispatch {dispatch}: status is {workers[dispatch].get('status')}, expected planned")
    for worker_id, worker in workers.items():
        problems.extend(check_worker(worker_id, worker, workers, root))
    problems.extend(check_shared(workers, dispatch))
    if alive:
        problems.extend(check_alive(workers, root))
    return workers, problems


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("state", nargs="?", type=Path, default=Path("harness/state.json"))
    parser.add_argument("--dispatch", metavar="ID", help="treat this planned worker as started")
    parser.add_argument("--alive", action="store_true", help="check that local running pids still exist")
    parser.add_argument("--summary", action="store_true", help="print the worker table")
    args = parser.parse_args()
    try:
        workers, problems = run(args.state, args.dispatch, args.alive)
    except (OSError, ValueError) as error:
        print(error, file=sys.stderr)
        return 1
    if args.summary:
        sys.stdout.write(summary(workers))
    for problem in problems:
        print(problem, file=sys.stderr if problem.startswith("ERROR") else sys.stdout)
    errors = [p for p in problems if p.startswith("ERROR")]
    if not errors:
        print(f"State passed: {len(workers)} worker(s), {len(problems)} note(s) or warning(s).")
    return int(bool(errors))


if __name__ == "__main__":
    raise SystemExit(main())
