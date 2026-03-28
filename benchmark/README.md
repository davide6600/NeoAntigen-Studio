# NeoAntigen-Studio — TESLA Benchmark

## ⚠️ Important: Stub vs Real Results

This benchmark has two modes:

### Stub Mode (default, CI-compatible)
Runs with `stub_fallback` predictor (SHA-256 deterministic hash).
**Results are NOT biologically meaningful.**
Used only for CI pipeline integrity testing.

```bash
python -m benchmark.run_tesla_benchmark --mode stub
```

### Real Mode (requires a real predictor)
Runs against the published TESLA dataset with:
- `IEDB API` on Python 3.13+
- `MHCflurry 2.0` on Python 3.10-3.12

**These are the only results suitable for publication.**

```bash
# 1. Optional: install MHCflurry and download models (~500MB)
#    Recommended on Python 3.10-3.12 only
pip install mhcflurry
mhcflurry-downloads fetch

# 2. Download TESLA Supplementary Table 2
# https://www.nature.com/articles/s41587-020-0556-3
# Save as benchmark/tesla_supplementary_table2.csv

# 3. Run benchmark
bash benchmark/run_real_benchmark.sh \
  benchmark/tesla_supplementary_table2.csv
```

## Expected Performance (Real Mode)

| Metric | NeoAntigen-Studio | pVACseq 2.0 | NetMHCpan-4.1 |
|--------|------------------|-------------|----------------|
| F1     | TBD*             | ~0.36       | ~0.41          |
| AUC    | TBD*             | ~0.68       | ~0.72          |
| PPV    | TBD*             | ~0.29       | ~0.34          |

*Run `bash benchmark/run_real_benchmark.sh` with real data to populate.

MHCflurry requires Python 3.10-3.12. On Python 3.13+,
NeoAntigen-Studio uses the IEDB REST API automatically.

Stub-mode results intentionally omitted — they reflect hash
distribution, not biology.
