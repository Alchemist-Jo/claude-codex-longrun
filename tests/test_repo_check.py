"""Tests for scripts/repo_check.py."""
from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import repo_check  # noqa: E402

IMPLEMENTED = """# Agent Note: Example

Status: implemented

## Problem

p

## Decision

d

## Alternatives considered

a

## Consequences

c
"""


class RepoCase(unittest.TestCase):
    def setUp(self):
        # An unresolved temporary path: on macOS it sits behind the /var symlink.
        self.root = Path(tempfile.mkdtemp())

    def write(self, rel: str, text: str) -> Path:
        path = self.root / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        return path

    def git(self, *args: str) -> str:
        return subprocess.run(["git", "-C", str(self.root), *args], capture_output=True, text=True, check=True).stdout

    def init_git(self):
        self.git("init", "-q", "-b", "main")
        self.git("config", "user.email", "t@example.com")
        self.git("config", "user.name", "t")

    def commit(self, message: str = "c"):
        self.git("add", "-A")
        self.git("commit", "-q", "--no-verify", "-m", message)

    def problems(self, *only: str, base: str | None = None) -> list[str]:
        return repo_check.run(self.root.resolve(), list(only) or None, base)

    def errors(self, *only: str, base: str | None = None) -> list[str]:
        return [p for p in self.problems(*only, base=base) if p.startswith("ERROR")]


class LinkTests(RepoCase):
    def test_inline_reference_and_image_links_resolve(self):
        self.write("docs/target.md", "# t\n")
        self.write(".agents/hidden.md", "# h\n")
        self.write("img.png", "x")
        self.write("README.md", "[a](docs/target.md#part) [b][ref] ![c](img.png) [web](https://example.com) "
                                "[anchor](#top)\n\n[ref]: .agents/hidden.md\n")
        self.assertEqual(self.errors("links"), [])

    def test_missing_target_and_escape_are_errors(self):
        self.write("README.md", "[a](docs/missing.md)\n\n[b](../outside.md)\n")
        errors = self.errors("links")
        self.assertEqual(len(errors), 2, errors)
        self.assertIn("README.md:1", errors[0])
        self.assertIn("leaves the repository", errors[1])

    def test_code_is_not_a_link(self):
        self.write("README.md", "~~~md\n[a](missing.md)\n~~~\n\n```\n[b](missing.md)\n```\n\n`[c](missing.md)`\n")
        self.assertEqual(self.errors("links"), [])

    def test_archived_notes_and_work_records_are_skipped(self):
        self.write(".agents/notes/archived/process/2026-01-01-old.md", "[gone](missing.md)\n")
        self.write(".agents/work/runs/w1-r1/last-message.md", "[runner](src/runner.py)\n")
        self.assertEqual(self.errors("links"), [])

    def test_footnotes_and_root_relative_links(self):
        self.write("docs/usage.md", "# u\n")
        self.write("docs/guide.md", "[usage](/docs/usage.md) and a note[^1].\n\n[^1]: Smith et al., 2024.\n")
        self.assertEqual(self.errors("links"), [])


class InstructionTests(RepoCase):
    def test_chain_over_the_codex_limit_is_an_error(self):
        self.write("AGENTS.md", "x" * 20000)
        self.write("src/AGENTS.md", "y" * 13000)
        self.write("docs/AGENTS.md", "z" * 100)
        errors = self.errors("instructions")
        self.assertEqual(len(errors), 1, errors)
        self.assertIn("AGENTS.md + src/AGENTS.md", errors[0])

    def test_long_file_and_claude_file_without_import_warn(self):
        self.write("AGENTS.md", "line\n" * 250)
        self.write("CLAUDE.md", "Claude rules\n")
        warnings = self.problems("instructions")
        self.assertTrue(any("250 lines" in w for w in warnings), warnings)
        self.assertTrue(any("add the line @AGENTS.md" in w for w in warnings), warnings)

    def test_claude_file_that_imports_passes(self):
        self.write("AGENTS.md", "rules\n")
        self.write("CLAUDE.md", "@AGENTS.md\n\nClaude-only notes\n")
        self.assertEqual(self.problems("instructions"), [])


class NoteTests(RepoCase):
    def test_valid_notes_of_each_lifecycle_pass(self):
        self.write(".agents/notes/README.md", "# Notes\n")
        self.write(".agents/notes/implemented/feature/2026-10-01-a.md", IMPLEMENTED)
        archived = IMPLEMENTED.replace("Status: implemented\n", "Status: implemented\nArchived: 2026-10-10\n")
        self.write(".agents/notes/archived/process/2026-10-01-b.md", archived)
        self.write(".agents/notes/proposed/experiment/2026-10-02-c.md",
                   "# Agent Note: C\n\nStatus: proposed\n\n## Problem\n\n## Proposal\n\n"
                   "## Alternatives considered\n\n## Acceptance\n\n## Risks\n")
        self.write(".agents/notes/rejected/testing/2026-10-03-d.md",
                   "# Agent Note: D\n\nStatus: rejected\n\n## Problem\n\n## Proposal\n\n"
                   "## Alternatives considered\n\n## Rejection\n")
        self.assertEqual(self.errors("notes"), [])

    def test_wrong_place_name_status_and_sections(self):
        self.write(".agents/notes/feature/2026-10-01-a.md", IMPLEMENTED)
        self.write(".agents/notes/implemented/feature/notes-a.md", IMPLEMENTED)
        self.write(".agents/notes/proposed/feature/2026-10-01-b.md", IMPLEMENTED)
        self.write(".agents/notes/implemented/feature/2026-10-01-c.md", IMPLEMENTED + "\n## Plan\n\nlater\n")
        self.write(".agents/notes/archived/feature/2026-10-05-d.md",
                   IMPLEMENTED.replace("Status: implemented\n", "Status: implemented\nArchived: 2026-10-01\n"))
        errors = " | ".join(self.errors("notes"))
        for text in ("a note lives at", "YYYY-MM-DD-topic.md", "'Status: proposed'", "missing section(s) Proposal",
                     "remove section(s) Plan", "before the note was created"):
            self.assertIn(text, errors)

    def test_example_notes_pass(self):
        self.assertEqual([p for p in repo_check.run(ROOT / "examples" / "project") if p.startswith("ERROR")], [])


class ArchiveTests(RepoCase):
    def test_only_additions_pass_against_the_base(self):
        self.init_git()
        self.write(".agents/notes/archived/process/2026-10-01-a.md", "old\n")
        self.commit()
        base = self.git("rev-parse", "HEAD").strip()
        self.write(".agents/notes/archived/process/2026-10-02-b.md", "new\n")
        self.commit()
        self.assertEqual(self.errors("archive", base=base), [])
        self.write(".agents/notes/archived/process/2026-10-01-a.md", "rewritten\n")
        self.commit()
        errors = self.errors("archive", base=base)
        self.assertEqual(len(errors), 1, errors)
        self.assertIn("2026-10-01-a.md", errors[0])

    def test_uncommitted_edit_is_caught_against_head(self):
        self.init_git()
        self.write(".agents/notes/archived/process/2026-10-01-a.md", "old\n")
        self.commit()
        (self.root / ".agents/notes/archived/process/2026-10-01-a.md").unlink()
        self.assertEqual(len(self.errors("archive")), 1)

    def test_deleting_the_whole_archive_is_caught(self):
        self.init_git()
        self.write(".agents/notes/archived/process/2026-10-01-a.md", "old\n")
        self.commit()
        shutil.rmtree(self.root / ".agents/notes/archived")
        self.assertEqual(len(self.errors("archive")), 1)

    def test_unknown_base_is_an_error_only_when_given(self):
        self.write(".agents/notes/archived/process/2026-10-01-a.md", "old\n")
        self.assertTrue(self.errors("archive", base="nosuchref"))
        self.assertEqual(self.errors("archive"), [])


class ResidueTests(RepoCase):
    def setUp(self):
        super().setUp()
        state = {"workers": [{"id": "w12"}, {"id": "w1"}, {"id": "r12-1"}]}
        self.write(".agents/work/state.json", json.dumps(state))

    def test_work_record_and_worker_round_references_are_errors(self):
        self.write("src/runner.py", "# see .agents/work/reviews/w12-r1.md\n# fixed in w12 round 2\nx = 1\n")
        self.write("docs/guide.md", "As the review of w12 found, shards resume.\n")
        errors = " | ".join(self.errors("residue"))
        self.assertEqual(errors.count("ERROR"), 3, errors)
        for text in ("docs/guide.md:1", "src/runner.py:1: cites the work record", "src/runner.py:2: 'w12 round'"):
            self.assertIn(text, errors)

    def test_ordinary_code_and_layout_mentions_pass(self):
        self.write("src/model.py", "w1 = init_weights()\nw12 = w1 @ w2  # review the shapes below\n")
        self.write("AGENTS.md", "Work records live in `.agents/work/`, briefs in `.agents/work/briefs/`.\n")
        self.write(".agents/notes/implemented/process/2026-10-01-a.md", "Evidence: .agents/work/reviews/w12-r1.md\n")
        self.write(".github/workflows/ci.yml", "run: cat .agents/work/runs/x/tests.log\n")
        self.assertEqual(self.problems("residue"), [])

    def test_worker_ids_come_from_the_main_checkout_in_a_worktree(self):
        self.init_git()
        self.write("src/a.py", "x = 1\n")
        self.commit()
        worktree = Path(tempfile.mkdtemp()) / "w13"
        self.git("worktree", "add", "-q", "-b", "worker/w13", str(worktree))
        state = {"workers": [{"id": "w13"}]}
        self.write(".agents/work/state.json", json.dumps(state))
        (worktree / "src" / "a.py").write_text("# fixed in w13 round 2\nx = 1\n", encoding="utf-8")
        errors = [p for p in repo_check.run(worktree, ["residue"]) if p.startswith("ERROR")]
        self.assertEqual(len(errors), 1, errors)

    def test_review_phrases_are_warnings(self):
        self.write("src/a.py", "# addressed the review comment\n")
        problems = self.problems("residue")
        self.assertEqual(len(problems), 1, problems)
        self.assertTrue(problems[0].startswith("WARN"))


class CommandLineTests(unittest.TestCase):
    def test_exit_status_follows_errors(self):
        root = Path(tempfile.mkdtemp())
        (root / "README.md").write_text("[a](missing.md)\n", encoding="utf-8")
        script = str(ROOT / "scripts" / "repo_check.py")
        failed = subprocess.run([sys.executable, script, str(root)], capture_output=True, text=True)
        self.assertEqual(failed.returncode, 1)
        (root / "missing.md").write_text("# m\n", encoding="utf-8")
        passed = subprocess.run([sys.executable, script, str(root)], capture_output=True, text=True)
        self.assertEqual(passed.returncode, 0, passed.stderr)


if __name__ == "__main__":
    unittest.main()
