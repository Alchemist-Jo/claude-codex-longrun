"""Check the work state file and print the bearings for a new session.

The state file (default .agents/work/state.json) lists every worker the main
session has dispatched: Codex runs, subagents, advisor questions and paid
runs. Only the main session writes it. This script reports, without changing
anything:

- workers whose write sets or resources overlap while both hold them
- running processes without a log or a pid
- two workers that share an output directory
- briefs that do not exist
- with --alive, local running processes that finished, which need
  collection, and those that died without an exit-status file

With --dispatch ID the named worker is treated as holding its write set and
resources, so the check answers whether it can start now. With --context ID
the script lists the AGENTS.md files below the repository root that apply to
the worker's write set; Codex started at the worktree root does not load
them, so the brief names them. With --summary the script prints the worker
table first. With --bearings it prints git status, the worker table, the
liveness check and the ledger tail for a session start, and always exits 0.
Errors exit with status 1.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import re
import subprocess
import sys

STATUSES = ("planned", "running", "review", "changes", "accepted", "merged", "done", "stopped", "abandoned")
HOLDING = {"running", "review", "changes", "accepted"}
CLOSED = {"merged", "done", "abandoned"}
ROUTES = ("codex", "subagent", "advisor", "paid-run", "main")
PROCESS_ROUTES = {"codex", "advisor", "paid-run"}
REQUIRED = ("id", "route", "status", "brief", "out")
BASE = re.compile(r"^[^@\s]+@[0-9a-f]{7,40}$")
DEFAULT_STATE = Path(".agents/work/state.json")


def listed(worker: dict, key: str) -> list[str]:
    value = worker.get(key) or []
    return value if isinstance(value, list) else [value]


def writes(worker: dict) -> list[str]:
    return listed(worker, "writes")


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


def repo_root(state: Path) -> Path:
    """The state file sits at <root>/.agents/work/state.json."""
    return state.resolve().parents[2]


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
    live = [w for w, worker in workers.items()
            if worker.get("status") not in CLOSED and (writes(worker) or listed(worker, "resources"))]
    for i, a in enumerate(live):
        for b in live[i + 1:]:
            if b in lineage(a, workers) or a in lineage(b, workers):
                continue
            shared = sorted({describe(p, q) for p in writes(workers[a]) for q in writes(workers[b]) if overlaps(p, q)})
            held = sorted(set(listed(workers[a], "resources")) & set(listed(workers[b], "resources")))
            if not shared and not held:
                continue
            holding = [w for w in (a, b) if workers[w].get("status") in HOLDING or w == dispatch]
            level = "ERROR" if len(holding) == 2 else "WARN"
            if shared:
                problems.append(f"{level} {a} and {b} both write {', '.join(shared)}; run them in sequence or give the files to one combined brief")
            if held:
                problems.append(f"{level} {a} and {b} both hold {', '.join(held)}; run them in sequence or assign another resource")
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


def context(worker: dict, root: Path) -> list[str]:
    """AGENTS.md files below the root that apply to the worker's write set."""
    found: list[str] = []

    def add(path: Path) -> None:
        rel = path.relative_to(root).as_posix()
        if rel not in found:
            found.append(rel)

    for entry in writes(worker):
        target = root / entry
        folder = target if entry.endswith("/") else target.parent
        parts = folder.relative_to(root).parts
        for depth in range(1, len(parts) + 1):
            candidate = root.joinpath(*parts[:depth]) / "AGENTS.md"
            if candidate.is_file():
                add(candidate)
        if entry.endswith("/") and folder.is_dir():
            for candidate in sorted(folder.rglob("AGENTS.md")):
                add(candidate)
    return found


def summary(workers: dict[str, dict]) -> str:
    rows = ["| Worker | Route | Status | Writes | Worktree | Out |", "| --- | --- | --- | --- | --- | --- |"]
    for worker_id, worker in workers.items():
        held = [f"`{p}`" for p in writes(worker)] + listed(worker, "resources")
        rows.append("| {} | {} | {} | {} | {} | {} |".format(
            worker_id, worker.get("route", ""), worker.get("status", ""),
            ", ".join(held) or "none", worker.get("worktree", ""), worker.get("out", "")))
    return "\n".join(rows) + "\n"


def run(state: Path, dispatch: str | None = None, alive: bool = False) -> tuple[dict[str, dict], list[str]]:
    workers, problems = load(state)
    root = repo_root(state)
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


def bearings(state: Path) -> str:
    """Read-only orientation for a session start, bounded in length."""
    root = repo_root(state)
    lines = []
    for title, args in (("git status", ["status", "--short"]), ("worktrees", ["worktree", "list"]),
                        ("recent commits", ["log", "--oneline", "-5"])):
        result = subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True, check=False)
        output = result.stdout.splitlines()
        lines.append(f"## {title}")
        lines.extend(output[:20] or ["(none)"])
        if len(output) > 20:
            lines.append(f"... {len(output) - 20} more lines")
    workers, problems = run(state, alive=True)
    lines.append("## workers")
    lines.append(summary(workers).rstrip())
    lines.extend(problems or ["State passed."])
    ledger = state.parent / "ledger.md"
    if ledger.is_file():
        tail = [line for line in ledger.read_text(encoding="utf-8").splitlines() if line.strip()][-15:]
        lines.append("## ledger, last entries")
        lines.extend(tail)
    lines.append("Reconcile finished and dead jobs before choosing the next route.")
    return "\n".join(lines) + "\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("state", nargs="?", type=Path, default=DEFAULT_STATE)
    parser.add_argument("--dispatch", metavar="ID", help="treat this planned worker as started")
    parser.add_argument("--context", metavar="ID", help="list the AGENTS.md files that apply to this worker's write set")
    parser.add_argument("--alive", action="store_true", help="check that local running pids still exist")
    parser.add_argument("--summary", action="store_true", help="print the worker table")
    parser.add_argument("--bearings", action="store_true", help="print the session-start bearings and exit 0")
    args = parser.parse_args()
    if args.bearings:
        if args.state.is_file():
            try:
                sys.stdout.write(bearings(args.state))
            except (OSError, ValueError) as error:
                print(f"bearings failed: {error}")
        return 0
    try:
        workers, problems = run(args.state, args.dispatch, args.alive)
    except (OSError, ValueError) as error:
        print(error, file=sys.stderr)
        return 1
    if args.context:
        if args.context not in workers:
            print(f"ERROR --context {args.context}: no such worker", file=sys.stderr)
            return 1
        for path in context(workers[args.context], repo_root(args.state)):
            print(path)
        return 0
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
