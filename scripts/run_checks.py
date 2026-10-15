"""Run the project's checks from .agents/checks.json, by mode or by id.

The pipeline runner, the git hooks and CI call this one script, so a check
means the same thing everywhere. The file lists checks in order:

    {"checks": [
      {"id": "repo", "command": ["python3", ".agents/bin/repo_check.py"],
       "modes": ["commit", "ci"]},
      {"id": "tests", "command": ["python3", "-m", "pytest", "-q"],
       "modes": ["test", "ci"], "needs": [], "timeout": 1800}
    ]}

A command is an argument array run from the repository root without a shell.
`needs` names earlier checks that must pass first; a check whose need failed
or was skipped is skipped and counts as a failure. `timeout` is in seconds
(default 600); on expiry the check's whole process group is terminated, and
so is a running check when this script receives SIGTERM or SIGINT. The full
output of every check is printed under a header, so a redirected run is
the evidence. Exit status: 0 when every selected check passed, 1 when any
failed or was skipped, 2 for a configuration error.
"""
from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import time

DEFAULT_CONFIG = Path(".agents/checks.json")
DEFAULT_TIMEOUT = 600
FIELDS = {"id", "command", "modes", "needs", "timeout"}


def load(path: Path) -> list[dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    checks = data.get("checks") if isinstance(data, dict) else None
    if not isinstance(checks, list) or not checks:
        raise ValueError(f"{path}: needs a non-empty list under 'checks'")
    seen: set[str] = set()
    for item in checks:
        if not isinstance(item, dict) or set(item) - FIELDS:
            raise ValueError(f"{path}: each check may only have {', '.join(sorted(FIELDS))}")
        key = item.get("id")
        if not isinstance(key, str) or not key or key in seen:
            raise ValueError(f"{path}: check id {key!r} is missing or repeated")
        for field in ("command", "modes"):
            value = item.get(field)
            if not isinstance(value, list) or not value or not all(isinstance(v, str) and v for v in value):
                raise ValueError(f"{path}: {key}.{field} must be a non-empty list of strings")
        needs = item.setdefault("needs", [])
        if not isinstance(needs, list) or any(n not in seen for n in needs):
            raise ValueError(f"{path}: {key}.needs may only name checks listed before it")
        timeout = item.setdefault("timeout", DEFAULT_TIMEOUT)
        if isinstance(timeout, bool) or not isinstance(timeout, (int, float)) or timeout <= 0:
            raise ValueError(f"{path}: {key}.timeout must be a positive number of seconds")
        seen.add(key)
    return checks


def select(checks: list[dict], modes: list[str], only: list[str]) -> list[dict]:
    by_id = {item["id"]: item for item in checks}
    unknown = [key for key in only if key not in by_id]
    if unknown:
        raise ValueError(f"no check named {', '.join(unknown)}")
    chosen = {item["id"] for item in checks if set(item["modes"]) & set(modes)} | set(only)
    if not chosen:
        raise ValueError(f"mode {', '.join(modes)} selects no check")
    pending = list(chosen)
    while pending:
        for need in by_id[pending.pop()]["needs"]:
            if need not in chosen:
                chosen.add(need)
                pending.append(need)
    return [item for item in checks if item["id"] in chosen]


def terminate(group: int, sig: int) -> None:
    try:
        os.killpg(group, sig)
    except ProcessLookupError:
        pass


RUNNING: list[int] = []


def stop_running(signum, frame) -> None:
    """A check runs in its own process group; end it with this script."""
    for group in RUNNING:
        terminate(group, signal.SIGTERM)
    raise SystemExit(128 + signum)


def execute(item: dict, root: Path) -> tuple[str, str, float]:
    start = time.monotonic()
    try:
        process = subprocess.Popen(item["command"], cwd=root, stdout=subprocess.PIPE,
                                   stderr=subprocess.STDOUT, start_new_session=True)
    except OSError as error:
        return "failed", f"could not start: {error}\n", time.monotonic() - start
    RUNNING[:] = [process.pid]
    try:
        output, _ = process.communicate(timeout=item["timeout"])
        status = "passed" if process.returncode == 0 else f"failed (exit {process.returncode})"
    except subprocess.TimeoutExpired:
        terminate(process.pid, signal.SIGTERM)
        try:
            output, _ = process.communicate(timeout=10)
        except subprocess.TimeoutExpired:
            terminate(process.pid, signal.SIGKILL)
            output, _ = process.communicate()
        status = f"failed (timed out after {item['timeout']}s)"
    return status, output.decode("utf-8", errors="replace"), time.monotonic() - start


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    parser.add_argument("--mode", action="append", default=[], help="run the checks of this mode; repeatable")
    parser.add_argument("--only", action="append", default=[], metavar="ID", help="run this check and its needs; repeatable")
    parser.add_argument("--list", action="store_true", help="print the selected checks without running them")
    args = parser.parse_args()
    if not args.mode and not args.only:
        parser.error("give --mode or --only")
    root = args.config.resolve().parent.parent
    try:
        selected = select(load(args.config), args.mode, args.only)
    except (OSError, ValueError) as error:
        print(f"configuration error: {error}", file=sys.stderr)
        return 2
    if args.list:
        for item in selected:
            print(f"{item['id']}: {' '.join(item['command'])}")
        return 0
    signal.signal(signal.SIGTERM, stop_running)
    signal.signal(signal.SIGINT, stop_running)
    results: dict[str, str] = {}
    for item in selected:
        key = item["id"]
        if any(results[need] != "passed" for need in item["needs"]):
            results[key] = "skipped"
            print(f"== {key}: skipped, a check it needs did not pass ==", flush=True)
            continue
        print(f"== {key}: {' '.join(item['command'])} ==", flush=True)
        status, output, seconds = execute(item, root)
        results[key] = status
        sys.stdout.write(output if output.endswith("\n") or not output else output + "\n")
        print(f"== {key}: {status} in {seconds:.1f}s ==", flush=True)
    failed = [key for key, status in results.items() if status != "passed"]
    print("Summary: " + ", ".join(f"{key} {status}" for key, status in results.items()))
    return int(bool(failed))


if __name__ == "__main__":
    raise SystemExit(main())
