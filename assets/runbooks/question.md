# Question runbook: a<NN>

Role: draft one question for the design advisor. Read-only on the repository.

## Inputs

- The decision to inform: <one sentence from the main session>
- Paths to read: <list>
- Ledger lines and advice files already relevant: <list>

## Output

`/abs/path/.agents/work/advice/a<NN>-question.md`. Stop if it exists.

## Steps

1. Read the listed paths and the relevant ledger lines.
2. Write the question in this format:
   - Decision: the one decision this answer informs
   - Context: paths to read, one line each on why
   - Current state: what exists now, with file locations
   - Options seen: each option with its known costs
   - Constraints: what cannot change
   - What would change the decision: the evidence that would favour each option
   - Answer format: a recommendation, the reasons, the risks, and what to verify first
3. Keep it under 600 words. Leave out implementation questions that a test could settle, and list them separately at the end as "not for the advisor".

## Forbidden

Running Codex or Gemini. Editing any other file. Writing state or ledger. Starting another agent.

## Stop conditions

A decision that turns out to be the user's, such as budget or scope. Inputs that contradict each other. Write the problem into the question file and return.

## Return

The question path and one line on the decision it informs. At most 80 words.
