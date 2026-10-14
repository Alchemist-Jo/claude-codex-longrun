Illustrative answer for the example project.

Recommendation: option 1, resumption in the runner, judged by an end marker in each result file. Keep dataset-specific recovery, such as download retries, inside adapters, and do not let adapters decide whether a shard is complete.

Reasons: completeness is a property of the result file, which the runner writes for every dataset. One path keeps resumed and uninterrupted runs comparable.

Risks: a dataset whose shard output is valid but empty would look incomplete if the end marker is missing.

Verify first: that every adapter returns through the runner's writer, so every result file gets the end marker.
