# Personalized Neoantigen Platform — ARCHITECTURE.md

# Overview

A modular, reproducible platform that ingests tumor/normal sequencing (FASTQ/BAM/VCF + RNA), identifies somatic mutations, predicts and ranks neoantigens, designs candidate mRNA constructs, exposes results via a web UI + API, and **self-improves over time** using an active-learning loop fed by wet-lab validation (immunopeptidomics, pooled functional screens, single-cell TCR mapping).

This document describes an MVP (research use only) → production roadmap, technical stack, data models, ML and active-learning design, security & governance, and implementation priorities.

---

# High-level architecture (text diagram)

User (Web UI / CLI)
  ↓
Frontend (React)
  ↓ REST
Backend API (FastAPI) + Auth
  ↓ Queue (Celery/Redis)
Workers → Workflow engine (Nextflow) → Bioinformatics tool containers
  ↓
Agent Engine / Skills (agent/skills/)
  ├─ Scoring & Ranking (Seq2Neo, ensemble)
  ├─ mRNA Design (DnaChisel + ViennaRNA)
  └─ AI Orchestrator (LangChain / explainability)
  ↓
Results store (Postgres + object store) + Scientific Reports (Markdown/HTML/PDF)
  ↓
Wet-lab (Immunopeptidomics / Pooled screens) → Label ingestion → Retrain triggers (agent/skills/ml_trainer)
```

---

# Predictor integration points (current implementation)

## Binding predictor interface

The canonical integration point for real MHC-I binding predictors is
`services/worker/real_predictors.py`.

`predict_binding(peptide, allele, prefer_offline=True, backend="auto")`
returns a stable dictionary schema:

```python
{
    "score": float,
    "affinity_nm": float | None,
    "percentile_rank": float | None,
    "predictor": str,
}
```

Current backend order:

* `mhcflurry_2` for offline prediction when available
* `netmhcpan_iedb_api` for remote fallback
* `stub_fallback` only when no real backend is reachable
* `pvacseq` via `services/worker/pvacseq_backend.py` as an optional explicit backend

## HLA typing integration point

The HLA typing entrypoint lives in `services/worker/hla_typing.py`.

`type_hla()` and manifest resolution return `HLATypingResult` with:

* `alleles: list[str]`
* `typing_method: str`
* `confidence: float | None`
* `source_files: list[str]`

Current cascade:

* `OptiType`
* `HLA-HD`
* stub common alleles fallback

## Phase 2 scoring formula

Current Phase 2 ranking in `services/worker/phase2_predictors.py` uses:

```text
final_score = (
    0.40 * binding_score
  + 0.20 * stability_score
  + 0.25 * tcr_score
  + 0.10 * expression_score
  + 0.05 * clonality_score
)
```

`scores_are_partial=True` is set when stability or TCR scores come from stub fallbacks.

**Note:** When no RNA-seq input is provided via `--expression-file`,
`expression_tpm` is estimated synthetically via an internal stability
fraction heuristic. For accurate expression filtering, provide a
quantification file (Salmon `quant.sf`, Kallisto `abundance.tsv`,
STAR `ReadsPerGene.out.tab`, or any TSV/CSV with `gene_id` and `TPM`
columns) — NeoAntigen-Studio will automatically detect the format.

## Python version compatibility

| Component | Python 3.10 | 3.11 | 3.12 | 3.13 |
|-----------|-------------|------|------|------|
| Pipeline core | ✅ | ✅ | ✅ | ✅ |
| MHCflurry 2.x | ✅ | ✅ | ✅ | ⚠️ limited / upstream compatibility issue |
| IEDB API path | ✅ | ✅ | ✅ | ✅ |
| pVACseq wrapper | ✅ | ✅ | ✅ | ✅ |

---

# Key external components (use once each in the implementation)

* OpenVax neoantigen pipeline — use as an end-to-end bioinformatics reference/pipeline base.
* pVACtools — core toolkit for VCF→neoepitope prediction and visualization.
* Seq2Neo — deep learning model for immunogenicity scoring (use as ML component).
* NetTCR-2.0 — baseline for TCR↔peptide specificity prediction.
* DnaChisel — codon optimization and constrained sequence design for mRNA ORF.
* ViennaRNA — RNA secondary structure prediction and energy evaluation.
* Nextflow — primary workflow engine for reproducible pipelines and scalability.
* Snakemake — alternative for Python-native pipeline rules.
* NetMHCpan — MHC binding affinity predictor (use ensemble).
* MHCflurry — alternate binding predictor for ensemble scoring.
* FastAPI — backend API server framework.
* React — frontend UI framework.
* LangChain — LLM orchestration / explainability & agent features.
* Docker — container images for reproducibility and packaging.
* Kubernetes — production orchestration and scaling.
* S3-compatible object storage — primary object store (AWS S3 / MinIO).
* PostgreSQL — primary metadata DB.
* Celery — background job orchestration (or Redis+RQ alternative).
* Redis — caching and Celery broker/use.
* PyTorch — ML training and model runtime.
* Hugging Face — model hub / tokenizers / transformers tooling.
* MLflow — model registry and experiment tracking.
* IEDB — public epitope dataset for model training/benchmarks.
* VDJdb — TCR↔epitope pairing data for training TCR models.
* McPAS-TCR — supplementary TCR dataset.
* pVACview — inspiration for frontend visualization and export features.

> Note: include each external component once in code and dependency manifests. Keep versions pinned in Dockerfiles and environment files.

---

# Goals & non-goals

**Goals (MVP, research use):**

* Ingest tumor/normal sequencing and HLA typing.
* Produce ranked neoantigen candidates with explainable scoring.
* Generate candidate mRNA constructs (ORF with linkers, codon optimization, UTR suggestions).
* Provide reproducible pipelines (containerized) and human-readable reports.
* Collect experimental labels and run an active-learning loop to improve models.

**Non-goals (MVP):**

* Not a clinical or manufacturing system (no GMP, no automated synthesis orders).
* Not intended to make clinical claims — research only until regulatory validation.

---

# Components & responsibilities (detailed)

## 1. Data ingestion & storage

* Accept input: FASTQ/BAM (tumor, normal), RNA-seq, VCF 4.2 (from `sample.vcf`), HLA alleles, sample metadata.
* Store raw files in object store (S3-compatible). Store metadata in PostgreSQL.
* Validate file integrity (checksums), file types and size at upload.

## 2. Preprocessing pipeline (Nextflow)

* QC: FastQC or equivalent. Adapter trimming (e.g., TrimGalore).
* Alignment: BWA (DNA) / STAR (RNA).
* Expression quant: Salmon / RSEM.
* Output: BAM/CRAM, expression TPMs, intermediate QC reports.

## 3. Variant calling & annotation

* Somatic callers: Mutect2 (GATK) and/or Strelka; joint calling where appropriate.
* Annotate variants using VEP / ANNOVAR / Ensembl REST API lookup (fallback for missing GENE fields) to identify coding nonsynonymous variants, frameshifts, splice variants.
* Produce VCFs + annotated tables for downstream peptide generation (via native VCF parsing filtering for `PASS` variants).

## 4. Peptide generation & MHC binding/presentation scoring

* For each coding somatic event, generate mutant peptide candidates (sliding windows 8–14 aa for Class I; longer for Class II if supported).
* Run ensemble MHC predictors (NetMHCpan + MHCflurry) for binding affinity; run eluted-ligand predictors and stability predictors when available.
* Assemble features: binding scores, eluted probability, expression TPM, clonality (VAF), proteasome cleavage and TAP scores.

## 5. ML scoring & ranking

* Immunogenicity model (Seq2Neo as baseline): multimodal model combining peptide embeddings (transformer / protein language model), MHC allele features, and tabular features (expression, binding, clonality).
* If patient TCR repertoire available, optionally use a NetTCR-style model to estimate existing recognition probability.
* Save model version, dataset snapshot, and feature vector for each prediction.

## 6. mRNA construct design (Agent Skill)

* **Skill Location:** `agent/skills/mrna_design/`
* Input: top N peptides + design policy (linker choice, signal peptide, UTR templates).
* Process:
  * concatenate epitopes + linkers,
  * codon-optimize ORF (DnaChisel) for host species,
  * evaluate and adjust sequence using ViennaRNA to prevent problematic secondary structures,
  * enforce forbidden motif checks (e.g., restriction sites, homopolymer runs),
  * produce synthesis-ready FASTA + manufacturing notes (no automatic ordering).
* Exports: sequence files, PDF summary, synthesis-ready manifest (manual approval required).

## 7. AI Orchestrator & Explainability (Agent Skill)

* **Skill Location:** `agent/skills/orchestration/`
* LLM agent (LangChain) for:
  * generating human-readable rationales for top candidates,
  * suggesting Nextflow config adjustments,
  * drafting report text and summarizing QC issues.
* LLM use is limited to explainability, orchestration, and human assistance — not to replace wet-lab validation.

## 8. Active learning & wet-lab ingestion (Agent Skill)

* **Skill Location:** `agent/skills/active_learning/` and `agent/skills/ml_trainer/`
* Acquisition function: balanced mix of high predicted score (exploit), high uncertainty (explore), and diversity (clustering sample).
* Use IEDB REST API for retrieving real world baseline binding data to robustly train early models.
* Send selection batch to wet-lab (immunopeptidomics, pooled screens, scTCR mapping).
* Ingest experimental labels via standardized schema (persistence handled via `services/worker/phase5_postgres_persistence.py`), run QC, and append to labeled dataset for retraining.

## 9. API, frontend & user flows

* REST API (FastAPI) endpoints: job submission, job status, results, label ingestion, admin operations.
* Frontend (React) for uploads, job monitor, interactive result table (filter/sort), explainability panels, and report export (PDF/CSV).
* RBAC and tenant isolation for organizations/projects.

---

# Data model (core objects)

* **Patient**: `patient_id, consent_status, project_id, clinical_metadata`
* **Sample**: `sample_id, patient_id, sample_type, collection_date, LIMS_id`
* **SequenceRun**: `run_id, object_store_path, md5, platform, read_type`
* **Variant**: `variant_id, chr, pos, ref, alt, gene, effect, vaf, depth, clonal_status`
* **PeptideCandidate**: `peptide_id, seq, source_variant_id, hla_allele, binding_scores, expression_tpm, clonality, features_vector`
* **PredictionRecord**: `prediction_id, peptide_id, model_version, score, feature_snapshot`
* **ExperimentLabel**: `label_id, peptide_id, assay_type, assay_id, result, qc_flags, uploaded_by, timestamp`
* **TCRRecord**: `tcr_id, cdr3_alpha, cdr3_beta, v_gene, j_gene, paired_cell_id, linked_peptide_id(s)`

All records must include provenance metadata (dataset_id, model_version, pipeline_version, Docker image sha256, parameters).

---

# Active-learning loop (concrete algorithm)

1. **Scoring & uncertainty**: for each peptide compute `score` and `uncertainty` (predictive entropy or ensemble variance).
2. **Acquisition function**: compute `acq = α * normalized_score + β * normalized_uncertainty - γ * diversity_penalty`. Tune α/β/γ.
3. **Batch selection**: pick top B peptides by acq, ensure diversity via clustering on peptide embeddings.
4. **Wet-lab assignment**: create manifest & run plan for assays (MS targeted PRM, pooled T-Scan, scTCR antigen mapping).
5. **Label ingestion & QC**: parse assay outputs, apply QC thresholds, mark labels as `accepted` / `rejected` with reasons.
6. **Retrain**: schedule retraining (incremental or full) with new labels; validate on holdout; promote via canary release if metrics improve.

**Metrics to track**: precision@10, recall@top20, AUPRC for immunogenicity, fraction of peptides MS-confirmed, label acquisition rate.

---

# Data governance, provenance & consent (must have)

* Dataset registry: maintain `dataset_id`, source, checksum, consent flags, curation notes.
* Consent tracking: map patient consent to allowed uses (research only, shared, allowed assays).
* Retention policy & deletion: implement deletion requests with secure wiping of storage and logs.
* Access control: RBAC, project scoping, and access logs per record.
* Provenance: every prediction/result must store pipeline version, Docker image SHA, model version, and parameter set.

---

# Model governance & MLOps

* Use MLflow as the model registry: store model binaries, metrics, training dataset IDs, and artifacts.
* Training pipelines run in containers via Nextflow; store training code & hyperparams in git.
* Promotion workflow: staging → canary (subset of projects) → production with automatic rollback on metric regressions.
* Monitor model drift: input distribution monitoring, output score distribution, and an alerting policy.

---

# Label ingestion & quality control (spec & validator)

**ExperimentLabel JSON schema (high level)**

```json
{
  "label_id": "string",
  "peptide_id": "string",
  "assay_type": "MS|TSCAN|MULTIMER|ELISPOT|KILLING|SCTCR",
  "assay_id": "string",
  "result": "positive|negative|ambiguous",
  "score": "number (optional)",
  "qc_metrics": { "psm_count": 5, "fdr": 0.01 },
  "uploaded_by": "user_id",
  "timestamp": "ISO8601"
}
```

**Pydantic validator (example skeleton)**

```python
from pydantic import BaseModel, Field, validator
from typing import Literal, Optional, Dict

class ExperimentLabel(BaseModel):
    label_id: str
    peptide_id: str
    assay_type: Literal['MS','TSCAN','MULTIMER','ELISPOT','KILLING','SCTCR']
    assay_id: str
    result: Literal['positive','negative','ambiguous']
    score: Optional[float] = None
    qc_metrics: Optional[Dict[str, float]] = None
    uploaded_by: str
    timestamp: str

    @validator('timestamp')
    def valid_ts(cls, v):
        # validate ISO8601; omitted for brevity
        return v
```

* Implement automated QC rules (min PSM, max FDR for MS; replicate concordance for pooled screens). Labels failing QC are `flagged` and require human review.

---

# Biosecurity & sequence export controls (required)

* Implement **Sequence Safety Check** microservice that:

  * scans for blacklisted motifs and homology to toxins/pathogens,
  * forbids exports that match defined hazardous patterns,
  * rate-limits sequence export and requires manual approval for any sequence destined for synthesis providers.
* All sequence exports must be logged (who, when, why) and retain audit trail for at least retention period.

**Policy text to display on UI**:

> “All sequence exports intended for synthesis must pass automatic safety checks and be explicitly approved by an authorized reviewer. The platform is research-only and must not be used for harmful purposes.”

---

# Wet-lab integration & LIMS

* Provide LIMS connector: import sample manifests, export assay manifests, map `sample_id ↔ file_id ↔ job_id`.
* Support automatic manifest generation for assays (MS run sheets, pooled library designs).
* Provide secure endpoints to ingest assay outputs (raw MS files parsed by centralized parser).

---

# Observability, logging & cost monitoring

* Centralized logging (ELK stack or Grafana Loki), tracing (OpenTelemetry), and metrics dashboards (Prometheus + Grafana).
* Cost estimation tooling (per-job estimate): CPU/GPU hours, storage egress, expected cost per sample (displayed to user).
* Alerts for pipeline failures, model drift, and security anomalies.

---

# Security & compliance (practical)

* TLS everywhere; encrypt object store at rest. Use KMS for key management.
* Secrets in Vault / cloud KMS; implement key rotation.
* Container scanning (SCA) and signed images (image signing).
* RBAC, audit logs, and fine-grained data isolation between projects/organizations.
* Research Use Only (RUO) disclaimers; IRB/MTA processes required for human sample handling.

---

# Testing & benchmarking strategy

* Unit tests for microservices and pydantic validators.
* Integration tests: run minimal Nextflow pipeline on synthetic FASTQ/VCF in CI.
* Benchmark datasets: IEDB subsets, public immunopeptidomics runs, published neoantigen validation sets. Track baseline metrics and acceptance thresholds (e.g., precision@10 target for MVP).
* Reproducibility tests: identical inputs → identical outputs given same pipeline/version; log stochastic variations.

---

# CI / CD & deployment

* CI: GitHub Actions or GitLab CI to build images, run unit tests, and run a small Nextflow smoke test.
* CD: container images pushed to registry; Helm charts for K8s deploy.
* Canary deploy for new models and pipelines.
* Local dev: `docker-compose.yml` for local testing with `minio`, `postgres`, `redis`, and `rabbitmq`/`celery`.

---

# Repo layout (monorepo recommended)

```
/repo-root
  /services
    /api/                # FastAPI backend
    /frontend/           # Vite / React UI
    /worker/             # Celery background tasks & predictors
  /agent                 # Agentic Skill Layer
    /skills/             # mRNA design, Retrain, Orchestration, etc.
    /learnings/          # Active learning event store
    /context/            # Resource indexing
  /pipelines
    /nextflow/           # Core bioinformatics (alignment/variants)
  /benchmark             # TESLA dataset validation & runners
  /containers/           # Docker / environment definitions
  /infra/                # docker-compose & k8s manifests
  /docs/                 # Governance & Compliance
  /tests/                # Unit, integration, and E2E tests
  /scripts/              # Deployment & utility scripts
  README.md
  ARCHITECTURE.md
  DOC_INDEX.md
```

---

# Minimal MVP roadmap (8–12 weeks) — priorities

**Week 0–2**

* Fork `pVACtools` + `OpenVax` and create Docker images for required tools.
* Implement Nextflow skeleton: VCF/HLA → pVACtools → ranked_peptides.json.

**Week 3–4**

* Add `Seq2Neo` scoring integration; implement FastAPI job submission + Celery trigger for Nextflow jobs.
* Implement simplified results storage (Postgres + MinIO).

**Week 5**

* Implement mRNA designer microservice using `DnaChisel` + `ViennaRNA` and basic forbidden motif checks. Generate synthesis-ready FASTA (manual approval).

**Week 6**

* Add React UI for upload, result monitoring, and report download. Add LangChain agent for explanation generation.

**Week 7–8**

* Implement label ingestion endpoint + simulated active learning loop (synthetic labels). Add MLflow model registry & retraining job.
* Hardening, tests, and documentation.

---

# Success metrics (KPIs)

* precision@10 (fraction of experimentally validated immunogenic peptides among top 10).
* fraction of top N peptides observed in immunopeptidomics (presentation confirmation).
* model AUPRC on held-out validation sets.
* time from upload → ranked report (target <72 hours for MVP).
* number of validated labels collected per week (data growth).

---

# Risks & mitigations

* **Low label availability**: partner with wet-lab and run pooled screens.
* **Regulatory & clinical claims risk**: RUO disclaimers and restrict exports; require IRB for human experiments.
* **Biosecurity risk**: sequence export gating, manual approval.
* **Model drift**: monitoring and scheduled retraining with governance.

---

# Benchmarks, datasets & references to seed training

* Use public resources for initial training and benchmarking: `IEDB`, `VDJdb`, `McPAS-TCR`.
* Seed immunopeptidomic validation by ingesting published MS datasets and targeted runs from pilot labs.
* Use `pVACtools` examples and `OpenVax` pipeline outputs as baseline integration tests.

---

# Appendices

## A — ExperimentLabel JSON schema (full)

(Include as `schemas/experiment_label.json` in repo.)

```json
{
  "$schema": "http://json-schema.org/draft-07/schema#",
  "title": "ExperimentLabel",
  "type": "object",
  "properties": {
    "label_id": { "type": "string" },
    "peptide_id": { "type": "string" },
    "assay_type": { "type": "string", "enum": ["MS","TSCAN","MULTIMER","ELISPOT","KILLING","SCTCR"] },
    "assay_id": { "type": "string" },
    "result": { "type": "string", "enum": ["positive","negative","ambiguous"] },
    "score": { "type": ["number","null"] },
    "qc_metrics": { "type": ["object","null"] },
    "uploaded_by": { "type": "string" },
    "timestamp": { "type": "string", "format": "date-time" }
  },
  "required": ["label_id","peptide_id","assay_type","assay_id","result","uploaded_by","timestamp"]
}
```

## B — Example Nextflow snippet (starter)

Create `/pipelines/nextflow/main.nf` — agent will expand this.

```nextflow
#!/usr/bin/env nextflow
nextflow.enable.dsl=2

process variantCalling {
  input:
    path tumor_fastq
    path normal_fastq
  output:
    path "somatic.vcf"
  container 'registry.example/variant_pipeline:latest'
  script:
  """
  # run bwa -> gatk -> mutect2 in container
  """
}

process neoPredict {
  input:
    path vcf
    val hla
  output:
    path "ranked_peptides.json"
  container 'registry.example/pvactools:latest'
  script:
  """
  pvacseq run $vcf $hla -o ranked_peptides.json
  """
}

workflow {
  variantCalling()
  neoPredict(variantCalling.out, params.hla)
}
```

## C — Minimal FastAPI endpoints (skeleton)

* `POST /jobs` — submit job (multipart/form-data, files + JSON metadata).
* `GET /jobs/{id}` — job status and progress.
* `GET /jobs/{id}/results` — summary JSON + file links.
* `GET /jobs/{id}/report.pdf` — report download.
* `POST /ingest-labels` — upload experiment labels (validates against schema).
* `POST /admin/retry/{id}` — admin-only job retry.

---

# Final operational notes & human policies

* **Human-in-the-loop**: every sequence export destined for synthesis must require manual approval.
* **Consent & ethics**: require documented patient consent for each sample and assay; enforce at upload.
* **RUO**: platform must be clearly labeled Research Use Only. Avoid clinical terminology that implies diagnostic or therapeutic claims.
* **Open-source governance**: adopt an open license (e.g., Apache 2.0) for code; clarify dataset licensing separately. Use contributor guidelines and code of conduct.

---

# Next steps for the AI agent (practical checklist)

1. `git clone` starter repos: OpenVax, pVACtools, Seq2Neo, NetTCR-2.0 (fork).
2. Create Docker images for base tools and push to dev registry.
3. Implement Nextflow skeleton chaining preproc → pVACtools.
4. Implement FastAPI skeleton and endpoints.
5. Implement `mrna_designer` microservice (DnaChisel + ViennaRNA wrappers).
6. Implement a minimal React UI for upload and results.
7. Add LangChain agent for explainability scaffolding.
8. Implement label ingestion endpoint and simulated active learning loop.
9. Add MLflow model registry and a retraining pipeline.

---
