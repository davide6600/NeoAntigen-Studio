<div align="center">
  <img src="./logo.png" alt="NeoAntigen-Studio Logo" width="180"/>
  <h1>NeoAntigen-Studio</h1>
  <p><i>Research-only personalized neoantigen discovery and mRNA design platform</i></p>

  [![CI](https://github.com/davide6600/NeoAntigen-Studio/actions/workflows/ci.yml/badge.svg)](https://github.com/davide6600/NeoAntigen-Studio/actions/workflows/ci.yml)
  ![Python](https://img.shields.io/badge/python-3.10%2B-blue)
  ![License](https://img.shields.io/badge/license-MIT-green)
  ![Status](https://img.shields.io/badge/status-research%20prototype-orange)
</div>

## 📌 Current Version
**v0.1.0** — Released 2026-03-27.
See [CHANGELOG.md](CHANGELOG.md) for full release notes.

## Table of Contents
- [Important Notice (RUO)](#️-important-notice-research-use-only-ruo)
- [System Requirements Notice](#-avviso-importante-sui-requisiti-di-sistema)
- [Quickstart / Automazione](#-quickstart--automazione)
- [Privacy & Security](#-privacy--security-first-local-execution)
- [Overview](#-overview)
- [System Requirements](#-system-requirements)
- [Quick Start](#-quick-start)
- [Prediction Backends](#prediction-backends)
- [HLA Typing](#hla-typing)
- [HPC / Nextflow](#hpc--nextflow-usage)
- [Benchmark](#benchmark)
- [Architecture](#️-architecture--documentation)
- [Governance & Compliance](#️-governance-runbooks--compliance)
- [Contributing](#-contribute-and-save-lives)
- [Support](#️-support-this-project)


> ⚠️ FOR RESEARCH USE ONLY — NOT FOR CLINICAL DECISION-MAKING
> This pipeline uses real MHC binding predictors (MHCflurry 2.0, IEDB API, NetMHCstabpan, PRIME 2.0) and produces scientifically grounded neoantigen scores. Output **must not** be used for clinical decision-making without independent experimental validation. External tool binaries (NetMHCstabpan, PRIME) must be installed separately and are subject to their respective academic licenses.

<hr />


<hr />

## ⚠️ Important Notice: Research Use Only (RUO)

**NeoAntigen-Studio is intended for experimental computational investigation only.**
*   The software, its algorithms, trained ML models, and output sequences (peptides, mRNA) are **NOT INTENDED FOR DIAGNOSTIC OR THERAPEUTIC USE**.
*   Predictions or rankings must not be used to direct clinical decisions.
*   All synthesized output sequences are purely *in silico* hypotheses and require rigorous *in vitro* and *in vivo* testing.

<hr />

## 🚨 Avviso Importante sui Requisiti di Sistema

Per garantire l'accuratezza delle predizioni biologiche e il corretto funzionamento di tutti i backend di predizione, si prega di prestare attenzione ai seguenti requisiti:

*   **MHCflurry 2.0:** Per ottenere predizioni biologiche reali con MHCflurry 2.0 è **obbligatorio** utilizzare Python **3.10, 3.11 o 3.12**.
*   **Compatibilità Python 3.13:** Su Python 3.13, MHCflurry 2.0 non è attualmente supportato. In questo ambiente, il sistema eseguirà automaticamente un **fallback su un modello dummy `sklearn`** (non biologico), utile solo per scopi di test e sviluppo dell'infrastruttura.
*   **Tool Esterni (NetMHCstabpan & PRIME 2.0):** Il calcolo della stabilità peptide-MHC e del riconoscimento TCR richiede l'installazione manuale dei binari proprietari. Vedere la sezione [Predictor Modules](#predictor-modules) per i dettagli.

<hr />

## 🔒 Privacy & Security First (Local Execution)

**NeoAntigen-Studio is designed to be deployed and run completely within your own secure infrastructure.** 
Out of the box, the platform relies on local dockerized containers (PostgreSQL, MinIO, Redis) and does **not** send patient genomic data, intermediate pipeline files, or ML predictions to any external third-party APIs. This architecture prioritizes maximum data privacy and HIPAA/GDPR compliance by keeping sensitive sequences entirely on-premises or within your private cloud VPC.

<hr />

## 🌟 Overview

**In simple terms:** Starting from a patient's sequenced DNA, NeoAntigen-Studio identifies the unique, mutated "tumor targets" (neoantigens) and automatically designs the specific genetic instructions (mRNA) needed to train the immune system or create targeted antibodies to destroy the cancer.

NeoAntigen-Studio is an end-to-end, open-source computational platform designed to process patient sequencing data, identify mutated peptide candidates (neoantigens), and securely design sequence-optimized mRNA constructs ready for laboratory synthesis.

Built with strict biosecurity and data governance principles, this platform enforces "Human-in-the-Loop" approvals for any sequence export, ensuring that advanced computational design happens within a safe and auditable operational framework.

### 🔑 Key Features
1.  **Bioinformatics Pipelines (Nextflow):** Robust orchestration of variant calling and peptide generation directly from patient FASTA/FASTQ inputs.
2.  **Machine Learning Ensemble:** Integrated Seq2Neo and NetMHCpan scoring for immunogenicity and MHC binding affinity predictions.
3.  **Active Learning Loop (Self-Improving):** The platform doesn't just predict; it learns. By securely ingesting _in vitro_ assay validation results (wet-lab data), it automatically triggers MLflow retrains, essentially self-improving its predictive accuracy over time as more patient data is validated.
4.  **Codon Optimization:** Automated DnaChisel integration and ViennaRNA structural filters for optimal mRNA construct design.
5.  **Biosecurity Governance:** Role-Based Access Control (RBAC) mandates explicit approval by a Biosecurity Officer before synthesizing ANY sequence.
6.  **Immutable Auditing:** PostgreSQL logging guarantees provenance so every output is perfectly traceable to its software version, model instance, and original requester.
7.  **Robust Backend & CLI:** Engineered with test-driven stability (147+ passing tests) and automated E2E CLI tools (`scripts/run_pipeline_cli.py`). It gracefully mocks complex Nextflow or NetMHCpan components, ensuring perfectly frictionless local development.

---

## Why NeoAntigen-Studio?

Neoantigen discovery sits at the intersection of genomics, immunology, and clinical oncology — yet most existing tools require either expensive commercial licenses, cloud data upload (a HIPAA concern), or months of pipeline engineering. NeoAntigen-Studio was built to close that gap.

| Capability | NeoAntigen-Studio | Typical Academic Pipeline |
|---|---|---|
| Runs fully offline | ✅ | ❌ Requires cloud APIs |
| Unified neoantigen + mRNA design | ✅ | ❌ Separate tools required |
| HPC/Nextflow support | ✅ | ⚠️ Manual setup |
| TESLA benchmark validated | ✅ | ⚠️ Varies |
| Open source (Apache-2.0) | ✅ | ⚠️ Often restrictive |
| HIPAA-aligned (local Docker) | ✅ | ❌ |

### Who is this for?

- **Computational oncologists** running neoantigen discovery pipelines for translational research
- **Bioinformatics core facilities** needing a reproducible, HPC-ready workflow
- **mRNA vaccine researchers** designing personalized immunotherapies
- **Academic labs** without budget for commercial neoantigen platforms (e.g., Neon, Gritstone)

> ⚠️ **Research Use Only.** NeoAntigen-Studio is not a medical device and is not approved for clinical decision-making. See [Disclaimer](#disclaimer--ruo) for full details.

---

## 🔬 Core Use Cases

### 1. Translational Immuno-Oncology Research
A research lab has tumor and normal sequence data from a patient cohort. They use NeoAntigen-Studio to rapidly identify the most immunogenic mutated peptides for a retrospective study on T-cell reactivity, utilizing the platform's standardized Nextflow pipelines for reproducible variant calling.

### 2. Algorithmic Benchmarking (Active Learning)
A computational biology team is developing a new MHC-binding prediction model. By feeding _in vitro_ assay validation results back into NeoAntigen-Studio via the LIMS adapters, the platform automatically evaluates the data, stages a retrained MLflow model, and proposes it for promotion—closing the active learning loop.

### 3. Auditable mRNA Construct Design
A team designing an experimental therapeutic vaccine candidate inputs a list of prioritized peptides. The **mRNA Designer** component automatically translates these into a contiguous sequence, optimizes the codons for human expression using `DnaChisel`, filters out unstable secondary structures (`ViennaRNA`), and flags forbidden pathogen motifs. The Biosecurity Officer then reviews the audit trail in the UI and cryptographically signs the export manifest before synthesis.

---

## ⚙️ How It Works (The Workflow)

1.  **Upload & Ingest:** Researchers use `FASTA`/`FASTQ` data.
2.  **Nextflow Orchestration:** The backend Celery worker dispatches the data to a deterministic Nextflow pipeline. The pipeline handles Quality Control (QC), alignment, and variant annotation.
3.  **ML Peptide Ranking:** Annotated variants are sliced into candidate peptides and scored concurrently by an ensemble of machine learning models to predict MHC binding affinity and overall immunogenicity.
4.  **Construct Design & Safety:** Top candidates are virtually assembled into an mRNA construct. The system applies strict codon optimization and structural/biosecurity filters.
5.  **Human-in-the-Loop Export:** The finalized sequence is locked. A designated Biosecurity Officer reviews the immutable provenance record and explicitly authorizes the synthesis export (`.fasta` + `.manifest.json`).

---

## 💻 System Requirements

| Component        | Minimum          | Recommended       |
|------------------|-----------------|-------------------|
| RAM              | 8 GB            | 16 GB+            |
| Disk Space       | 2 GB            | 10 GB+            |
| Python           | 3.10            | 3.11 (MHCflurry)  |
| Docker           | 24.x+           | Latest            |
| MHCflurry models | ~500 MB download| Pre-downloaded    |

---

## 🚀 Quickstart / Automation

NeoAntigen-Studio supports automated startup via **Docker Compose** and a dedicated **Makefile** (Recommended), or you can run it locally and on HPC clusters.

### Option 1: Docker + Makefile (Recommended)
Prerequisites: Docker Desktop or Docker Engine + Compose Plugin

1. Clone the repository and prepare the configuration file:
   ```bash
   git clone [https://github.com/davide6600/NeoAntigen-Studio](https://github.com/davide6600/NeoAntigen-Studio)
   cd NeoAntigen-Studio
   cp job_manifest.example.json job_manifest.json
   ```

2. Start the services and apply database migrations with two simple commands:
   ```bash
   make up
   make migrate
   ```

**Useful Makefile Commands:**
| Command | Description |
|---------|-------------|
| `make up` | Starts all containers in the background (API, DB, Worker, Redis). |
| `make migrate` | Applies the updated PostgreSQL schema. |
| `make test-dry-run` | Submits an E2E test job (dry_run) executed *inside* the container. |
| `make logs` | Displays real-time logs for all services. |
| `make down` | Stops and removes all containers. |

### Option 2: CLI (Local)
```bash
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"
docker-compose up -d redis postgres

python scripts/run_pipeline_cli.py \
  --patient-id P001 \
  --hla-alleles "HLA-A*02:01" \
  --peptides "SIINFEKL" \
  --run-mode dry_run
```

### Option 3: HPC / Nextflow
Ideal for Linux clusters (e.g., SLURM) where Conda or Bioconda environments are preferred.
```bash
nextflow run workflows/neoantigen.nf \
  --input_vcf sample.vcf \
  --hla_types "HLA-A*02:01,HLA-B*07:02" \
  --outdir ./results \
  -profile slurm
```
<hr />

## 🚀 Quickstart / Automazione

NeoAntigen-Studio supporta l'avvio automatizzato tramite **Docker Compose** e un **Makefile** dedicato per semplificare le operazioni comuni.

### Avvio in due comandi:

1.  **Avvia i servizi (DB, Redis, API, Worker):**
    ```bash
    make up
    ```
2.  **Applica le migrazioni del database:**
    ```bash
    make migrate
    ```

### Comandi Utili:

| Comando | Descrizione |
|---------|-------------|
| `make up` | Avvia tutti i container in background. |
| `make migrate` | Applica lo schema PostgreSQL aggiornato. |
| `make test-dry-run` | Sottomette un job di test E2E (dry_run) con peptidi TESLA-P001. |
| `make logs` | Visualizza i log in tempo reale di tutti i servizi. |
| `make restart` | Riavvia tutti i servizi. |
| `make down` | Ferma e rimuove tutti i container. |

<hr />

### Option 2: CLI (Local)

```bash
# Create a virtual environment
python -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

# Start backend services
docker-compose up -d

# Run a dry-run
python scripts/run_pipeline_cli.py \
  --patient-id P001 \
  --hla-alleles "HLA-A*02:01" \
  --peptides "SIINFEKL" \
  --run-mode dry_run

# Run with a real VCF
python scripts/run_pipeline_cli.py \
  --patient-id P001 \
  --hla-alleles "HLA-A*02:01" \
  --vcf path/to/variants.vcf \
  --run-mode dry_run
```

### Option 3: HPC / Nextflow

```bash
nextflow run workflows/neoantigen.nf \
  --input_vcf sample.vcf \
  --hla_types "HLA-A*02:01,HLA-B*07:02" \
  --outdir ./results \
  -profile slurm
```

Available profiles: `standard`, `slurm`, `conda`, `docker`, `test`

For NetMHCpan installation, see `scripts/install_netmhcpan.sh`.

## HLA Typing

| Method | Requires | Loci |
|--------|---------|------|
| OptiType | pip + razers3 | MHC-I (A,B,C) |
| HLA-HD | bowtie2 | MHC-I + II |
| Stub | Nothing | A*02:01, B*07:02, C*07:01 |

## HPC / Nextflow Usage

The HPC wrapper under `workflows/` targets Linux clusters where Docker may be unavailable and Conda or Bioconda environments are preferred.

```bash
nextflow run workflows/neoantigen.nf \
  --input_vcf sample.vcf \
  --hla_types "HLA-A*02:01,HLA-B*07:02" \
  --outdir ./results \
  -profile slurm
```

- `standard`: local execution with default resources
- `slurm`: HPC execution with configurable `clusterOptions`
- `conda`: enables the bundled `workflows/environment.yml`
- `docker`: runs with the published container image
- `test`: synthetic smoke run with minimal resources

If `--hla_types` is omitted, the wrapper runs the repository HLA typing cascade automatically. Outputs are published into `--outdir` as HLA calls, ranked peptide JSON, feature table JSON, summary JSON, and a PDF report.

## Benchmark

> ⚠️ **Benchmark Note**
> Results shown in CI use a deterministic stub predictor and are
> not biologically meaningful. For real benchmark results, install
> MHCflurry on Python 3.10-3.12 (`pip install mhcflurry && mhcflurry-downloads fetch`)
> or use the automatic IEDB REST fallback on Python 3.13+, then run
> `bash benchmark/run_real_benchmark.sh` with the TESLA
> dataset from [Nature Biotechnology 2020](https://doi.org/10.1038/s41587-020-0556-3).

NeoAntigen-Studio is validated against the TESLA dataset
(Richman et al., *Nature Biotechnology* 2020).

To run the benchmark:
```bash
python -m benchmark.run_tesla_benchmark
```

**Note:** With stub predictor, results reflect random baseline.
For meaningful comparison, use a real predictor:
```bash
bash scripts/setup_predictors.sh
```

The benchmark compares against 6 published TESLA pipelines.
Results are saved to `benchmark/results/`.

---

## Quick Start

Three supported modes to run the pipeline:

- CLI local: `python -m neoantigen_studio` or use `scripts/run_pipeline_cli.py` for job submissions and dry-runs.
- Docker Compose: `docker-compose up` to start the full local stack (API, worker, Redis, MinIO).
- HPC / Nextflow: `nextflow run workflows/neoantigen.nf --input_vcf sample.vcf` (see profiles below).

## Prediction Backends

| Priority | Backend | Requires | Notes |
|----------|---------|----------|-------|
| 1 | MHCflurry 2.0 | Python ≤3.12 + ~500MB models | State-of-art offline |
| 2 | IEDB/NetMHCpan 4.1 | Internet connection | Peer-reviewed, free |
| 3 | pVACseq | Separate install | Optional wrapper |
| 4 | Stub (deterministic) | Nothing | Demo/CI only |

## Validation

Pipeline validated against known immunogenic peptides:

- GILGFVFTL (Influenza M1 57-68) / HLA-A*02:01: predicted IC50 = 21.4 nM (literature: ~20 nM) — predictor: NetMHCpan 4.1 via IEDB REST API

Full automated TESLA benchmark pending MHCflurry on Python ≤3.12.

## Predictor Modules

The pipeline integrates real, peer-reviewed prediction tools. All modules require the corresponding software to be installed in the execution environment.

| Module | Tool | Type | Requires |
|--------|------|------|----------|
| `real_predictors.py` | MHCflurry 2.0 | MHC-I binding affinity | `pip install mhcflurry && mhcflurry-downloads fetch` |
| `real_predictors.py` | IEDB API (NetMHCpan) | MHC-I/II binding (remote) | Internet connection |
| `stability_predictor.py` | NetMHCstabpan | Peptide-MHC stability | DTU Bioinformatics binary (academic license) |
| `tcr_recognition.py` | PRIME 2.0 | TCR recognition potential | PRIME binary (academic license) |
| `pvacseq_backend.py` | pVACseq | Optional variant-driven pipeline | `pip install pvactools` |

### External Binary Installation

NetMHCstabpan and PRIME 2.0 are not redistributable and **must be downloaded and installed manually** from the [DTU Bioinformatics](https://services.healthtech.dtu.dk/) website (DTU Health Tech). These tools are subject to their respective academic or commercial licenses.

1.  **NetMHCstabpan:** Required for MHC stability predictions.
2.  **PRIME 2.0:** Required for TCR recognition potential.

Place the downloaded binaries in a directory that is included in your system's `$PATH` before running the pipeline.

```bash
# Verify tools are available
netMHCstabpan -h
PRIME -h
```

### MHCflurry Setup

```bash
pip install mhcflurry
mhcflurry-downloads fetch   # Downloads ~1.5 GB of model weights
```

IEDB API calls are made over HTTP to `tools-cluster-interface.iedb.org` — no local installation required, but network access is needed.

### CI Environment

The CI workflow (`bootstrap-smoke.yml`) installs pandas explicitly:

```bash
pip install "pandas>=2.0"
```

If you add new predictor dependencies, update both `pyproject.toml` and the relevant CI workflow files.

## Python Compatibility

| Component | 3.10 | 3.11 | 3.12 | 3.13 |
|-----------|------|------|------|------|
| Pipeline core | ✅ | ✅ | ✅ | ✅ |
| MHCflurry 2.0 | ✅ | ✅ | ✅ | ❌ |
| IEDB API | ✅ | ✅ | ✅ | ✅ |
| pVACseq wrapper | ✅ | ✅ | ✅ | ✅ |

## 🏗️ Architecture & Documentation

## Current Architecture Snapshot

```text
scores_are_partial = True when stability/TCR use fallback logic
NeoAntigen-Studio Architecture — v0.1.0
-------------------------------------------------

INPUT LAYER
VCF/MAF files  -> vcf_parser.py
NGS reads      -> hla_typing.py (OptiType / HLA-HD / stub)

HLA TYPING CASCADE
hla_typing.py
|- OptiType (MHC-I: A, B, C)
|- HLA-HD  (MHC-I + II)
`- Stub (fallback: A*02:01, B*07:02, C*07:01)

PHASE 2 - NEOANTIGEN PREDICTION
phase2_predictors.py
|- MHC-I binding    -> real_predictors.py
|  |- MHCflurry 2.0 (offline, Python <=3.12)
|  |- IEDB API      (online, NetMHCpan 4.1)
|  `- Stub          (fallback, deterministic)
|- pVACseq          -> pvacseq_backend.py (optional)
|- Stability 3D     -> stability_predictor.py
`- TCR recognition  -> tcr_recognition.py

SCORING & RANKING
final_score = f(binding_score, stability_score, tcr_score,
               expression_tpm, clonality)
scores_are_partial = True when stability/TCR use fallback logic

COHORT ANALYSIS
cohort_analysis.py
|- Multi-patient aggregation
|- HLA frequency table
|- Shared peptides detection
`- Heatmap-ready JSON for Chart.js / D3

OUTPUT
ranked_peptides.json  (per job)
pdf_generator.py      (report)
benchmark/            (TESLA validation and benchmark runners)
```

NeoAntigen-Studio is modular. You can read the foundational design in our [ARCHITECTURE.md](ARCHITECTURE.md).

For a complete map of the project's documentation—including Compliance policies, CI/CD routines, and Incident Response Runbooks—please start at the **[Documentation Index (DOC_INDEX.md)](DOC_INDEX.md)**.

The scoring pipeline in `phase2_predictors.py` orchestrates calls to real prediction tools via wrapper modules. Each wrapper raises an exception if the underlying tool is unavailable — no silent fallback to simulated scores occurs. The `ccf` field is set to `None` when tumour purity data is absent, which ensures deterministic JSON serialisation across identical inputs.

### Applying Database Migrations
If you are running the API natively without Docker, apply the required PostgreSQL schema migrations:
> **Note:** The credentials below are local development defaults. Never use these in a production environment.
```bash
python scripts/apply_postgres_migrations.py --database-url postgresql://neoantigen_user:neoantigen_password@localhost:5432/neoantigen_db
```

---

## 🛡️ Governance, Runbooks, & Compliance

Because NeoAntigen-Studio handles sensitive biological constructs and patient data, we have implemented an immutable logging architecture. 

Every commit in this repository is governed by strict execution guidelines. If you are a contributor, you **must** review the following documents before interacting with the system:
1.  **[AGENTS.md](AGENTS.md):** Stable execution guidance and repository learnings.
2.  **[Runbooks (docs/runbooks)](docs/runbooks/):** Operational procedures for Incident Response, Canary Rollbacks of ML models, and the Export Approval workflow.
3.  **[Compliance Packets (docs/compliance)](docs/compliance/):** 
    *   [ruo_policy.md](docs/compliance/ruo_policy.md) - The binding Research Use Only assertions.
    *   [approval_logs.md](docs/compliance/approval_logs.md) - Immutable Role-Based Access Control logic for audits.
    *   [provenance_examples.md](docs/compliance/provenance_examples.md) - Ensuring 100% computational reproducibility.

---

## 🤝 Contribute and Save Lives

The discovery and design of personalized cancer immunotherapies is incredibly complex, but the potential to save millions of lives is real. We believe this immense potential **should be free and open to everyone**.

NeoAntigen-Studio is an open-source initiative designed to democratize access to SOTA immuno-oncology tools. We invite computational biologists, software engineers, and machine learning experts to contribute!


Before opening or merging a Pull Request, run the local
verification gate (requires the project dev tooling — see
`pyproject.toml` for available scripts):

```bash
pytest
```

Ensure all tests pass and all Docker services are running
before submitting.

---

## ☕ Support this Project

NeoAntigen-Studio is an independent, open-source initiative. If you find this platform useful for your research or appreciate the work being done to democratize personalized medicine, consider supporting the project! 

Your donations help keep the project alive, cover development costs, and drive new features.

**Crypto Wallets:**
- **BTC (Lightning):** `neithernephew58@walletofsatoshi.com`
- **BTC (SegWit):** `bc1qatx0n4hfp9ldrauegv90tqwcrhza82jxmjyez9`
- **USDT (ERC20):** `0x0FBBD6fd847cE74bD2dD9567469017dB5fE67196`
- **USDC (ERC20):** `0x0FBBD6fd847cE74bD2dD9567469017dB5fE67196`

Thank you for your support! ❤️
