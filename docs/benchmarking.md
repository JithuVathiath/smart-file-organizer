# Benchmark methodology

`benchmarks/run_benchmark.py` creates real temporary directory trees containing synthetic files, scans every file with SHA-256 enabled, produces a complete organization plan, records timings, and deletes the temporary corpus afterward.

Run the published benchmark sizes:

```bash
PYTHONPATH=src python benchmarks/run_benchmark.py \
  --files 1000 10000 100000 \
  --output reports/benchmark.json
```

The committed result is one transparent local run, not a statistically rigorous performance study. Storage, antivirus software, filesystem caching, and hardware affect results. The raw JSON includes its platform and Python version so comparisons are not presented without context.
