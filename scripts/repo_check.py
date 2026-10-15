"""Check the repository layer that agents depend on across sessions.

    repo_check.py [ROOT] [--only CHECK]... [--base REF]

Checks, all run by default:

- links: local links in Markdown files point to files inside ROOT; a link
  starting with / is read from ROOT. Code blocks, code spans, footnotes, work
  records under .agents/work/ and the frozen archive of notes are skipped.
- instructions: each chain of AGENTS.md files from ROOT down to a directory
  stays within 32768 bytes, the default project_doc_max_bytes at which Codex
  stops adding instruction files. A file over 200 lines is a warning, the
  per-file target in the Claude Code memory documentation. A CLAUDE.md beside
  an AGENTS.md that does not import it with a line `@AGENTS.md` is a
  warning, since Claude Code then skips AGENTS.md.
- notes: every decision note under .agents/notes/ has the path, header and
  sections of its lifecycle.
- archive: relative to REF (default HEAD), files under
  .agents/notes/archived/ were only added, never modified, renamed or
  deleted. CI passes the pull request base or the previous push.
- residue: files outside .agents/ and outside dot-directories do not cite
  work records. References to a specific brief, review, run, advice or
  report under .agents/work/, and a worker id from the state file next to
  round, brief, review, verdict or ruling, are errors. Common review
  phrases such as "review round 2" are warnings for a reader to judge. In a
  linked worktree, worker ids also come from the main checkout's state file.

Errors exit with status 1. The script reads files only and needs no
dependency beyond Python and git.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import os
from pathlib import Path
import re
import subprocess
import sys
from urllib.parse import unquote, urlsplit

CHECKS = ("links", "instructions", "notes", "archive", "residue")
LIMIT = 32768
LINE_TARGET = 200
SKIP = {".git", "node_modules", ".venv", "venv", "__pycache__"}
NOTES = ".agents/notes/"
ARCHIVE = ".agents/notes/archived/"
WORK = ".agents/work/"
LIFECYCLES = ("proposed", "implemented", "rejected", "archived")
CLASSES = ("feature", "bug-fix", "simplification", "architecture", "process", "testing", "experiment")
SECTIONS = {
    "proposed": (("Problem", "Proposal", "Alternatives considered", "Acceptance", "Risks"), ()),
    "implemented": (("Problem", "Decision", "Alternatives considered", "Consequences"), ("Proposal", "Plan", "Acceptance")),
    "rejected": (("Problem", "Proposal", "Alternatives considered", "Rejection"), ()),
}
NOTE_NAME = re.compile(r"^(\d{4}-\d{2}-\d{2})-[a-z0-9][a-z0-9-]*\.md$")
INLINE = re.compile(r"!?\[[^\]]*\]\(\s*<?([^)\s>]+)>?(?:\s+\"[^\"]*\")?\s*\)")
REFERENCE = re.compile(r"^ {0,3}\[(?!\^)[^\]]+\]:\s*<?(\S+?)>?(?:\s+.*)?$", re.M)
FENCE = re.compile(r"^ {0,3}(`{3,}|~{3,})")
WORK_REF = re.compile(r"\.agents/work/(?:runs|briefs|reviews|advice|reports)/[\w.\-/]+")
PROBES = re.compile(
    r"review round \d+|\(round \d+\)|addressed (?:the )?review|per (?:the )?reviewer"
    r"|as requested in (?:the )?review|as discussed (?:above|earlier|in (?:the )?(?:chat|thread|session))",
    re.I)


def listing(root: Path) -> list[str]:
    """Tracked and untracked, not ignored files, relative to root."""
    result = subprocess.run(["git", "-C", str(root), "ls-files", "-co", "--exclude-standard", "-z"],
                            capture_output=True, check=False)
    if result.returncode == 0:
        names = [n for n in result.stdout.decode("utf-8", "replace").split("\0") if n]
        return sorted(n for n in names if (root / n).is_file())
    found = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in SKIP]
        for name in filenames:
            found.append(Path(dirpath, name).relative_to(root).as_posix())
    return sorted(found)


def read(root: Path, rel: str) -> str | None:
    path = root / rel
    if path.stat().st_size > 2_000_000:
        return None
    data = path.read_bytes()
    if b"\0" in data[:8192]:
        return None
    return data.decode("utf-8", errors="replace")


def strip_code(text: str) -> str:
    """Blank out fenced blocks and code spans, keeping line numbers."""
    lines, fence = [], None
    for line in text.splitlines():
        match = FENCE.match(line)
        if fence:
            if match and match.group(1)[0] == fence[0] and len(match.group(1)) >= len(fence):
                fence = None
            lines.append("")
        elif match:
            fence = match.group(1)
            lines.append("")
        else:
            lines.append(re.sub(r"(`+).+?\1", "", line))
    return "\n".join(lines)


def line_of(text: str, index: int) -> int:
    return text.count("\n", 0, index) + 1


def check_links(root: Path, files: list[str]) -> list[str]:
    problems = []
    for rel in files:
        if not rel.endswith(".md") or rel.startswith((ARCHIVE, WORK)):
            continue
        text = strip_code(read(root, rel) or "")
        for pattern in (INLINE, REFERENCE):
            for match in pattern.finditer(text):
                target = match.group(1)
                parsed = urlsplit(target)
                if parsed.scheme or target.startswith(("#", "//")) or not parsed.path:
                    continue
                path = unquote(parsed.path)
                start = "" if path.startswith("/") else os.path.dirname(rel)
                joined = os.path.normpath(os.path.join(start, path.lstrip("/")))
                where = f"{rel}:{line_of(text, match.start())}"
                if joined == ".." or joined.startswith("../") or os.path.isabs(joined):
                    problems.append(f"ERROR {where}: link {target} leaves the repository")
                elif not (root / joined).exists():
                    problems.append(f"ERROR {where}: link target {target} does not exist")
    return problems


def check_instructions(root: Path, files: list[str]) -> list[str]:
    problems = []
    agents = {os.path.dirname(rel): rel for rel in files if os.path.basename(rel) == "AGENTS.md"}
    for folder, rel in sorted(agents.items()):
        chain, parts = [], folder.split("/") if folder else []
        for depth in range(len(parts) + 1):
            prefix = "/".join(parts[:depth])
            if prefix in agents:
                chain.append(agents[prefix])
        size = sum((root / name).stat().st_size for name in chain)
        if size > LIMIT:
            problems.append(f"ERROR {rel}: the AGENTS.md chain {' + '.join(chain)} is {size} bytes; "
                            f"Codex stops adding instruction files at {LIMIT} bytes")
        lines = len((read(root, rel) or "").splitlines())
        if lines > LINE_TARGET:
            problems.append(f"WARN {rel}: {lines} lines; keep standing instructions under {LINE_TARGET} "
                            "lines and link the detail")
    for rel in files:
        if os.path.basename(rel) != "CLAUDE.md":
            continue
        if (root / rel).is_symlink():
            problems.append(f"WARN {rel}: is a symlink; Claude Code's Edit and Write refuse to write "
                            "through symlinks; use a file with the line @AGENTS.md")
        elif os.path.dirname(rel) in agents and not re.search(r"(?m)^@AGENTS\.md\s*$", read(root, rel) or ""):
            problems.append(f"WARN {rel}: Claude Code skips AGENTS.md where a CLAUDE.md exists; "
                            "add the line @AGENTS.md")
    return problems


def valid_date(value: str) -> dt.date | None:
    try:
        return dt.date.fromisoformat(value)
    except ValueError:
        return None


def check_notes(root: Path, files: list[str]) -> list[str]:
    problems = []
    for rel in files:
        if not rel.startswith(NOTES) or not rel.endswith(".md"):
            continue
        parts = rel[len(NOTES):].split("/")
        if parts[-1] in ("README.md", "AGENTS.md"):
            continue
        if len(parts) != 3 or parts[0] not in LIFECYCLES or parts[1] not in CLASSES:
            problems.append(f"ERROR {rel}: a note lives at .agents/notes/<{'|'.join(LIFECYCLES)}>/"
                            f"<{'|'.join(CLASSES)}>/YYYY-MM-DD-topic.md")
            continue
        name = NOTE_NAME.match(parts[2])
        created = valid_date(name.group(1)) if name else None
        if not created:
            problems.append(f"ERROR {rel}: the file name must be YYYY-MM-DD-topic.md with a real date "
                            "and lowercase words joined by hyphens")
        lines = (read(root, rel) or "").splitlines()
        lifecycle = parts[0]
        status = "implemented" if lifecycle == "archived" else lifecycle
        if len(lines) < 3 or not lines[0].startswith("# Agent Note: ") or lines[1].strip():
            problems.append(f"ERROR {rel}: the first line is '# Agent Note: <topic>' followed by a blank line")
        elif lines[2].strip() != f"Status: {status}":
            problems.append(f"ERROR {rel}: line 3 must be 'Status: {status}' for a note in {lifecycle}/")
        if lifecycle == "archived":
            archived = re.fullmatch(r"Archived: (\d{4}-\d{2}-\d{2})", lines[3].strip()) if len(lines) > 3 else None
            day = valid_date(archived.group(1)) if archived else None
            if not day:
                problems.append(f"ERROR {rel}: line 4 must be 'Archived: YYYY-MM-DD'")
            elif created and day < created:
                problems.append(f"ERROR {rel}: archived on {day}, before the note was created on {created}")
        headings = {line[3:].strip() for line in lines if line.startswith("## ")}
        required, forbidden = SECTIONS[status]
        missing = [h for h in required if h not in headings]
        if missing:
            problems.append(f"ERROR {rel}: missing section(s) {', '.join(missing)}")
        present = [h for h in forbidden if h in headings]
        if present:
            problems.append(f"ERROR {rel}: an implemented note states current facts; remove section(s) "
                            f"{', '.join(present)}")
    return problems


def check_archive(root: Path, base: str, explicit: bool) -> list[str]:
    result = subprocess.run(["git", "-C", str(root), "diff", "--name-status", base, "--", ARCHIVE],
                            capture_output=True, text=True, check=False)
    if result.returncode != 0:
        level = "ERROR" if explicit else "NOTE"
        return [f"{level} archive: cannot compare with {base}: {result.stderr.strip() or 'git failed'}"]
    problems = []
    for line in result.stdout.splitlines():
        status, _, paths = line.partition("\t")
        if not status.startswith("A"):
            problems.append(f"ERROR {paths}: archived notes are frozen; this change ({status}) "
                            f"against {base} modifies, renames or deletes one")
    return problems


def state_files(root: Path) -> list[Path]:
    """The state file of this tree and, in a linked worktree, that of the main checkout.

    A worker's worktree starts at its base commit, whose state file cannot list
    the worker itself; the main checkout's state file does.
    """
    files = [root / ".agents/work/state.json"]
    common = subprocess.run(["git", "-C", str(root), "rev-parse", "--path-format=absolute", "--git-common-dir"],
                            capture_output=True, text=True, check=False)
    prefix = subprocess.run(["git", "-C", str(root), "rev-parse", "--show-prefix"],
                            capture_output=True, text=True, check=False)
    if common.returncode == 0 and prefix.returncode == 0:
        main = Path(common.stdout.strip()).parent / prefix.stdout.strip() / ".agents/work/state.json"
        if main.resolve() != files[0].resolve():
            files.append(main)
    return files


def worker_ids(root: Path) -> list[str]:
    ids: set[str] = set()
    for path in state_files(root):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        ids.update(w["id"] for w in data.get("workers", []) if isinstance(w, dict) and isinstance(w.get("id"), str))
    return sorted(ids, key=len, reverse=True)


def check_residue(root: Path, files: list[str]) -> list[str]:
    ids = worker_ids(root)
    near = None
    if ids:
        names = "|".join(re.escape(i) for i in ids)
        near = re.compile(rf"\b(?:{names})\b[\s,:-]+(?:round|brief|review|verdict|ruling)\b"
                          rf"|\b(?:round\s+\d+|brief|review|verdict|ruling)\s+(?:of\s+|for\s+)?(?:{names})\b", re.I)
    problems = []
    for rel in files:
        if rel.startswith(".agents/") or any(part.startswith(".") for part in rel.split("/")):
            continue
        text = read(root, rel)
        if not text:
            continue
        for match in WORK_REF.finditer(text):
            problems.append(f"ERROR {rel}:{line_of(text, match.start())}: cites the work record {match.group(0)}; "
                            "state the fact itself, or move the rationale to a note")
        if near:
            for match in near.finditer(text):
                problems.append(f"ERROR {rel}:{line_of(text, match.start())}: '{match.group(0)}' refers to a "
                                "worker's round or review; state the current fact instead")
        for match in PROBES.finditer(text):
            problems.append(f"WARN {rel}:{line_of(text, match.start())}: '{match.group(0)}' reads like review "
                            "history; keep it only if a reader of this checkout can verify it")
    return problems


def run(root: Path, only: list[str] | None = None, base: str | None = None) -> list[str]:
    files = listing(root)
    chosen = only or list(CHECKS)
    problems: list[str] = []
    if "links" in chosen:
        problems += check_links(root, files)
    if "instructions" in chosen:
        problems += check_instructions(root, files)
    if "notes" in chosen:
        problems += check_notes(root, files)
    if "archive" in chosen:
        problems += check_archive(root, base or "HEAD", base is not None)
    if "residue" in chosen:
        problems += check_residue(root, files)
    return problems


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("root", nargs="?", type=Path, default=Path("."))
    parser.add_argument("--only", action="append", choices=CHECKS, help="run only this check; repeatable")
    parser.add_argument("--base", help="commit the archive is compared with (default HEAD)")
    args = parser.parse_args()
    root = args.root.resolve()
    if not root.is_dir():
        print(f"{root} is not a directory", file=sys.stderr)
        return 1
    problems = run(root, args.only, args.base)
    for problem in problems:
        print(problem, file=sys.stderr if problem.startswith("ERROR") else sys.stdout)
    errors = sum(p.startswith("ERROR") for p in problems)
    print(f"Repository checks: {errors} error(s), {len(problems) - errors} warning(s) or note(s).")
    return int(bool(errors))


if __name__ == "__main__":
    raise SystemExit(main())
