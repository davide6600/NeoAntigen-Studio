"""
HLA-I typing per NeoAntigen-Studio.
Priorita: OptiType (da FASTQ/BAM) -> alleli da manifest -> default.
"""
from __future__ import annotations

from dataclasses import dataclass
import logging
import os
import re
import shutil
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)

SUPPORTED_LOCI = ("HLA-A", "HLA-B", "HLA-C")

# Alleli di default (fallback finale - solo per demo/test)
DEFAULT_HLA_ALLELES = ["HLA-A*02:01", "HLA-B*07:02", "HLA-C*07:01"]
_STANDARD_ALLELE_RE = re.compile(r"^HLA-[A-Z]\*\d\d:\d\d$")


@dataclass(frozen=True)
class HLATypingResult:
    alleles: list[str]
    typing_method: str
    confidence: float | None
    source_files: list[str]


def normalize_allele_format(allele: str) -> str | None:
    """
    Normalizza un allele HLA al formato standard HLA-A*02:01.
    Gestisce varianti comuni:
      "A*02:01"       -> "HLA-A*02:01"
      "HLA-A02:01"    -> "HLA-A*02:01"
      "A-02:01"       -> "HLA-A*02:01"
      "hla-a*02:01"   -> "HLA-A*02:01"
    Restituisce None se il formato non e riconoscibile.
    """
    raw = str(allele or "").strip().upper()
    if not raw:
        return None
    raw = raw.replace("HLA-", "").replace("-", "")
    match = re.fullmatch(r"([A-Z])\*?(\d{2}):(\d{2})", raw)
    if not match:
        return None
    locus, field1, field2 = match.groups()
    return f"HLA-{locus}*{field1}:{field2}"


def optitype_available() -> bool:
    """Verifica se OptiType e installato e nel PATH."""
    return shutil.which("OptiTypePipeline.py") is not None or \
           shutil.which("optitype") is not None


def hlahd_available() -> bool:
    """Verifica se HLA-HD e installato e nel PATH."""
    return shutil.which("hlahd.sh") is not None


def docker_available() -> bool:
    """Verifica se Docker e disponibile per backend opzionali."""
    return shutil.which("docker") is not None


def run_optitype(
    fastq_paths: list[str],
    output_dir: str,
    rna_mode: bool = False,
) -> list[str] | None:
    """
    Esegue OptiType su file FASTQ e ritorna lista di alleli HLA-I.

    Args:
        fastq_paths: lista di path FASTQ (1 o 2 per paired-end)
        output_dir: cartella di output per i risultati
        rna_mode: True per RNAseq, False per WES/WGS

    Returns:
        Lista di alleli es. ["HLA-A*02:01", "HLA-B*07:02", "HLA-C*07:01"]
        oppure None se OptiType non disponibile o fallisce.
    """
    if not optitype_available():
        logger.info("OptiType not found in PATH")
        return None

    os.makedirs(output_dir, exist_ok=True)

    cmd = ["OptiTypePipeline.py", "--input"] + fastq_paths
    cmd.extend(["--outdir", output_dir, "--prefix", "hla_result"])
    cmd.append("--rna" if rna_mode else "--dna")

    logger.info("Running OptiType: %s", " ".join(cmd))
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=3600,
        )
        if result.returncode != 0:
            logger.error("OptiType failed (rc=%d): %s",
                         result.returncode, result.stderr[:500])
            return None
        return _parse_optitype_output(output_dir)
    except subprocess.TimeoutExpired:
        logger.error("OptiType timed out after 1h")
        return None
    except Exception as e:
        logger.error("OptiType execution error: %s", e)
        return None


def run_hlahd(
    input_files: list[str],
    sample_id: str,
    output_dir: str,
) -> list[str] | None:
    """Esegue HLA-HD e ritorna lista di alleli HLA se disponibile."""
    if not hlahd_available():
        logger.info("HLA-HD not found in PATH")
        return None

    os.makedirs(output_dir, exist_ok=True)
    cmd = ["hlahd.sh", "-t", "4", sample_id] + input_files
    logger.info("Running HLA-HD: %s", " ".join(cmd))
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=7200,
            cwd=output_dir,
        )
        if result.returncode != 0:
            logger.error("HLA-HD failed (rc=%d): %s",
                         result.returncode, result.stderr[:500])
            return None
        return _parse_hlahd_output(Path(output_dir), sample_id)
    except subprocess.TimeoutExpired:
        logger.error("HLA-HD timed out after 2h")
        return None
    except Exception as e:
        logger.error("HLA-HD execution error: %s", e)
        return None


def run_polysolver(
    input_files: list[str],
    sample_id: str,
    output_dir: str,
) -> list[str] | None:
    """Stub strutturato per POLYSOLVER via Docker, se disponibile."""
    _ = input_files, sample_id, output_dir
    if not docker_available():
        logger.info("Docker not found in PATH; POLYSOLVER unavailable")
        return None
    logger.warning("POLYSOLVER backend placeholder not configured; skipping")
    return None


def _parse_optitype_output(output_dir: str) -> list[str] | None:
    """
    Legge il file TSV di output di OptiType e ritorna gli alleli.
    Il file si chiama hla_result_result.tsv
    Formato: A1  A2  B1  B2  C1  C2  Reads  Objective
    """
    tsv_path = Path(output_dir) / "hla_result_result.tsv"
    if not tsv_path.exists():
        logger.error("OptiType output TSV not found: %s", tsv_path)
        return None

    with tsv_path.open(encoding="utf-8") as handle:
        lines = handle.readlines()
    if len(lines) < 2:
        return None

    cols = lines[1].strip().split("\t")
    if len(cols) < 7:
        logger.error("OptiType TSV malformed: %s", tsv_path)
        return None

    raw = cols[1:7]
    alleles: list[str] = []
    seen: set[str] = set()
    for allele in raw:
        if not allele:
            continue
        normalized = f"HLA-{allele}" if not allele.startswith("HLA-") else allele
        if normalized not in seen:
            seen.add(normalized)
            alleles.append(normalized)

    return validate_hla_format(alleles) or None


def _parse_hlahd_output(output_dir: Path, sample_id: str) -> list[str] | None:
    """Legge il file finale di HLA-HD e restituisce gli alleli validi."""
    result_path = output_dir / "result" / f"{sample_id}_final.result.txt"
    if not result_path.exists():
        logger.error("HLA-HD output not found: %s", result_path)
        return None

    alleles: list[str] = []
    with result_path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            for token in line.replace(",", " ").split():
                if token.startswith("HLA-"):
                    alleles.append(token)
                elif token.startswith(("A*", "B*", "C*")):
                    alleles.append(f"HLA-{token}")

    return validate_hla_format(alleles) or None


def _stub_result(source_files: list[str]) -> HLATypingResult:
    logger.warning(
        "No real HLA typing backend available. Using common stub alleles "
        "for demo/testing only: %s",
        DEFAULT_HLA_ALLELES,
    )
    return HLATypingResult(
        alleles=DEFAULT_HLA_ALLELES,
        typing_method="stub_common_alleles",
        confidence=None,
        source_files=source_files,
    )


def resolve_hla_from_manifest(
    manifest: dict,
    input_paths: list[str] | None = None,
    work_dir: str | None = None,
    sample_id: str = "sample",
) -> HLATypingResult:
    """
    Entry point principale per risolvere gli HLA da un job manifest.

    Logica di priorita:
    1. manifest contiene "hla_alleles" valorizzato -> usali direttamente
       (typing_method = "manifest_provided")
    2. manifest contiene "hla_types" valorizzato (compat) -> stessa cosa
       (typing_method = "manifest_provided_legacy")
    3. input_paths non vuoto -> chiama type_hla(...)
    4. Nessuna delle precedenti -> stub
    """
    manifest = manifest or {}
    normalized_inputs = [str(Path(p)) for p in (input_paths or [])]

    def _normalize_many(values: list[str], *, method_name: str) -> list[str]:
        normalized: list[str] = []
        for value in values:
            formatted = normalize_allele_format(value)
            if formatted is None:
                logger.warning("Invalid HLA allele format in manifest, skipping: %s", value)
                continue
            if not _STANDARD_ALLELE_RE.match(formatted):
                logger.warning("Normalized HLA allele did not match standard pattern, skipping: %s", value)
                continue
            normalized.append(formatted)
        return validate_hla_format(normalized)

    direct = manifest.get("hla_alleles") or []
    if direct:
        normalized = _normalize_many(list(direct), method_name="manifest_provided")
        if normalized:
            return HLATypingResult(
                alleles=normalized,
                typing_method="manifest_provided",
                confidence=None,
                source_files=normalized_inputs,
            )

    legacy = manifest.get("hla_types") or []
    if legacy:
        logger.warning("Manifest field 'hla_types' is deprecated; use 'hla_alleles' instead")
        normalized = _normalize_many(list(legacy), method_name="manifest_provided_legacy")
        if normalized:
            return HLATypingResult(
                alleles=normalized,
                typing_method="manifest_provided_legacy",
                confidence=None,
                source_files=normalized_inputs,
            )

    if normalized_inputs:
        return type_hla(
            input_files=normalized_inputs,
            sample_id=sample_id,
            method="auto",
            work_dir=work_dir,
        )

    return _stub_result(normalized_inputs)


def type_hla(
    input_files: list[str],
    sample_id: str,
    method: str = "auto",
    work_dir: str | None = None,
) -> HLATypingResult:
    """
    Cascata: optitype -> hlahd -> stub.
    Se input_files e vuoto -> usa stub direttamente.
    """
    normalized_inputs = [str(Path(p)) for p in input_files]
    if not normalized_inputs:
        return _stub_result([])

    work_root = Path(work_dir) if work_dir else Path("data") / "hla_typing" / sample_id
    work_root.mkdir(parents=True, exist_ok=True)
    method = method.lower().strip()

    if method == "stub":
        return _stub_result(normalized_inputs)

    if method in {"auto", "optitype"}:
        optitype_result = run_optitype(
            normalized_inputs,
            str(work_root / "optitype"),
            rna_mode=False,
        )
        if optitype_result:
            return HLATypingResult(
                alleles=optitype_result,
                typing_method="optitype",
                confidence=None,
                source_files=normalized_inputs,
            )
        if method == "optitype":
            return _stub_result(normalized_inputs)

    if method in {"auto", "hlahd"}:
        hlahd_result = run_hlahd(
            normalized_inputs,
            sample_id=sample_id,
            output_dir=str(work_root / "hlahd"),
        )
        if hlahd_result:
            return HLATypingResult(
                alleles=hlahd_result,
                typing_method="hlahd",
                confidence=None,
                source_files=normalized_inputs,
            )
        if method == "hlahd":
            return _stub_result(normalized_inputs)

    if method in {"auto", "polysolver"}:
        polysolver_result = run_polysolver(
            normalized_inputs,
            sample_id=sample_id,
            output_dir=str(work_root / "polysolver"),
        )
        if polysolver_result:
            return HLATypingResult(
                alleles=polysolver_result,
                typing_method="polysolver",
                confidence=None,
                source_files=normalized_inputs,
            )

    return _stub_result(normalized_inputs)


def get_available_hla_typer() -> str:
    """Ritorna il nome del miglior typer disponibile."""
    if optitype_available():
        return "optitype"
    if hlahd_available():
        return "hlahd"
    if docker_available():
        return "polysolver"
    return "stub"


def resolve_hla_alleles(
    manifest_hla: list[str] | None,
    fastq_paths: list[str] | None = None,
    output_dir: str | None = None,
    rna_mode: bool = False,
) -> tuple[list[str], str]:
    """
    Risolve gli alleli HLA con questa priorita:
    1. OptiType da FASTQ (se fastq_paths fornito e OptiType disponibile)
    2. Alleli espliciti dal manifest (se manifest_hla non vuoto)
    3. Default hardcoded (solo fallback demo)

    Returns:
        (alleles, source) dove source e una delle stringhe:
        "optitype", "manifest", "default"
    """
    _ = rna_mode
    result = resolve_hla_from_manifest(
        manifest={"hla_alleles": manifest_hla} if manifest_hla else {},
        input_paths=fastq_paths,
        work_dir=output_dir,
        sample_id=Path(output_dir).name if output_dir else "sample",
    )
    if result.typing_method == "manifest_provided":
        return result.alleles, "manifest"
    if result.typing_method == "manifest_provided_legacy":
        return result.alleles, "manifest_legacy"
    if result.typing_method in {"stub", "stub_common_alleles"}:
        return result.alleles, "default"
    return result.alleles, result.typing_method


def validate_hla_format(alleles: list[str]) -> list[str]:
    """
    Valida e normalizza il formato degli alleli.
    Formato atteso: HLA-A*02:01
    Rimuove alleli malformati con WARNING.
    """
    valid: list[str] = []
    for allele in alleles:
        normalized = normalize_allele_format(allele)
        if normalized is None:
            logger.warning("Invalid HLA allele format, skipping: %s", allele)
            continue
        parts = normalized.split("*")
        if len(parts) != 2 or not parts[0].startswith("HLA-"):
            logger.warning("Invalid HLA allele format, skipping: %s", allele)
            continue
        if parts[0] not in SUPPORTED_LOCI:
            logger.warning("Unsupported HLA locus, skipping: %s", allele)
            continue
        locus_parts = parts[1].split(":")
        if len(locus_parts) < 2:
            logger.warning("Invalid HLA allele resolution, skipping: %s", allele)
            continue
        if any(len(part) < 2 or not part.isdigit() for part in locus_parts[:2]):
            logger.warning("Invalid HLA allele digits, skipping: %s", allele)
            continue
        valid.append(normalized)
    return valid
