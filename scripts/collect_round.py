"""Collect one finished worker round: commit the write set, then check that commit alone.

    collect_round.py --run RUN --worktree WT --base REF --parent REF \\
        [--label TEXT] [--mode MODE] -- PATH [PATH ...]

RUN is the round's run directory, WT the worker's worktree, BASE the commit
recorded in the state file, PARENT the previous round commit (the base in
round 1), and PATH the write set, a directory ending with /. Every path is
used as given, so the script works from any current directory; a subagent's
working directory is reset between commands.

Steps, each stopping the collection when its precondition fails:

1. RUN/exit-status exists: the worker job finished.
2. HEAD of WT equals PARENT: the worker made no commit.
3. The index is reset, so nothing the worker staged outside the write set can
   enter the commit, and RUN/outside.txt lists every change outside it.
4. The write set is staged and committed as the round commit, with
   --no-verify; a round that changed nothing in the write set keeps PARENT.
   RUN/round-commit, RUN/diff.patch (from BASE) and RUN/fix.patch (from
   PARENT) are written.
5. What is left uncommitted lies outside the write set. It is saved as
   RUN/outside.patch and RUN/outside-new.tar and removed, so the worktree
   equals the round commit plus ignored files.
6. `.agents/bin/run_checks.py --mode MODE` runs in WT; output goes to
   RUN/tests.log and its exit status to RUN/tests-exit-status.
7. The saved changes are restored.

git stash is not used: all worktrees of a repository share one stash stack.
Exit status: 0 when the checks passed and outside.txt is empty, 1 when the
round needs attention (checks failed or changes outside the write set), 2
when the collection stopped; the reason is printed and written to
RUN/collect-report.md.
"""
from __future__ import annotations

import argparse
import os
from pathlib import Path
import signal
import subprocess
import sys
import tarfile


class Stop(Exception):
    pass


def git_bytes(wt: Path, *args: str) -> bytes:
    result = subprocess.run(["git", "-C", str(wt), *args], capture_output=True, check=False)
    if result.returncode != 0:
        raise Stop(f"git {' '.join(args)} failed: {result.stderr.decode('utf-8', 'replace').strip()}")
    return result.stdout


def git(wt: Path, *args: str) -> str:
    return git_bytes(wt, *args).decode("utf-8", "replace")


def rev(wt: Path, ref: str) -> str:
    return git(wt, "rev-parse", "--verify", f"{ref}^{{commit}}").strip()


def outside_changes(wt: Path, paths: list[str]) -> list[str]:
    keep = [f":!{p}" for p in paths]
    changed = git(wt, "diff", "--name-only", "--", ".", *keep).splitlines()
    new = git(wt, "ls-files", "-o", "--exclude-standard", "--", ".", *keep).splitlines()
    return [line for line in changed + new if line]


def commit_write_set(wt: Path, paths: list[str], parent: str, label: str) -> str:
    for path in paths:
        tracked = subprocess.run(["git", "-C", str(wt), "ls-files", "--error-unmatch", "--", path],
                                 capture_output=True, check=False).returncode == 0
        if (wt / path).exists() or tracked:
            git(wt, "add", "-A", "--", path)
    staged = subprocess.run(["git", "-C", str(wt), "diff", "--cached", "--quiet"], check=False).returncode
    if staged == 0:
        return parent
    git(wt, "commit", "-q", "--no-verify", "-m", label)
    return rev(wt, "HEAD")


def set_aside(wt: Path, run: Path) -> tuple[bool, list[str]]:
    patch = git_bytes(wt, "diff", "--binary")
    (run / "outside.patch").write_bytes(patch)
    new = [n for n in git(wt, "ls-files", "-o", "--exclude-standard", "-z").split("\0") if n]
    (run / "outside-new.lst").write_text("".join(n + "\n" for n in new), encoding="utf-8")
    if new:
        with tarfile.open(run / "outside-new.tar", "w") as archive:
            for name in new:
                archive.add(wt / name, arcname=name, recursive=False)
        for name in new:
            (wt / name).unlink()
    if patch:
        git(wt, "checkout", "--", ".")
    left = git(wt, "status", "--porcelain", "--untracked-files=all").strip()
    if left:
        restore(wt, run, bool(patch), new)
        raise Stop(f"the worktree was not clean after setting changes aside, so they were restored:\n{left}")
    return bool(patch), new


def restore(wt: Path, run: Path, patched: bool, new: list[str]) -> None:
    if patched:
        git(wt, "apply", "--binary", str(run / "outside.patch"))
    if new:
        with tarfile.open(run / "outside-new.tar") as archive:
            try:
                archive.extractall(wt, filter="data")
            except TypeError:
                archive.extractall(wt)


def run_checks(wt: Path, run: Path, mode: str) -> int:
    """Run the checks in their own process group; a SIGTERM to this script ends them too."""
    with open(run / "tests.log", "wb") as log:
        process = subprocess.Popen([sys.executable, str(wt / ".agents/bin/run_checks.py"), "--mode", mode],
                                   cwd=wt, stdout=log, stderr=subprocess.STDOUT, start_new_session=True)

        def forward(signum, frame):
            try:
                os.killpg(process.pid, signal.SIGTERM)
            except ProcessLookupError:
                pass
            raise SystemExit(128 + signum)

        signal.signal(signal.SIGTERM, forward)
        signal.signal(signal.SIGINT, forward)
        status = process.wait()
    (run / "tests-exit-status").write_text(f"{status}\n", encoding="utf-8")
    return status


def collect(run: Path, wt: Path, base: str, parent: str, label: str, mode: str, paths: list[str]) -> int:
    if not (run / "exit-status").is_file():
        raise Stop(f"{run / 'exit-status'} does not exist; the job has not finished")
    base_commit, parent_commit = rev(wt, base), rev(wt, parent)
    if rev(wt, "HEAD") != parent_commit:
        raise Stop(f"HEAD of {wt} is not {parent}; the worker committed or the branch moved")
    git(wt, "reset", "-q")
    outside = outside_changes(wt, paths)
    (run / "outside.txt").write_text("".join(p + "\n" for p in outside), encoding="utf-8")
    commit = commit_write_set(wt, paths, parent_commit, label)
    (run / "round-commit").write_text(commit + "\n", encoding="utf-8")
    (run / "diff.patch").write_bytes(git_bytes(wt, "diff", "--binary", base_commit, commit))
    (run / "fix.patch").write_bytes(git_bytes(wt, "diff", "--binary", parent_commit, commit))
    patched, new = set_aside(wt, run)
    try:
        status = run_checks(wt, run, mode)
    finally:
        restore(wt, run, patched, new)
    summary = [line for line in (run / "tests.log").read_text("utf-8", "replace").splitlines()
               if line.startswith("Summary:")]
    lines = [f"round commit: {commit}", f"outside the write set: {len(outside)} path(s), see outside.txt",
             f"checks: exit status {status}" + (f"; {summary[-1]}" if summary else "")]
    (run / "collect-report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    return 0 if status == 0 and not outside else 1


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--worktree", type=Path, required=True)
    parser.add_argument("--base", required=True)
    parser.add_argument("--parent", required=True)
    parser.add_argument("--label", default="round")
    parser.add_argument("--mode", default="ci")
    parser.add_argument("paths", nargs="+", help="the write set, after --")
    args = parser.parse_args()
    run, wt = args.run.resolve(), args.worktree.resolve()
    try:
        return collect(run, wt, args.base, args.parent, args.label, args.mode, args.paths)
    except Stop as stop:
        message = f"STOP: {stop}"
        print(message, file=sys.stderr)
        if run.is_dir():
            (run / "collect-report.md").write_text(message + "\n", encoding="utf-8")
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
