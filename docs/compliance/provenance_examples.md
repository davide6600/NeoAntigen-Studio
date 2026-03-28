# Provenance Architecture and Examples

## Purpose
Traceability is critical in computational biology. A sequence exported today must be fully reproducible tomorrow. NeoAntigen-Studio enforces this by immutably tying every artifact to a structured "Provenance Record" that details exactly how it was generated.

## Mechanism
Every job executed by the `pipeline_runtime` generates a `provenance_json` artifact alongside its scientific results. This guarantees that parameters, model versions, and software versions are known.

## Example: Peptide Candidate Ranking
When the ML ensemble scores neoantigens, it produces the following provenance metadata linked to the job ID:

```json
{
  "pipeline_version": "v2.1.0-alpha",
  "execution_mode": "phase2_real",
  "compute_environment": {
    "nextflow_version": "23.04.1",
    "docker_image": "neoantigen-worker:latest",
    "image_digest": "sha256:abcd1234efgh5678"
  },
  "inputs": {
    "patient_sequence_reads": "s3://bucket/reads/PT-001.fastq.gz",
    "checksum_sha256": "8d969eef6ecad3c29a3a629280e686cf"
  },
  "models_used": [
    {
      "model_name": "Seq2Neo",
      "version": "v1.4.2",
      "mlflow_run_id": "def456"
    },
    {
      "model_name": "NetMHCpan",
      "version": "4.1"
    }
  ],
  "parameters": {
    "hla_alleles": ["HLA-A*02:01", "HLA-B*07:02"],
    "min_peptide_length": 8,
    "max_peptide_length": 11
  },
  "timestamp_completed_utc": "2026-03-16T10:05:00Z"
}
```

## Example: mRNA Synthesis Manifest
When a Biosecurity Officer approves an export, the FastA file is accompanied by an approval manifest ensuring wet-lab traceability:

```json
{
  "manifest_version": "1.0",
  "design_intent": "research_use_only",
  "approver_id": "bio-officer-991",
  "approval_timestamp_utc": "2026-03-16T15:22:11Z",
  "source_job_id": "job-4fa9b-11ee",
  "sequence_metadata": {
    "codon_optimization_tool": "dnachisel v3.2",
    "target_organism": "h_sapiens",
    "folding_mfe_score_kcal_mol": -45.2,
    "safety_checks": {
      "forbidden_motifs_present": false,
      "homopolymer_runs_length_exceeded": false
    }
  }
}
```
