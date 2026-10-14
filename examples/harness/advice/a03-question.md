Decision: where shard resumption lives, in the generic runner or in each dataset adapter.

Context:
- src/evalkit/runner.py, because it schedules shards for every dataset.
- src/evalkit/adapters/, because two adapters already carry their own retry logic.

Current state: resumption restarts from shard 0 for every dataset; adapters for streaming datasets retry failed downloads themselves.

Options seen:
1. Resumption in the runner, by result-file completeness. One code path; adapters cannot customise it.
2. Resumption in each adapter. Full control per dataset; four copies of similar logic.

Constraints: result files keep their current names; adapters must keep working unchanged in the next release.

What would change the decision: a dataset whose shards cannot be judged complete from the result file alone.

Answer format: a recommendation, the reasons, the risks, and what to verify first.
