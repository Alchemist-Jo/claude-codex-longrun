"""Enforce a per-run Gemini tool policy and record every tool decision.

Called as gemini_hook.py start|tool with a JSON event on stdin. An unset or
empty LONGRUN_GEMINI_POLICY leaves interactive sessions unchanged. Start
events write hook-started; tool events write tools.jsonl and always return
an allow or deny decision, including when the policy or event is invalid.
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


def env_path(value: Any) -> bool:
    if isinstance(value, dict):
        return any(env_path(item) for item in value.values())
    if isinstance(value, list):
        return any(env_path(item) for item in value)
    if not isinstance(value, str):
        return False
    try:
        tokens = shlex.split(value)
    except ValueError:
        tokens = value.split()
    for token in [value, *tokens]:
        path = token.split("=", 1)[-1]
        name = Path(path).name
        if name == ".env" or name.startswith(".env."):
            return True
    return False


def command_decision(args: dict[str, Any], policy: dict[str, Any], roots: list[Path],
                     root: Path) -> tuple[str, str]:
    cmd = args.get("CommandLine", "")
    if any(text in cmd for text in ("\n", "\r", "`", "$(", "${")):
        return "deny", "Use one allowed read-only command without substitutions or newlines."
    lexer = shlex.shlex(cmd, posix=True, punctuation_chars=True)
    lexer.whitespace_split = True
    lexer.commenters = ""
    argv = list(lexer)
    if any(token and all(char in "();<>|&" for char in token) for token in argv):
        return "deny", "Use one allowed read-only command without shell operators or redirection."
    prefixes = [shlex.split(entry) for entry in policy["commands"]]
    if not argv or not any(prefix and argv[:len(prefix)] == prefix for prefix in prefixes):
        return "deny", "Use an allowed command prefix: " + ", ".join(policy["commands"]) + "."
    if argv[0] == "find" and any(arg in {
        "-exec", "-execdir", "-ok", "-okdir", "-delete", "-fprint", "-fprint0", "-fprintf", "-fls"
    } for arg in argv[1:]):
        return "deny", "Use find only to read paths, without execution, deletion or file output."
    if argv[0] == "rg" and any(arg.startswith("--pre") for arg in argv[1:]):
        return "deny", "Use rg without a preprocessor."
    for arg in argv:
        if arg.startswith(("/", "~")) and not inside(canonical(os.path.expanduser(arg), root), roots):
            return "deny", "Keep absolute and home-relative command paths inside the read roots."
    if "Cwd" in args and not inside(canonical(args["Cwd"], root), roots):
        return "deny", "Run commands with Cwd inside a read root."
    return "allow", "The command matches an allowed read-only prefix."


def decide(event: dict[str, Any], policy: dict[str, Any]) -> tuple[str, str]:
    tool = event["toolCall"]["name"]
    args = event["toolCall"].get("args", {})
    if env_path(args):
        return "deny", "Use paths whose basename is neither .env nor a name starting with .env."
    root = Path(os.path.realpath(policy["root"]))
    roots = [root, *(canonical(path, root) for path in policy["read"])]
    if tool in {"read_file", "write_file", "edit_file"}:
        if not args.get("Path"):
            return "deny", "Supply Path inside a read root or the permitted write set."
        path = canonical(args["Path"], root)
        if env_path(str(path)):
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
    print(json.dumps({"decision": decision, "reason": reason}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
