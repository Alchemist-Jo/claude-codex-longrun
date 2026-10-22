# g00 One line that names the question

Worker: g00
Route: search | research | document review | upkeep check
Working directory: /abs/repo
Grants: the `gemini_run.py` flags of this run, such as `--read /abs/other --web`

## Constraints

- Read only. Do not create, edit or delete any file.
- Do not read `.env` or credential files.
- A tool call outside the grants above is denied and ends the run as blocked. If the question needs more, stop and name what is missing in the answer.
- Do not ask questions during the run. Put open questions at the end of the answer.

## Standing rules

- `AGENTS.md` of the working directory, loaded automatically.
- `path/to/AGENTS.md` of each area the question touches.

## Question

One paragraph: the decision or document this answer feeds, and what the answer must settle.

## Sources

- Files and directories to read first, with the reason for each.
- Web sources or search terms, for research.
- Facts already established, with their evidence path, so they are not rediscovered.

## Out of scope

- Questions that look related but belong to another brief.

## Answer

1. Status on the first line: DONE, DONE_WITH_CONCERNS, BLOCKED or NEEDS_CONTEXT.
2. The answer, at most <n> words, or one issue per item for a review or upkeep check: the defect, the location, why it matters.
3. Every claim cites its source: `path:line` with the quoted text for a file, the URL with the quoted text for a web page. A claim without a source is marked "unsourced".
4. What was not checked, and why.
