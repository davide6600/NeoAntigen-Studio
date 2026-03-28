"""
expression_parser.py
--------------------
Parses RNA-seq quantification files (Salmon, STAR, Kallisto) into a
standardised TPM DataFrame for downstream neoantigen filtering.

Supported formats
-----------------
- Salmon  : quant.sf  (TSV, columns: Name, Length, EffectiveLength, TPM, NumReads)
- STAR    : ReadsPerGene.out.tab (TSV, 4-column STAR format)
- Kallisto: abundance.tsv (TSV, columns: target_id, length, eff_length, est_counts, tpm)
- Generic : any TSV/CSV with a gene_id/gene/Name column and a TPM/tpm column

Public API
----------
parse_expression(path, fmt="auto", tpm_threshold=1.0, gene_id_col=None,
                 tpm_col=None) -> pd.DataFrame
    Returns DataFrame[gene_id: str, tpm: float] filtered to expressed genes.
"""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Optional
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import pandas as pd

logger = logging.getLogger(__name__)

# ──────────────────────────────────────────────────────────────────────────────
# Internal helpers
# ──────────────────────────────────────────────────────────────────────────────

_SALMON_COLS   = {"Name": "gene_id", "TPM": "tpm"}
_KALLISTO_COLS = {"target_id": "gene_id", "tpm": "tpm"}

# STAR ReadsPerGene: col 0 = gene_id, col 1 = unstranded counts
# We flag STAR files as count-based and convert via pseudo-TPM normalization.
_STAR_SKIP_PREFIXES = ("N_unmapped", "N_multimapping", "N_noFeature", "N_ambiguous")


def _detect_format(path: Path) -> str:
    """Heuristic format detection based on filename and header."""
    name = path.name.lower()
    if "quant.sf" in name or name == "quant.sf":
        return "salmon"
    if "abundance" in name and name.endswith(".tsv"):
        return "kallisto"
    if "readspergenei" in name or "readspergenei" in name or name.startswith("readspergen"):
        return "star"
    # Try reading header
    try:
        import pandas as pd
        header = pd.read_csv(path, sep=None, engine="python", nrows=0).columns.tolist()
        if "TPM" in header and "Name" in header:
            return "salmon"
        if "tpm" in header and "target_id" in header:
            return "kallisto"
    except Exception:
        pass
    return "generic"


def _parse_salmon(path: Path) -> pd.DataFrame:
    import pandas as pd
    df = pd.read_csv(path, sep="\t")
    if "Name" not in df.columns or "TPM" not in df.columns:
        raise ValueError(f"Salmon file {path} missing expected columns 'Name' / 'TPM'.")
    return df[["Name", "TPM"]].rename(columns=_SALMON_COLS)


def _parse_kallisto(path: Path) -> pd.DataFrame:
    import pandas as pd
    df = pd.read_csv(path, sep="\t")
    if "target_id" not in df.columns or "tpm" not in df.columns:
        raise ValueError(f"Kallisto file {path} missing 'target_id' / 'tpm' columns.")
    return df[["target_id", "tpm"]].rename(columns=_KALLISTO_COLS)


def _parse_star(path: Path) -> pd.DataFrame:
    """
    STAR ReadsPerGene output has no TPM; we compute length-normalised CPM
    as a TPM proxy (sufficient for expressed / not-expressed filtering).
    """
    import pandas as pd
    df = pd.read_csv(path, sep="\t", header=None,
                     names=["gene_id", "unstranded", "sense", "antisense"])
    # Remove STAR summary rows
    df = df[~df["gene_id"].str.startswith(_STAR_SKIP_PREFIXES)]
    total_counts = df["unstranded"].sum()
    if total_counts == 0:
        raise ValueError(f"STAR file {path}: total counts are 0.")
    # CPM as TPM proxy — adequate for binary expressed/not-expressed gate
    df["tpm"] = (df["unstranded"] / total_counts) * 1_000_000
    return df[["gene_id", "tpm"]]


def _parse_generic(path: Path,
                   gene_id_col: Optional[str],
                   tpm_col: Optional[str]) -> pd.DataFrame:
    sep = "\t" if str(path).endswith(".tsv") else ","
    import pandas as pd
    df = pd.read_csv(path, sep=sep)

    # Auto-detect columns if not specified
    if gene_id_col is None:
        for candidate in ("gene_id", "gene", "Name", "target_id", "feature_id"):
            if candidate in df.columns:
                gene_id_col = candidate
                break
    if tpm_col is None:
        for candidate in ("TPM", "tpm", "tpm_value"):
            if candidate in df.columns:
                tpm_col = candidate
                break

    if gene_id_col is None or tpm_col is None:
        raise ValueError(
            f"Cannot auto-detect gene_id / tpm columns in {path}. "
            "Pass gene_id_col and tpm_col explicitly."
        )
    return df[[gene_id_col, tpm_col]].rename(columns={gene_id_col: "gene_id", tpm_col: "tpm"})


# ──────────────────────────────────────────────────────────────────────────────
# Public API
# ──────────────────────────────────────────────────────────────────────────────

def parse_expression(
    path: str | Path,
    fmt: str = "auto",
    tpm_threshold: float = 1.0,
    gene_id_col: Optional[str] = None,
    tpm_col: Optional[str] = None,
) -> pd.DataFrame:
    """
    Parse an RNA-seq quantification file and return expressed genes.

    Parameters
    ----------
    path : str | Path
        Path to the quantification file.
    fmt : str
        One of 'auto', 'salmon', 'kallisto', 'star', 'generic'.
    tpm_threshold : float
        Minimum TPM (or CPM for STAR) to consider a gene expressed.
        Default 1.0 — standard threshold in neoantigen pipelines.
    gene_id_col : str, optional
        Column name for gene IDs (generic format only).
    tpm_col : str, optional
        Column name for TPM values (generic format only).

    Returns
    -------
    pd.DataFrame
        Columns: ['gene_id', 'tpm']
        Filtered to rows where tpm >= tpm_threshold.
        gene_id values are stripped of version suffixes (e.g. ENSG00000...1 → ENSG00000...).
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Expression file not found: {path}")

    if fmt == "auto":
        fmt = _detect_format(path)
        logger.info("expression_parser: detected format '%s' for %s", fmt, path.name)

    parsers = {
        "salmon":   lambda: _parse_salmon(path),
        "kallisto": lambda: _parse_kallisto(path),
        "star":     lambda: _parse_star(path),
        "generic":  lambda: _parse_generic(path, gene_id_col, tpm_col),
    }

    if fmt not in parsers:
        raise ValueError(f"Unknown format '{fmt}'. Choose from: {list(parsers)}")

    df = parsers[fmt]()

    # Strip Ensembl version suffix (ENSG000001234.5 → ENSG000001234)
    df["gene_id"] = df["gene_id"].str.split(".").str[0]

    # Ensure tpm is numeric
    import pandas as pd
    df["tpm"] = pd.to_numeric(df["tpm"], errors="coerce").fillna(0.0)

    before = len(df)
    df = df[df["tpm"] >= tpm_threshold].reset_index(drop=True)
    after = len(df)

    logger.info(
        "expression_parser: %d / %d genes pass TPM >= %.2f threshold",
        after, before, tpm_threshold,
    )

    return df