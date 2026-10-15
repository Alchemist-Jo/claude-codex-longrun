# AGENTS.md: src/evalkit

- A shard's result file is complete only when its last line is `#end`. Code that reads results treats any other file as missing.
- Results are merged in shard order, never in completion order, so a resumed run and an uninterrupted run write identical files.
- Shard resumption belongs in `runner.py`. Dataset adapters keep only dataset-specific recovery. The reasons are in the note on generic shard resumption.
- Seeds for bootstrap and sampling come from the run configuration; no module seeds a global generator.
