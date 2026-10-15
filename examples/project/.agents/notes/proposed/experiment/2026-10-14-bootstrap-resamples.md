# Agent Note: Number of bootstrap resamples for report intervals

Status: proposed

## Problem

Report intervals use 1000 bootstrap resamples. On the tiny fixture the interval bounds move by up to 0.004 between seeds, which is larger than the differences the reports are used to compare.

## Proposal

Use 10000 resamples for the final report and keep 1000 for the quick report printed during a run. The seed stays in the run configuration.

## Alternatives considered

- Keep 1000 everywhere. The seed-to-seed movement stays above the differences being compared.
- Analytic intervals. They assume a distribution the per-example scores do not follow.

## Acceptance

Across 5 seeds on the tiny fixture, each interval bound moves by less than 0.001, and the final report takes less than 30 seconds longer.

## Risks

Large suites may need more time than the 30-second budget; the quick report is unaffected.
