"""Tests for scripts/run_checks.py."""
from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "run_checks.py"
PY = sys.executable


def check(check_id: str, code: str, modes=("ci",), **fields) -> dict:
    entry = {"id": check_id, "command": [PY, "-c", code], "modes": list(modes)}
    entry.update(fields)
    return entry


class RunChecksCase(unittest.TestCase):
    def run_checks(self, checks, *args: str) -> subprocess.CompletedProcess:
        root = Path(tempfile.mkdtemp())
        (root / ".agents").mkdir()
        config = root / ".agents" / "checks.json"
        config.write_text(json.dumps({"checks": checks}), encoding="utf-8")
        self.root = root
        return subprocess.run([PY, str(SCRIPT), "--config", str(config), *args],
                              capture_output=True, text=True, timeout=60)


class SelectionTests(RunChecksCase):
    def test_mode_selects_its_checks_and_their_needs(self):
        result = self.run_checks([
            check("first", "print('first ran')", modes=["commit"]),
            check("second", "print('second ran')", modes=["test"], needs=["first"]),
            check("third", "print('third ran')", modes=["ci"]),
        ], "--mode", "test")
        self.assertEqual(result.returncode, 0, result.stdout)
        self.assertIn("first ran", result.stdout)
        self.assertIn("second ran", result.stdout)
        self.assertNotIn("third ran", result.stdout)

    def test_only_runs_a_named_check(self):
        result = self.run_checks([check("a", "print('a ran')"), check("b", "print('b ran')")], "--only", "b")
        self.assertEqual(result.returncode, 0)
        self.assertNotIn("a ran", result.stdout)
        self.assertIn("b ran", result.stdout)

    def test_commands_run_from_the_repository_root(self):
        result = self.run_checks([check("cwd", "import os; print('cwd=' + os.getcwd())")], "--mode", "ci")
        self.assertIn("cwd=" + str(self.root.resolve()), result.stdout)

    def test_list_prints_without_running(self):
        result = self.run_checks([check("a", "open('ran', 'w')")], "--mode", "ci", "--list")
        self.assertEqual(result.returncode, 0)
        self.assertFalse((self.root / "ran").exists())


class OutcomeTests(RunChecksCase):
    def test_failure_exits_1_and_skips_dependents(self):
        result = self.run_checks([
            check("bad", "import sys; print('bad output'); sys.exit(3)"),
            check("after", "print('after ran')", needs=["bad"]),
            check("independent", "print('independent ran')"),
        ], "--mode", "ci")
        self.assertEqual(result.returncode, 1)
        self.assertIn("bad output", result.stdout)
        self.assertIn("failed (exit 3)", result.stdout)
        self.assertIn("after: skipped", result.stdout)
        self.assertNotIn("after ran", result.stdout)
        self.assertIn("independent ran", result.stdout)

    def test_timeout_terminates_the_process_group(self):
        code = ("import subprocess, sys, time; "
                "subprocess.Popen([sys.executable, '-c', 'import time; time.sleep(30); open(\"late\", \"w\")']); "
                "time.sleep(30)")
        start = time.monotonic()
        result = self.run_checks([check("slow", code, timeout=1)], "--mode", "ci")
        self.assertEqual(result.returncode, 1)
        self.assertIn("timed out after 1s", result.stdout)
        self.assertLess(time.monotonic() - start, 20)
        time.sleep(1)
        self.assertFalse((self.root / "late").exists())

    def test_sigterm_ends_the_running_check(self):
        root = Path(tempfile.mkdtemp())
        (root / ".agents").mkdir()
        code = "import time; time.sleep(3); open('late', 'w')"
        config = root / ".agents" / "checks.json"
        config.write_text(json.dumps({"checks": [check("slow", code)]}), encoding="utf-8")
        process = subprocess.Popen([PY, str(SCRIPT), "--config", str(config), "--mode", "ci"],
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(1)
        process.terminate()
        self.assertEqual(process.wait(timeout=10), 143)
        time.sleep(3)
        self.assertFalse((root / "late").exists())

    def test_missing_program_is_a_failure(self):
        result = self.run_checks([{"id": "x", "command": ["no-such-program-xyz"], "modes": ["ci"]}], "--mode", "ci")
        self.assertEqual(result.returncode, 1)
        self.assertIn("could not start", result.stdout)


class ConfigurationTests(RunChecksCase):
    def test_bad_configurations_exit_2(self):
        cases = [
            [],
            [{"id": "a", "command": "echo a", "modes": ["ci"]}],
            [check("a", "pass"), check("a", "pass")],
            [check("a", "pass", needs=["later"]), check("later", "pass")],
            [check("a", "pass", timeout=0)],
            [check("a", "pass", unknown=True)],
        ]
        for checks in cases:
            with self.subTest(checks=checks):
                self.assertEqual(self.run_checks(checks, "--mode", "ci").returncode, 2)

    def test_mode_without_checks_and_unknown_id_exit_2(self):
        self.assertEqual(self.run_checks([check("a", "pass")], "--mode", "nothing").returncode, 2)
        self.assertEqual(self.run_checks([check("a", "pass")], "--only", "b").returncode, 2)

    def test_project_template_is_valid(self):
        result = subprocess.run([PY, str(SCRIPT), "--config", str(ROOT / "assets" / "project" / "checks.json"),
                                 "--mode", "ci", "--list"], capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual([line.split(":")[0] for line in result.stdout.splitlines()], ["repo", "tests"])


if __name__ == "__main__":
    unittest.main()
