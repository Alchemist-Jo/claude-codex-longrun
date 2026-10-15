# Agent Note: Generic shard resumption in the runner

Status: proposed

## Problem

An evaluation interrupted after hours restarts from shard 0. Two dataset adapters have grown their own partial-resume code, each with a different test for a complete shard, and a third adapter is about to copy one of them.

## Proposal

`runner.py` resumes every run from the first shard without a complete result file, where complete means the last line is `#end`. Adapters keep only recovery that depends on the dataset, such as re-downloading a missing split, and lose their resume code.

## Alternatives considered

- Resume inside each adapter. Three implementations of one rule have already diverged on what counts as complete.
- Checkpoint the runner's in-memory state. The result files already record progress, and a second record can disagree with them after a crash.

The design advisor compared the three options; its answer is in `.agents/work/advice/a03-answer.md`.

## Acceptance

A run interrupted after shard 2 and resumed writes a results file identical to an uninterrupted run, and a shard truncated before `#end` is rerun. Both are tests in `tests/test_runner.py`. No adapter contains resume code.

## Risks

Reversing the decision later means moving the rule back into two adapters. Resumption across a change of shard count is not covered.
