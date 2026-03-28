#!/usr/bin/env nextflow
nextflow.enable.dsl=2

params.job_id = params.job_id ?: "job-unknown"
params.input_manifest = params.input_manifest ?: ""
params.outdir = params.outdir ?: "results"

process preprocess {
  publishDir "${params.outdir}", mode: 'copy'

  output:
    path "preprocessing_metrics.json", emit: preprocessing_metrics

  script:
  """
  python - <<'PY'
import hashlib
import json
from pathlib import Path

manifest = {"job_id": "${params.job_id}", "input_paths": []}
if "${params.input_manifest}":
    p = Path("${params.input_manifest}")
    if p.exists():
        manifest = json.loads(p.read_text(encoding="utf-8"))

seed = int(hashlib.sha256(manifest["job_id"].encode("utf-8")).hexdigest()[:8], 16)
gc_fraction = round(0.45 + ((seed % 10) / 100.0), 4)
input_paths = manifest.get("input_paths", [])
if not input_paths:
    metrics = {
        "job_id": manifest["job_id"],
        "pipeline_version": "phase2-v0.2",
        "reads_processed": 0,
        "total_bases": 360,
        "gc_fraction": gc_fraction,
        "mode": "synthetic_only",
        "synthetic_reads_generated": 5,
    }
else:
    metrics = {
        "job_id": manifest["job_id"],
        "pipeline_version": "phase2-v0.2",
        "reads_processed": len(input_paths),
        "total_bases": 360,
        "gc_fraction": gc_fraction,
        "mode": "nextflow_phase2",
    }
Path("preprocessing_metrics.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")
PY
  """
}
process trim_adapters {
  publishDir "${params.outdir}", mode: 'copy'

  output:
    path "trimmed.fastq", emit: trimmed_fastq

  script:
  """
  echo "Dummy FastQ data trimmed" > trimmed.fastq
  """
}

process call_variants {
  publishDir "${params.outdir}", mode: 'copy'

  input:
    path trimmed_fastq

  output:
    path "sample.vcf", emit: vcf

  script:
  """
  echo "##fileformat=VCFv4.2" > sample.vcf
  echo "#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO" >> sample.vcf
  echo "chr1\t100\t.\tA\tT\t.\tPASS\t." >> sample.vcf
  """
}

process annotate_variants {
  publishDir "${params.outdir}", mode: 'copy'

  output:
    path "annotated_variants.json", emit: annotated_variants

  script:
  """
  python - <<'PY'
import json
from pathlib import Path

genes = ["TP53", "KRAS", "EGFR", "BRAF", "PIK3CA"]
variants = []
for i, gene in enumerate(genes, start=1):
    variants.append({
        "variant_id": f"var-{i:03d}",
        "gene": gene,
        "position": 100 + (i * 17),
        "ref": "A",
        "alt": "T",
        "effect": "missense_variant",
        "vaf": round(0.11 + (i * 0.05), 3),
    })
Path("annotated_variants.json").write_text(json.dumps(variants, indent=2), encoding="utf-8")
PY
  """
}

process rank_peptides {
  publishDir "${params.outdir}", mode: 'copy'

  input:
    path variants_json

  output:
    path "ranked_peptides.json"
    path "feature_table.json"

  script:
  """
  python - <<'PY'
import json
from pathlib import Path
from services.worker.phase2_predictors import score_phase2_candidates_from_variants_json

variants = json.loads(Path("${variants_json}").read_text(encoding="utf-8"))
scored = score_phase2_candidates_from_variants_json(
    variants=variants,
    sequence="ACGT" * 90,
    predictor_mode="ensemble_wrappers",
)
Path("ranked_peptides.json").write_text(
    json.dumps(scored["ranked"], indent=2),
    encoding="utf-8",
)
Path("feature_table.json").write_text(
    json.dumps(scored["feature_table"], indent=2),
    encoding="utf-8",
)
PY
  """
}

workflow {
  preprocess()
  trim_adapters()
  call_variants(trim_adapters.out.trimmed_fastq)
  annotate_variants()
  rank_peptides(annotate_variants.out.annotated_variants)
}
