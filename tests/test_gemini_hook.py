"""Tool policy rules and the hook's stdin, stdout and audit contract."""
from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
from typing import Any
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import gemini_hook


class HookTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.base = Path(temporary.name).resolve()
        self.root = self.base / "project"
        self.root.mkdir()
        self.extra = self.base / "read"
        self.extra.mkdir()
        self.run = self.base / "run"
        self.run.mkdir()
        self.policy: dict[str, Any] = {"root": str(self.root), "read": [str(self.extra)],
                                      "write": ["guide.md", "docs/"],
                                      "commands": ["cat", "rg", "find", "git diff"], "web": False}
        self.path = self.run / "policy.json"
        self.path.write_text(json.dumps(self.policy), encoding="utf-8")

    def event(self, tool: str, **args: Any) -> dict[str, Any]:
        return {"stepIdx": 7, "toolCall": {"name": tool, "args": args}}

    def decision(self, tool: str, **args: Any) -> str:
        return gemini_hook.decide(self.event(tool, **args), self.policy)[0]

    def invoke(self, event: dict[str, Any], mode: str = "tool",
               policy: str | None = "default") -> subprocess.CompletedProcess[str]:
        env = dict(os.environ)
        env.pop("LONGRUN_GEMINI_POLICY", None)
        if policy is not None:
            env["LONGRUN_GEMINI_POLICY"] = str(self.path) if policy == "default" else policy
        return subprocess.run([sys.executable, str(ROOT / "scripts/gemini_hook.py"), mode],
                              input=json.dumps(event), capture_output=True, text=True, env=env)

    def test_read_in_root(self) -> None:
        self.assertEqual(self.decision("read_file", Path=str(self.root / "a")), "allow")

    def test_read_in_extra_root(self) -> None:
        self.assertEqual(self.decision("read_file", Path=str(self.extra / "a")), "allow")

    def test_read_relative_to_root(self) -> None:
        self.assertEqual(self.decision("read_file", Path="docs/a.md"), "allow")

    def test_read_outside_roots(self) -> None:
        self.assertEqual(self.decision("read_file", Path=str(self.base / "outside")), "deny")

    def test_read_missing_path(self) -> None:
        self.assertEqual(self.decision("read_file"), "deny")

    def test_environment_paths_are_denied_for_every_tool(self) -> None:
        for tool in ("read_file", "write_file", "edit_file", "search_web", "manage_task"):
            for path in (".env", "docs/.env.local"):
                with self.subTest(tool=tool, path=path):
                    self.assertEqual(self.decision(tool, Path=path), "deny")

    def test_environment_command_arguments(self) -> None:
        for cmd in ("cat .env", f"cat {self.root}/.env.production", 'cat "docs/.env.local"'):
            with self.subTest(cmd=cmd):
                self.assertEqual(self.decision("run_command", CommandLine=cmd), "deny")

    def test_symlinked_root(self) -> None:
        link = self.base / "linked"
        link.symlink_to(self.root, target_is_directory=True)
        self.policy["root"] = str(link)
        self.assertEqual(self.decision("read_file", Path=str(self.root / "file")), "allow")
        self.assertEqual(self.decision("write_file", Path=str(link / "guide.md")), "allow")

    def test_symlink_cannot_escape_root(self) -> None:
        (self.root / "docs").symlink_to(self.extra, target_is_directory=True)
        self.assertEqual(self.decision("write_file", Path="docs/new.md"), "deny")
        self.assertEqual(self.decision("read_file", Path="docs/new.md"), "allow")

    def test_env_symlink_is_denied(self) -> None:
        (self.root / "alias").symlink_to(self.root / ".env")
        self.assertEqual(self.decision("read_file", Path="alias"), "deny")

    def test_exact_write_and_edit(self) -> None:
        for tool in ("write_file", "edit_file"):
            self.assertEqual(self.decision(tool, Path="guide.md"), "allow")
            self.assertEqual(self.decision(tool, Path="guide.md.bak"), "deny")

    def test_directory_write(self) -> None:
        self.assertEqual(self.decision("write_file", Path="docs/deep/new.md"), "allow")
        self.assertEqual(self.decision("write_file", Path="docs-other/new.md"), "deny")

    def test_write_outside_root(self) -> None:
        self.assertEqual(self.decision("write_file", Path=str(self.extra / "guide.md")), "deny")

    def test_empty_write_set(self) -> None:
        self.policy["write"] = []
        self.assertEqual(self.decision("edit_file", Path="guide.md"), "deny")

    def test_allowed_command_prefix(self) -> None:
        self.assertEqual(self.decision("run_command", CommandLine="git diff --stat"), "allow")
        self.assertEqual(self.decision("run_command", CommandLine="git difference"), "deny")

    def test_unlisted_command(self) -> None:
        self.assertEqual(self.decision("run_command", CommandLine="touch new"), "deny")

    def test_compound_commands_and_redirections(self) -> None:
        for cmd in ("cat a; cat b", "cat a && cat b", "cat a | cat", "cat a > b", "cat < a",
                    "(cat a)", "cat a &"):
            with self.subTest(cmd=cmd):
                self.assertEqual(self.decision("run_command", CommandLine=cmd), "deny")

    def test_substitutions_and_newlines(self) -> None:
        for cmd in ("cat a\ncat b", "cat `pwd`", "cat $(pwd)", "cat ${FILE}"):
            with self.subTest(cmd=cmd):
                self.assertEqual(self.decision("run_command", CommandLine=cmd), "deny")

    def test_find_read_and_mutating_options(self) -> None:
        self.assertEqual(self.decision("run_command", CommandLine="find . -name '*.py'"), "allow")
        for option in ("-exec", "-execdir", "-ok", "-okdir", "-delete", "-fprint", "-fprint0", "-fprintf", "-fls"):
            with self.subTest(option=option):
                self.assertEqual(self.decision("run_command", CommandLine=f"find . {option} x"), "deny")

    def test_rg_preprocessor(self) -> None:
        self.assertEqual(self.decision("run_command", CommandLine="rg text ."), "allow")
        for arg in ("--pre=tool", "--pre tool", "--pre-glob=*.md"):
            self.assertEqual(self.decision("run_command", CommandLine=f"rg {arg} text"), "deny")

    def test_absolute_argument_roots(self) -> None:
        self.assertEqual(self.decision("run_command", CommandLine=f"cat {self.extra}/a"), "allow")
        self.assertEqual(self.decision("run_command", CommandLine=f"cat {self.base}/outside"), "deny")

    def test_home_argument_outside_roots(self) -> None:
        self.assertEqual(self.decision("run_command", CommandLine="cat ~/outside"), "deny")

    def test_command_cwd(self) -> None:
        self.assertEqual(self.decision("run_command", CommandLine="git diff", Cwd=str(self.extra)), "allow")
        self.assertEqual(self.decision("run_command", CommandLine="git diff", Cwd=str(self.base)), "deny")

    def test_web_search_policy(self) -> None:
        self.assertEqual(self.decision("search_web", query="json"), "deny")
        self.policy["web"] = True
        self.assertEqual(self.decision("search_web", query="json"), "allow")

    def test_task_actions(self) -> None:
        for action in ("list", "status"):
            self.assertEqual(self.decision("manage_task", Action=action), "allow")
        for action in ("kill", "send_input", ""):
            self.assertEqual(self.decision("manage_task", Action=action), "deny")

    def test_question_reason(self) -> None:
        decision, reason = gemini_hook.decide(self.event("ask_question"), self.policy)
        self.assertEqual(decision, "deny")
        self.assertEqual(reason, "No one can answer during this run. Put the question in your final message and stop.")

    def test_unknown_tool(self) -> None:
        for tool in ("schedule", "send_message", "define_subagent", "invoke_subagent", "manage_subagents", "unknown"):
            decision, reason = gemini_hook.decide(self.event(tool), self.policy)
            self.assertEqual(decision, "deny")
            self.assertIn(tool, reason)

    def test_unreadable_policy_denies_and_logs(self) -> None:
        self.path.unlink()
        result = self.invoke(self.event("read_file", Path="guide.md"))
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["decision"], "deny")
        self.assertEqual(len((self.run / "tools.jsonl").read_text().splitlines()), 1)

    def test_invalid_policy_denies(self) -> None:
        self.path.write_text("not JSON", encoding="utf-8")
        result = self.invoke(self.event("read_file", Path="guide.md"))
        self.assertEqual(result.returncode, 0)
        self.assertEqual(json.loads(result.stdout)["decision"], "deny")

    def test_exception_in_deciding_denies(self) -> None:
        result = self.invoke(self.event("run_command", CommandLine="cat 'unclosed"))
        self.assertEqual(result.returncode, 0)
        self.assertEqual(json.loads(result.stdout)["decision"], "deny")

    def test_neutral_when_variable_unset_or_empty(self) -> None:
        for policy in (None, ""):
            result = self.invoke({}, policy=policy)
            self.assertEqual((result.returncode, result.stdout), (0, ""))
        self.assertFalse((self.run / "tools.jsonl").exists())

    def test_start_marker_and_neutral_output(self) -> None:
        for _ in range(2):
            result = self.invoke({"conversationId": "session-123"}, mode="start")
            self.assertEqual((result.returncode, result.stdout), (0, ""))
        entries = [json.loads(line) for line in (self.run / "hook-started").read_text().splitlines()]
        self.assertEqual(len(entries), 2)
        self.assertEqual(entries[0]["conversation_id"], "session-123")
        self.assertTrue(entries[0]["time"])

    def test_one_audit_line_per_tool_with_shortened_strings(self) -> None:
        for content in ("a" * 401, "a" * 400):
            result = self.invoke(self.event("write_file", Path="guide.md", Content=content))
            self.assertEqual(json.loads(result.stdout)["decision"], "allow")
        entries = [json.loads(line) for line in (self.run / "tools.jsonl").read_text().splitlines()]
        self.assertEqual(len(entries), 2)
        self.assertEqual(entries[0], {"step": 7, "tool": "write_file",
                                     "args": {"Path": "guide.md", "Content": "<401 chars>"},
                                     "decision": "allow", "reason": "The file is inside the permitted write set."})
        self.assertEqual(entries[1]["args"]["Content"], "a" * 400)


if __name__ == "__main__":
    unittest.main()
