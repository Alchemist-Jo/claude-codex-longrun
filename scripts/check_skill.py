"""Check skill identity and repository-local Markdown links."""
from __future__ import annotations

import argparse
from pathlib import Path
import re
import sys
from urllib.parse import unquote, urlsplit

NAME = "claude-codex-longrun"
SKIP = {".git", "build", "node_modules", ".venv", "__pycache__"}


def check(root: Path) -> list[str]:
    root = root.resolve(strict=True)
    problems = []
    skill = (root / "SKILL.md").read_text(encoding="utf-8")
    match = re.match(r"\A---\n(.*?)\n---\n", skill, re.S)
    if not match:
        problems.append("SKILL.md: missing YAML frontmatter")
    else:
        fields = match.group(1)
        if not re.search(rf"(?m)^name: {re.escape(NAME)}$", fields):
            problems.append("SKILL.md: incorrect skill name")
        if not re.search(r"(?m)^description: \S.+$", fields):
            problems.append("SKILL.md: missing description")
        if not re.search(r"(?m)^license: \S+$", fields):
            problems.append("SKILL.md: missing license")
    for path in root.rglob("*.md"):
        if any(part in SKIP for part in path.relative_to(root).parts):
            continue
        text = path.read_text(encoding="utf-8")
        if "—" in text:
            problems.append(f"{path.relative_to(root)}: contains an em dash")
        for target in re.findall(r"!?\[[^\]]*\]\(([^)]+)\)", text):
            target = target.strip("<>")
            parsed = urlsplit(target)
            if parsed.scheme or not parsed.path:
                continue
            if not (path.parent / unquote(parsed.path)).exists():
                problems.append(f"{path.relative_to(root)}: missing target {target}")
    return problems


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", nargs="?", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args()
    try:
        problems = check(args.root)
    except (OSError, ValueError) as error:
        print(error, file=sys.stderr)
        return 1
    for problem in problems:
        print(problem, file=sys.stderr)
    if not problems:
        print("Skill identity and local Markdown links passed.")
    return int(bool(problems))


if __name__ == "__main__":
    raise SystemExit(main())
