# ## [Unreleased]
# *(No changes yet)*
#
# Changelog

All notable changes to NeoAntigen-Studio will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] — 2026-03-27

### Added

- Real MHC-I binding predictions via MHCflurry 2.0 and IEDB API
- HLA typing cascade: OptiType → HLA-HD → stub (hla_typing.py)
- pVACseq optional backend wrapper (pvacseq_backend.py)
- NetMHCstabpan peptide-MHC stability scoring (stability_predictor.py)
- PRIME 2.0 TCR recognition scoring (tcr_recognition.py)
- Multi-patient cohort analysis module (cohort_analysis.py) with HLA frequency tables and shared peptide detection
- REST API endpoints: /api/cohort/analyze, /api/cohort/hla-frequency, /api/cohort/shared-peptides
- Nextflow HPC workflow (workflows/neoantigen.nf) with SLURM, conda, and docker profiles
- TESLA validation dataset (benchmark/tesla_validated.csv)
- Partial TESLA benchmark: GILGFVFTL/HLA-A*02:01 IC50=21.4nM verified
- pytest markers: network, slow
- scripts/setup_predictors.sh for MHCflurry model download

### Changed

- phase2_predictors.py: replaced SHA-256 stubs with real predictors; final_score now incorporates tcr_score, stability_score. Output includes predictor_used, affinity_nm, percentile_rank, scores_are_partial per candidate
- pyproject.toml: added mhcflurry>=2.0.0 and pytest markers

### Fixed

- Removed hardcoded HLA allele from pipeline; now uses manifest or HLA typing result

### Known Limitations

- MHCflurry requires Python ≤3.12 (pipes module removal in 3.13)
- IEDB API Python client may be blocked by User-Agent policy on Python 3.13; use Python 3.11 virtualenv for MHCflurry
- pVACseq backend requires separate CLI installation
- TESLA automated benchmark pending Python 3.11 environment

## [0.1.0-draft] — Incorporated into v0.1.0

### Added

- `real_predictors.py`: MHC-I binding cascade MHCflurry 2.0 → IEDB REST API → stub fallback.
  `predictor_used` field propagated into every ranked candidate.
- `pvacseq_backend.py`: optional wrapper for pVACseq CLI. `backend` parameter supported in Phase 2 pipeline.
- `stability_predictor.py`: peptide-MHC stability with real backends and controlled fallback.
- `tcr_recognition.py`: TCR recognition prediction with `tcr_score`, `tcr_method`, and partial score flagging.
- `cohort_analysis.py`: multi-patient analysis with `analyze_cohort()`, `hla_frequency_table()`,
  `shared_peptides()`, `hla_heatmap_data()`, and CSV export.
- `hla_typing.py`: real HLA typing with OptiType → HLA-HD → stub cascade. `HLATypingResult` class.
- `benchmark/`: TESLA benchmark suite, local validation datasets, CLI runner, and benchmark reports.
- `scripts/setup_predictors.sh`: guided predictor setup with Python/MHCflurry compatibility notes.
- pytest markers `network` and `slow` registered.

### Changed

- `phase2_predictors.py`: removed old stub-only wrappers; integrated real predictors, `tcr_score`,
  `predictor_used`, `affinity_nm`, `percentile_rank`, and `scores_are_partial`.
- `README.md`: added Prediction Backends, HLA Typing, Benchmark, HPC/Nextflow sections and current architecture.
- `pyproject.toml`: added `mhcflurry>=2.0.0` dependency and updated pytest configuration.

### Fixed

- Removed hardcoded `HLA-A*02:01` from candidate construction; now uses manifest or real typing result.

### Known Limitations

- MHCflurry requires Python ≤3.12; on Python 3.13+ the pipeline relies on IEDB API or fails
  explicitly in real benchmarks.
- pVACseq backend requires separate CLI installation.
- External benchmark/prediction endpoints may be subject to redirects, downtime, or rate limiting.
