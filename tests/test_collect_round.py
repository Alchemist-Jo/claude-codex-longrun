"""Tests for scripts/collect_round.py, in throwaway repositories with a linked worktree."""
from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "collect_round.py"
CHECK = "import sys; sys.path.insert(0, 'src'); import a; sys.exit(0 if a.run() == 2 else 1)"


class CollectCase(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.repo = self.tmp / "repo"
        (self.repo / "src").mkdir(parents=True)
        (self.repo / ".agents" / "bin").mkdir(parents=True)
        shutil.copy(ROOT / "scripts" / "run_checks.py", self.repo / ".agents" / "bin")
        checks = {"checks": [{"id": "unit", "command": [sys.executable, "-c", CHECK], "modes": ["ci"]}]}
        (self.repo / ".agents" / "checks.json").write_text(json.dumps(checks), encoding="utf-8")
        (self.repo / "src" / "a.py").write_text("def run():\n    return 1\n", encoding="utf-8")
        (self.repo / "src" / "b.py").write_text("x = 1\n", encoding="utf-8")
        (self.repo / "docs.md").write_text("old\n", encoding="utf-8")
        self.git(self.repo, "init", "-q", "-b", "main")
        self.git(self.repo, "config", "user.email", "t@example.com")
        self.git(self.repo, "config", "user.name", "t")
        self.git(self.repo, "add", "-A")
        self.git(self.repo, "commit", "-q", "-m", "base")
        self.base = self.git(self.repo, "rev-parse", "HEAD").strip()
        self.wt = self.tmp / "wt" / "w1"
        self.git(self.repo, "worktree", "add", "-q", "-b", "worker/w1", str(self.wt), self.base)
        self.run_dir = self.repo / ".agents" / "work" / "runs" / "w1-r1"
        self.run_dir.mkdir(parents=True)
        (self.run_dir / "exit-status").write_text("0\n", encoding="utf-8")

    def git(self, where: Path, *args: str) -> str:
        return subprocess.run(["git", "-C", str(where), *args], capture_output=True, text=True, check=True).stdout

    def collect(self, *paths: str, parent: str | None = None) -> subprocess.CompletedProcess:
        return subprocess.run([sys.executable, str(SCRIPT), "--run", str(self.run_dir), "--worktree", str(self.wt),
                               "--base", self.base, "--parent", parent or self.base, "--label", "w1 round 1",
                               "--", *(paths or ("src/a.py",))],
                              capture_output=True, text=True, cwd=self.tmp, timeout=60)

    def read(self, name: str) -> str:
        return (self.run_dir / name).read_text(encoding="utf-8")


class CollectTests(CollectCase):
    def test_checks_see_the_round_commit_without_outside_changes(self):
        (self.wt / "src" / "a.py").write_text("from b import helper\ndef run():\n    return helper()\n")
        (self.wt / "src" / "b.py").write_text("x = 1\ndef helper():\n    return 2\n")
        (self.wt / "scratch.txt").write_text("scratch\n")
        (self.wt / "docs.md").unlink()
        result = self.collect()
        self.assertEqual(result.returncode, 1, result.stderr)
        self.assertEqual(self.read("tests-exit-status").strip(), "1")
        self.assertEqual(sorted(self.read("outside.txt").split()), ["docs.md", "scratch.txt", "src/b.py"])
        commit = self.read("round-commit").strip()
        self.assertEqual(self.git(self.wt, "show", "--name-only", "--format=", commit).split(), ["src/a.py"])
        self.assertIn("helper", (self.wt / "src" / "b.py").read_text())
        self.assertTrue((self.wt / "scratch.txt").exists())
        self.assertFalse((self.wt / "docs.md").exists())

    def test_clean_round_passes(self):
        (self.wt / "src" / "a.py").write_text("def run():\n    return 2\n")
        result = self.collect()
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertEqual(self.read("outside.txt"), "")
        self.assertIn("src/a.py", self.read("diff.patch"))
        self.assertIn("Summary: unit passed", self.read("tests.log"))

    def test_changes_staged_outside_the_write_set_stay_out_of_the_commit(self):
        (self.wt / "src" / "a.py").write_text("def run():\n    return 2\n")
        self.git(self.wt, "mv", "src/b.py", "src/c.py")
        result = self.collect()
        self.assertEqual(result.returncode, 1)
        commit = self.read("round-commit").strip()
        self.assertEqual(self.git(self.wt, "show", "--name-only", "--format=", commit).split(), ["src/a.py"])
        self.assertEqual(sorted(self.read("outside.txt").split()), ["src/b.py", "src/c.py"])

    def test_round_that_only_reverted_outside_files_keeps_the_parent(self):
        result = self.collect()
        self.assertEqual(result.returncode, 1)
        self.assertEqual(self.read("round-commit").strip(), self.base)
        self.assertEqual(self.read("fix.patch"), "")

    def test_a_commit_by_the_worker_stops_the_collection(self):
        (self.wt / "src" / "a.py").write_text("def run():\n    return 2\n")
        self.git(self.wt, "commit", "-qam", "codex committed")
        result = self.collect()
        self.assertEqual(result.returncode, 2)
        self.assertIn("the worker committed", result.stderr)
        self.assertFalse((self.run_dir / "round-commit").exists())

    def test_unfinished_job_stops_the_collection(self):
        (self.run_dir / "exit-status").unlink()
        result = self.collect()
        self.assertEqual(result.returncode, 2)
        self.assertIn("has not finished", self.read("collect-report.md"))

    def test_runs_from_any_directory_and_leaves_the_main_checkout_alone(self):
        (self.repo / "draft.md").write_text("main checkout draft\n")
        (self.wt / "src" / "a.py").write_text("def run():\n    return 2\n")
        self.assertEqual(self.collect().returncode, 0)
        self.assertTrue((self.repo / "draft.md").exists())
        self.assertEqual(self.git(self.repo, "rev-parse", "HEAD").strip(), self.base)


if __name__ == "__main__":
    unittest.main()
