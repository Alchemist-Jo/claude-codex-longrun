"""Run a headless Gemini worker with a recorded tool policy and checked result.

    gemini_run.py --run RUN --root DIR [--read DIR]... [--write PATH]... \\
        [--command CMD]... [--web] [--conversation ID] [--timeout SECONDS] \\
        --prompt-file FILE -- AGY [ARG...]
    gemini_run.py --preflight --run RUN --root DIR -- AGY [ARG...]

RUN must exist without artifacts from a worker run. DIR and read roots are
absolute directories; write entries are relative files or directories ending
with /.
The project must install gemini_hook.py and enable its PreInvocation and
PreToolUse commands in DIR/.agents/hooks.json.

Steps: validate the hooks and fresh preflight record, write policy.json,
launch AGY in its own process group with closed stdin and read-only shell
sandboxing, then check hook-started, hook-error, process status, result.json, tool
denials and the final response. Logs and session data stay in RUN. Preflight
runs six probes in new subdirectories and records their results beside runs/.

Exit statuses: 0 success, 1 failed, interrupted or timed out, 2 invalid launch inputs or
missing/stale preflight, 3 blocked by a tool denial. A judged run prints one
gemini_run: VERDICT reason line; invalid inputs print one reason to stderr.
"""
from __future__ import annotations

import argparse
import contextlib
from datetime import datetime, timezone
import io
import json
import math
import os
from pathlib import Path
import re
import shutil
import signal
import subprocess
import sys
from types import FrameType
from typing import Any

DEFAULT_COMMANDS = ["ls", "cat", "head", "tail", "wc", "pwd", "rg", "grep", "find",
                    "git status", "git diff", "git log", "git show", "git ls-files",
                    "git grep", "git rev-parse", "git blame"]


def one_line(value: object) -> str:
    return " ".join(str(value).splitlines())


def preflight_freshness(record: Path) -> str | None:
    """Return None for a passing probe record matching agy on PATH, else a reason."""
    suffix = "; run gemini_run.py --preflight"
    try:
        data = json.loads(record.read_text(encoding="utf-8"))
        if not isinstance(data, dict) or data.get("passed") is not True:
            return "Gemini preflight has not passed" + suffix
        binary = shutil.which("agy")
        if not binary:
            return "agy is not on PATH" + suffix
        actual = Path(binary).resolve()
        if data.get("agy") != str(actual):
            return "Gemini preflight names a different agy binary" + suffix
        if data.get("agy_mtime") != actual.stat().st_mtime:
            return "agy changed since Gemini preflight" + suffix
    except (OSError, ValueError) as error:
        return f"Gemini preflight record is unavailable: {one_line(error)}" + suffix
    return None


def check_hooks(root: Path) -> None:
    path = root / ".agents/hooks.json"
    hooks = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(hooks, dict):
        for named in hooks.values():
            if not isinstance(named, dict) or named.get("enabled") is not True:
                continue
            starts = named.get("PreInvocation", [])
            tools = named.get("PreToolUse", [])
            if (any(entry.get("type", "command") == "command"
                    and entry.get("command", "").endswith("gemini_hook.py start") for entry in starts)
                    and any(entry.get("matcher", "") in {".*", "*", ""}
                            and any(hook.get("type", "command") == "command"
                                    and hook.get("command", "").endswith("gemini_hook.py tool")
                                    for hook in entry.get("hooks", [])) for entry in tools)):
                return
    raise ValueError(f"{path} must enable gemini_hook.py start for PreInvocation and gemini_hook.py tool for all PreToolUse calls")


def validate(args: argparse.Namespace, require_fresh: bool) -> None:
    if not args.run.is_dir():
        raise ValueError(f"run directory does not exist: {args.run}")
    for name in ("policy.json", "hook-started", "hook-error", "tools.jsonl", "result.json", "session", "last-message.md"):
        if os.path.lexists(args.run / name):
            raise ValueError(f"run directory already holds {name}: {args.run}")
    for label, path in [("root", args.root), *(("read", path) for path in args.read)]:
        if not path.is_absolute() or not path.is_dir():
            raise ValueError(f"{label} must be an existing absolute directory: {path}")
    for path in args.write:
        if not path or Path(path).is_absolute() or ".." in Path(path).parts or re.search(r"[*?\[]", path):
            raise ValueError(f"write path {path!r} must be relative, without .. or globs; mark directories with a trailing /")
    if not math.isfinite(args.timeout) or args.timeout <= 0:
        raise ValueError("timeout must be a positive number of seconds")
    if not args.agy:
        raise ValueError("supply AGY [ARG...] after --")
    try:
        check_hooks(args.root)
    except (OSError, ValueError, TypeError, AttributeError) as error:
        raise ValueError(f"Gemini hooks are unavailable: {one_line(error)}") from error
    if require_fresh:
        reason = preflight_freshness(args.run.parent.parent / "gemini-preflight.json")
        if reason:
            raise ValueError(reason)


def prompt_text(policy: dict[str, Any], prompt: str) -> str:
    return (
        f"Working directory: {policy['root']}; all relative paths resolve against it.\n"
        f"Read roots: {json.dumps([policy['root'], *policy['read']])}.\n"
        + (f"Write set: {json.dumps(policy['write'])}.\n" if policy["write"] else "Nothing may be written.\n")
        + f"Allowed command prefixes: {json.dumps(policy['commands'])}.\n"
        + f"Web search is {'allowed' if policy['web'] else 'disabled'}. Shell commands are read-only.\n"
        + "Shell commands can read only inside the working directory because the sandbox blocks the rest; "
          "read files in the other read roots with the file tool.\n"
        + "A command is one allowed program with quoted arguments, without pipes, redirection, variables, "
          "command substitution, braces or unquoted glob characters; use rg for recursive search.\n"
        + "A call outside this policy is denied and ends the run as blocked; if the task needs more, "
          "stop and say what is needed in your final message.\n\n" + prompt
    )


def terminate_group(process: subprocess.Popen[bytes]) -> None:
    try:
        os.killpg(process.pid, signal.SIGTERM)
    except ProcessLookupError:
        pass
    try:
        process.wait(timeout=30)
    except subprocess.TimeoutExpired:
        pass
    # The group may still contain children after its leader exits.
    try:
        os.killpg(process.pid, signal.SIGKILL)
    except ProcessLookupError:
        pass
    process.wait()


def verdict(status: int, reason: str) -> int:
    label = {0: "SUCCESS", 1: "FAILED", 3: "BLOCKED"}[status]
    print(f"gemini_run: {label} {one_line(reason)}")
    return status


def judge(run: Path, returncode: int, killed: bool) -> int:
    data: Any = None
    parse_error = ""
    try:
        data = json.loads((run / "result.json").read_text(encoding="utf-8"))
    except (OSError, ValueError) as error:
        parse_error = one_line(error)
    if isinstance(data, dict):
        response = data.get("response", "")
        session = data.get("conversation_id", "")
        (run / "last-message.md").write_text(response if isinstance(response, str) else "", encoding="utf-8")
        (run / "session").write_text(str(session), encoding="utf-8")
    if not (run / "hook-started").is_file():
        return verdict(1, "the policy hook did not run (hook-started is missing)")
    if (run / "hook-error").exists():
        return verdict(1, "the policy hook could not record its audit; see hook-error")
    stderr = (run / "agy-stderr.log").read_text(encoding="utf-8", errors="replace")
    if killed or "print timeout after" in stderr:
        return verdict(1, "agy timed out")
    if returncode != 0:
        return verdict(1, f"agy exited with status {returncode}")
    if not isinstance(data, dict):
        return verdict(1, f"result.json is not a JSON object: {parse_error or 'unexpected JSON type'}")
    if data.get("status") != "SUCCESS":
        return verdict(1, f"agy status is {data.get('status')!r}, expected SUCCESS")
    denied = len(data.get("denied_actions") or [])
    tools = run / "tools.jsonl"
    if tools.exists():
        try:
            denied += sum(json.loads(line).get("decision") == "deny"
                          for line in tools.read_text(encoding="utf-8").splitlines())
        except (OSError, ValueError, AttributeError) as error:
            return verdict(1, f"cannot read tools.jsonl: {one_line(error)}")
    if denied:
        return verdict(3, f"{denied} denied tool action(s); see {tools}")
    if not isinstance(response, str) or not response.strip():
        return verdict(1, "agy returned an empty response")
    return verdict(0, "agy completed with a response and no denied tools")


def execute(args: argparse.Namespace, prompt: str | None = None, require_fresh: bool = True) -> int:
    try:
        validate(args, require_fresh)
        if prompt is None:
            if args.prompt_file is None:
                raise ValueError("--prompt-file is required for a worker run")
            prompt = args.prompt_file.read_text(encoding="utf-8")
        policy = {"root": str(args.root.resolve()), "read": [str(path.resolve()) for path in args.read],
                  "write": args.write, "commands": [*DEFAULT_COMMANDS, *args.command], "web": args.web}
        policy_path = args.run / "policy.json"
        with policy_path.open("x", encoding="utf-8") as output:
            json.dump(policy, output, indent=2)
        (args.run / "tools.jsonl").touch(exist_ok=False)
    except (OSError, ValueError) as error:
        print(f"gemini_run: {one_line(error)}", file=sys.stderr)
        return 2
    command = [*args.agy, "--output-format", "json", "--print-timeout", f"{args.timeout:g}s",
               "--log-file", str(args.run / "agy.log"), "--sandbox", "--dangerously-skip-permissions",
               "--disable-slash-commands"]
    if args.conversation:
        command.extend(["--conversation", args.conversation])
    command.extend(["-p", prompt_text(policy, prompt)])
    env = dict(os.environ, LONGRUN_GEMINI_POLICY=str(policy_path))
    killed = False
    process: subprocess.Popen[bytes] | None = None
    interrupted: int | None = None
    signals = (signal.SIGTERM, signal.SIGINT, signal.SIGHUP)
    previous = {signum: signal.getsignal(signum) for signum in signals}

    def interrupt(signum: int, frame: FrameType | None) -> None:
        nonlocal interrupted
        interrupted = signum
        if process is not None:
            for watched in signals:
                signal.signal(watched, signal.SIG_IGN)
            terminate_group(process)
            raise InterruptedError(signum, f"interrupted by signal {signum}")

    try:
        for signum in signals:
            signal.signal(signum, interrupt)
        with open(args.run / "result.json", "wb") as stdout, open(args.run / "agy-stderr.log", "wb") as stderr:
            process = subprocess.Popen(command, cwd=args.root, stdin=subprocess.DEVNULL,
                                       stdout=stdout, stderr=stderr, env=env, start_new_session=True)
            if interrupted is not None:
                interrupt(interrupted, None)
            try:
                returncode = process.wait(timeout=args.timeout + 300)
            except subprocess.TimeoutExpired:
                killed = True
                terminate_group(process)
                returncode = process.wait()
        return judge(args.run, returncode, killed)
    except InterruptedError:
        raise
    except (OSError, ValueError, TypeError) as error:
        return verdict(1, f"agy run failed: {one_line(error)}")
    finally:
        for signum, handler in previous.items():
            signal.signal(signum, handler)


def preflight(args: argparse.Namespace) -> int:
    try:
        validate(args, require_fresh=False)
        record_path = args.run.parent.parent / "gemini-preflight.json"
        if record_path.is_dir() or not record_path.parent.is_dir():
            raise ValueError(f"preflight record must be a file in an existing directory: {record_path}")
        binary = shutil.which("agy")
        if not binary:
            raise ValueError("agy is not on PATH")
        actual = Path(binary).resolve()
        mtime = actual.stat().st_mtime
        first_line = next(line for line in (args.root / "AGENTS.md").read_text(encoding="utf-8").splitlines()
                          if line.strip())
        head = subprocess.run(["git", "rev-parse", "HEAD"], cwd=args.root, capture_output=True,
                              text=True, check=True).stdout.strip()
        names = ("reply", "read", "command", "deny-command", "deny-write", "search")
        for name in names:
            if (args.run / name).exists():
                raise ValueError(f"probe directory already exists: {args.run / name}")
    except (OSError, ValueError, StopIteration, subprocess.CalledProcessError) as error:
        print(f"gemini_run: preflight inputs unavailable: {one_line(error)}", file=sys.stderr)
        return 2
    probes = [
        ("reply", "Reply with the single word READY.", 0, "READY"),
        ("read", "Read AGENTS.md in the working directory with your file tool and reply with its first line only.", 0, first_line),
        ("command", "Run `git rev-parse HEAD` and reply with its output only.", 0, head[:7]),
        ("deny-command", "This run tests that the policy hook denies a command. Call run_command with exactly "
         "`touch longrun-preflight-probe`; the call is expected to be denied. Then reply with the denial reason you received.", 3, ""),
        ("deny-write", "This run tests that the policy hook denies a write. Call write_file to create "
         "longrun-preflight-probe.md containing x; the call is expected to be denied. Then reply with the denial reason you received.", 3, ""),
        ("search", "Search the web for the Python documentation page of the json module and reply with its URL only.", 0, "docs.python.org"),
    ]
    results: dict[str, dict[str, Any]] = {}
    for name, prompt, expected_exit, expected_text in probes:
        probe = argparse.Namespace(**vars(args))
        probe.run = args.run / name
        try:
            probe.run.mkdir()
        except OSError as error:
            print(f"gemini_run: preflight setup failed: {one_line(error)}", file=sys.stderr)
            return 2
        probe.read, probe.write, probe.command = [], [], []
        probe.web, probe.timeout, probe.conversation = name == "search", 300, None
        with contextlib.redirect_stdout(io.StringIO()) as output:
            status = execute(probe, prompt, require_fresh=False)
        message = probe.run / "last-message.md"
        try:
            response = message.read_text(encoding="utf-8") if message.is_file() else ""
            tools = [json.loads(line) for line in (probe.run / "tools.jsonl").read_text(encoding="utf-8").splitlines()]
        except (OSError, ValueError) as error:
            print(f"gemini_run: preflight artifacts unavailable: {one_line(error)}", file=sys.stderr)
            return 2
        passed = status == expected_exit and expected_text in response
        if name == "deny-command":
            passed = (passed and any(tool.get("decision") == "deny" and tool.get("tool") == "run_command" for tool in tools)
                      and not (args.root / "longrun-preflight-probe").exists())
        if name == "deny-write":
            passed = (passed and any(tool.get("decision") == "deny" and tool.get("tool") in {"write_file", "edit_file"}
                                     for tool in tools) and not (args.root / "longrun-preflight-probe.md").exists())
        detail = f"exit {status}, expected {expected_exit}; {output.getvalue().strip()}; response {response!r}"
        results[name] = {"exit": status, "passed": passed, "detail": detail}
        print(f"gemini_run: preflight {name} {'PASS' if passed else 'FAIL'} {one_line(detail)}")
    passed = all(probe["passed"] for probe in results.values())
    record = {"time": datetime.now(timezone.utc).isoformat(), "agy": str(actual), "agy_mtime": mtime,
              "command": args.agy, "probes": results, "passed": passed}
    try:
        record_path.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    except OSError as error:
        print(f"gemini_run: cannot write preflight record: {one_line(error)}", file=sys.stderr)
        return 2
    return 0 if passed else 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--run", required=True, type=Path)
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--read", action="append", type=Path, default=[])
    parser.add_argument("--write", action="append", default=[])
    parser.add_argument("--command", action="append", default=[])
    parser.add_argument("--web", action="store_true")
    parser.add_argument("--conversation")
    parser.add_argument("--timeout", type=float, default=3600)
    parser.add_argument("--prompt-file", type=Path)
    parser.add_argument("--preflight", action="store_true")
    parser.add_argument("agy", nargs=argparse.REMAINDER, metavar="AGY [ARG...]")
    args = parser.parse_args()
    if args.agy[:1] == ["--"]:
        args.agy = args.agy[1:]
    args.run = args.run.resolve()
    try:
        return preflight(args) if args.preflight else execute(args)
    except InterruptedError as error:
        return verdict(1, f"interrupted by signal {error.errno}")


if __name__ == "__main__":
    raise SystemExit(main())
