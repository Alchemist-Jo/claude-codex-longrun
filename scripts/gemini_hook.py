"""Enforce a per-run Gemini tool policy and record every tool decision.

Called as gemini_hook.py start|tool with a JSON event on stdin. An unset or
empty LONGRUN_GEMINI_POLICY leaves interactive sessions unchanged.
PreInvocation calls start to append hook-started, including on resume.
Tool events write tools.jsonl and always return an allow or deny decision,
including when the policy or event is invalid; audit failures write hook-error.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
import os
from pathlib import Path
import shlex
import sys
from typing import Any


def canonical(path: str, root: Path) -> Path:
    return Path(os.path.realpath(root / path))


def inside(path: Path, roots: list[Path]) -> bool:
    return any(path.is_relative_to(root) for root in roots)


def env_path(path: Path) -> bool:
    return path.name == ".env" or path.name.startswith(".env.")


def shell_syntax_error(cmd: str) -> str | None:
    quote = ""
    for char in cmd:
        if quote == "'":
            if char == "'":
                quote = ""
        elif quote == '"':
            if char in "$`\\":
                return "Use double quotes without variables, substitutions or backslashes."
            if char == '"':
                quote = ""
        elif char in "'\"":
            quote = char
        elif char in ";&|<>()$`{}\\*?[\n\r":
            return "Use one allowed program with quoted arguments and no shell operators, expansions or unquoted globs."
    if quote:
        return "Close each quoted command argument."
    return None


def denied_option(argv: list[str]) -> tuple[str, str] | None:
    program = Path(argv[0]).name
    for index, arg in enumerate(argv[1:], 1):
        option, _, value = arg.partition("=")
        short = arg[1:] if arg.startswith("-") and not arg.startswith("--") else ""
        if program == "find" and (option in {
            "-exec", "-execdir", "-ok", "-okdir", "-delete", "-fprint", "-fprint0", "-fprintf", "-fls", "-follow"
        } or "L" in short):
            return arg, "use find -name for path listing without following links or performing actions"
        if program == "rg" and (arg.startswith(("--pre", "--no-ignore"))
                                or option in {"--hostname-bin", "--hidden", "--follow"}
                                or any(char in short for char in "Lu.")):
            return arg, "use rg with its default ignore and link rules"
        if program == "grep":
            directory_value = value or (argv[index + 1] if index + 1 < len(argv) else "")
            if (option in {"--recursive", "--dereference-recursive"}
                    or (option in {"--directories", "-d"} and directory_value == "recurse")
                    or arg == "-drecurse" or any(char in short for char in "rRSO")):
                return arg, "use rg for recursive search"
        if program == "git" and (arg.startswith(("--open-files-in-pager", "--output"))
                                 or option in {"--ext-diff", "--no-index", "--untracked"}
                                 or (index > 1 and "O" in short)):
            return arg, "use git show, git diff or git grep without external programs or file output"
    return None


def command_candidates(arg: str) -> list[str]:
    if not arg.startswith("-"):
        return [arg]
    if arg.startswith("--"):
        return [arg.split("=", 1)[1]] if "=" in arg else []
    return [arg[2:]] if len(arg) > 2 else []


def command_decision(args: dict[str, Any], policy: dict[str, Any], roots: list[Path],
                     root: Path) -> tuple[str, str]:
    cmd = args.get("CommandLine", "")
    error = shell_syntax_error(cmd)
    if error:
        return "deny", error
    argv = shlex.split(cmd)
    prefixes = [shlex.split(entry) for entry in policy["commands"]]
    if not argv or not any(prefix and argv[:len(prefix)] == prefix for prefix in prefixes):
        return "deny", "Use an allowed command prefix: " + ", ".join(policy["commands"]) + "."
    option = denied_option(argv)
    if option:
        return "deny", f"Option {option[0]} is denied; {option[1]}."
    cwd = canonical(args.get("Cwd", str(root)), root)
    for arg in argv[1:]:
        for candidate in command_candidates(arg):
            for piece in [candidate, *candidate.split(":")]:
                path = canonical(os.path.expanduser(piece), cwd)
                if env_path(Path(piece)) or env_path(path):
                    return "deny", "Use paths whose basename is neither .env nor a name starting with .env."
                if path.exists() and not inside(path, roots):
                    return "deny", f"Path {piece!r} is outside the read roots; use files inside a read root."
    if "Cwd" in args and (env_path(Path(args["Cwd"])) or env_path(cwd)):
        return "deny", "Use a Cwd whose basename is neither .env nor a name starting with .env."
    if not inside(cwd, roots):
        return "deny", "Run commands with Cwd inside a read root."
    return "allow", "The command matches an allowed read-only prefix."


def decide(event: dict[str, Any], policy: dict[str, Any]) -> tuple[str, str]:
    tool = event["toolCall"]["name"]
    args = event["toolCall"].get("args", {})
    root = Path(os.path.realpath(policy["root"]))
    roots = [root, *(canonical(path, root) for path in policy["read"])]
    if tool in {"read_file", "write_file", "edit_file"}:
        if not args.get("Path"):
            return "deny", "Supply Path inside a read root or the permitted write set."
        path = canonical(args["Path"], root)
        if env_path(Path(args["Path"])) or env_path(path):
            return "deny", "Use paths whose basename is neither .env nor a name starting with .env."
        if tool == "read_file":
            if inside(path, roots):
                return "allow", "The file is inside a read root."
            return "deny", "Read files only inside the read roots."
        if path.is_relative_to(root):
            for entry in policy["write"]:
                target = canonical(entry, root)
                if path == target or (entry.endswith("/") and path.is_relative_to(target)):
                    return "allow", "The file is inside the permitted write set."
        return "deny", "Write only the listed files or paths inside listed directories under the working directory."
    if tool == "run_command":
        return command_decision(args, policy, roots, root)
    if tool == "search_web":
        return ("allow", "Web search is permitted.") if policy["web"] else (
            "deny", "Use the supplied files and read roots because web search is disabled.")
    if tool == "manage_task":
        if args.get("Action") in {"list", "status"}:
            return "allow", "Task listing and status are permitted."
        return "deny", "Use manage_task only with Action list or status."
    if tool == "ask_question":
        return "deny", "No one can answer during this run. Put the question in your final message and stop."
    return "deny", f"Tool {tool} is unavailable; use file tools, allowed read-only commands or permitted web search."


def shortened(value: Any) -> Any:
    if isinstance(value, str) and len(value) > 400:
        return f"<{len(value)} chars>"
    if isinstance(value, dict):
        return {key: shortened(item) for key, item in value.items()}
    if isinstance(value, list):
        return [shortened(item) for item in value]
    return value


def one_line(value: object) -> str:
    return " ".join(str(value).splitlines())


def main() -> int:
    policy_path = os.environ.get("LONGRUN_GEMINI_POLICY")
    if not policy_path:
        return 0
    event: dict[str, Any] = {}
    try:
        event = json.load(sys.stdin)
        if sys.argv[1:] == ["start"]:
            with open(Path(policy_path).with_name("hook-started"), "a", encoding="utf-8") as output:
                output.write(json.dumps({"conversation_id": event.get("conversationId", ""),
                                         "invocationNum": event.get("invocationNum"),
                                         "time": datetime.now(timezone.utc).isoformat()}) + "\n")
            return 0
        if sys.argv[1:] != ["tool"]:
            raise ValueError("Use gemini_hook.py start or tool.")
        policy = json.loads(Path(policy_path).read_text(encoding="utf-8"))
        decision, reason = decide(event, policy)
    except Exception as error:
        decision, reason = "deny", f"Policy evaluation failed: {one_line(error)}"
    try:
        call = event.get("toolCall", {}) if isinstance(event, dict) else {}
        record = {"step": event.get("stepIdx") if isinstance(event, dict) else None,
                  "tool": call.get("name"), "args": shortened(call.get("args", {})),
                  "decision": decision, "reason": reason}
        with open(Path(policy_path).with_name("tools.jsonl"), "a", encoding="utf-8") as output:
            output.write(json.dumps(record) + "\n")
    except Exception as error:
        decision, reason = "deny", f"Policy audit failed: {one_line(error)}"
        try:
            Path(policy_path).with_name("hook-error").write_text(reason + "\n", encoding="utf-8")
        except OSError as marker_error:
            print(f"{reason}; cannot write hook-error: {one_line(marker_error)}", file=sys.stderr)
    print(json.dumps({"decision": decision, "reason": reason}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
