# Reporting

Read before reporting progress or results to the user.

## Facts sheet

The main session writes `harness/reports/<date>-<topic>/facts.md` before any drafting:

| Fact | Value | Source |
| --- | --- | --- |
| a number, a status, a commit, a path | as it appears in the source | file and line, or command and output file |

Only facts the main session has opened go into the sheet. A cause that is not established goes in as "cause not established".

## Drafts

The reporter receives the facts sheet and the [reporter runbook](../assets/runbooks/reporter.md), and returns into the same directory:

- `precise.md`: numbers, paths, commits and statuses, for the person who will act on them
- `plain.md`: the same results for a reader outside the project, without paths or jargon
- `checklist.md`: every number that appears in either version, with its row in the facts sheet

Default limits are 400 words for the precise version and 200 words for the plain one. For a report in another language, the runbook states the limit in that language's unit, such as characters for Chinese. The reporter adds no number, cause or recommendation that is not in the facts sheet.

## Check and send

The main session opens each source in the checklist, compares the value, and corrects or deletes any mismatch in both versions. It then sends the version the user asked for and names what waits for approval.

Use neutral status labels in the report, such as completed, confirmed, below baseline, or not yet established. In Chinese reports: 已完成、已确认、未达到基线、结论待定.
