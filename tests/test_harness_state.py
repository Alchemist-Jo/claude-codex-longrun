"""Tests for scripts/harness_state.py."""
from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import harness_state  # noqa: E402


def worker(worker_id: str, **fields) -> dict:
    entry = {
        "id": worker_id,
        "route": "codex",
        "status": "planned",
        "brief": f"harness/briefs/{worker_id}.md",
        "writes": [],
        "base": "main@1a2b3c4",
        "worktree": f"../wt/{worker_id}",
        "host": "local",
        "out": f"harness/runs/{worker_id}-r1/",
    }
    entry.update(fields)
    return entry


class StateCase(unittest.TestCase):
    def state(self, *workers: dict, briefs: bool = True) -> Path:
        tmp = Path(tempfile.mkdtemp())
        (tmp / "harness" / "briefs").mkdir(parents=True)
        if briefs:
            for entry in workers:
                (tmp / entry["brief"]).parent.mkdir(parents=True, exist_ok=True)
                (tmp / entry["brief"]).write_text("brief\n", encoding="utf-8")
        path = tmp / "harness" / "state.json"
        path.write_text(json.dumps({"workers": list(workers)}), encoding="utf-8")
        return path

    def problems(self, path: Path, **kwargs) -> list[str]:
        return harness_state.run(path, **kwargs)[1]

    def errors(self, path: Path, **kwargs) -> list[str]:
        return [p for p in self.problems(path, **kwargs) if p.startswith("ERROR")]


class ExampleTests(StateCase):
    def test_example_passes_with_one_overlap_warning(self):
        problems = self.problems(ROOT / "examples" / "harness" / "state.json")
        self.assertEqual(len(problems), 1, problems)
        self.assertTrue(problems[0].startswith("WARN w12 and w14"))

    def test_dispatching_the_overlapping_worker_fails(self):
        errors = self.errors(ROOT / "examples" / "harness" / "state.json", dispatch="w14")
        self.assertEqual(len(errors), 1, errors)
        self.assertIn("src/evalkit/runner.py", errors[0])


class OverlapTests(StateCase):
    def test_two_running_writers_on_one_file(self):
        path = self.state(
            worker("w1", status="running", pid=1, log="a.log", writes=["src/a.py"]),
            worker("w2", status="review", writes=["src/a.py", "src/b.py"]),
        )
        self.assertEqual(len(self.errors(path)), 1)

    def test_directory_write_set_covers_files_inside_it(self):
        path = self.state(
            worker("w1", status="changes", writes=["src/"]),
            worker("w2", status="accepted", writes=["src/deep/a.py"]),
        )
        self.assertIn("src/deep/a.py", self.errors(path)[0])

    def test_similar_prefix_without_directory_is_not_an_overlap(self):
        path = self.state(
            worker("w1", status="changes", writes=["src/a.py"]),
            worker("w2", status="changes", writes=["src/a.pyc"]),
        )
        self.assertEqual(self.problems(path), [])

    def test_follow_up_in_the_same_lineage_may_share_files(self):
        path = self.state(
            worker("w1", status="changes", writes=["src/a.py"]),
            worker("w1.1", status="running", pid=1, log="a.log", writes=["src/a.py"], parent="w1",
                   out="harness/runs/w1.1-r1/"),
        )
        self.assertEqual(self.problems(path), [])

    def test_closed_workers_release_their_files(self):
        path = self.state(
            worker("w1", status="merged", writes=["src/a.py"]),
            worker("w2", status="running", pid=1, log="a.log", writes=["src/a.py"]),
        )
        self.assertEqual(self.problems(path), [])

    def test_stopped_worker_does_not_hold_its_files(self):
        path = self.state(
            worker("w1", status="stopped", writes=["src/a.py"]),
            worker("w2", status="running", pid=1, log="a.log", writes=["src/a.py"]),
        )
        problems = self.problems(path)
        self.assertEqual([p for p in problems if p.startswith("ERROR")], [])
        self.assertTrue(problems and problems[0].startswith("WARN"), problems)

    def test_planned_overlap_warns_and_dispatch_errors(self):
        path = self.state(
            worker("w1", status="running", pid=1, log="a.log", writes=["src/a.py"]),
            worker("w2", writes=["src/a.py"]),
        )
        self.assertTrue(self.problems(path)[0].startswith("WARN"))
        self.assertEqual(len(self.errors(path, dispatch="w2")), 1)


class FieldTests(StateCase):
    def test_running_process_needs_pid_and_log(self):
        path = self.state(worker("w1", status="running"))
        errors = self.errors(path)
        self.assertTrue(any("without a log" in e for e in errors))
        self.assertTrue(any("integer pid" in e for e in errors))

    def test_output_directories_are_never_shared(self):
        path = self.state(worker("w1"), worker("w2", out="harness/runs/w1-r1"))
        self.assertTrue(any("share output directory" in e for e in self.errors(path)))

    def test_running_subagent_needs_no_pid_or_log(self):
        path = self.state(worker("r1", route="subagent", status="running", worktree=None, out="harness/reviews/w1-r1.md"))
        self.assertEqual(self.errors(path), [])

    def test_duplicate_ids_are_reported(self):
        path = self.state(worker("w1"), worker("w1", out="harness/runs/w1-r2/"))
        self.assertTrue(any("duplicate id" in e for e in self.errors(path)))

    def test_advisor_cannot_write(self):
        path = self.state(worker("a1", route="advisor", writes=["src/a.py"]))
        self.assertTrue(any("read-only" in e for e in self.errors(path)))

    def test_codex_writer_needs_a_worktree(self):
        entry = worker("w1", writes=["src/a.py"])
        del entry["worktree"]
        self.assertTrue(any("worktree" in e for e in self.errors(self.state(entry))))

    def test_missing_brief_and_bad_values(self):
        path = self.state(worker("w1", status="later", route="human", base="main", writes=["../x", "src/*.py"]),
                          briefs=False)
        errors = " ".join(self.errors(path))
        for text in ("does not exist", "status 'later'", "route 'human'", "base must", "'../x'", "'src/*.py'"):
            self.assertIn(text, errors)

    def test_dispatch_of_unknown_or_started_worker(self):
        path = self.state(worker("w1", status="running", pid=1, log="a.log"))
        self.assertTrue(self.errors(path, dispatch="w9"))
        self.assertTrue(self.errors(path, dispatch="w1"))


def dead_pid() -> int:
    done = subprocess.run([sys.executable, "-c", "import os; print(os.getpid())"], capture_output=True, text=True)
    return int(done.stdout)


class AliveTests(StateCase):
    def test_dead_process_without_exit_status_is_an_error(self):
        path = self.state(worker("w1", status="running", pid=dead_pid(), log="a.log"))
        errors = self.errors(path, alive=True)
        self.assertTrue(any("died without finishing" in e for e in errors), errors)

    def test_finished_process_is_listed_for_collection(self):
        path = self.state(worker("w1", status="running", pid=dead_pid(), log="a.log"))
        out = path.parent.parent / "harness" / "runs" / "w1-r1"
        out.mkdir(parents=True)
        (out / "exit-status").write_text("0\n", encoding="utf-8")
        problems = self.problems(path, alive=True)
        self.assertEqual([p for p in problems if p.startswith("ERROR")], [])
        self.assertTrue(any(p.startswith("NOTE w1") and "exit status 0" in p for p in problems), problems)

    def test_finished_advisor_reads_exit_status_from_its_run_directory(self):
        path = self.state(worker("a1", route="advisor", status="running", pid=dead_pid(), log="harness/runs/a1/stdout.log",
                                 worktree=None, out="harness/runs/a1/"))
        out = path.parent / "runs" / "a1"
        out.mkdir(parents=True)
        (out / "exit-status").write_text("0\n", encoding="utf-8")
        problems = self.problems(path, alive=True)
        self.assertEqual([p for p in problems if p.startswith("ERROR")], [])
        self.assertTrue(any(p.startswith("NOTE a1") for p in problems), problems)

    def test_live_process_passes(self):
        import os
        path = self.state(worker("w1", status="running", pid=os.getpid(), log="a.log"))
        self.assertEqual(self.problems(path, alive=True), [])

    def test_remote_process_is_listed_for_checking_there(self):
        path = self.state(worker("p1", route="paid-run", status="running", pid=99, log="t.log", host="gpu-host",
                                 worktree=None))
        problems = self.problems(path, alive=True)
        self.assertTrue(any(p.startswith("NOTE p1") for p in problems), problems)


class CommandLineTests(unittest.TestCase):
    def test_invalid_json_exits_with_status_1(self):
        tmp = Path(tempfile.mkdtemp()) / "state.json"
        tmp.write_text("{not json", encoding="utf-8")
        result = subprocess.run([sys.executable, str(ROOT / "scripts" / "harness_state.py"), str(tmp)],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, 1)


if __name__ == "__main__":
    unittest.main()
