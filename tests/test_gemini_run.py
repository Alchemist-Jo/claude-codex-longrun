"""Launch and preflight contracts exercised with a local fake agy and real hooks."""
from __future__ import annotations

import argparse
import contextlib
import io
import json
import os
from pathlib import Path
import selectors
import shutil
import signal
import subprocess
import sys
import tempfile
from typing import Any
import unittest
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import gemini_run

FAKE_AGY = r'''
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
from typing import Any

mode = sys.argv[1]
policy_path = Path(os.environ["LONGRUN_GEMINI_POLICY"])
run = policy_path.parent
root = Path.cwd()
(run / "fake-launch.json").write_text(json.dumps({
    "argv": sys.argv[1:], "cwd": str(root), "policy": str(policy_path),
    "stdin": sys.stdin.read(), "pid": os.getpid(), "pgid": os.getpgrp()}))
hooks = json.loads((root / ".agents/hooks.json").read_text())["longrun-gemini-policy"]
event = {"conversationId": "fake-session", "workspacePaths": [str(root)]}

def invoke(command: str, payload: dict[str, Any]) -> Any:
    done = subprocess.run(command, shell=True, cwd=root / ".agents", input=json.dumps(payload),
                          text=True, capture_output=True)
    if done.returncode:
        raise RuntimeError(done.stderr)
    return json.loads(done.stdout) if done.stdout else None

if mode != "no-hook":
    for invocation in (1, 2):
        for hook in hooks["PreInvocation"]:
            invoke(hook["command"], dict(event, invocationNum=invocation, initialNumSteps=0))

def tool(name: str, args: dict[str, Any]) -> dict[str, Any]:
    payload = dict(event, stepIdx=1, toolCall={"name": name, "args": args})
    result = {"decision": "allow", "reason": "No matching hook."}
    for group in hooks["PreToolUse"]:
        matcher = group.get("matcher", "")
        if matcher in ("*", "") or re.fullmatch(matcher, name):
            for hook in group["hooks"]:
                if hook.get("type", "command") == "command":
                    result = invoke(hook["command"], payload) or result
    return result

if mode == "sleep":
    with open(os.environ["FAKE_READY_FIFO"], "w") as ready:
        ready.write(str(os.getpid()))
    while True:
        signal.pause()

response = "finished"
denied = []
status = "SUCCESS"
if mode in ("probes", "bad-probe", "native-probes"):
    name = run.name
    if name == "reply":
        response = "WRONG" if mode == "bad-probe" else "READY"
    elif name == "read":
        tool("read_file", {"Path": str(root / "AGENTS.md")})
        response = next(line for line in (root / "AGENTS.md").read_text().splitlines() if line.strip())
    elif name == "command":
        tool("run_command", {"CommandLine": "git rev-parse HEAD"})
        response = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    elif name == "deny-command":
        assert "Call run_command with exactly `touch longrun-preflight-probe`" in sys.argv[-1]
        if mode == "native-probes":
            denied = [{"action": "command", "display_name": "RunCommand"}]
            response = "Native permissions denied the call."
            print(json.dumps({"conversation_id": "fake-session", "status": status,
                              "response": response, "denied_actions": denied}))
            sys.exit(0)
        result = tool("run_command", {"CommandLine": "touch longrun-preflight-probe"})
        if result["decision"] == "allow":
            (root / "longrun-preflight-probe").touch()
        response = result["reason"]
    elif name == "deny-write":
        assert "Call write_file to create longrun-preflight-probe.md containing x" in sys.argv[-1]
        if mode == "native-probes":
            denied = [{"action": "write", "display_name": "WriteFile"}]
            print(json.dumps({"conversation_id": "fake-session", "status": status,
                              "response": "Native permissions denied the call.", "denied_actions": denied}))
            sys.exit(0)
        result = tool("write_file", {"Path": str(root / "longrun-preflight-probe.md"), "Content": "x"})
        if result["decision"] == "allow":
            (root / "longrun-preflight-probe.md").write_text("x")
        response = result["reason"]
    elif name == "search":
        tool("search_web", {"query": "Python json documentation"})
        response = "https://docs.python.org/3/library/json.html"
elif mode == "hook-deny":
    result = tool("write_file", {"Path": str(root / "outside.md"), "Content": "x"})
    if result["decision"] == "allow":
        (root / "outside.md").write_text("x")
elif mode == "audit-failure":
    (run / "tools.jsonl").unlink()
    (run / "tools.jsonl").mkdir()
    tool("read_file", {"Path": str(root / "AGENTS.md")})
elif mode == "allowed-write":
    result = tool("write_file", {"Path": str(root / "docs/guide.md"), "Content": "x"})
    if result["decision"] == "allow":
        (root / "docs").mkdir(exist_ok=True)
        (root / "docs/guide.md").write_text("x")
elif mode == "denied":
    denied = [{"action": "command", "display_name": "RunCommand"}]
    response = ""
    print("jetski: no output produced", file=sys.stderr)
elif mode == "empty":
    response = "  \n "
elif mode == "timeout":
    print("[agy] print timeout after 3s with turn in progress; returning partial output", file=sys.stderr)
    response = "partial response"
elif mode == "bad-status":
    status = "FAILED"

if mode == "non-json":
    print("invalid JSON")
elif mode == "json-list":
    print("[]")
else:
    print(json.dumps({"conversation_id": "fake-session", "status": status,
                      "response": response, "denied_actions": denied}))
sys.exit(7 if mode == "nonzero" else 0)
'''


class LauncherTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.base = Path(temporary.name).resolve()
        self.root = self.base / "project"
        (self.root / ".agents/bin").mkdir(parents=True)
        (self.root / ".git").symlink_to(ROOT / ".git", target_is_directory=(ROOT / ".git").is_dir())
        self.hooks = self.root / ".agents/hooks.json"
        shutil.copyfile(ROOT / "assets/project/gemini-hooks.json", self.hooks)
        shutil.copyfile(ROOT / "scripts/gemini_hook.py", self.root / ".agents/bin/gemini_hook.py")
        (self.root / "AGENTS.md").write_text("# Project rules\nRead first.\n", encoding="utf-8")
        self.prompt = self.root / "BRIEF.md"
        self.prompt.write_text("Do the task.", encoding="utf-8")
        self.run = self.root / ".agents/work/runs/job-r1"
        self.run.mkdir(parents=True)
        self.bin = self.base / "bin"
        self.bin.mkdir()
        self.agy = self.bin / "agy"
        self.agy.write_text(f"#!{sys.executable}\n" + FAKE_AGY, encoding="utf-8")
        self.agy.chmod(0o755)
        self.env = dict(os.environ, PATH=str(self.bin) + os.pathsep + os.environ.get("PATH", ""))
        self.record = self.run.parent.parent / "gemini-preflight.json"
        self.fresh_record()

    def fresh_record(self) -> None:
        self.record.write_text(json.dumps({"passed": True, "agy": str(self.agy),
                                           "agy_mtime": self.agy.stat().st_mtime}), encoding="utf-8")

    def launch(self, mode: str = "pass", flags: tuple[str, ...] = (), preflight: bool = False,
               command: list[str] | None = None) -> subprocess.CompletedProcess[str]:
        args = [sys.executable, str(ROOT / "scripts/gemini_run.py"), "--run", str(self.run),
                "--root", str(self.root), *flags]
        args += ["--preflight"] if preflight else ["--prompt-file", str(self.prompt)]
        return subprocess.run([*args, "--", *(command or ["agy", mode])],
                              capture_output=True, text=True, env=self.env)

    def test_pass_and_session_artifacts(self) -> None:
        result = self.launch()
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertIn("gemini_run: SUCCESS", result.stdout)
        self.assertEqual((self.run / "last-message.md").read_text(), "finished")
        self.assertEqual((self.run / "session").read_text(), "fake-session")
        self.assertEqual(len(result.stdout.splitlines()), 1)

    def test_native_denied_actions_exit_three(self) -> None:
        result = self.launch("denied")
        self.assertEqual(result.returncode, 3, result.stderr + result.stdout)
        self.assertIn("1 denied tool action(s)", result.stdout)
        self.assertIn("tools.jsonl", result.stdout)
        self.assertEqual((self.run / "last-message.md").read_text(), "")
        self.assertIn("jetski: no output produced", (self.run / "agy-stderr.log").read_text())

    def test_hook_denial_exits_three(self) -> None:
        result = self.launch("hook-deny")
        self.assertEqual(result.returncode, 3, result.stderr + result.stdout)
        self.assertEqual(json.loads((self.run / "tools.jsonl").read_text())["decision"], "deny")
        self.assertEqual(json.loads((self.run / "result.json").read_text())["denied_actions"], [])
        self.assertFalse((self.root / "outside.md").exists())

    def test_file_write_in_directory_write_set(self) -> None:
        result = self.launch("allowed-write", flags=("--write", "docs/"))
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        self.assertEqual((self.root / "docs/guide.md").read_text(), "x")

    def test_empty_response_fails(self) -> None:
        result = self.launch("empty")
        self.assertEqual(result.returncode, 1)
        self.assertIn("empty response", result.stdout)

    def test_timeout_stderr_overrides_success(self) -> None:
        result = self.launch("timeout")
        self.assertEqual(result.returncode, 1)
        self.assertIn("timed out", result.stdout)
        self.assertEqual((self.run / "last-message.md").read_text(), "partial response")

    def test_bad_status_fails(self) -> None:
        result = self.launch("bad-status")
        self.assertEqual(result.returncode, 1)
        self.assertIn("expected SUCCESS", result.stdout)

    def test_non_json_fails(self) -> None:
        result = self.launch("non-json")
        self.assertEqual(result.returncode, 1)
        self.assertIn("not a JSON object", result.stdout)

    def test_json_list_fails(self) -> None:
        result = self.launch("json-list")
        self.assertEqual(result.returncode, 1)
        self.assertIn("not a JSON object", result.stdout)

    def test_missing_hook_marker_exits_one(self) -> None:
        result = self.launch("no-hook")
        self.assertEqual(result.returncode, 1, result.stderr + result.stdout)
        self.assertIn("policy hook did not run", result.stdout)
        self.assertEqual((self.run / "session").read_text(), "fake-session")

    def test_nonzero_agy_status(self) -> None:
        result = self.launch("nonzero")
        self.assertEqual(result.returncode, 1)
        self.assertIn("status 7", result.stdout)

    def test_missing_hooks_rejected_before_launch(self) -> None:
        self.hooks.unlink()
        result = self.launch()
        self.assertEqual(result.returncode, 2)
        self.assertIn("hooks", result.stderr)
        self.assertFalse((self.run / "fake-launch.json").exists())

    def test_invalid_hooks_rejected_before_launch(self) -> None:
        self.hooks.write_text("invalid", encoding="utf-8")
        result = self.launch()
        self.assertEqual(result.returncode, 2)
        self.assertFalse((self.run / "policy.json").exists())

    def test_both_hooks_must_belong_to_same_enabled_group(self) -> None:
        hooks = json.loads(self.hooks.read_text())["longrun-gemini-policy"]
        self.hooks.write_text(json.dumps({"a": {"enabled": True, "PreInvocation": hooks["PreInvocation"]},
                                          "b": {"enabled": True, "PreToolUse": hooks["PreToolUse"]}}))
        self.assertEqual(self.launch().returncode, 2)

    def test_restrictive_matcher_is_refused_and_would_bypass_writes(self) -> None:
        hooks = json.loads(self.hooks.read_text())
        hooks["longrun-gemini-policy"]["PreToolUse"][0]["matcher"] = "^read_file$"
        self.hooks.write_text(json.dumps(hooks))
        result = self.launch("hook-deny")
        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertFalse((self.run / "fake-launch.json").exists())
        policy = {"root": str(self.root), "read": [], "write": [], "commands": gemini_run.DEFAULT_COMMANDS, "web": False}
        policy_path = self.run / "policy.json"
        policy_path.write_text(json.dumps(policy))
        direct = subprocess.run([str(self.agy), "hook-deny"], cwd=self.root, stdin=subprocess.DEVNULL,
                                capture_output=True, text=True,
                                env=dict(self.env, LONGRUN_GEMINI_POLICY=str(policy_path)))
        self.assertEqual(direct.returncode, 0, direct.stderr)
        self.assertEqual((self.root / "outside.md").read_text(), "x")
        self.assertFalse((self.run / "tools.jsonl").exists())

    def test_hook_handlers_require_exact_command_suffix_and_type(self) -> None:
        original = self.hooks.read_text()
        for field, value in (("start-command", "echo gemini_hook.py start extra"),
                             ("tool-command", "echo gemini_hook.py tool extra"),
                             ("tool-type", "prompt"), ("enabled", False)):
            with self.subTest(field=field):
                hooks = json.loads(original)
                group = hooks["longrun-gemini-policy"]
                if field == "start-command":
                    group["PreInvocation"][0]["command"] = value
                elif field == "tool-command":
                    group["PreToolUse"][0]["hooks"][0]["command"] = value
                elif field == "tool-type":
                    group["PreToolUse"][0]["hooks"][0]["type"] = value
                else:
                    group["enabled"] = value
                self.hooks.write_text(json.dumps(hooks))
                self.assertEqual(self.launch().returncode, 2)
                self.assertFalse((self.run / "policy.json").exists())

    def test_all_tool_matchers_and_absent_type_are_accepted(self) -> None:
        original = self.hooks.read_text()
        for matcher in (".*", "*", ""):
            with self.subTest(matcher=matcher):
                hooks = json.loads(original)
                group = hooks["longrun-gemini-policy"]["PreToolUse"][0]
                group["matcher"] = matcher
                group["hooks"][0].pop("type")
                self.hooks.write_text(json.dumps(hooks))
                self.run = self.run.parent / f"matcher-{len(matcher)}"
                self.run.mkdir()
                result = self.launch("hook-deny")
                self.assertEqual(result.returncode, 3, result.stdout + result.stderr)

    def test_resumed_run_proves_liveness_with_preinvocation(self) -> None:
        result = self.launch(flags=("--conversation", "existing-session"))
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        entries = [json.loads(line) for line in (self.run / "hook-started").read_text().splitlines()]
        self.assertEqual([entry["invocationNum"] for entry in entries], [1, 2])

    def test_audit_failure_is_a_failed_run(self) -> None:
        result = self.launch("audit-failure")
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        self.assertIn("hook-error", result.stdout)
        self.assertIn("Policy audit failed", (self.run / "hook-error").read_text())

    def test_missing_preflight_rejected_before_launch(self) -> None:
        self.record.unlink()
        result = self.launch()
        self.assertEqual(result.returncode, 2)
        self.assertIn("; run gemini_run.py --preflight", result.stderr)
        self.assertFalse((self.run / "fake-launch.json").exists())

    def test_stale_preflight_rejected_before_launch(self) -> None:
        stat = self.agy.stat()
        os.utime(self.agy, (stat.st_atime, stat.st_mtime + 1))
        result = self.launch()
        self.assertEqual(result.returncode, 2)
        self.assertIn("agy changed", result.stderr)
        self.assertFalse((self.run / "fake-launch.json").exists())

    def test_existing_policy_rejected(self) -> None:
        (self.run / "policy.json").write_text("{}")
        result = self.launch()
        self.assertEqual(result.returncode, 2)
        self.assertIn("already holds policy.json", result.stderr)

    def test_existing_worker_artifacts_are_refused(self) -> None:
        for name in ("hook-error", "tools.jsonl", "result.json", "session", "last-message.md"):
            with self.subTest(name=name):
                path = self.run / name
                path.touch()
                result = self.launch()
                self.assertEqual(result.returncode, 2)
                self.assertIn(f"already holds {name}", result.stderr)
                self.assertFalse((self.run / "fake-launch.json").exists())
                path.unlink()

    def test_old_hook_marker_cannot_prove_liveness_for_a_new_run(self) -> None:
        (self.run / "hook-started").write_text("old session\n")
        result = self.launch("no-hook")
        self.assertEqual(result.returncode, 2)
        self.assertIn("already holds hook-started", result.stderr)
        self.assertFalse((self.run / "fake-launch.json").exists())

    def test_stopping_launcher_stops_agy(self) -> None:
        for signum, preflight in ((signal.SIGTERM, False), (signal.SIGINT, False), (signal.SIGHUP, False),
                                  (signal.SIGTERM, True)):
            with self.subTest(signum=signum, preflight=preflight):
                self.run = self.run.parent / f"signal-{signum}-{preflight}"
                self.run.mkdir()
                fifo = self.base / f"ready-{signum}-{preflight}"
                os.mkfifo(fifo)
                descriptor = os.open(fifo, os.O_RDONLY | os.O_NONBLOCK)
                child_pid: int | None = None
                launcher = subprocess.Popen(
                    [sys.executable, str(ROOT / "scripts/gemini_run.py"), "--run", str(self.run),
                     "--root", str(self.root), *(["--preflight"] if preflight else ["--prompt-file", str(self.prompt)]),
                     "--", "agy", "sleep"],
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True,
                    env=dict(self.env, FAKE_READY_FIFO=str(fifo)))
                try:
                    with selectors.DefaultSelector() as selector:
                        selector.register(descriptor, selectors.EVENT_READ)
                        self.assertTrue(selector.select(timeout=10), "fake agy did not report readiness")
                        child_pid = int(os.read(descriptor, 100))
                    os.kill(launcher.pid, signum)
                    stdout, stderr = launcher.communicate(timeout=10)
                    self.assertEqual(launcher.returncode, 1, stdout + stderr)
                    self.assertEqual(stdout.strip(), f"gemini_run: FAILED interrupted by signal {signum}")
                    if preflight:
                        self.assertFalse((self.run / "read").exists())
                    with self.assertRaises(ProcessLookupError):
                        os.kill(child_pid, 0)
                finally:
                    os.close(descriptor)
                    if launcher.poll() is None:
                        launcher.kill()
                        launcher.communicate()
                    launched = (self.run / "reply" if preflight else self.run) / "fake-launch.json"
                    if child_pid is None and launched.exists():
                        child_pid = json.loads(launched.read_text())["pid"]
                    if child_pid is not None:
                        try:
                            os.killpg(child_pid, signal.SIGKILL)
                        except ProcessLookupError:
                            pass

    def test_invalid_write_paths_rejected(self) -> None:
        for entry in ("../file", "/absolute", "dir/*.py", "x?", "x[ab]"):
            with self.subTest(entry=entry):
                result = self.launch(flags=("--write", entry))
                self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
                self.assertFalse((self.run / "policy.json").exists())

    def test_argv_policy_prompt_and_process_group(self) -> None:
        extra = self.base / "extra"
        extra.mkdir()
        extra_two = self.base / "extra two"
        extra_two.mkdir()
        result = self.launch(flags=("--read", str(extra), "--read", str(extra_two), "--write", "docs/",
                                    "--command", "python3 -m unittest", "--conversation", "resume-id", "--web",
                                    "--timeout", "12"))
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        launch = json.loads((self.run / "fake-launch.json").read_text())
        argv = launch["argv"]
        for flag in ("--sandbox", "--dangerously-skip-permissions", "--disable-slash-commands"):
            self.assertIn(flag, argv)
        for flag, value in (("--output-format", "json"), ("--print-timeout", "12s"),
                            ("--log-file", str(self.run / "agy.log")), ("--conversation", "resume-id")):
            self.assertEqual(argv[argv.index(flag) + 1], value)
        self.assertNotIn("--add-dir", argv)
        self.assertEqual(launch["cwd"], str(self.root))
        self.assertEqual(launch["policy"], str(self.run / "policy.json"))
        self.assertEqual(launch["stdin"], "")
        self.assertEqual(launch["pid"], launch["pgid"])
        policy = json.loads((self.run / "policy.json").read_text())
        self.assertEqual(policy["commands"], [*gemini_run.DEFAULT_COMMANDS, "python3 -m unittest"])
        self.assertEqual(policy["write"], ["docs/"])
        self.assertEqual(policy["read"], [str(extra), str(extra_two)])
        prompt = argv[argv.index("-p") + 1]
        for text in (str(self.root), str(extra), "docs/", "read-only", "Web search is allowed", "blocked",
                     "file tool", "quoted arguments", "variables", "braces", "rg for recursive search"):
            self.assertIn(text, prompt)
        self.assertTrue(prompt.endswith("Do the task."))

    def test_wrapper_receives_all_launcher_arguments(self) -> None:
        wrapper = self.bin / "klein-gemini"
        wrapper.write_text(f"#!{sys.executable}\nimport os, sys\nos.execv({str(self.agy)!r}, ['agy', 'pass', *sys.argv[2:]])\n")
        wrapper.chmod(0o755)
        result = self.launch(command=["klein-gemini", "writing"])
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        argv = json.loads((self.run / "fake-launch.json").read_text())["argv"]
        self.assertIn("--sandbox", argv)

    def test_preflight_writes_passing_record(self) -> None:
        self.record.unlink()
        result = self.launch("probes", preflight=True)
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        data = json.loads(self.record.read_text())
        self.assertEqual(len(result.stdout.splitlines()), 6)
        self.assertTrue(data["passed"])
        self.assertEqual(data["agy"], str(self.agy))
        self.assertEqual(data["agy_mtime"], self.agy.stat().st_mtime)
        self.assertEqual(data["command"], ["agy", "probes"])
        self.assertEqual(set(data["probes"]), {"reply", "read", "command", "deny-command", "deny-write", "search"})
        for name, probe in data["probes"].items():
            self.assertTrue(probe["passed"], (name, probe))
            self.assertIn(f"preflight {name} PASS", result.stdout)
            self.assertEqual(probe["exit"], 3 if name.startswith("deny-") else 0)
            self.assertTrue((self.run / name / "hook-started").is_file())
        self.assertFalse((self.root / "longrun-preflight-probe").exists())
        self.assertFalse((self.root / "longrun-preflight-probe.md").exists())
        with patch.dict(os.environ, self.env, clear=True):
            self.assertIsNone(gemini_run.preflight_freshness(self.record))

    def test_preflight_records_failed_probe(self) -> None:
        result = self.launch("bad-probe", preflight=True)
        self.assertEqual(result.returncode, 1, result.stderr + result.stdout)
        data = json.loads(self.record.read_text())
        self.assertFalse(data["passed"])
        self.assertFalse(data["probes"]["reply"]["passed"])
        self.assertTrue(data["probes"]["search"]["passed"])
        self.assertIn("preflight reply FAIL", result.stdout)

    def test_preflight_requires_denial_from_the_expected_tool_hook(self) -> None:
        result = self.launch("native-probes", preflight=True)
        self.assertEqual(result.returncode, 1, result.stdout + result.stderr)
        data = json.loads(self.record.read_text())
        self.assertFalse(data["passed"])
        for name in ("deny-command", "deny-write"):
            self.assertEqual(data["probes"][name]["exit"], 3)
            self.assertFalse(data["probes"][name]["passed"])
            self.assertEqual((self.run / name / "tools.jsonl").read_text(), "")

    def test_preflight_refuses_a_directory_at_record_path_before_probes(self) -> None:
        self.record.unlink()
        self.record.mkdir()
        result = self.launch("probes", preflight=True)
        self.assertEqual(result.returncode, 2)
        self.assertIn("record must be a file", result.stderr)
        self.assertFalse((self.run / "reply").exists())

    def preflight_args(self) -> argparse.Namespace:
        return argparse.Namespace(run=self.run, root=self.root, read=[], write=[], command=[], web=False,
                                  conversation=None, timeout=3600, prompt_file=None, agy=[str(self.agy), "probes"])

    def test_preflight_catches_probe_directory_creation_error(self) -> None:
        stderr = io.StringIO()
        with patch.dict(os.environ, self.env, clear=True), contextlib.redirect_stderr(stderr):
            with patch.object(Path, "mkdir", side_effect=PermissionError("cannot create probe")):
                status = gemini_run.preflight(self.preflight_args())
        self.assertEqual(status, 2)
        self.assertEqual(len(stderr.getvalue().splitlines()), 1)
        self.assertIn("preflight setup failed", stderr.getvalue())

    def test_preflight_catches_record_write_error(self) -> None:
        write_text = Path.write_text

        def write(path: Path, *args: Any, **kwargs: Any) -> int:
            if path == self.record:
                raise PermissionError("cannot write record")
            return write_text(path, *args, **kwargs)

        stderr = io.StringIO()
        with patch.dict(os.environ, self.env, clear=True), contextlib.redirect_stderr(stderr), contextlib.redirect_stdout(io.StringIO()):
            with patch.object(Path, "write_text", autospec=True, side_effect=write):
                status = gemini_run.preflight(self.preflight_args())
        self.assertEqual(status, 2)
        self.assertEqual(len(stderr.getvalue().splitlines()), 1)
        self.assertIn("cannot write preflight record", stderr.getvalue())

    def test_preflight_requires_agy_on_path(self) -> None:
        self.env["PATH"] = str(self.base / "empty")
        result = self.launch("probes", preflight=True, command=[str(self.agy), "probes"])
        self.assertEqual(result.returncode, 2)
        self.assertIn("agy is not on PATH", result.stderr)


class ProcessTests(unittest.TestCase):
    def test_termination_kills_group_even_if_leader_exits(self) -> None:
        process = MagicMock(pid=123)
        with patch.object(gemini_run.os, "killpg") as killpg:
            gemini_run.terminate_group(process)
        self.assertEqual(killpg.call_args_list[0].args, (123, signal.SIGTERM))
        self.assertEqual(killpg.call_args_list[1].args, (123, signal.SIGKILL))
        self.assertEqual(process.wait.call_args_list[0].kwargs, {"timeout": 30})

    def test_timeout_escalation(self) -> None:
        process = MagicMock(pid=123)
        process.wait.side_effect = [subprocess.TimeoutExpired("agy", 30), -9]
        with patch.object(gemini_run.os, "killpg") as killpg:
            gemini_run.terminate_group(process)
        self.assertEqual(killpg.call_args_list[-1].args, (123, signal.SIGKILL))
        self.assertEqual(process.wait.call_count, 2)

    def test_freshness_rejects_changed_binary_path_and_failed_record(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            record = Path(directory) / "record.json"
            for data in ({"passed": False}, {"passed": True, "agy": "/other"}, []):
                record.write_text(json.dumps(data))
                with patch.object(gemini_run.shutil, "which", return_value=sys.executable):
                    reason = gemini_run.preflight_freshness(record)
                self.assertIsNotNone(reason)
                self.assertTrue(reason.endswith("; run gemini_run.py --preflight"))


if __name__ == "__main__":
    unittest.main()
