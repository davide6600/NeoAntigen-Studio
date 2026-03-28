#!/usr/bin/env nextflow
nextflow.enable.dsl=2

params.input_vcf = params.input_vcf ?: null
params.hla_types = params.hla_types ?: null
params.sample_id = params.sample_id ?: "sample"
params.outdir = params.outdir ?: "./results"
params.predictor = params.predictor ?: "auto"
params.tumor_type = params.tumor_type ?: "unknown"

def allowedPredictors = ["auto", "iedb", "stub"]
if (!allowedPredictors.contains(params.predictor)) {
    exit 1, "Parameter --predictor must be one of: auto, iedb, stub"
}

if (!params.input_vcf) {
    exit 1, "Parameter --input_vcf is required"
}

process HLA_TYPING {
    tag "${sample_id}"
    errorStrategy 'retry'
    maxRetries 2
    publishDir "${params.outdir}", mode: 'copy'

    input:
    tuple val(sample_id), path(vcf_file)

    output:
    tuple val(sample_id), path("${sample_id}_hla.txt")

    script:
    """
    export PYTHONPATH="${projectDir}/..:\${PYTHONPATH:-}"
    python - <<'PY'
    from pathlib import Path

    from services.worker import hla_typing

    sample_id = "${sample_id}"
    input_file = "${vcf_file}"
    manual_hla = """${params.hla_types ?: ""}""".strip()

    if manual_hla:
        alleles = [item.strip() for item in manual_hla.split(",") if item.strip()]
    else:
        result = hla_typing.type_hla(
            input_files=[input_file],
            sample_id=sample_id,
            method="auto",
            work_dir=".",
        )
        alleles = result.alleles

    Path(f"{sample_id}_hla.txt").write_text("\\n".join(alleles) + "\\n", encoding="utf-8")
    PY
    """
}

process PHASE2_PREDICT {
    tag "${sample_id}"
    errorStrategy 'retry'
    maxRetries 2
    publishDir "${params.outdir}", mode: 'copy'

    input:
    tuple val(sample_id), path(vcf_file), path(hla_file)

    output:
    tuple val(sample_id), path("${sample_id}_ranked.json"), path("${sample_id}_feature_table.json"), path("${sample_id}_summary.json")

    script:
    """
    export PYTHONPATH="${projectDir}/..:\${PYTHONPATH:-}"
    python - <<'PY'
    import json
    from pathlib import Path

    from agent.data.vcf_parser import parse_vcf

    vcf_path = Path("${vcf_file}")
    variants = []
    for index, row in enumerate(parse_vcf(str(vcf_path)), start=1):
        info = dict(row.get("info") or {})
        raw_vaf = info.get("VAF", 0.25)
        try:
            vaf = float(raw_vaf)
        except (TypeError, ValueError):
            vaf = 0.25
        variants.append(
            {
                "variant_id": f"var-{index:03d}",
                "gene": str(row.get("gene") or info.get("GENE") or f"GENE{index}"),
                "position": int(row["pos"]),
                "ref": str(row["ref"]),
                "alt": str(row["alt"]),
                "effect": str(info.get("EFFECT") or "missense_variant"),
                "vaf": vaf,
            }
        )

    Path("${sample_id}_variants.json").write_text(
        json.dumps(variants, indent=2),
        encoding="utf-8",
    )
    PY

    HLA_CSV="$(paste -sd, ${hla_file})"

    python -m services.worker.phase2_predictors \
      --variants-json ${sample_id}_variants.json \
      --sequence "" \
      --hla-alleles "${HLA_CSV}" \
      --backend ${params.predictor} \
      --sample-id ${sample_id} \
      --ranked-output ${sample_id}_ranked.json \
      --feature-output ${sample_id}_feature_table.json \
            --summary-output ${sample_id}_summary.json \
            ${params.expression_file ? "--expression-file ${params.expression_file}" : ""}
            ${params.tumour_purity != null ? "--tumour-purity ${params.tumour_purity}" : ""} \
            ${params.clonal_threshold != null ? "--clonal-threshold ${params.clonal_threshold}" : ""}
    """
}

process REPORT {
    tag "${sample_id}"
    errorStrategy 'retry'
    maxRetries 2
    publishDir "${params.outdir}", mode: 'copy'

    input:
    tuple val(sample_id), path(ranked_json), path(feature_json), path(summary_json)

    output:
    path("${sample_id}_report.pdf")

    script:
    """
    export PYTHONPATH="${projectDir}/..:\${PYTHONPATH:-}"
    python - <<'PY'
    from pathlib import Path

    from services.worker.pdf_generator import generate_job_report_pdf

    sample_id = "${sample_id}"
    ranked_path = Path("${ranked_json}")
    _ = Path("${feature_json}")
    _ = Path("${summary_json}")

    pipeline_result = {
        "engine": "nextflow",
        "outputs": {"ranked_peptides_json": str(ranked_path)},
        "metadata": {
            "sample_id": sample_id,
            "tumor_type": "${params.tumor_type}",
        },
    }
    generated_path = generate_job_report_pdf(sample_id, pipeline_result, output_dir=".")
    target = Path(f"{sample_id}_report.pdf")
    if generated_path != target:
        target.write_bytes(generated_path.read_bytes())
    PY
    """
}

workflow {
    Channel
        .fromPath(params.input_vcf, checkIfExists: true)
        .ifEmpty { exit 1, "No VCF matched: ${params.input_vcf}" }
        .map { vcf_file ->
            def resolvedSampleId = params.sample_id == "sample" ? vcf_file.baseName : params.sample_id
            tuple(resolvedSampleId, vcf_file)
        }
        .set { sample_inputs }

    hla_results = HLA_TYPING(sample_inputs)
    prediction_inputs = sample_inputs.combine(hla_results, by: 0).map { sample_id, vcf_file, ignored_sample_id, hla_file ->
        tuple(sample_id, vcf_file, hla_file)
    }
    prediction_results = PHASE2_PREDICT(prediction_inputs)
    REPORT(prediction_results)
}
