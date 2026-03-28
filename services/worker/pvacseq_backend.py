"""
pVACseq wrapper backend for NeoAntigen-Studio.
pVACseq (https://pvactools.readthedocs.io) is the gold-standard
neoantigen prediction pipeline used in academic oncology.

This module wraps pVACseq as an OPTIONAL backend. The pipeline
functions normally without it (falls back to real_predictors.py).

Installation (not a default dependency):
    pip install pvactools
    # requires NetMHCpan, MHCflurry, or other tools configured
"""
from __future__ import annotations

import logging
import os
import subprocess
import tempfile
from pathlib import Path

logger = logging.getLogger(__name__)


class PVACseqNotAvailableError(RuntimeError):
    """Raised when pvacseq is not installed or not executable."""


def is_pvacseq_available() -> bool:
    """Check if pvacseq CLI is available."""
    try:
        result = subprocess.run(
            ["pvacseq", "--version"],
            capture_output=True, text=True, timeout=10
        )
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


def get_pvacseq_version() -> str | None:
    """Return pvacseq version string or None."""
    try:
        result = subprocess.run(
            ["pvacseq", "--version"],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass
    return None


def run_pvacseq_single_peptide(
    peptide: str,
    allele: str,
    sample_name: str = "sample",
) -> dict | None:
    """
    Run pVACseq on a single peptide/allele pair using a minimal VCF.
    Returns dict with binding prediction or None on failure.

    This uses the pvacseq run command with a synthetic VCF containing
    the peptide-encoding variant, which is the standard academic workflow.
    """
    if not is_pvacseq_available():
        raise PVACseqNotAvailableError(
            "pvacseq not found. Install with: pip install pvactools"
        )

    with tempfile.TemporaryDirectory() as tmpdir:
        tmp = Path(tmpdir)

        vcf_content = _build_minimal_vcf(peptide, sample_name)
        vcf_path = tmp / "input.vcf"
        vcf_path.write_text(vcf_content, encoding="utf-8")

        output_dir = tmp / "pvacseq_output"
        allele_norm = allele.replace("*", "")

        cmd = [
            "pvacseq", "run",
            str(vcf_path),
            sample_name,
            allele_norm,
            "NetMHCpan",
            str(output_dir),
            "--iedb-install-directory", os.environ.get(
                "IEDB_DIR", "/opt/iedb"),
            "--epitope-length", str(len(peptide)),
            "--keep-tmp-files",
        ]

        try:
            result = subprocess.run(
                cmd, capture_output=True, text=True, timeout=120
            )
            if result.returncode != 0:
                logger.warning(
                    "pvacseq failed (rc=%d): %s",
                    result.returncode, result.stderr[:500]
                )
                return None

            return _parse_pvacseq_output(output_dir, peptide, allele)

        except subprocess.TimeoutExpired:
            logger.warning("pvacseq timed out for %s/%s", peptide, allele)
            return None
        except Exception as e:
            logger.warning("pvacseq error: %s", e)
            return None


def _build_minimal_vcf(peptide: str, sample_name: str) -> str:
    """
    Build a minimal VCF file containing a synthetic missense variant
    that encodes the given peptide. Used for pvacseq input.

    Note: This is a simplified representation for architecture testing.
    In production, the real VCF from GATK/Mutect2 should be used.
    """
    header = "\n".join([
        "##fileformat=VCFv4.2",
        "##FILTER=<ID=PASS,Description=\"All filters passed\">",
        "##INFO=<ID=CSQ,Number=.,Type=String,Description=\"Consequence\">",
        "##FORMAT=<ID=GT,Number=1,Type=String,Description=\"Genotype\">",
        f"#CHROM\tPOS\tID\tREF\tALT\tQUAL\tFILTER\tINFO\tFORMAT\t{sample_name}",
    ])
    csq = f"A|missense_variant|MODERATE|GENE1|ENSG001|Transcript|ENST001|"
    csq += f"protein_coding|1/10|c.1A>T|p.{peptide}1{peptide}|"
    csq += f"1000|334|112|{peptide}|rs000001"
    variant = f"1\t1000000\t.\tA\tT\t100\tPASS\tCSQ={csq}\tGT\t0/1"
    return header + "\n" + variant + "\n"


def _parse_pvacseq_output(
    output_dir: Path, peptide: str, allele: str
) -> dict | None:
    """Parse pVACseq TSV output and extract binding scores."""
    tsv_files = list(output_dir.glob("**/*.filtered.tsv"))
    if not tsv_files:
        tsv_files = list(output_dir.glob("**/*.all_epitopes.tsv"))

    if not tsv_files:
        logger.warning("No pVACseq output TSV found in %s", output_dir)
        return None

    try:
        import csv
        import math

        with tsv_files[0].open(newline="", encoding="utf-8") as handle:
            reader = csv.DictReader(handle, delimiter="\t")
            for row in reader:
                mt_peptide = row.get("MT Epitope Seq", "")
                if mt_peptide == peptide:
                    ic50 = float(row.get("Best MT IC50 Score", 500.0))
                    pct = float(row.get("Best MT Percentile", 50.0))
                    log_min = math.log10(50.0)
                    log_max = math.log10(50_000.0)
                    raw = 1.0 - (math.log10(max(ic50, 1.0)) - log_min) / (
                        log_max - log_min)
                    score = round(max(0.0, min(1.0, raw)), 4)
                    return {
                        "score": score,
                        "affinity_nm": round(ic50, 2),
                        "percentile_rank": round(pct, 2),
                        "predictor": "pvacseq",
                        "pvacseq_version": get_pvacseq_version(),
                    }
    except Exception as e:
        logger.warning("Failed to parse pVACseq output: %s", e)

    return None


def predict_binding_pvacseq(peptide: str, allele: str) -> dict | None:
    """
    Public API: predict MHC-I binding using pVACseq.
    Returns None if pVACseq is not available or prediction fails.
    Compatible with real_predictors.predict_binding() output format.
    """
    if not is_pvacseq_available():
        return None
    return run_pvacseq_single_peptide(peptide, allele)
