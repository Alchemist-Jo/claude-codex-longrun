# Design advisor

Read when the next step depends on a direction rather than an implementation.

## Which questions go to the advisor

Questions of direction, where the answer shapes several later briefs:

- how an intake or onboarding flow should be fixed
- where a general mechanism ends and special-purpose handling begins
- how a candidate pool is chosen
- how a boundary between cases is characterised

These stay out: bugs, implementation detail, the choice between two implementations a test can separate, and anything the user must decide, such as budget or scope.

## Steps

1. A subagent drafts the question from the [question runbook](../assets/runbooks/question.md) into `harness/advice/a<NN>-question.md`.
2. The main session edits the draft. The question must name the decision it informs and what evidence would change it.
3. The main session runs Codex read-only at maximum effort, as in [dispatch](dispatch.md), with the answer written to `harness/advice/a<NN>-answer.md`.
4. The answer is kept verbatim. The main session writes its ruling to the ledger, citing the answer, before any brief depends on it.
5. Briefs that follow cite the advice file and the ledger line in their Context section.

## Question format

~~~text
Decision: the one decision this answer informs
Context: paths to read, with one line each on why
Current state: what exists now, with file locations
Options seen: each option with its known costs
Constraints: what cannot change
What would change the decision: the evidence that would favour each option
Answer format: a recommendation, the reasons, the risks, and what to verify first
~~~

An answer is advice. It becomes a direction only through the main session's ruling.
